import pandas as pd

from src.good_day_thresholds import PRIMARY, rule_grid, signal_mask


def test_grid_has_36_unique_rules_and_all_primary_rules():
    grid = rule_grid()
    assert len(grid) == 36
    assert grid.rule.nunique() == 36
    assert set(PRIMARY.values()).issubset(set(grid.rule))


def test_primary_rule_definitions_are_exact():
    grid = rule_grid().set_index("rule")
    assert grid.loc["RULE_A", "favourability_threshold"] == 0.80
    assert pd.isna(grid.loc["RULE_A", "past_advantage_threshold"])
    assert grid.loc["RULE_A", "predicted_regret_threshold"] == 0.010
    assert grid.loc["RULE_B", "past_advantage_threshold"] == 0.0
    assert grid.loc["RULE_C", "past_advantage_threshold"] == 0.002


def test_signal_generation_does_not_depend_on_actual_regret():
    frame = pd.DataFrame({
        "favourability_percentile_90": [0.95, 0.70],
        "past_advantage_5": [0.01, -0.01],
        "predicted_regret_5": [0.001, 0.020],
        "actual_regret_5": [0.99, 0.0],
    })
    rule = rule_grid().loc[lambda x: x.rule.eq("RULE_C")].iloc[0]
    original = signal_mask(frame, rule)
    frame["actual_regret_5"] = [0.0, 0.99]
    assert original.equals(signal_mask(frame, rule))
