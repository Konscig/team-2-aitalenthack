"""Policy-matched random schedules for fair signal baselines."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def _can_add(
    date: pd.Timestamp,
    selected: list[pd.Timestamp],
    weekly_counts: dict[tuple[int, int], int],
    *,
    cooldown_days: int,
    weekly_cap: int,
) -> bool:
    iso = date.isocalendar()
    week = (int(iso.year), int(iso.week))
    return weekly_counts.get(week, 0) < weekly_cap and all(
        abs((date - previous).days) >= cooldown_days for previous in selected
    )


def random_legal_schedules(
    dates: Sequence[pd.Timestamp],
    *,
    n_pushes: int,
    replicates: int = 1_000,
    cooldown_days: int = 4,
    weekly_cap: int = 2,
    seed: int = 42,
    max_attempts: int = 200,
) -> pd.DataFrame:
    """Sample schedules with exact signal count and communication constraints."""
    available = pd.DatetimeIndex(pd.to_datetime(dates)).sort_values().unique()
    if len(available) == 0 or n_pushes < 0 or n_pushes > len(available):
        raise ValueError("Invalid candidate dates or requested push count")
    if replicates < 1 or cooldown_days < 1 or weekly_cap < 1:
        raise ValueError("Replicates and policy limits must be positive")
    if n_pushes == 0:
        return pd.DataFrame(columns=["replicate", "date"])

    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    for replicate in range(replicates):
        completed: list[pd.Timestamp] | None = None
        for _ in range(max_attempts):
            selected: list[pd.Timestamp] = []
            weekly_counts: dict[tuple[int, int], int] = {}
            for position in rng.permutation(len(available)):
                date = pd.Timestamp(available[position])
                if not _can_add(
                    date,
                    selected,
                    weekly_counts,
                    cooldown_days=cooldown_days,
                    weekly_cap=weekly_cap,
                ):
                    continue
                selected.append(date)
                iso = date.isocalendar()
                week = (int(iso.year), int(iso.week))
                weekly_counts[week] = weekly_counts.get(week, 0) + 1
                if len(selected) == n_pushes:
                    completed = sorted(selected)
                    break
            if completed is not None:
                break
        if completed is None:
            raise ValueError(f"Could not sample {n_pushes} legal pushes; reduce count or relax policy")
        rows.extend({"replicate": replicate, "date": date} for date in completed)
    return pd.DataFrame(rows)
