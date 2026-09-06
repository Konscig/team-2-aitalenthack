"""Compatibility metrics used by the initial rule-based baselines."""

import numpy as np
import pandas as pd

from src.backtest.metrics.outcomes import HORIZONS


def quality_metrics(rows: pd.DataFrame, feature_column: str = "percentile_90") -> pd.DataFrame:
    result = []
    for corridor, group in rows.groupby("corridor", sort=True):
        for horizon in HORIZONS:
            valid = group[feature_column].notna() & group[f"no_lower_rate_next_{horizon}d"].notna()
            outcomes = group.loc[valid, f"no_lower_rate_next_{horizon}d"]
            signals = group.loc[valid & group.triggered, f"no_lower_rate_next_{horizon}d"]
            benefit = group.loc[group.triggered, f"benefit_bps_{horizon}d"].dropna()
            baseline = float(outcomes.mean()) if len(outcomes) else np.nan
            hit = float(signals.mean()) if len(signals) else np.nan
            result.append(
                {
                    "corridor": corridor,
                    "h_days": horizon,
                    "eligible_count": len(outcomes),
                    "baseline_successes": int(outcomes.sum()),
                    "signal_count": len(signals),
                    "signal_successes": int(signals.sum()),
                    "baseline_hit_rate": baseline,
                    "signal_hit_rate": hit,
                    "lift": hit / baseline if baseline > 0 else np.nan,
                    "benefit_count": len(benefit),
                    "benefit_mean_bps": benefit.mean(),
                }
            )
    return pd.DataFrame(result)


def frequency_metrics(
    rows: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    feature_column: str = "percentile_90",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    weekly, summaries = [], []
    first_monday = start - pd.Timedelta(days=start.dayofweek)
    weeks = pd.date_range(first_monday, end, freq="7D")
    for corridor, group in rows.groupby("corridor", sort=True):
        group = group.sort_values("date")
        dates = group.loc[group.triggered, "date"]
        counts = (dates - pd.to_timedelta(dates.dt.dayofweek, unit="D")).value_counts()
        week = pd.DataFrame({"week_start": weeks})
        week["corridor"] = corridor
        week["signal_count"] = week.week_start.map(counts).fillna(0).astype(int)
        week["full_week"] = (week.week_start >= start) & (week.week_start + pd.Timedelta(days=6) <= end)
        weekly.append(week)
        full = week.loc[week.full_week, "signal_count"]
        flags = group.triggered.astype(bool)
        runs = flags.groupby((~flags).cumsum()).sum()
        gaps = dates.diff().dt.days.dropna()
        summaries.append(
            {
                "corridor": corridor,
                "raw_signals": int(flags.sum()),
                "missing_feature_dates": int(group[feature_column].isna().sum()),
                "full_weeks": len(full),
                "mean_per_full_week": full.mean(),
                "empty_full_week_share": float(full.eq(0).mean()) if len(full) else np.nan,
                "gap_median_days": gaps.median(),
                "gap_max_days": gaps.max(),
                "max_run": int(runs.max()),
                "continuation_share": (
                    float((flags & flags.shift(1, fill_value=False)).sum() / flags.sum()) if flags.sum() else np.nan
                ),
            }
        )
    return pd.concat(weekly, ignore_index=True), pd.DataFrame(summaries)
