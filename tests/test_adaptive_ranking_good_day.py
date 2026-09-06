import numpy as np
import pandas as pd

from src.adaptive_ranking_good_day import _adaptive_policy, apply_adaptive_ranking


def test_adaptive_threshold_uses_prior_scores_only():
    scores = pd.Series(np.arange(30, dtype=float))
    out = _adaptive_policy(scores, pd.Series(np.zeros(30)), cooldown=3)
    assert out.loc[20, "adaptive_threshold"] == np.quantile(np.arange(20), .5)


def test_hard_regret_limit_blocks_signal():
    scores = pd.Series(np.r_[np.arange(20), 100.0])
    out = _adaptive_policy(scores, pd.Series([0.0] * 20 + [0.011]))
    assert not out.loc[20, "signal"]


def test_cooldown_blocks_next_three_quote_observations():
    scores = pd.Series(np.r_[np.arange(20), np.repeat(100.0, 10)])
    out = _adaptive_policy(scores, pd.Series(np.zeros(30)), cooldown=3)
    positions = np.flatnonzero(out.signal)
    assert len(positions) > 1 and (np.diff(positions) >= 4).all()


def test_actual_regret_cannot_change_signals():
    n = 50
    base = pd.DataFrame({
        "corridor": ["X"] * n, "date": pd.date_range("2020-01-01", periods=n),
        "score_full": np.linspace(0, 1, n), "score_simple": np.linspace(0, 1, n),
        "predicted_regret_5": np.zeros(n), "favourability_percentile_20": np.ones(n),
        "actual_regret_5": np.zeros(n),
    })
    first = apply_adaptive_ranking(base)
    base.actual_regret_5 = 1.0
    second = apply_adaptive_ranking(base)
    assert first.signal_full.equals(second.signal_full)
    assert first.signal_simple.equals(second.signal_simple)
