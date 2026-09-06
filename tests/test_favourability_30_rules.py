import numpy as np
import pandas as pd

from src.favourability_30_rules import ground_truth, rule_grid, signal
from src.good_day_features import _past_percentile


def test_favourability_30_strictly_excludes_current_observation():
    rates = pd.Series([10.0] * 30 + [1.0, 20.0])
    values = _past_percentile(rates, 30)
    assert np.isnan(values.iloc[29])
    assert values.iloc[30] == 1.0
    assert values.iloc[31] == 0.0


def test_favourability_30_grid_has_exactly_48_rules():
    rules = rule_grid()
    assert len(rules) == 48
    assert rules.rule.nunique() == 48


def test_live_signal_does_not_depend_on_actual_regret():
    frame = pd.DataFrame({
        "favourability_percentile_30": [0.95, 0.5],
        "past_advantage_5": [0.01, -0.01],
        "predicted_regret_5": [0.001, 0.02],
        "actual_regret_5": [1.0, 0.0],
    })
    rule = rule_grid().iloc[0]
    before = signal(frame, rule)
    frame.actual_regret_5 = [0.0, 1.0]
    assert before.equals(signal(frame, rule))
    assert ground_truth(frame).tolist() == [True, False]
