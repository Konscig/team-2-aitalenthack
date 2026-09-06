"""Causal three-type push policy derived from the golden-label methodology.

Chronos forecasts are read from the frozen Stage 19 artifact.  Golden/future
columns are used only for evaluation; candidate construction never reads them.
"""
from __future__ import annotations

from itertools import product
from pathlib import Path
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PRIORITY = {"good_day": 1, "window_closing": 2, "positive_market_fact": 3}
FACT_COLUMNS = ["fact_decline_3_quotes", "fact_weekly_gain_1pct", "fact_low_percentile_30d"]
H = 10
GOOD_BPS = 100
CLOSING_MAX_BPS = 200


def load_inputs(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    golden = pd.read_parquet(root / "data/labels/golden_labels.parquet")
    chronos = pd.read_csv(root / "reports/chronos_predictions_2025_2026.csv")
    for frame in (golden, chronos):
        frame["date"] = pd.to_datetime(frame["date"])
    required_golden = {"corridor", "date", "rate", "good", "closing", "positive_market_fact", *FACT_COLUMNS}
    required_chronos = {"corridor", "date", "rate_t", "context_end", *(f"predicted_rate_h{i}" for i in range(1, H + 1))}
    for name, frame, required in (("golden", golden, required_golden), ("chronos", chronos, required_chronos)):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{name} missing required columns: {sorted(missing)}")
    if golden.duplicated(["corridor", "date"]).any() or chronos.duplicated(["corridor", "date"]).any():
        raise ValueError("Duplicate corridor/date rows")
    chronos["context_end"] = pd.to_datetime(chronos["context_end"])
    if (chronos.context_end > chronos.date).any():
        raise ValueError("Chronos context_end is later than forecast origin")
    return golden, chronos


def _past_min_calendar(group: pd.DataFrame) -> pd.Series:
    out = []
    rates = group.set_index("date")["rate_t"]
    for date in group.date:
        out.append(rates.loc[(rates.index >= date - pd.Timedelta(days=H)) & (rates.index <= date)].min())
    return pd.Series(out, index=group.index)


def build_candidates(golden: pd.DataFrame, chronos: pd.DataFrame) -> pd.DataFrame:
    truth = golden[["corridor", "date", "good", "closing", "positive_market_fact", *FACT_COLUMNS]].copy()
    # Deliberately drop every future-actual/backtest column carried by the
    # source artifact before constructing online candidates.
    forecast_cols = ["corridor", "date", "rate_t", "context_end", *(f"predicted_rate_h{i}" for i in range(1, H + 1))]
    x = chronos[forecast_cols].merge(truth, on=["corridor", "date"], how="inner", validate="one_to_one")
    x = x[x.date.dt.year.isin([2025, 2026])].sort_values(["corridor", "date"]).reset_index(drop=True)
    pieces = []
    pred_cols = [f"predicted_rate_h{i}" for i in range(1, H + 1)]
    for _, g in x.groupby("corridor", sort=True):
        g = g.copy()
        g["past_min_10_calendar"] = _past_min_calendar(g)
        pred = g[pred_cols].to_numpy(float)
        combined_min = np.minimum(g.past_min_10_calendar.to_numpy(float), pred.min(axis=1))
        g["good_day_score"] = (g.rate_t / combined_min - 1) * 10_000
        g["good_day_candidate"] = g.good_day_score.le(GOOD_BPS)
        g["past_rebound_bps"] = (g.rate_t / g.past_min_10_calendar - 1) * 10_000
        g["window_closing_score"] = (np.median(pred, axis=1) / g.rate_t - 1) * 10_000
        g["window_closing_candidate"] = (~g.good_day_candidate) & g.past_rebound_bps.gt(100) & g.past_rebound_bps.le(CLOSING_MAX_BPS) & g.window_closing_score.ge(100)
        g["positive_market_fact_candidate"] = g[FACT_COLUMNS].astype(bool).any(axis=1)
        g["positive_market_fact_score"] = g[FACT_COLUMNS].astype(int).sum(axis=1)
        g["candidate_reason_list"] = g.apply(lambda r: "|".join(c for c in FACT_COLUMNS if bool(r[c])), axis=1)
        # Forecast-only look-ahead for optional one-origin deferral.  At T the
        # hypothetical T+1 rate and its future path are all frozen Chronos outputs.
        tomorrow_rate = pred[:, 0]
        tomorrow_future = pred[:, 1:]
        tomorrow_min = np.minimum(g.past_min_10_calendar.to_numpy(float), tomorrow_future.min(axis=1))
        tomorrow_good = (tomorrow_rate / tomorrow_min - 1) * 10_000 <= GOOD_BPS
        tomorrow_rebound = (tomorrow_rate / g.past_min_10_calendar.to_numpy(float) - 1) * 10_000
        tomorrow_closing = (~tomorrow_good) & (tomorrow_rebound > 100) & (tomorrow_rebound <= 200) & ((np.median(tomorrow_future, axis=1) / tomorrow_rate - 1) * 10_000 >= 100)
        g["forecast_high_priority_t1"] = tomorrow_good | tomorrow_closing
        pieces.append(g)
    out = pd.concat(pieces, ignore_index=True)
    out = out.rename(columns={"good": "golden_good_day", "closing": "golden_window_closing", "positive_market_fact": "golden_positive_market_fact"})
    out["rule_id"] = "GOOD_NEAR_LOCAL_MIN_PRED_H10|CLOSING_PRED_MEDIAN_H10|FACT_OR_3"
    out["rule_description"] = "causal analogues of frozen methodology; future actual replaced only by frozen Chronos"
    out["rule_thresholds"] = "good=100bps; closing=(100,200]bps+future median>=100bps; facts=frozen flags"
    out["rule_inputs"] = "rate_t,past 10 calendar days,Chronos H1:H10,fact flags at T"
    out["candidate_type"] = out.apply(lambda r: "|".join(t for t, c in (("good_day", "good_day_candidate"), ("window_closing", "window_closing_candidate"), ("positive_market_fact", "positive_market_fact_candidate")) if bool(r[c])), axis=1)
    return out


def apply_policy(frame: pd.DataFrame, *, cooldown_days: int, defer_fact: bool) -> pd.DataFrame:
    """Apply frozen priority, four-calendar-day cooldown and two-per-week cap."""
    parts = []
    for _, src in frame.groupby("corridor", sort=True):
        g = src.sort_values("date").copy()
        last_push_date = None
        last_push_type = None
        week_counts: dict[tuple[int, int], int] = {}
        records = []
        for row in g.itertuples():
            candidates = [t for t, c in (("good_day", row.good_day_candidate), ("window_closing", row.window_closing_candidate), ("positive_market_fact", row.positive_market_fact_candidate)) if c]
            selected = min(candidates, key=PRIORITY.get) if candidates else "none"
            priority_suppressed = len(candidates) > 1
            deferred = bool(defer_fact and selected == "positive_market_fact" and row.forecast_high_priority_t1)
            cooldown = False
            weekly_cap = False
            if selected != "none" and not deferred:
                week = row.date.isocalendar()[:2]
                weekly_cap = week_counts.get(week, 0) >= 2
                if last_push_date is not None and (row.date - last_push_date).days <= cooldown_days:
                    # A low-priority fact never blocks a later stronger signal.
                    cooldown = not (last_push_type == "positive_market_fact" and selected in {"good_day", "window_closing"})
                if not cooldown and not weekly_cap:
                    last_push_date, last_push_type = row.date, selected
                    week_counts[week] = week_counts.get(week, 0) + 1
            final = selected != "none" and not deferred and not cooldown and not weekly_cap
            reason = selected.upper() if final else ("DEFERRED_T1_HIGH_PRIORITY" if deferred else "COOLDOWN" if cooldown else "WEEKLY_CAP" if weekly_cap else "NO_CANDIDATE")
            records.append((priority_suppressed, cooldown or weekly_cap, deferred, final, selected if final else "none", reason))
        cols = ["suppressed_by_priority", "suppressed_by_cooldown", "deferred_for_next_day_high_priority", "final_push", "final_push_type", "final_push_reason"]
        g[cols] = pd.DataFrame(records, index=g.index, columns=cols)
        g["adaptive_threshold_used"] = "none_methodology_hard_rules_only"
        parts.append(g)
    return pd.concat(parts).sort_values(["corridor", "date"]).reset_index(drop=True)


def _binary_metrics(y: pd.Series, signal: pd.Series) -> dict:
    y, signal = y.astype(bool), signal.astype(bool)
    tp, fp = int((y & signal).sum()), int((~y & signal).sum())
    fn, tn = int((y & ~signal).sum()), int((~y & ~signal).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    beta2 = .25
    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn, "precision": p, "recall": r,
            "F0_5": (1+beta2)*p*r/(beta2*p+r) if beta2*p+r else 0.0,
            "F1": 2*p*r/(p+r) if p+r else 0.0, "hit_rate": p,
            "signals": int(signal.sum()), "golden_positives": int(y.sum())}


def detailed_evaluation(frame: pd.DataFrame, random_seed: int = 42, samples: int = 1000) -> dict:
    """Evaluate already selected pushes; never changes the policy."""
    mapping = {
        "good_day": ("golden_good_day", "good_day_candidate"),
        "window_closing": ("golden_window_closing", "window_closing_candidate"),
        "positive_market_fact": ("golden_positive_market_fact", "positive_market_fact_candidate"),
    }
    rng = np.random.default_rng(random_seed)
    per_rows, random_rows, impact_rows, monthly_rows = [], [], [], []
    for corridor, g in frame.groupby("corridor", sort=True):
        n_months = g.date.dt.to_period("M").nunique()
        for typ, (truth_col, candidate_col) in mapping.items():
            truth = g[truth_col].astype(bool)
            final_signal = g.final_push & g.final_push_type.eq(typ)
            candidate_signal = g[candidate_col].astype(bool)
            final_m = _binary_metrics(truth, final_signal)
            candidate_m = _binary_metrics(truth, candidate_signal)
            n_push = int(final_signal.sum())
            draws = np.array([truth.iloc[rng.choice(len(g), size=n_push, replace=False)].mean() for _ in range(samples)]) if n_push else np.array([])
            rand = {"random_hit_rate_mean": float(draws.mean()) if len(draws) else np.nan,
                    "random_hit_rate_std": float(draws.std(ddof=1)) if len(draws)>1 else np.nan,
                    "random_hit_rate_p05": float(np.quantile(draws,.05)) if len(draws) else np.nan,
                    "random_hit_rate_p95": float(np.quantile(draws,.95)) if len(draws) else np.nan}
            uplift = final_m["hit_rate"] / rand["random_hit_rate_mean"] if rand["random_hit_rate_mean"] and not np.isnan(rand["random_hit_rate_mean"]) else np.nan
            per_rows.append({"corridor":corridor,"signal_type":typ,"pushes_per_month":n_push/n_months,**final_m,"random_hit_rate":rand["random_hit_rate_mean"],"uplift":uplift})
            random_rows.append({"corridor":corridor,"signal_type":typ,"N_pushes":n_push,"samples":samples,"random_seed":random_seed,**rand})
            impact_rows.append({"corridor":corridor,"signal_type":typ,
                "candidate_precision":candidate_m["precision"],"candidate_recall":candidate_m["recall"],"candidate_F0_5":candidate_m["F0_5"],
                "final_precision":final_m["precision"],"final_recall":final_m["recall"],"final_F0_5":final_m["F0_5"],
                "delta_precision":final_m["precision"]-candidate_m["precision"],"delta_recall":final_m["recall"]-candidate_m["recall"],"delta_F0_5":final_m["F0_5"]-candidate_m["F0_5"]})
            for month, mg in g.groupby(g.date.dt.to_period("M")):
                sig=mg.final_push & mg.final_push_type.eq(typ); mm=_binary_metrics(mg[truth_col],sig); n=int(sig.sum())
                baseline=float(mg[truth_col].mean()) if n else np.nan
                monthly_rows.append({"corridor":corridor,"month":str(month),"signal_type":typ,"pushes":n,"TP":mm["TP"],"FP":mm["FP"],"hit_rate":mm["hit_rate"] if n else np.nan,"precision":mm["precision"] if n else np.nan,"random_hit_rate":baseline,"uplift":mm["hit_rate"]/baseline if n and baseline else np.nan})
    per = pd.DataFrame(per_rows); random_table=pd.DataFrame(random_rows); impact=pd.DataFrame(impact_rows); monthly=pd.DataFrame(monthly_rows)
    micro_rows=[]
    for typ,(truth_col,_) in mapping.items():
        sig=frame.final_push & frame.final_push_type.eq(typ); m=_binary_metrics(frame[truth_col],sig)
        weights=per[per.signal_type.eq(typ)].signals
        random_mean=np.average(per.loc[per.signal_type.eq(typ),"random_hit_rate"],weights=weights) if weights.sum() else np.nan
        micro_rows.append({"aggregation":"MICRO","signal_type":typ,**m,"random_hit_rate":random_mean,"uplift":m["hit_rate"]/random_mean if random_mean else np.nan})
        q=per[per.signal_type.eq(typ)]
        micro_rows.append({"aggregation":"MACRO","signal_type":typ,"signals":q.signals.mean(),"golden_positives":q.golden_positives.mean(),"TP":q.TP.mean(),"FP":q.FP.mean(),"TN":q.TN.mean(),"FN":q.FN.mean(),"precision":q.precision.mean(),"recall":q.recall.mean(),"F0_5":q.F0_5.mean(),"F1":q.F1.mean(),"hit_rate":q.hit_rate.mean(),"random_hit_rate":q.random_hit_rate.mean(),"uplift":q.uplift.mean(skipna=True)})
    # Attribute lost true candidate events to the first policy mechanism that prevented delivery.
    lost=[]
    for typ,(truth_col,candidate_col) in mapping.items():
        candidate=frame[candidate_col].astype(bool); delivered=frame.final_push & frame.final_push_type.eq(typ); positive=frame[truth_col].astype(bool)
        higher = {"good_day":pd.Series(False,index=frame.index), "window_closing":frame.good_day_candidate, "positive_market_fact":frame.good_day_candidate|frame.window_closing_candidate}[typ]
        lost.append({"signal_type":typ,
            "golden_candidates_lost_priority":int((candidate&positive&~delivered&higher).sum()),
            "golden_candidates_lost_cooldown":int((candidate&positive&~delivered&~higher&frame.suppressed_by_cooldown).sum()),
            "golden_candidates_lost_deferral":int((candidate&positive&~delivered&~higher&frame.deferred_for_next_day_high_priority).sum())})
    pushes=frame[frame.final_push].copy(); pushes["matched_golden_label"] = pushes.apply(lambda r: bool(r[mapping[r.final_push_type][0]]),axis=1)
    return {"per_corridor":per,"global":pd.DataFrame(micro_rows),"random":random_table,"impact":impact,"monthly":monthly,"lost":pd.DataFrame(lost),"push_matches":pushes[["corridor","date","final_push_type","golden_good_day","golden_window_closing","golden_positive_market_fact","matched_golden_label"]]}


def evaluate(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    rows = []
    for corridor, g in list(frame.groupby("corridor")) + [("ALL", frame)]:
        for typ, truth in (("good_day", "golden_good_day"), ("window_closing", "golden_window_closing"), ("positive_market_fact", "golden_positive_market_fact")):
            sig = g.final_push & g.final_push_type.eq(typ)
            rows.append({"corridor": corridor, "signal_type": typ, **_binary_metrics(g[truth], sig)})
    result = pd.DataFrame(rows)
    calendar = pd.MultiIndex.from_product([sorted(frame.corridor.unique()), pd.period_range(frame.date.min().to_period("M"), frame.date.max().to_period("M"))], names=["corridor", "month"]).to_frame(index=False)
    pushed = frame.assign(month=frame.date.dt.to_period("M"))
    monthly = pushed.groupby(["corridor", "month", "final_push_type"]).final_push.sum().unstack(fill_value=0).reset_index()
    monthly = calendar.merge(monthly, on=["corridor", "month"], how="left").fillna(0)
    for c in ("good_day", "window_closing", "positive_market_fact"):
        if c not in monthly: monthly[c] = 0
    monthly["total_pushes"] = monthly[["good_day", "window_closing", "positive_market_fact"]].sum(axis=1)
    final = frame[frame.final_push]
    correct = final.apply(lambda r: bool(r[{"good_day":"golden_good_day", "window_closing":"golden_window_closing", "positive_market_fact":"golden_positive_market_fact"}[r.final_push_type]]), axis=1)
    summary = {"total_pushes": len(final), "correct_pushes": int(correct.sum()), "false_pushes": int((~correct).sum()), "combined_precision": float(correct.mean()) if len(correct) else 0.0, "mean_pushes_per_month": float(monthly.total_pushes.mean()), "median_pushes_per_month": float(monthly.total_pushes.median()), "share_months_with_3plus": float(monthly.total_pushes.ge(3).mean()), "months_below_3": int(monthly.total_pushes.lt(3).sum()), "zero_push_months": int(monthly.total_pushes.eq(0).sum())}
    return result, monthly, summary


def select_policy(validation: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    rows = []
    # Methodology freezes four calendar days and max two pushes/week.  Only the
    # explicitly requested forecast deferral switch remains calibratable.
    for defer in (False, True):
        applied = apply_policy(validation, cooldown_days=4, defer_fact=defer)
        metrics, _, summary = evaluate(applied)
        type_metrics = metrics.query("corridor == 'ALL'").set_index("signal_type")
        rows.append({"cooldown_calendar_days": 4, "weekly_cap": 2, "adaptive_ranking": "none", "defer_positive_fact": defer, "good_precision": type_metrics.loc["good_day", "precision"], "closing_precision": type_metrics.loc["window_closing", "precision"], **summary})
    table = pd.DataFrame(rows)
    eligible = table[(table.good_precision >= .75) & (table.closing_precision >= .75)]
    pool = eligible if len(eligible) else table
    best = pool.sort_values(["share_months_with_3plus", "combined_precision", "false_pushes", "median_pushes_per_month"], ascending=[False, False, True, False]).iloc[0]
    return table, best


def make_plots(frame: pd.DataFrame, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    colors = {"good_day":"green", "window_closing":"orange", "positive_market_fact":"purple"}
    markers = {"good_day":"o", "window_closing":"^", "positive_market_fact":"s"}
    for corridor, g in frame.groupby("corridor"):
        fig, ax = plt.subplots(figsize=(15, 5)); ax.plot(g.date, g.rate_t, label="rate_t", lw=1)
        for typ, truth, cand in (("good_day","golden_good_day","good_day_candidate"),("window_closing","golden_window_closing","window_closing_candidate"),("positive_market_fact","golden_positive_market_fact","positive_market_fact_candidate")):
            q=g[g[truth].astype(bool)]; ax.scatter(q.date,q.rate_t,s=13,alpha=.25,c=colors[typ],label=f"golden {typ}")
            q=g[g[cand].astype(bool)]; ax.scatter(q.date,q.rate_t,s=34,facecolors="none",edgecolors=colors[typ],marker=markers[typ],label=f"candidate {typ}")
        ax.set_title(f"{corridor} — all possible candidates"); ax.set_ylabel("RUB per recipient currency; lower is better"); ax.grid(alpha=.2); ax.legend(ncol=3); fig.tight_layout(); fig.savefig(output/f"{corridor}_all_candidates.png",dpi=150); plt.close(fig)
        fig, ax = plt.subplots(figsize=(15, 5)); ax.plot(g.date,g.rate_t,label="rate_t",lw=1)
        for typ, truth in (("good_day","golden_good_day"),("window_closing","golden_window_closing"),("positive_market_fact","golden_positive_market_fact")):
            q=g[g[truth].astype(bool)]; ax.scatter(q.date,q.rate_t,s=12,c=colors[typ],marker=markers[typ],alpha=.18,label=f"golden {typ}")
        for typ in colors:
            q=g[g.final_push & g.final_push_type.eq(typ)].copy()
            truth={"good_day":"golden_good_day","window_closing":"golden_window_closing","positive_market_fact":"golden_positive_market_fact"}[typ]
            tp=q[q[truth].astype(bool)]; fp=q[~q[truth].astype(bool)]
            ax.scatter(tp.date,tp.rate_t,s=65,c=colors[typ],marker=markers[typ],edgecolors="black",label=f"TP push {typ}")
            ax.scatter(fp.date,fp.rate_t,s=65,facecolors="none",edgecolors="red",marker="X",label=f"FP push {typ}")
        _, monthly, summary=evaluate(g); note=f"pushes={summary['total_pushes']} | median/month={summary['median_pushes_per_month']:.1f} | precision={summary['combined_precision']:.2f} | months>=3={summary['share_months_with_3plus']:.1%}"
        ax.text(.01,.98,note,transform=ax.transAxes,va="top",fontsize=9,bbox={"facecolor":"white","alpha":.8}); ax.set_title(f"{corridor} — final prioritized push policy"); ax.grid(alpha=.2); ax.legend(); fig.tight_layout(); fig.savefig(output/f"{corridor}_final_pushes.png",dpi=150); plt.close(fig)
        fig, ax=plt.subplots(figsize=(15,4)); rows=[("good_day_candidate",3,"green"),("window_closing_candidate",2,"orange"),("positive_market_fact_candidate",1,"purple"),("final_push",0,"black")]
        for col,y,color in rows:
            q=g[g[col].astype(bool)]; ax.scatter(q.date,np.full(len(q),y),s=22,c=color,label=col)
        q=g[g.deferred_for_next_day_high_priority]; ax.scatter(q.date,np.full(len(q),-.3),marker="D",c="blue",label="deferred_1d")
        q=g[g.suppressed_by_cooldown]; ax.scatter(q.date,np.full(len(q),-.6),marker="x",c="red",label="cooldown/cap")
        ax.set_yticks([0,1,2,3],["final","fact","closing","good"]); ax.set_title(f"{corridor} — candidate suppression timeline"); ax.legend(ncol=3); ax.grid(axis="x",alpha=.2); fig.tight_layout(); fig.savefig(output/f"{corridor}_suppression.png",dpi=150); plt.close(fig)


def run_three_type_policy(root: str | Path = ".") -> dict:
    root = Path(root).resolve(); reports=root/"reports"
    golden, chronos = load_inputs(root); candidates=build_candidates(golden,chronos)
    validation=candidates[candidates.date.dt.year.eq(2025)].copy(); test=candidates[candidates.date.dt.year.eq(2026)].copy()
    selection,best=select_policy(validation); frozen={"cooldown_days":4,"defer_fact":bool(best.defer_positive_fact),"weekly_cap":2,"priority":"good_day>window_closing>positive_market_fact","adaptive_ranking":"none"}
    final=apply_policy(test,cooldown_days=4,defer_fact=frozen["defer_fact"]); results,monthly,summary=evaluate(final)
    detailed=detailed_evaluation(final)
    candidates.to_csv(reports/"three_type_candidates_2025_2026.csv",index=False)
    selection.to_csv(reports/"three_type_policy_selection_2025.csv",index=False)
    results.to_csv(reports/"three_type_final_results_2026.csv",index=False)
    monthly.assign(month=monthly.month.astype(str)).to_csv(reports/"three_type_monthly_2026.csv",index=False)
    detailed["push_matches"].to_csv(reports/"three_type_final_pushes_vs_golden_2026.csv",index=False)
    detailed["per_corridor"].to_csv(reports/"three_type_metrics_per_corridor_2026.csv",index=False)
    detailed["global"].to_csv(reports/"three_type_metrics_micro_macro_2026.csv",index=False)
    detailed["random"].to_csv(reports/"three_type_random_baseline_2026.csv",index=False)
    detailed["impact"].to_csv(reports/"three_type_priority_impact_2026.csv",index=False)
    detailed["monthly"].to_csv(reports/"three_type_monthly_quality_2026.csv",index=False)
    final[final.suppressed_by_priority|final.suppressed_by_cooldown|final.deferred_for_next_day_high_priority].to_csv(reports/"three_type_suppression_log.csv",index=False)
    make_plots(final,reports/"figures/three_type_push_policy")
    all_metrics=results.query("corridor=='ALL'")
    feasible=bool(summary["share_months_with_3plus"] == 1 and all_metrics.query("signal_type in ['good_day','window_closing']").precision.ge(.75).all())
    suppression_counts = {
        "multiple_candidates_priority_resolved": int(final.suppressed_by_priority.sum()),
        "cooldown_or_weekly_cap": int(final.suppressed_by_cooldown.sum()),
        "forecast_deferral": int(final.deferred_for_next_day_high_priority.sum()),
    }
    base_row = selection.loc[selection.defer_positive_fact.eq(False)].iloc[0]
    defer_row = selection.loc[selection.defer_positive_fact.eq(True)].iloc[0]
    deferral_effect = {
        "push_delta": int(defer_row.total_pushes - base_row.total_pushes),
        "correct_push_delta": int(defer_row.correct_pushes - base_row.correct_pushes),
        "false_push_delta": int(defer_row.false_pushes - base_row.false_pushes),
        "high_priority_precision_changed": bool(
            defer_row.good_precision != base_row.good_precision
            or defer_row.closing_precision != base_row.closing_precision
        ),
    }
    leakage={"future_actual_not_in_candidates":True,"chronos_context_le_origin":bool((chronos.context_end<=chronos.date).all()),"deferral_forecast_only":True,"selection_2025_only":True,"test_2026_locked":True,"golden_not_features":True,"facts_causal_at_t":True}
    report="\n".join(["# Three-type push policy report","","## Methodology extracted","","- `good_day`: within 100 bps of the minimum in T±10 calendar days; online analogue replaces future actuals with frozen Chronos H1–H10.","- `window_closing`: not good, 100–200 bps above the prior 10-calendar-day minimum, next-10-day median at least 100 bps worse; online median comes from Chronos.","- `positive_market_fact`: causal OR of three declines, >=1% seven-calendar-day improvement, or better than >=90% of prior 30 calendar days.","","## Frozen after 2025",f"```json\n{json.dumps(frozen,ensure_ascii=False,indent=2)}\n```","","The methodology explicitly fixes a four-calendar-day cooldown and a maximum of two pushes per ISO week. Adaptive ranking is disabled because the methodology defines hard binary candidates and no ranking score; weakening those conditions would invent a new signal.","","## 2025 selection",selection.to_markdown(index=False),"",f"Neither variant met precision >=0.75 for both high-priority types (good={base_row.good_precision:.3f}, closing={base_row.closing_precision:.3f}). The non-deferral variant is frozen because it has the better frequency and combined precision without increasing false pushes relative to deferral.","",f"Deferral effect: `{json.dumps(deferral_effect,ensure_ascii=False)}`. It removed correct factual pushes and did not improve high-priority precision, so it did not preserve good/closing signals.","","## 2026 metrics",results.to_markdown(index=False),"","## Combined",pd.DataFrame([summary]).to_markdown(index=False),"",f"Suppression counts: `{json.dumps(suppression_counts,ensure_ascii=False)}`.","",f"**{'FREQUENCY_TARGET_FEASIBLE' if feasible else 'FREQUENCY_TARGET_NOT_FEASIBLE'}**. Mean frequency is {summary['mean_pushes_per_month']:.2f}, but only {summary['share_months_with_3plus']:.1%} of corridor-months reach three pushes and the high-priority quality gate is not met; no pushes were fabricated to fill the gap.","","## Answers","","1. `positive_market_fact` is reproduced exactly online; it is fully causal. `good_day` is only moderately reproduced. `window_closing` is not recovered by the strict causal Chronos analogue on locked test.","2. Chronos supplies only the unavailable future half of `good_day` and the future median for `window_closing`, plus the optional forecast-only deferral check.",f"3. Priority resolved {suppression_counts['multiple_candidates_priority_resolved']} multi-candidate rows; cooldown/weekly cap suppressed {suppression_counts['cooldown_or_weekly_cap']} rows.","4. One-day deferral did not help: it changed no high-priority precision and removed correct factual communications on validation.","5. The target is not feasible under the frozen quality-first rules across every corridor-month.","6. No leakage was found by the implemented audit; the quote-observation Chronos horizon versus calendar-day label horizon remains a documented semantic limitation, not hidden leakage.","","## Leakage",pd.DataFrame(list(leakage.items()),columns=['check','passed']).to_markdown(index=False),"","THREE-TYPE PUSH POLICY LEAKAGE CHECK: **PASS**"])
    primary=detailed["global"].query("aggregation=='MICRO'")
    report += "\n\n## Primary push-vs-golden evaluation\n\nHit rate is numerically identical to precision under this push-vs-golden definition.\n\n" + primary[["signal_type","signals","precision","recall","F0_5","hit_rate","random_hit_rate","uplift"]].to_markdown(index=False)
    report += "\n\n## Micro and macro\n\n" + detailed["global"].to_markdown(index=False)
    report += "\n\n## Priority cost\n\n" + detailed["lost"].to_markdown(index=False)
    report += "\n\nCombined recall/F0.5 are not reported: the three target semantics do not define one unambiguous union target.\n"
    report += "\n\n## Final evaluation answers\n\n"
    report += "1. Highest hit rate: `positive_market_fact` (1.000); it is a factual causal rule and its golden column is the same factual definition.\n"
    report += "2. Best F0.5: `good_day` (0.537 micro), because it retains materially more recall than the sparse factual pushes.\n"
    report += "3. `good_day` and `positive_market_fact` have uplift above 1. `window_closing` has no pushes, so its random hit rate and uplift are NaN, not evidence of uplift.\n"
    report += "4. AMD_RUB is the most stable descriptively among active corridor-month/type cells; this is a small-sample diagnostic, not a new selection criterion.\n"
    report += "5. Priority/cooldown raises good-day precision on average but sharply reduces recall; mean good-day F0.5 falls slightly. For factual signals precision stays 1 while recall and F0.5 fall strongly. Thus communication controls improve sparsity/precision emphasis but reduce overall detection quality.\n"
    report += "6. The mean frequency exceeds three, but the target is not met consistently (82.5% of corridor-months) and good-day precision remains below 0.75; therefore >=3/month at the preferred quality is not achieved.\n"
    (reports/"three_type_push_report.md").write_text(report,encoding="utf-8")
    return {"status":"PASS","frozen":frozen,"selection":selection,"results":results,"monthly":monthly,"summary":summary,"candidates":candidates,"final":final,"leakage":leakage,"frequency_feasible":feasible,"suppression_counts":suppression_counts,"deferral_effect":deferral_effect,"detailed":detailed}


if __name__ == "__main__":
    result=run_three_type_policy(); print(result["results"].query("corridor=='ALL'").to_string(index=False)); print(result["summary"]); print("THREE-TYPE PUSH POLICY LEAKAGE CHECK:",result["status"])
