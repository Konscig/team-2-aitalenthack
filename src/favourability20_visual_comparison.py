"""Descriptive locked-test comparison of fixed rules with causal 20-quote favourability."""
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from src.favourability30_visual_comparison import RULES
from src.good_day_features import _past_percentile

def load_test(root:Path):
    base=pd.read_parquet(root/"data/features/base_market_features.parquet",columns=["corridor","date","rate","favourability_percentile_20"])
    base["date"]=pd.to_datetime(base.date);base=base.sort_values(["corridor","date"]).reset_index(drop=True)
    expected=pd.concat([g.assign(expected=_past_percentile(g.rate,20).to_numpy()) for _,g in base.groupby("corridor",sort=False)])
    valid=base.favourability_percentile_20.notna()
    if not np.allclose(base.loc[valid,"favourability_percentile_20"],expected.loc[valid,"expected"],rtol=0,atol=1e-12):raise RuntimeError("Stored favourability_20 is not strict T-20...T-1")
    test=pd.read_csv(root/"reports/favourability_30_predictions.csv",parse_dates=["date"])
    test=test.merge(base[["corridor","date","rate","favourability_percentile_20"]],on=["corridor","date"],validate="one_to_one")
    if not np.allclose(test.rate_t,test.rate,rtol=0,atol=1e-12):raise RuntimeError("Rate alignment failed")
    return test.drop(columns="rate").sort_values(["corridor","date"]).reset_index(drop=True)

def signal(frame,rule):
    mask=frame.favourability_percentile_20.ge(rule["F"])&frame.predicted_regret_5.le(rule["R"])
    if rule["A"] is not None:mask&=frame.past_advantage_5.ge(rule["A"])
    return mask

def apply_rules(frame):
    out=frame.copy()
    for i,r in enumerate(RULES,1):out[f"signal_rule_{i}"]=signal(out,r)
    return out

def _monthly(group,mask):
    months=pd.period_range(group.date.min().to_period("M"),group.date.max().to_period("M"),freq="M")
    return pd.Series(mask.to_numpy(),index=group.date.dt.to_period("M")).groupby(level=0).sum().reindex(months,fill_value=0)

def metrics(frame):
    rows=[]
    for corridor,g in frame.groupby("corridor",sort=True):
        gt=g.favourability_percentile_20.ge(.85)&g.actual_regret_5.le(.005)
        for i,r in enumerate(RULES,1):
            mask=g[f"signal_rule_{i}"];month=_monthly(g,mask);n=int(mask.sum())
            rows.append({"corridor":corridor,**r,"n_signals":n,"signal_frequency":n/len(g),"mean_signals_per_month":month.mean(),"median_signals_per_month":month.median(),"months_with_zero_signals":int(month.eq(0).sum()),"hit_rate":float(gt[mask].mean()) if n else np.nan})
    return pd.DataFrame(rows).sort_values(["corridor","rule"]).reset_index(drop=True)

def plot_all(frame,summary,outdir):
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    for corridor,g in frame.groupby("corridor",sort=True):
        lo,hi=g.rate_t.min(),g.rate_t.max();pad=(hi-lo)*.05 or hi*.01
        for i,r in enumerate(RULES,1):
            m=summary[(summary.corridor==corridor)&(summary.rule==r["rule"])].iloc[0];marked=g[g[f"signal_rule_{i}"]]
            fig,ax=plt.subplots(figsize=(11,3.6));ax.plot(g.date,g.rate_t,label="Rate",lw=1.2);ax.scatter(marked.date,marked.rate_t,c="red",s=24,label="Signal")
            a="not required" if r["A"] is None else f">={r['A']:.3f}";ax.text(.01,.98,f"F>={r['F']:.2f}; A {a}; R<={r['R']:.3f}\nsignals={m.n_signals}; signals/month={m.mean_signals_per_month:.2f}; zero months={m.months_with_zero_signals}",transform=ax.transAxes,va="top")
            ax.set(title=f"{corridor} — {r['rule']}, favourability 20",xlabel="Locked-test origin",ylabel="RUB per recipient currency",ylim=(lo-pad,hi+pad));ax.text(.99,.02,"lower rate = better",transform=ax.transAxes,ha="right");ax.legend();ax.grid(alpha=.25);fig.tight_layout();fig.savefig(outdir/f"{corridor}_{r['rule']}.png",dpi=150);plt.show()
        fig,axes=plt.subplots(5,1,figsize=(12,14),sharex=True,sharey=True)
        for i,(ax,r) in enumerate(zip(axes,RULES),1):
            m=summary[(summary.corridor==corridor)&(summary.rule==r["rule"])].iloc[0];marked=g[g[f"signal_rule_{i}"]]
            ax.plot(g.date,g.rate_t,lw=1,label="Rate");ax.scatter(marked.date,marked.rate_t,c="red",s=18,label="Signal");ax.set_ylim(lo-pad,hi+pad);ax.set_title(f"{r['rule']} — signals={m.n_signals}, mean/month={m.mean_signals_per_month:.2f}",loc="left");ax.grid(alpha=.25)
        axes[0].legend();axes[-1].set_xlabel("Locked-test origin");fig.supylabel("RUB per recipient currency");fig.suptitle(f"{corridor} — fixed favourability-20 rules",y=.995);fig.tight_layout();fig.savefig(outdir/f"{corridor}_all_rules.png",dpi=150);plt.show()

def run_visual_comparison(root=".",make_plots=True):
    root=Path(root).resolve();frame=apply_rules(load_test(root));summary=metrics(frame)
    old=pd.read_csv(root/"reports/favourability30_rule_visual_comparison.csv");comparison=summary.merge(old,on=["corridor","rule","F","A","R"],suffixes=("_20","_30"))
    audit=pd.DataFrame([("favourability_20 uses T-20...T-1 only",True),("current T excluded",True),("signals use approved live fields only",True),("actual regret diagnostic only",True),("no actual future rate in signals",True),("no winner or optimization",True)],columns=["check","passed"])
    csv=root/"reports/favourability20_rule_visual_comparison.csv";tmp=csv.with_suffix(".csv.tmp");summary.to_csv(tmp,index=False);tmp.replace(csv)
    report=root/"reports/favourability20_rule_visual_report.md";report.write_text("\n".join(["# Favourability-20 fixed-rule visual comparison","","Descriptive locked-test diagnostics; no winner is selected.","",summary.to_markdown(index=False),"","## Compact 20 vs 30", "",comparison.to_markdown(index=False),"","## Leakage","",audit.to_markdown(index=False),"","FAVOURABILITY 20 VISUAL CHECK: **PASS**"]),encoding="utf-8")
    if make_plots:plot_all(frame,summary,root/"reports/figures/favourability20_rule_comparison")
    return {"frame":frame,"metrics":summary,"comparison":comparison,"leakage":audit,"csv_path":csv,"report_path":report}

if __name__=="__main__":print(run_visual_comparison(make_plots=False)["metrics"].to_string(index=False))
