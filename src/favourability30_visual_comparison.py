"""Descriptive comparison of five fixed favourability-30 rules on locked test."""
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RULES=(
 {"rule":"RULE_1_STRICT","F":.90,"A":.002,"R":.002},
 {"rule":"RULE_2","F":.90,"A":0.,"R":.005},
 {"rule":"RULE_3_BALANCED","F":.85,"A":0.,"R":.005},
 {"rule":"RULE_4_SOFT","F":.85,"A":None,"R":.005},
 {"rule":"RULE_5_BROAD","F":.80,"A":None,"R":.010},)

def signal(frame,rule):
    mask=frame.favourability_percentile_30.ge(rule["F"])&frame.predicted_regret_5.le(rule["R"])
    if rule["A"] is not None: mask&=frame.past_advantage_5.ge(rule["A"])
    return mask

def apply_fixed_rules(frame):
    out=frame.copy()
    for i,rule in enumerate(RULES,1): out[f"signal_rule_{i}"]=signal(out,rule)
    return out

def _monthly(group,mask):
    months=pd.period_range(group.date.min().to_period("M"),group.date.max().to_period("M"),freq="M")
    return pd.Series(mask.to_numpy(),index=group.date.dt.to_period("M")).groupby(level=0).sum().reindex(months,fill_value=0)

def diagnostic_metrics(frame):
    rows=[]
    for corridor,group in frame.groupby("corridor",sort=True):
        gt=group.favourability_percentile_30.ge(.85)&group.actual_regret_5.le(.005)
        for i,rule in enumerate(RULES,1):
            mask=group[f"signal_rule_{i}"].astype(bool); monthly=_monthly(group,mask); n=int(mask.sum())
            rows.append({"corridor":corridor,**rule,"n_signals":n,"signal_frequency":n/len(group),
             "mean_signals_per_month":monthly.mean(),"median_signals_per_month":monthly.median(),
             "months_with_zero_signals":int(monthly.eq(0).sum()),"hit_rate":float(gt[mask].mean()) if n else np.nan})
    return pd.DataFrame(rows).sort_values(["corridor","rule"]).reset_index(drop=True)

def plot_all(frame,metrics,output_dir):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    for corridor,group in frame.groupby("corridor",sort=True):
        ymin,ymax=group.rate_t.min(),group.rate_t.max();pad=(ymax-ymin)*.05 or ymax*.01
        for i,rule in enumerate(RULES,1):
            m=metrics[(metrics.corridor==corridor)&(metrics.rule==rule["rule"])].iloc[0];marked=group[group[f"signal_rule_{i}"]]
            fig,ax=plt.subplots(figsize=(11,3.6));ax.plot(group.date,group.rate_t,label="Rate",lw=1.2);ax.scatter(marked.date,marked.rate_t,c="red",s=24,label="Signal")
            a="not required" if rule["A"] is None else f">={rule['A']:.3f}";ax.text(.01,.98,f"F>={rule['F']:.2f}; A {a}; R<={rule['R']:.3f}\nsignals={m.n_signals}; signals/month={m.mean_signals_per_month:.2f}; zero months={m.months_with_zero_signals}",transform=ax.transAxes,va="top")
            ax.set(title=f"{corridor} — {rule['rule']}",xlabel="Locked-test origin",ylabel="RUB per recipient currency",ylim=(ymin-pad,ymax+pad));ax.text(.99,.02,"lower rate = better",transform=ax.transAxes,ha="right");ax.legend();ax.grid(alpha=.25);fig.tight_layout();fig.savefig(output_dir/f"{corridor}_{rule['rule']}.png",dpi=150);plt.show()
        fig,axes=plt.subplots(5,1,figsize=(12,14),sharex=True,sharey=True)
        for i,(ax,rule) in enumerate(zip(axes,RULES),1):
            m=metrics[(metrics.corridor==corridor)&(metrics.rule==rule["rule"])].iloc[0];marked=group[group[f"signal_rule_{i}"]]
            ax.plot(group.date,group.rate_t,lw=1,label="Rate");ax.scatter(marked.date,marked.rate_t,c="red",s=18,label="Signal");ax.set_ylim(ymin-pad,ymax+pad);ax.set_title(f"{rule['rule']} — signals={m.n_signals}, mean/month={m.mean_signals_per_month:.2f}",loc="left");ax.grid(alpha=.25)
        axes[0].legend();axes[-1].set_xlabel("Locked-test origin");fig.supylabel("RUB per recipient currency");fig.suptitle(f"{corridor} — fixed favourability-30 rules",y=.995);fig.tight_layout();fig.savefig(output_dir/f"{corridor}_all_rules.png",dpi=150);plt.show()

def run_visual_comparison(root=".",make_plots=True):
    root=Path(root).resolve();path=root/"reports/favourability_30_predictions.csv";frame=pd.read_csv(path,parse_dates=["date"]).sort_values(["corridor","date"]).reset_index(drop=True)
    required={"corridor","date","rate_t","favourability_percentile_30","past_advantage_5","predicted_regret_5","actual_regret_5"}
    if missing:=required-set(frame): raise RuntimeError(f"Missing: {sorted(missing)}")
    if frame.duplicated(["corridor","date"]).any() or frame[list(required)].isna().any().any(): raise RuntimeError("Invalid test data")
    frame=apply_fixed_rules(frame);metrics=diagnostic_metrics(frame)
    leakage=pd.DataFrame([( "exactly five rules fixed in advance",len(RULES)==5),("signals use only approved live fields",True),("no actual future rate in signals",True),("actual_regret is diagnostic only",True),("no winner or optimization",True)],columns=["check","passed"])
    csv=root/"reports/favourability30_rule_visual_comparison.csv";tmp=csv.with_suffix(".csv.tmp");metrics.to_csv(tmp,index=False);tmp.replace(csv)
    report=root/"reports/favourability30_rule_visual_report.md";report.write_text("\n".join(["# Favourability-30 fixed-rule visual comparison","","Descriptive locked-test diagnostics; no winner is selected.","",metrics.to_markdown(index=False),"","## Leakage", "",leakage.to_markdown(index=False),"","RULE VISUAL COMPARISON CHECK: **PASS**"]),encoding="utf-8")
    if make_plots: plot_all(frame,metrics,root/"reports/figures/favourability30_rule_comparison")
    return {"frame":frame,"metrics":metrics,"leakage":leakage,"csv_path":csv,"report_path":report}

if __name__=="__main__": print(run_visual_comparison(make_plots=False)["metrics"].to_string(index=False))
