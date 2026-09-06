import numpy as np
import pandas as pd
from src.adaptive_good_day_policy import _rank,apply_policies

def test_rolling_rank_excludes_current_observation():
    x=pd.Series([10.]*20+[1.,20.]);r=_rank(x,20,True)
    assert np.isnan(r.iloc[19]) and r.iloc[20]==0 and r.iloc[21]==1

def test_hard_safety_floor_blocks_all_policies():
    n=25;f=pd.DataFrame({"corridor":["X"]*n,"favourability_percentile_20":[.5]*n,"predicted_regret_5":[.02]*n,"score_trailing_percentile":[1.]*n})
    out=apply_policies(f)
    assert not out[["policy_a_signal","policy_b_signal","policy_c_signal"]].any().any()

def test_policy_c_cooldown_separates_emitted_signals():
    n=30;f=pd.DataFrame({"corridor":["X"]*n,"favourability_percentile_20":[.9]*n,"predicted_regret_5":[0.]*n,"score_trailing_percentile":[1.]*n})
    idx=np.flatnonzero(apply_policies(f).policy_c_signal)
    assert (np.diff(idx)>=4).all()
