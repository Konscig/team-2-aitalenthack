import pandas as pd

from src.signal_frequency_calibration import apply_cooldown, grid, monthly_table


def test_compact_frequency_grid_has_exactly_80_rules():
    rules = grid()
    assert len(rules) == 80
    assert rules.rule.nunique() == 80
    assert rules.R.max() <= 0.01


def test_monthly_table_includes_zero_signal_months():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-03", "2024-03-04"]),
        "favourability_percentile_90": [0.9, 0.9],
        "actual_regret_5": [0.001, 0.001],
    })
    monthly = monthly_table(frame, pd.Series([True, True]), "RAW")
    assert monthly.month.tolist() == ["2024-01", "2024-02", "2024-03"]
    assert monthly.n_signals.tolist() == [1, 0, 1]


def test_cooldown_suppresses_next_three_quote_observations():
    raw = pd.Series([True, True, True, True, True, False, True])
    assert apply_cooldown(raw, 3).tolist() == [True, False, False, False, True, False, False]
