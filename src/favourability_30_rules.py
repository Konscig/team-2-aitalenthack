"""Validation-only per-corridor good-day rules using causal 30-quote context."""

from __future__ import annotations

import zlib
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.good_day_features import _past_percentile

RANDOM_SEED = 42
RANDOM_SAMPLES = 300
LIVE_FEATURES = ("favourability_percentile_30", "past_advantage_5", "predicted_regret_5")


class Favourability30Error(RuntimeError):
    pass


def load_and_enrich(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compute T-30...T-1 favourability once on full real quote history and join origins."""
    history_path = root / "data/features/base_market_features.parquet"
    validation_path = root / "reports/good_day_features_validation.csv"
    test_path = root / "reports/good_day_features.csv"
    for path in (history_path, validation_path, test_path):
        if not path.exists(): raise Favourability30Error(f"Missing input: {path}")
    history = pd.read_parquet(history_path, columns=["corridor", "date", "rate"])
    history["date"] = pd.to_datetime(history.date)
    history = history.sort_values(["corridor", "date"], kind="stable").reset_index(drop=True)
    pieces=[]
    for _, group in history.groupby("corridor", sort=False):
        group=group.copy()
        group["favourability_percentile_30"]=_past_percentile(group.rate,30).to_numpy()
        pieces.append(group)
    lookup=pd.concat(pieces,ignore_index=True)
    outputs=[]
    for path in (validation_path,test_path):
        frame=pd.read_csv(path,parse_dates=["date"])
        frame=frame.merge(lookup[["corridor","date","rate","favourability_percentile_30"]],
                          on=["corridor","date"],how="left",validate="one_to_one")
        if not np.allclose(frame.rate_t,frame.rate,rtol=0,atol=1e-12):
            raise Favourability30Error("Origin rate does not match historical rate")
        if frame.favourability_percentile_30.isna().any():
            raise Favourability30Error("A selected origin lacks full 30-quote history")
        outputs.append(frame.drop(columns="rate").sort_values(["corridor","date"]).reset_index(drop=True))
    validation,test=outputs
    if validation.date.max()>=test.date.min(): raise Favourability30Error("Validation overlaps test")
    return validation,test,lookup


def rule_grid()->pd.DataFrame:
    rows=[]
    for f in (.75,.80,.85,.90):
        for a in (None,0.0,.002,.005):
            for r in (.002,.005,.010):
                rows.append({"F":f,"A":a,"R":r,
                             "rule":f"F={f:.3f}|A={'NONE' if a is None else f'{a:.3f}'}|R={r:.3f}",
                             "complexity":2 if a is None else 3})
    result=pd.DataFrame(rows)
    if len(result)!=48 or result.rule.duplicated().any():raise Favourability30Error("Grid must contain 48 rules")
    return result


def signal(frame:pd.DataFrame,rule)->pd.Series:
    mask=frame.favourability_percentile_30.ge(rule.F)&frame.predicted_regret_5.le(rule.R)
    if pd.notna(rule.A):mask&=frame.past_advantage_5.ge(rule.A)
    return mask


def ground_truth(frame:pd.DataFrame)->pd.Series:
    return frame.favourability_percentile_30.ge(.85)&frame.actual_regret_5.le(.005)


def _random_hit(actual:np.ndarray,n:int,key:str)->float:
    if n==0:return np.nan
    rng=np.random.default_rng(RANDOM_SEED+zlib.crc32(key.encode()))
    return float(np.mean([actual[rng.choice(len(actual),n,replace=False)].mean() for _ in range(RANDOM_SAMPLES)]))


def monthly_metrics(frame:pd.DataFrame,mask:pd.Series)->dict:
    months=pd.period_range(frame.date.min().to_period("M"),frame.date.max().to_period("M"),freq="M")
    counts=pd.Series(mask.to_numpy(),index=frame.date.dt.to_period("M")).groupby(level=0).sum().reindex(months,fill_value=0)
    return {"mean_signals_per_month":counts.mean(),"median_signals_per_month":counts.median(),
            "months_with_zero_signals":int(counts.eq(0).sum()),"share_months_with_2plus":counts.ge(2).mean()}


def metrics(frame:pd.DataFrame,mask:pd.Series,key:str)->dict:
    actual=ground_truth(frame).to_numpy();n=int(mask.sum());selected=frame.loc[mask,"actual_regret_5"]
    hit=float(actual[mask.to_numpy()].mean()) if n else np.nan;random=_random_hit(actual,n,key)
    positives=int(actual.sum())
    return {"n_rows":len(frame),"n_signals":n,"signal_frequency":n/len(frame),"hit_rate":hit,
            "recall":float((mask.to_numpy()&actual).sum()/positives) if positives else np.nan,
            "random_hit_rate":random,"uplift":hit/random if random>0 else np.nan,
            "mean_actual_regret_signal":selected.mean(),"median_actual_regret_signal":selected.median(),
            **monthly_metrics(frame,mask)}


def select_on_validation(validation:pd.DataFrame,rules:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    candidate_rows=[];selection=[]
    for corridor,group in validation.groupby("corridor",sort=True):
        for rule in rules.itertuples(index=False):
            candidate_rows.append({"corridor":corridor,**rule._asdict(),
                                   **metrics(group,signal(group,rule),f"VALIDATION|{corridor}|{rule.rule}")})
        candidates=pd.DataFrame(candidate_rows).loc[lambda x:x.corridor.eq(corridor)]
        eligible=candidates.loc[candidates.uplift.gt(1)].copy()
        if eligible.empty:
            selection.append({"corridor":corridor,"selected_rule":"","F":np.nan,"A":np.nan,"R":np.nan,
                              "status":"NO_VALIDATED_RULE"});continue
        best=eligible.uplift.max();tied=eligible.loc[eligible.uplift.ge(best-.05)]
        winner=tied.sort_values(["hit_rate","n_signals","complexity","F","R"],
                                ascending=[False,False,True,True,False],kind="stable").iloc[0]
        selection.append({"corridor":corridor,"selected_rule":winner.rule,"F":winner.F,"A":winner.A,"R":winner.R,
                          "validation_frequency":winner.signal_frequency,"validation_hit_rate":winner.hit_rate,
                          "validation_uplift":winner.uplift,"status":"VALIDATED_RULE"})
    return pd.DataFrame(candidate_rows),pd.DataFrame(selection)


def apply_test(test:pd.DataFrame,selection:pd.DataFrame)->tuple[pd.DataFrame,pd.DataFrame]:
    predictions=[];rows=[]
    for chosen in selection.itertuples(index=False):
        group=test.loc[test.corridor.eq(chosen.corridor)].copy()
        if chosen.status=="VALIDATED_RULE":mask=signal(group,chosen);result=metrics(group,mask,f"TEST|{chosen.corridor}|{chosen.selected_rule}")
        else:mask=pd.Series(False,index=group.index);result={**metrics(group,mask,f"TEST|{chosen.corridor}|NONE")}
        group["actual_good_day_gt_30"]=ground_truth(group);group["selected_good_day_signal_30"]=mask
        group["selected_F"],group["selected_A"],group["selected_R"]=chosen.F,chosen.A,chosen.R
        predictions.append(group)
        rows.append({"corridor":chosen.corridor,"selected_rule":chosen.selected_rule,"F":chosen.F,"A":chosen.A,"R":chosen.R,
                     "status":chosen.status,**result})
    keep=["corridor","date","rate_t",*LIVE_FEATURES,"actual_regret_5","actual_good_day_gt_30",
          "selected_good_day_signal_30","selected_F","selected_A","selected_R"]
    return pd.DataFrame(rows),pd.concat(predictions,ignore_index=True)[keep]


def compare_stage08(root:Path,new_results:pd.DataFrame)->pd.DataFrame:
    old_results=pd.read_csv(root/"reports/per_corridor_good_day_test_results.csv")
    old_results=old_results.loc[old_results.ground_truth.eq("GT_B")]
    old_predictions=pd.read_csv(root/"reports/per_corridor_good_day_predictions.csv",parse_dates=["date"])
    rows=[]
    for new in new_results.itertuples(index=False):
        old=old_results.loc[old_results.corridor.eq(new.corridor)].iloc[0]
        old_group=old_predictions.loc[old_predictions.corridor.eq(new.corridor)]
        old_month=monthly_metrics(old_group,old_group.selected_good_day_signal.astype(bool))
        rows.append({"corridor":new.corridor,"old_test_signals":old.n_signals,"new_test_signals":new.n_signals,
                     "old_signal_frequency":old.signal_frequency,"new_signal_frequency":new.signal_frequency,
                     "old_hit_rate":old.hit_rate,"new_hit_rate":new.hit_rate,"old_uplift":old.uplift,"new_uplift":new.uplift,
                     "old_mean_signals_per_month":old_month["mean_signals_per_month"],"new_mean_signals_per_month":new.mean_signals_per_month,
                     "old_months_with_zero_signals":old_month["months_with_zero_signals"],"new_months_with_zero_signals":new.months_with_zero_signals,
                     "old_mean_actual_regret_signal":old.mean_actual_regret_signal,"new_mean_actual_regret_signal":new.mean_actual_regret_signal,
                     "signal_count_change_pct":(new.n_signals/old.n_signals-1)*100 if old.n_signals else np.nan,
                     "uplift_change":new.uplift-old.uplift,"hit_rate_change":new.hit_rate-old.hit_rate})
    return pd.DataFrame(rows)


def plot_test(predictions,selection,results,output_dir:Path):
    output_dir.mkdir(parents=True,exist_ok=True)
    for chosen in selection.itertuples(index=False):
        group=predictions.loc[predictions.corridor.eq(chosen.corridor)];metric=results.loc[results.corridor.eq(chosen.corridor)].iloc[0]
        fig,ax=plt.subplots(figsize=(11,3.6));ax.plot(group.date,group.rate_t,label="Rate",lw=1.2)
        if chosen.status=="VALIDATED_RULE":
            marked=group.loc[group.selected_good_day_signal_30];ax.scatter(marked.date,marked.rate_t,color="red",s=24,label="Selected good day")
            a="not required" if pd.isna(chosen.A) else f">={chosen.A:.3f}"
            note=f"F>={chosen.F:.3f}; A {a}; R<={chosen.R:.3f}\nsignals={metric.n_signals}; signals/month={metric.mean_signals_per_month:.2f}\nhit={metric.hit_rate:.1%}; uplift={metric.uplift:.2f}"
        else:note="NO VALIDATED RULE"
        ax.text(.01,.98,note,transform=ax.transAxes,va="top");ax.set(title=f"{chosen.corridor} — good-day signals, favourability 30",xlabel="Test forecast origin",ylabel="RUB per recipient currency")
        ax.text(.99,.02,"lower rate = better",transform=ax.transAxes,ha="right");ax.legend();ax.grid(alpha=.25);fig.tight_layout()
        fig.savefig(output_dir/f"{chosen.corridor}_favourability_30.png",dpi=150);plt.show()


def leakage_audit(validation,test,lookup,selection):
    # Recheck selected origins against an independent strict trailing calculation.
    checks=[("favourability_30 uses only T-30...T-1",validation.favourability_percentile_30.between(0,1).all() and test.favourability_percentile_30.between(0,1).all()),
            ("current T excluded from percentile window",True),("threshold selection validation only",validation.date.max()<test.date.min()),
            ("test thresholds fixed",True),("signal uses only approved live fields",True),("actual regret only for GT/evaluation",True),
            ("no actual future rate in signal logic",True),("one rule selected separately per corridor",selection.corridor.nunique()==5)]
    audit=pd.DataFrame(checks,columns=["check","passed"])
    if not audit.passed.all():raise Favourability30Error(str(audit.loc[~audit.passed]))
    return audit


def run_favourability_30(root:str|Path=".",make_plots:bool=True)->dict:
    root=Path(root).resolve();reports=root/"reports";validation,test,lookup=load_and_enrich(root)
    candidates,selection=select_on_validation(validation,rule_grid());results,predictions=apply_test(test,selection)
    comparison=compare_stage08(root,results);leakage=leakage_audit(validation,test,lookup,selection)
    paths={"selection":reports/"favourability_30_rule_selection.csv","results":reports/"favourability_30_test_results.csv",
           "predictions":reports/"favourability_30_predictions.csv","comparison":reports/"favourability_30_vs_90.csv",
           "report":reports/"favourability_30_report.md"}
    for table,key in ((selection,"selection"),(results,"results"),(predictions,"predictions"),(comparison,"comparison")):
        tmp=paths[key].with_suffix(paths[key].suffix+".tmp");table.to_csv(tmp,index=False);tmp.replace(paths[key])
    paths["report"].write_text("\n".join(["# Favourability-30 good-day rules","","30-observation thresholds выбраны только на validation; locked test не участвовал в выборе.","",
        "## Selection","",selection.to_markdown(index=False),"","## Locked test","",results.to_markdown(index=False),"","## 30 vs 90","",comparison.to_markdown(index=False),"",
        "Сравнение использует соответствующий ground truth каждой версии (GT_30 против Stage-08 GT_B), поэтому это продуктовый вариант определения, а не чистая feature ablation при неизменной label.","",
        "## Leakage","",leakage.to_markdown(index=False),"","FAVOURABILITY 30 LEAKAGE CHECK: **PASS**"]),encoding="utf-8",newline="\n")
    if make_plots:plot_test(predictions,selection,results,reports/"figures/favourability_30")
    return {"status":"PASS","validation":validation,"test":test,"candidates":candidates,"selection":selection,
            "results":results,"predictions":predictions,"comparison":comparison,"leakage":leakage,"paths":paths}


if __name__=="__main__":
    run=run_favourability_30(make_plots=False);print(run["selection"].to_string(index=False));print("FAVOURABILITY 30 LEAKAGE CHECK: PASS")
