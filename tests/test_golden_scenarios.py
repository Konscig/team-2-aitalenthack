import pandas as pd

from src.build_golden_labels import _closing
from src.visualize_golden_labels import select_scenario_pushes


def test_closing_starts_strictly_above_good_tolerance():
    frame = pd.DataFrame(
        {
            "good": [False, False, False, False],
            "rebound_from_past_min_bps": [100.0, 100.1, 200.0, 200.1],
            "future_median_change_bps": [100, 100, 100, 100],
        }
    )

    assert _closing(frame).tolist() == [False, True, True, False]


def test_closing_requires_not_good_and_one_percent_future_median_rise():
    frame = pd.DataFrame(
        {
            "good": [True, False, False],
            "rebound_from_past_min_bps": [150, 150, 150],
            "future_median_change_bps": [100, 99.9, 100],
        }
    )

    assert _closing(frame).tolist() == [False, False, True]


def test_combined_policy_prefers_good_on_same_day_and_applies_cooldown():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-09"]),
            "good": [True, False, False],
            "closing": [1, 1, 1],
        }
    )

    selected, scenario = select_scenario_pushes(frame, cooldown_days=4, weekly_cap=2)

    assert selected.tolist() == [True, False, True]
    assert scenario.iloc[0] == "good_now"
    assert pd.isna(scenario.iloc[1])
    assert scenario.iloc[2] == "window_closing"
