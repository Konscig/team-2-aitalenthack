"""Communication policy shared by visualisation and backtests."""

from __future__ import annotations

import pandas as pd

SCENARIO_PRIORITY = ("good_now", "window_closing", "positive_market_fact")


def select_scenario_pushes(
    frame: pd.DataFrame,
    *,
    cooldown_days: int = 4,
    weekly_cap: int = 2,
) -> tuple[pd.Series, pd.Series]:
    """Select a causal stream with same-day scenario priority.

    The policy cannot reserve capacity for a higher-priority event that has not
    happened yet. Priority therefore resolves only signals available on the
    same date; cooldown and weekly limits are then applied chronologically.
    """
    required = {"date", "good", "closing"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Communication policy is missing columns: {sorted(missing)}")
    if cooldown_days < 1 or weekly_cap < 1:
        raise ValueError("Cooldown and weekly cap must be positive")

    selected = pd.Series(False, index=frame.index, dtype=bool)
    scenario = pd.Series(pd.NA, index=frame.index, dtype="string")
    last_push: pd.Timestamp | None = None
    weekly_counts: dict[tuple[int, int], int] = {}
    for index, row in frame.sort_values("date").iterrows():
        candidate = (
            "good_now"
            if bool(row.good)
            else "window_closing"
            if bool(row.closing)
            else "positive_market_fact"
            if bool(row.get("positive_market_fact", False))
            else None
        )
        if candidate is None:
            continue
        date = pd.Timestamp(row.date)
        iso = date.isocalendar()
        week = (int(iso.year), int(iso.week))
        cooldown_passed = last_push is None or (date - last_push).days >= cooldown_days
        if cooldown_passed and weekly_counts.get(week, 0) < weekly_cap:
            selected.loc[index] = True
            scenario.loc[index] = candidate
            last_push = date
            weekly_counts[week] = weekly_counts.get(week, 0) + 1
    return selected, scenario
