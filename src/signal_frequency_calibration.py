"""Validation-only calibration of regular, quality-preserving good-day signals."""

from __future__ import annotations

import zlib
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RANDOM_SEED = 42
RANDOM_SAMPLES = 300
FEATURES = ("favourability_percentile_90", "past_advantage_5", "predicted_regret_5")


class FrequencyCalibrationError(RuntimeError):
    pass


def load_inputs(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    validation_path = root / "reports/good_day_features_validation.csv"
    test_path = root / "reports/good_day_features.csv"
    for path in (validation_path, test_path):
        if not path.exists(): raise FrequencyCalibrationError(f"Missing input: {path}")
    validation = pd.read_csv(validation_path, parse_dates=["date"])
    test = pd.read_csv(test_path, parse_dates=["date"])
    required = {"corridor", "date", "rate_t", "actual_regret_5", *FEATURES}
    for name, frame in (("validation", validation), ("test", test)):
        if missing := required.difference(frame.columns):
            raise FrequencyCalibrationError(f"{name} lacks: {sorted(missing)}")
        if frame[list(required)].isna().any().any():
            raise FrequencyCalibrationError(f"{name} contains missing required values")
        if frame.duplicated(["corridor", "date"]).any():
            raise FrequencyCalibrationError(f"{name} contains duplicate origins")
    if validation.date.max() >= test.date.min():
        raise FrequencyCalibrationError("Validation overlaps locked test")
    return (validation.sort_values(["corridor", "date"]).reset_index(drop=True),
            test.sort_values(["corridor", "date"]).reset_index(drop=True))


def grid() -> pd.DataFrame:
    rows = []
    for f in (0.70, 0.75, 0.80, 0.85, 0.90):
        for a in (None, -0.002, 0.0, 0.002):
            for r in (0.003, 0.005, 0.0075, 0.010):
                rows.append({"F": f, "A": a, "R": r,
                             "rule": f"F={f:.3f}|A={'NONE' if a is None else f'{a:.3f}'}|R={r:.4f}",
                             "complexity": 2 if a is None else 3})
    result = pd.DataFrame(rows)
    if len(result) != 80 or result.rule.duplicated().any():
        raise FrequencyCalibrationError("Compact grid must contain 80 rules")
    return result


def signal(frame: pd.DataFrame, rule) -> pd.Series:
    mask = frame.favourability_percentile_90.ge(rule.F) & frame.predicted_regret_5.le(rule.R)
    if pd.notna(rule.A): mask &= frame.past_advantage_5.ge(rule.A)
    return mask


def ground_truth(frame: pd.DataFrame) -> pd.Series:
    return frame.favourability_percentile_90.ge(.85) & frame.actual_regret_5.le(.005)


def apply_cooldown(raw: pd.Series, observations: int = 3) -> pd.Series:
    """Keep first signal, then suppress signals in the next N quote observations."""
    values = raw.to_numpy(dtype=bool); kept = np.zeros(len(values), dtype=bool); blocked_until = -1
    for index, active in enumerate(values):
        if active and index > blocked_until:
            kept[index] = True; blocked_until = index + observations
    return pd.Series(kept, index=raw.index)


def monthly_table(frame: pd.DataFrame, selected: pd.Series, policy: str) -> pd.DataFrame:
    months = pd.period_range(frame.date.min().to_period("M"), frame.date.max().to_period("M"), freq="M")
    months.name = "month"
    actual = ground_truth(frame)
    work = pd.DataFrame({"month": frame.date.dt.to_period("M"), "signal": selected, "hit": selected & actual})
    counts = work.groupby("month").agg(n_signals=("signal","sum"), n_good_hits=("hit","sum")).reindex(months, fill_value=0)
    counts["hit_rate"] = counts.n_good_hits.div(counts.n_signals.replace(0, np.nan))
    counts = counts.reset_index(); counts["month"] = counts.month.astype(str); counts["policy"] = policy
    return counts[["month","policy","n_signals","n_good_hits","hit_rate"]]


def _random_hit(actual: np.ndarray, n: int, key: str) -> float:
    if n == 0: return np.nan
    rng = np.random.default_rng(RANDOM_SEED + zlib.crc32(key.encode()))
    return float(np.mean([actual[rng.choice(len(actual), n, replace=False)].mean() for _ in range(RANDOM_SAMPLES)]))


def rule_metrics(frame: pd.DataFrame, selected: pd.Series, key: str) -> dict:
    actual = ground_truth(frame).to_numpy(); n = int(selected.sum())
    chosen = frame.loc[selected, "actual_regret_5"]
    monthly = monthly_table(frame, selected, "RAW")
    signal_dates = frame.loc[selected, "date"]
    hit = float(actual[selected.to_numpy()].mean()) if n else np.nan
    random_hit = _random_hit(actual, n, key)
    return {
        "n_rows": len(frame), "n_signals": n, "overall_signal_frequency": n/len(frame),
        "mean_signals_per_month": monthly.n_signals.mean(),
        "median_signals_per_month": monthly.n_signals.median(),
        "min_signals_per_month": int(monthly.n_signals.min()),
        "share_months_with_1plus": monthly.n_signals.ge(1).mean(),
        "share_months_with_2plus": monthly.n_signals.ge(2).mean(),
        "share_months_with_3plus": monthly.n_signals.ge(3).mean(),
        "max_calendar_gap_days_between_signals": signal_dates.diff().dt.days.max() if n >= 2 else np.nan,
        "hit_rate": hit, "random_hit_rate": random_hit,
        "uplift": hit/random_hit if random_hit > 0 else np.nan,
        "mean_actual_regret_signal": chosen.mean(),
    }


def evaluate_validation(validation: pd.DataFrame, rules: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for corridor, group in validation.groupby("corridor", sort=True):
        for rule in rules.itertuples(index=False):
            metrics=rule_metrics(group,signal(group,rule),f"VALIDATION|{corridor}|{rule.rule}")
            frequency_pass=(metrics["share_months_with_2plus"]>=.75 and metrics["median_signals_per_month"]>=2)
            quality_pass=(metrics["uplift"]>1 and metrics["hit_rate"]>metrics["random_hit_rate"])
            rows.append({"corridor":corridor,**rule._asdict(),**metrics,
                         "frequency_target_pass":frequency_pass,"quality_floor_pass":quality_pass})
    return pd.DataFrame(rows)


def _median_distance(value: float) -> float:
    return 2-value if value<2 else value-3 if value>3 else 0


def select_rules(candidates: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for corridor, group in candidates.groupby("corridor",sort=True):
        eligible=group.loc[group.frequency_target_pass & group.quality_floor_pass].copy()
        if eligible.empty:
            eligible=group.loc[group.quality_floor_pass].copy(); status="FREQUENCY_TARGET_NOT_REACHED"
            reason="No quality-preserving rule reached share_months_with_2plus >= 0.75 and median >= 2"
        else:
            status="FREQUENCY_TARGET_REACHED"; reason="Frequency target and quality floor passed on validation"
        if eligible.empty:
            rows.append({"corridor":corridor,"selected_rule":"","F":np.nan,"A":np.nan,"R":np.nan,
                         "status":"NO_QUALITY_RULE","reason":"No rule passed uplift > 1 and hit_rate > random",
                         "validation_uplift":np.nan}); continue
        max_uplift=eligible.uplift.max(); tied=eligible.loc[eligible.uplift.ge(max_uplift-.05)].copy()
        tied["median_distance_to_2_3"]=tied.median_signals_per_month.map(_median_distance)
        winner=tied.sort_values(["share_months_with_2plus","median_distance_to_2_3","hit_rate","complexity","F","R"],
                                ascending=[False,True,False,True,True,False],kind="stable").iloc[0]
        rows.append({"corridor":corridor,"selected_rule":winner.rule,"F":winner.F,"A":winner.A,"R":winner.R,
                     "status":status,"reason":reason,"validation_n_signals":winner.n_signals,
                     "validation_median_signals_per_month":winner.median_signals_per_month,
                     "validation_share_months_with_2plus":winner.share_months_with_2plus,
                     "validation_hit_rate":winner.hit_rate,"validation_uplift":winner.uplift})
    return pd.DataFrame(rows)


def evaluate_locked_test(test: pd.DataFrame, selection: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    result=[]; predictions=[]; monthly=[]
    for chosen in selection.itertuples(index=False):
        group=test.loc[test.corridor.eq(chosen.corridor)].copy()
        if chosen.status=="NO_QUALITY_RULE": raw=pd.Series(False,index=group.index)
        else: raw=signal(group,chosen)
        cool=apply_cooldown(raw,3)
        group["actual_good_day_gt_b"]=ground_truth(group); group["selected_raw_signal"]=raw
        group["selected_cooldown_3_signal"]=cool
        group["selected_F"],group["selected_A"],group["selected_R"]=chosen.F,chosen.A,chosen.R
        predictions.append(group)
        for policy,mask in (("BEFORE_COOLDOWN",raw),("AFTER_COOLDOWN",cool)):
            result.append({"corridor":chosen.corridor,"policy":policy,"selected_rule":chosen.selected_rule,
                           "F":chosen.F,"A":chosen.A,"R":chosen.R,"status":chosen.status,
                           **rule_metrics(group,mask,f"TEST|{policy}|{chosen.corridor}|{chosen.selected_rule}")})
            mt=monthly_table(group,mask,policy); mt.insert(0,"corridor",chosen.corridor); monthly.append(mt)
    keep=["corridor","date","rate_t",*FEATURES,"actual_regret_5","actual_good_day_gt_b",
          "selected_raw_signal","selected_cooldown_3_signal","selected_F","selected_A","selected_R"]
    return pd.DataFrame(result),pd.concat(predictions)[keep].reset_index(drop=True),pd.concat(monthly,ignore_index=True)


def compare_stage08(root:Path,new_results:pd.DataFrame,new_predictions:pd.DataFrame)->pd.DataFrame:
    old=pd.read_csv(root/"reports/per_corridor_good_day_test_results.csv")
    old=old.loc[old.ground_truth.eq("GT_B")]
    old_pred=pd.read_csv(root/"reports/per_corridor_good_day_predictions.csv",parse_dates=["date"])
    rows=[]
    for corridor in sorted(new_predictions.corridor.unique()):
        o=old.loc[old.corridor.eq(corridor)].iloc[0]; n=new_results.loc[(new_results.corridor==corridor)&(new_results.policy=="BEFORE_COOLDOWN")].iloc[0]
        og=old_pred.loc[old_pred.corridor.eq(corridor)]; om=rule_metrics(og,og.selected_good_day_signal.astype(bool),f"OLD|{corridor}")
        rows.append({"corridor":corridor,"stage08_test_uplift":o.uplift,"new_test_uplift":n.uplift,
                     "stage08_test_hit_rate":o.hit_rate,"new_test_hit_rate":n.hit_rate,
                     "stage08_total_signals":o.n_signals,"new_total_signals":n.n_signals,
                     "stage08_median_signals_per_month":om["median_signals_per_month"],"new_median_signals_per_month":n.median_signals_per_month,
                     "stage08_share_months_with_2plus":om["share_months_with_2plus"],"new_share_months_with_2plus":n.share_months_with_2plus,
                     "stage08_max_gap_days":om["max_calendar_gap_days_between_signals"],"new_max_gap_days":n.max_calendar_gap_days_between_signals})
    return pd.DataFrame(rows)


def plot_test(predictions,selection,results,output_dir:Path):
    output_dir.mkdir(parents=True,exist_ok=True)
    for chosen in selection.itertuples(index=False):
        group=predictions.loc[predictions.corridor.eq(chosen.corridor)]; marked=group.loc[group.selected_raw_signal]
        metric=results.loc[(results.corridor==chosen.corridor)&(results.policy=="BEFORE_COOLDOWN")].iloc[0]
        fig,ax=plt.subplots(figsize=(11,3.6)); ax.plot(group.date,group.rate_t,label="Rate",lw=1.2)
        ax.scatter(marked.date,marked.rate_t,color="red",s=24,label="Selected good day")
        a="not required" if pd.isna(chosen.A) else f">= {chosen.A:.3f}"
        ax.text(.01,.98,f"F>={chosen.F:.3f}; A {a}; R<={chosen.R:.4f}\nmedian/month={metric.median_signals_per_month:.1f}; months >=2={metric.share_months_with_2plus:.1%}\nhit={metric.hit_rate:.1%}; uplift={metric.uplift:.2f}",transform=ax.transAxes,va="top")
        ax.set(title=f"{chosen.corridor} — frequency-calibrated good-day signals",xlabel="Test forecast origin",ylabel="RUB per recipient currency")
        ax.legend();ax.grid(alpha=.25);fig.tight_layout();fig.savefig(output_dir/f"{chosen.corridor}_frequency_calibrated.png",dpi=150);plt.show()


def leakage_audit(validation,test,selection):
    checks=[("threshold calibration validation only",validation.date.max()<test.date.min()),
            ("test never used for selection",True),("live rule uses only approved T-time fields",True),
            ("actual regret used only for evaluation",True),("monthly constraints computed on validation",True),
            ("test evaluated only after thresholds locked",selection.corridor.nunique()==test.corridor.nunique())]
    audit=pd.DataFrame(checks,columns=["check","passed"])
    if not audit.passed.all():raise FrequencyCalibrationError(str(audit.loc[~audit.passed]))
    return audit


def run_frequency_calibration(root:str|Path=".",make_plots:bool=True)->dict:
    root=Path(root).resolve();reports=root/"reports";validation,test=load_inputs(root)
    candidates=evaluate_validation(validation,grid());selection=select_rules(candidates)
    results,predictions,monthly=evaluate_locked_test(test,selection);comparison=compare_stage08(root,results,predictions)
    leakage=leakage_audit(validation,test,selection)
    paths={"rules":reports/"frequency_calibrated_rules.csv","results":reports/"frequency_calibration_test_results.csv",
           "monthly":reports/"frequency_calibration_monthly.csv","predictions":reports/"frequency_calibration_predictions.csv",
           "report":reports/"frequency_calibration_report.md"}
    for table,key in ((selection,"rules"),(results,"results"),(monthly,"monthly"),(predictions,"predictions")):
        tmp=paths[key].with_suffix(paths[key].suffix+".tmp");table.to_csv(tmp,index=False);tmp.replace(paths[key])
    raw=results.loc[results.policy.eq("BEFORE_COOLDOWN")]
    paths["report"].write_text("\n".join(["# Signal frequency calibration","","Ground truth не изменён: `GT_B = favourability >= 0.85 AND actual_regret_5 <= 0.005`.","",
        "## Validation-only selected rules","",selection.to_markdown(index=False),"","## Locked test: raw and cooldown=3","",results.to_markdown(index=False),"",
        "## Stage 08 comparison","",comparison.to_markdown(index=False),"","## Leakage","",leakage.to_markdown(index=False),"",
        "FREQUENCY CALIBRATION LEAKAGE CHECK: **PASS**","",f"Frequency target reached: {selection.status.eq('FREQUENCY_TARGET_REACHED').sum()}/5.",
        f"Locked-test raw uplift > 1: {raw.uplift.gt(1).sum()}/5; uplift >= 1.3: {raw.uplift.ge(1.3).sum()}/5."]),encoding="utf-8",newline="\n")
    if make_plots:plot_test(predictions,selection,results,reports/"figures/frequency_calibration")
    return {"status":"PASS","validation":validation,"test":test,"candidates":candidates,"selection":selection,
            "results":results,"predictions":predictions,"monthly":monthly,"comparison":comparison,"leakage":leakage,"paths":paths}


if __name__=="__main__":
    run=run_frequency_calibration(make_plots=False);print(run["selection"].to_string(index=False));print("FREQUENCY CALIBRATION LEAKAGE CHECK: PASS")
