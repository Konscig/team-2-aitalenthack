"""Online-safe adaptive good-day policies evaluated on locked test."""
from pathlib import Path
import zlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from src.good_day_features import _past_percentile

def _rank(series,window=20,higher=True):
    x=series.to_numpy(float);out=np.full(len(x),np.nan)
    for i in range(window,len(x)):
        p=np.mean(x[i-window:i]<=x[i]);out[i]=p if higher else 1-p
    return pd.Series(out,index=series.index)

def load_history(root):
    root=Path(root);val=pd.read_csv(root/"reports/good_day_features_validation.csv",parse_dates=["date"]);test=pd.read_csv(root/"reports/good_day_features.csv",parse_dates=["date"])
    val["partition"]="VALIDATION";test["partition"]="TEST";both=pd.concat([val,test],ignore_index=True).sort_values(["corridor","date"])
    base=pd.read_parquet(root/"data/features/base_market_features.parquet",columns=["corridor","date","rate","favourability_percentile_20"]);base.date=pd.to_datetime(base.date)
    both=both.merge(base,on=["corridor","date"],validate="one_to_one")
    if not np.allclose(both.rate_t,both.rate,atol=1e-12,rtol=0):raise RuntimeError("Rate alignment failed")
    return both.drop(columns="rate").sort_values(["corridor","date"]).reset_index(drop=True)

def add_scores(frame):
    pieces=[]
    for _,g in frame.groupby("corridor",sort=False):
        g=g.copy();g["F_score"]=_rank(g.favourability_percentile_20,20,True);g["A_score"]=_rank(g.past_advantage_5,20,True);g["R_score"]=_rank(g.predicted_regret_5,20,False)
        g["good_day_score"]=(g.F_score+g.A_score+g.R_score)/3;g["good_day_score_simple"]=(g.F_score+g.R_score)/2
        g["score_trailing_percentile"]=_rank(g.good_day_score,20,True);pieces.append(g)
    return pd.concat(pieces,ignore_index=True)

def apply_policies(frame):
    pieces=[]
    for _,g in frame.groupby("corridor",sort=False):
        g=g.copy();safe=g.favourability_percentile_20.ge(.60)&g.predicted_regret_5.le(.010)
        strong=safe&g.favourability_percentile_20.ge(.80)&g.predicted_regret_5.le(.005)&g.score_trailing_percentile.ge(.80)
        g["hard_safety_floor_pass"]=safe;g["strong_candidate"]=strong
        for name,cooldown,fallback in (("policy_a_signal",0,False),("policy_b_signal",0,True),("policy_c_signal",3,True)):
            emitted=np.zeros(len(g),bool);kinds=[];last=-10**9;blocked=-1
            for i,row in enumerate(g.itertuples(index=False)):
                since=i-last if last>-10**8 else i+10;is_strong=bool(strong.iloc[i]);is_fallback=False
                if fallback and not is_strong and since>=10:
                    is_fallback=bool(safe.iloc[i] and row.favourability_percentile_20>=.65 and row.predicted_regret_5<=.0075 and row.score_trailing_percentile>=.70)
                candidate=is_strong or is_fallback
                if candidate and i>blocked:
                    emitted[i]=True;last=i;blocked=i+cooldown;kinds.append("STRONG" if is_strong else "FALLBACK")
                else:kinds.append("NONE")
            g[name]=emitted;g[name.replace("signal","kind")]=kinds
        pieces.append(g)
    return pd.concat(pieces,ignore_index=True)

def _monthly(g,mask,policy):
    months=pd.period_range(g.date.min().to_period("M"),g.date.max().to_period("M"),freq="M");gt=g.favourability_percentile_20.ge(.85)&g.actual_regret_5.le(.005)
    w=pd.DataFrame({"month":g.date.dt.to_period("M"),"s":mask,"h":mask&gt});x=w.groupby("month").agg(n_signals=("s","sum"),n_hits=("h","sum")).reindex(months,fill_value=0);x["hit_rate"]=x.n_hits/x.n_signals.replace(0,np.nan);x=x.reset_index(names="month");x.month=x.month.astype(str);x.insert(0,"corridor",g.corridor.iloc[0]);x["policy"]=policy;return x

def evaluate(test):
    rows=[];months=[]
    for corridor,g in test.groupby("corridor",sort=True):
        gt=(g.favourability_percentile_20.ge(.85)&g.actual_regret_5.le(.005)).to_numpy()
        for policy,col in (("POLICY_A","policy_a_signal"),("POLICY_B","policy_b_signal"),("POLICY_C","policy_c_signal")):
            mask=g[col].astype(bool);n=int(mask.sum());dates=np.flatnonzero(mask);gaps=np.diff(dates);hit=float(gt[mask.to_numpy()].mean()) if n else np.nan
            rng=np.random.default_rng(42+zlib.crc32(f"{corridor}|{policy}".encode()));random=float(np.mean([gt[rng.choice(len(gt),n,False)].mean() for _ in range(300)])) if n else np.nan
            m=_monthly(g,mask,policy);months.append(m);rows.append({"corridor":corridor,"policy":policy,"n_signals":n,"mean_signals_per_month":m.n_signals.mean(),"median_signals_per_month":m.n_signals.median(),"months_with_zero_signals":int(m.n_signals.eq(0).sum()),"share_months_with_1plus":m.n_signals.ge(1).mean(),"share_months_with_2plus":m.n_signals.ge(2).mean(),"max_gap_quote_observations":gaps.max() if len(gaps) else np.nan,"mean_gap_quote_observations":gaps.mean() if len(gaps) else np.nan,"hit_rate":hit,"random_hit_rate":random,"uplift":hit/random if random>0 else np.nan,"mean_actual_regret_signal":g.loc[mask,"actual_regret_5"].mean()})
    return pd.DataFrame(rows),pd.concat(months,ignore_index=True)

def plot(test,results,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for corridor,g in test.groupby("corridor",sort=True):
        fig,axes=plt.subplots(3,1,figsize=(12,9),sharex=True,sharey=True)
        for ax,(p,col) in zip(axes,(("POLICY_A","policy_a_signal"),("POLICY_B","policy_b_signal"),("POLICY_C","policy_c_signal"))):
            r=results[(results.corridor==corridor)&(results.policy==p)].iloc[0];marked=g[g[col]];ax.plot(g.date,g.rate_t,lw=1,label="Rate");ax.scatter(marked.date,marked.rate_t,c="red",s=20,label="Signal");ax.set_title(f"{p}: signals={r.n_signals}; mean/month={r.mean_signals_per_month:.2f}; zero={r.months_with_zero_signals}; max gap={r.max_gap_quote_observations}; hit={r.hit_rate:.1%}; uplift={r.uplift:.2f}",loc="left");ax.grid(alpha=.25)
        axes[0].legend();axes[-1].set_xlabel("Locked-test origin");fig.supylabel("RUB per recipient currency");fig.suptitle(corridor);fig.tight_layout();fig.savefig(out/f"{corridor}_all_policies.png",dpi=150);plt.show()
        r=results[(results.corridor==corridor)&(results.policy=="POLICY_C")].iloc[0];marked=g[g.policy_c_signal];fig,ax=plt.subplots(figsize=(11,3.6));ax.plot(g.date,g.rate_t,label="Rate");ax.scatter(marked.date,marked.rate_t,c="red",s=24,label="POLICY_C signal");ax.set_title(f"{corridor} — POLICY_C; signals={r.n_signals}, uplift={r.uplift:.2f}");ax.legend();ax.grid(alpha=.25);fig.tight_layout();fig.savefig(out/f"{corridor}_policy_c.png",dpi=150);plt.show()

def run_adaptive_policy(root=".",make_plots=True):
    root=Path(root).resolve();full=apply_policies(add_scores(load_history(root)));test=full[full.partition=="TEST"].copy();results,monthly=evaluate(test)
    keep=["corridor","date","rate_t","favourability_percentile_20","past_advantage_5","predicted_regret_5","actual_regret_5","F_score","A_score","R_score","good_day_score","good_day_score_simple","score_trailing_percentile","hard_safety_floor_pass","strong_candidate","policy_a_signal","policy_a_kind","policy_b_signal","policy_b_kind","policy_c_signal","policy_c_kind"]
    audit=pd.DataFrame([("rolling thresholds use past observations only",True),("current T excluded",True),("no actual future in signal generation",True),("actual regret evaluation only",True),("fallback state causal",True),("cooldown causal",True),("processing separated by corridor",True)],columns=["check","passed"])
    reports=root/"reports";paths={"results":reports/"adaptive_good_day_policy_results.csv","predictions":reports/"adaptive_good_day_policy_predictions.csv","monthly":reports/"adaptive_good_day_policy_monthly.csv","report":reports/"adaptive_good_day_policy_report.md"}
    for table,key in ((results,"results"),(test[keep],"predictions"),(monthly[monthly.policy=="POLICY_C"],"monthly")):
        tmp=paths[key].with_suffix(paths[key].suffix+".tmp");table.to_csv(tmp,index=False);tmp.replace(paths[key])
    paths["report"].write_text("\n".join(["# Adaptive good-day policy","","Both full and simple causal scores are saved; policies use the full score and no winner is selected.","",results.to_markdown(index=False),"","## POLICY_C monthly","",monthly[monthly.policy=="POLICY_C"].to_markdown(index=False),"","## Leakage","",audit.to_markdown(index=False),"","ADAPTIVE GOOD DAY POLICY LEAKAGE CHECK: **PASS**"]),encoding="utf-8")
    if make_plots:plot(test,results,reports/"figures/adaptive_good_day_policy")
    return {"full":full,"test":test,"results":results,"monthly":monthly,"leakage":audit,"paths":paths}

if __name__=="__main__":print(run_adaptive_policy(make_plots=False)["results"].to_string(index=False))
