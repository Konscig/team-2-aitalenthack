import pandas as pd

from src.per_corridor_good_day_rules import _ground_truth, _signal, threshold_grid


def test_per_corridor_grid_has_exactly_48_rules():
    grid = threshold_grid()
    assert len(grid) == 48
    assert grid.rule.nunique() == 48
    assert set(grid.F) == {0.75, 0.80, 0.85, 0.90}
    assert set(grid.R) == {0.002, 0.005, 0.010}


def test_gt_b_requires_attractive_now_and_safe_to_act():
    frame = pd.DataFrame({
        "favourability_percentile_90": [0.90, 0.80, 0.90],
        "past_advantage_5": [0.0, 0.0, 0.0],
        "actual_regret_5": [0.004, 0.004, 0.006],
    })
    assert _ground_truth(frame, "GT_B").tolist() == [True, False, False]


def test_live_signal_does_not_use_actual_regret():
    frame = pd.DataFrame({
        "favourability_percentile_90": [0.90, 0.70],
        "past_advantage_5": [0.01, -0.01],
        "predicted_regret_5": [0.001, 0.02],
        "actual_regret_5": [1.0, 0.0],
    })
    rule = threshold_grid().iloc[0]
    before = _signal(frame, rule)
    frame["actual_regret_5"] = [0.0, 1.0]
    assert before.equals(_signal(frame, rule))
