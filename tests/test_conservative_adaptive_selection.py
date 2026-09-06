import numpy as np
import pandas as pd

from src.conservative_adaptive_selection import _run_online_policy, apply_policies, invariant_checks


def _frame(n=40):
    return pd.DataFrame({"corridor":["X"]*n, "date":pd.date_range("2020-01-01", periods=n), "rate_t":np.ones(n),
        "favourability_percentile_20":np.ones(n), "predicted_regret_5":np.zeros(n), "actual_regret_5":np.zeros(n),
        "regret_quality":np.ones(n), "good_day_score":np.linspace(0,1,n), "actual_good_day":np.ones(n,dtype=bool),
        "rate_relative_to_prior_20_range":np.zeros(n)})


def test_threshold_excludes_current_observation():
    frame=_frame(21); frame.good_day_score=np.r_[np.arange(20),100]
    out=_run_online_policy(frame,.70,.010)
    assert out.loc[20,"adaptive_score_threshold"] == np.quantile(np.arange(20),.60)


def test_absolute_eligibility_cannot_be_relaxed_by_policy_c():
    frame=_frame(); frame.favourability_percentile_20=.69
    out=apply_policies(frame)
    assert not out.signal_c_more_frequent.any()


def test_cooldown_blocks_three_following_observations():
    out=_run_online_policy(_frame(),.70,.010); positions=np.flatnonzero(out.signal)
    assert len(positions)>1 and (np.diff(positions)>=4).all()


def test_invariants_pass_for_generated_signals():
    out=apply_policies(_frame())
    assert invariant_checks(out).passed.all()
