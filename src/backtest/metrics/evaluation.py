"""Scenario, portfolio, and random-baseline metric aggregation."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from src.backtest.metrics.classification import classification_metrics
from src.backtest.metrics.random_baseline import random_legal_schedules

SCENARIOS = ("good_now", "window_closing", "positive_market_fact")


def _actual_metrics(
    dates: pd.Series,
    outcomes: pd.DataFrame,
    *,
    average_transfer_rub: float,
) -> pd.DataFrame:
    selected = pd.DataFrame({"date": pd.to_datetime(dates).drop_duplicates()})
    merged = selected.merge(outcomes, on="date", how="left", validate="one_to_many")
    rows = []
    for horizon, group in merged.groupby("h_days", sort=True):
        safety = group.safety_hit.dropna().astype(bool)
        closing = group.closing_confirmation_hit.dropna().astype(bool)
        benefits = group.benefit_bps.dropna()
        rows.append(
            {
                "h_days": int(horizon),
                "signal_count": len(selected),
                "safety_count": len(safety),
                "safety_hits": int(safety.sum()),
                "safety_hit_rate": float(safety.mean()) if len(safety) else np.nan,
                "closing_confirmation_count": len(closing),
                "closing_confirmation_hits": int(closing.sum()),
                "closing_confirmation_hit_rate": float(closing.mean()) if len(closing) else np.nan,
                "benefit_count": len(benefits),
                "benefit_mean_bps": float(benefits.mean()) if len(benefits) else np.nan,
                "benefit_median_bps": float(benefits.median()) if len(benefits) else np.nan,
                "benefit_positive_share": float(benefits.gt(0).mean()) if len(benefits) else np.nan,
                "estimated_mean_value_rub": (
                    float(average_transfer_rub * benefits.mean() / 10_000) if len(benefits) else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def _random_metrics(
    schedules: pd.DataFrame,
    outcomes: pd.DataFrame,
) -> pd.DataFrame:
    merged = schedules.merge(outcomes, on="date", how="left", validate="many_to_many")
    rows = []
    for (replicate, horizon), group in merged.groupby(["replicate", "h_days"], sort=True):
        safety = group.safety_hit.dropna().astype(bool)
        closing = group.closing_confirmation_hit.dropna().astype(bool)
        benefits = group.benefit_bps.dropna()
        rows.append(
            {
                "replicate": int(replicate),
                "h_days": int(horizon),
                "random_safety_hit_rate": float(safety.mean()) if len(safety) else np.nan,
                "random_closing_confirmation_hit_rate": float(closing.mean()) if len(closing) else np.nan,
                "random_benefit_mean_bps": float(benefits.mean()) if len(benefits) else np.nan,
                "random_benefit_positive_share": float(benefits.gt(0).mean()) if len(benefits) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def evaluate_schedule(
    pushes: pd.DataFrame,
    outcomes: pd.DataFrame,
    eligible_dates: Sequence[pd.Timestamp],
    *,
    replicates: int = 1_000,
    cooldown_days: int = 4,
    weekly_cap: int = 2,
    seed: int = 42,
    average_transfer_rub: float = 22_000,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate each scenario and the final portfolio against random schedules."""
    required = {"date", "push_scenario"}
    missing = required - set(pushes.columns)
    if missing:
        raise ValueError(f"Push table is missing columns: {sorted(missing)}")
    if pushes.empty:
        raise ValueError("Push table is empty")
    if outcomes.corridor.nunique() != 1:
        raise ValueError("Evaluate one corridor at a time")

    metric_parts = []
    random_parts = []
    groups = [(scenario, group.date) for scenario, group in pushes.groupby("push_scenario", sort=False)]
    groups.append(("portfolio", pushes.date))
    for offset, (scenario, dates) in enumerate(groups):
        actual = _actual_metrics(
            dates,
            outcomes,
            average_transfer_rub=average_transfer_rub,
        )
        schedules = random_legal_schedules(
            eligible_dates,
            n_pushes=dates.nunique(),
            replicates=replicates,
            cooldown_days=cooldown_days,
            weekly_cap=weekly_cap,
            seed=seed + offset,
        )
        random = _random_metrics(schedules, outcomes)
        random["scenario"] = scenario
        random_parts.append(random)
        summaries = []
        for horizon, group in random.groupby("h_days", sort=True):
            safety = group.random_safety_hit_rate.dropna()
            closing = group.random_closing_confirmation_hit_rate.dropna()
            benefit = group.random_benefit_mean_bps.dropna()
            positive = group.random_benefit_positive_share.dropna()
            summaries.append(
                {
                    "h_days": int(horizon),
                    "random_safety_hit_rate_mean": safety.mean(),
                    "random_safety_hit_rate_p05": safety.quantile(0.05),
                    "random_safety_hit_rate_p95": safety.quantile(0.95),
                    "random_closing_confirmation_hit_rate_mean": closing.mean(),
                    "random_benefit_mean_bps": benefit.mean(),
                    "random_benefit_mean_bps_p05": benefit.quantile(0.05),
                    "random_benefit_mean_bps_p95": benefit.quantile(0.95),
                    "random_benefit_positive_share": positive.mean(),
                }
            )
        actual = actual.merge(pd.DataFrame(summaries), on="h_days", validate="one_to_one")
        actual["scenario"] = scenario
        actual["safety_lift"] = actual.safety_hit_rate / actual.random_safety_hit_rate_mean
        actual["closing_confirmation_lift"] = (
            actual.closing_confirmation_hit_rate / actual.random_closing_confirmation_hit_rate_mean
        )
        if scenario != "window_closing":
            actual[
                [
                    "closing_confirmation_count",
                    "closing_confirmation_hits",
                    "closing_confirmation_hit_rate",
                    "random_closing_confirmation_hit_rate_mean",
                    "closing_confirmation_lift",
                ]
            ] = np.nan
        actual["incremental_benefit_bps"] = actual.benefit_mean_bps - actual.random_benefit_mean_bps
        safety_p_values = []
        closing_p_values = []
        benefit_p_values = []
        for row in actual.itertuples(index=False):
            same_horizon = random.loc[random.h_days.eq(row.h_days)]
            random_safety = same_horizon.random_safety_hit_rate.dropna()
            random_closing = same_horizon.random_closing_confirmation_hit_rate.dropna()
            random_benefits = same_horizon.random_benefit_mean_bps.dropna()
            safety_p_values.append(
                (1 + random_safety.ge(row.safety_hit_rate).sum()) / (1 + len(random_safety))
                if pd.notna(row.safety_hit_rate)
                else np.nan
            )
            closing_p_values.append(
                (1 + random_closing.ge(row.closing_confirmation_hit_rate).sum()) / (1 + len(random_closing))
                if scenario == "window_closing" and pd.notna(row.closing_confirmation_hit_rate)
                else np.nan
            )
            benefit_p_values.append(
                (1 + random_benefits.ge(row.benefit_mean_bps).sum()) / (1 + len(random_benefits))
                if pd.notna(row.benefit_mean_bps)
                else np.nan
            )
        actual["safety_randomization_p"] = safety_p_values
        actual["closing_confirmation_randomization_p"] = closing_p_values
        actual["benefit_randomization_p"] = benefit_p_values
        metric_parts.append(actual)
    metrics = pd.concat(metric_parts, ignore_index=True)
    columns = ["scenario", *[c for c in metrics if c != "scenario"]]
    return metrics[columns], pd.concat(random_parts, ignore_index=True)


def random_classification_sanity(
    labels: pd.DataFrame,
    *,
    targets: Sequence[str] = ("good", "closing"),
    replicates: int = 1_000,
    seed: int = 42,
) -> pd.DataFrame:
    """Verify that same-count random predictions converge to target prevalence."""
    rng = np.random.default_rng(seed)
    rows = []
    for target in targets:
        if target not in labels:
            raise ValueError(f"Missing classification target: {target}")
        truth = labels[target].astype(bool).to_numpy()
        predicted_positive = int(truth.sum())
        samples = []
        for _ in range(replicates):
            prediction = np.zeros(len(truth), dtype=bool)
            if predicted_positive:
                prediction[rng.choice(len(truth), size=predicted_positive, replace=False)] = True
            samples.append(classification_metrics(truth, prediction)["precision"])
        values = pd.Series(samples, dtype=float)
        rows.append(
            {
                "target": target,
                "rows": len(truth),
                "actual_positive": predicted_positive,
                "prevalence": truth.mean(),
                "random_predicted_positive": predicted_positive,
                "random_precision_mean": values.mean(),
                "random_precision_p05": values.quantile(0.05),
                "random_precision_p95": values.quantile(0.95),
                "replicates": replicates,
            }
        )
    return pd.DataFrame(rows)


def factual_push_breakdown(
    pushes: pd.DataFrame,
    outcomes: pd.DataFrame,
    *,
    fact_columns: Sequence[str] = (
        "fact_decline_3_quotes",
        "fact_weekly_gain_1pct",
        "fact_low_percentile_30d",
    ),
) -> pd.DataFrame:
    """Describe overlapping fact flags among factual pushes."""
    facts = pushes.loc[pushes.push_scenario.eq("positive_market_fact")].copy()
    missing = set(fact_columns) - set(facts.columns)
    if missing:
        raise ValueError(f"Push table is missing fact columns: {sorted(missing)}")
    if facts.empty:
        return pd.DataFrame()
    facts["fact_combination"] = facts[list(fact_columns)].apply(
        lambda row: "+".join(column.removeprefix("fact_") for column in fact_columns if row[column]),
        axis=1,
    )
    rows = []
    groups = [
        ("individual_overlapping", column.removeprefix("fact_"), facts.loc[facts[column].astype(bool)].date)
        for column in fact_columns
    ]
    groups.extend(
        ("exclusive_combination", combination, group.date)
        for combination, group in facts.groupby("fact_combination", sort=True)
    )
    for group_type, name, dates in groups:
        metrics = _actual_metrics(
            dates,
            outcomes,
            average_transfer_rub=22_000,
        )
        metrics.insert(0, "fact", name)
        metrics.insert(0, "group_type", group_type)
        rows.append(metrics)
    return pd.concat(rows, ignore_index=True)


def frequency_tables(
    pushes: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return weekly counts and compact portfolio frequency metrics."""
    first_monday = start - pd.Timedelta(days=start.dayofweek)
    weeks = pd.date_range(first_monday, end, freq="7D")
    dates = pd.to_datetime(pushes.date).sort_values()
    week_starts = dates - pd.to_timedelta(dates.dt.dayofweek, unit="D")
    counts = week_starts.value_counts()
    weekly = pd.DataFrame({"week_start": weeks})
    weekly["push_count"] = weekly.week_start.map(counts).fillna(0).astype(int)
    weekly["full_week"] = (weekly.week_start >= start) & (weekly.week_start + pd.Timedelta(days=6) <= end)
    for scenario in SCENARIOS:
        scenario_dates = pd.to_datetime(pushes.loc[pushes.push_scenario.eq(scenario), "date"])
        scenario_weeks = scenario_dates - pd.to_timedelta(scenario_dates.dt.dayofweek, unit="D")
        weekly[scenario] = weekly.week_start.map(scenario_weeks.value_counts()).fillna(0).astype(int)
    gaps = dates.diff().dt.days.dropna()
    full_weeks = weekly.loc[weekly.full_week]
    summary = pd.DataFrame(
        [
            {
                "pushes": len(pushes),
                "observed_weeks": len(weekly),
                "pushes_per_week": len(pushes) / len(weekly),
                "empty_week_share": weekly.push_count.eq(0).mean(),
                "full_weeks": len(full_weeks),
                "pushes_per_full_week": full_weeks.push_count.mean(),
                "empty_full_week_share": full_weeks.push_count.eq(0).mean(),
                "weeks_with_one_push": int(weekly.push_count.eq(1).sum()),
                "weeks_with_two_pushes": int(weekly.push_count.eq(2).sum()),
                "median_gap_days": gaps.median() if len(gaps) else np.nan,
                "max_gap_days": gaps.max() if len(gaps) else np.nan,
                "share_gaps_within_7_days": gaps.le(7).mean() if len(gaps) else np.nan,
            }
        ]
    )
    return weekly, summary
