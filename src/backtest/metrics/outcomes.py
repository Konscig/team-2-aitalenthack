"""Retrospective market outcomes for scenario and economic evaluation."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

HORIZONS = (1, 3, 5, 10, 20)
KEYS = ("date", "corridor")


def _candidate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = {"date", "corridor", "rate"} - set(frame.columns)
    if missing:
        raise ValueError(f"Candidate data is missing columns: {sorted(missing)}")
    result = frame[["date", "corridor", "rate"]].copy()
    result["date"] = pd.to_datetime(result.date, errors="raise")
    result["rate"] = pd.to_numeric(result.rate, errors="raise")
    if result.empty or result[[*KEYS, "rate"]].isna().any().any():
        raise ValueError("Candidate data must be non-empty and complete")
    if result.duplicated(list(KEYS)).any():
        raise ValueError("Candidate data has duplicate date/corridor rows")
    if not np.isfinite(result.rate).all() or not result.rate.gt(0).all():
        raise ValueError("Rates must be finite and positive")
    return result.sort_values(list(KEYS)).reset_index(drop=True)


def _calendar_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "corridor" not in result and "currency" in result:
        result["corridor"] = result.currency.astype(str) + "_RUB"
    if "rate" not in result and "unit_rate" in result:
        result = result.rename(columns={"unit_rate": "rate"})
    result = _candidate_frame(result)
    for corridor, group in result.groupby("corridor", sort=False):
        if not group.date.diff().dropna().eq(pd.Timedelta(days=1)).all():
            raise ValueError(f"Calendar dates are incomplete for {corridor}")
    return result


def build_outcomes(
    candidates: pd.DataFrame,
    calendar: pd.DataFrame,
    *,
    horizons: Sequence[int] = HORIZONS,
    good_tolerance_bps: int = 100,
    closing_rise_bps: int = 100,
) -> pd.DataFrame:
    """Build one long-form outcome row per candidate date and horizon.

    Safety and closing confirmation use only T+1..T+h. Economic benefit uses
    the centered calendar window T-h..T+h, including T.
    """
    if not horizons or len(horizons) != len(set(horizons)):
        raise ValueError("Horizons must be non-empty and unique")
    if any(type(horizon) is not int or horizon <= 0 for horizon in horizons):
        raise ValueError("Horizons must be positive integers")
    if good_tolerance_bps < 0 or closing_rise_bps < 0:
        raise ValueError("Outcome thresholds must be non-negative")

    selected = _candidate_frame(candidates)
    daily = _calendar_frame(calendar)
    calendar_groups = {
        corridor: group.set_index("date").rate.astype(float)
        for corridor, group in daily.groupby("corridor", sort=False)
    }
    rows: list[dict[str, object]] = []
    for item in selected.itertuples(index=False):
        if item.corridor not in calendar_groups:
            raise ValueError(f"Calendar is missing corridor {item.corridor}")
        series = calendar_groups[item.corridor]
        if item.date not in series.index or not np.isclose(series.at[item.date], item.rate):
            raise ValueError(f"Candidate rate does not match calendar at {item.corridor} {item.date.date()}")
        for horizon in horizons:
            future = series.reindex(pd.date_range(item.date + pd.Timedelta(days=1), periods=horizon, freq="D"))
            centered = series.reindex(
                pd.date_range(item.date - pd.Timedelta(days=horizon), periods=2 * horizon + 1, freq="D")
            )
            complete = not future.isna().any() and not centered.isna().any()
            if complete:
                future_regret = max(0.0, 10_000 * (item.rate - future.min()) / item.rate)
                future_median_change = 10_000 * (future.median() - item.rate) / item.rate
                centered_mean = centered.mean()
                benefit = 10_000 * (centered_mean - item.rate) / centered_mean
                safety_hit = future_regret <= good_tolerance_bps
                closing_confirmation_hit = future_median_change >= closing_rise_bps
                economic_positive = benefit > 0
            else:
                future_regret = np.nan
                future_median_change = np.nan
                benefit = np.nan
                safety_hit = pd.NA
                closing_confirmation_hit = pd.NA
                economic_positive = pd.NA
            rows.append(
                {
                    "date": item.date,
                    "corridor": item.corridor,
                    "rate": item.rate,
                    "h_days": horizon,
                    "future_regret_bps": future_regret,
                    "future_median_change_bps": future_median_change,
                    "safety_hit": safety_hit,
                    "closing_confirmation_hit": closing_confirmation_hit,
                    "benefit_bps": benefit,
                    "economic_positive": economic_positive,
                }
            )
    result = pd.DataFrame(rows)
    for column in ("safety_hit", "closing_confirmation_hit", "economic_positive"):
        result[column] = result[column].astype("boolean")
    return result
