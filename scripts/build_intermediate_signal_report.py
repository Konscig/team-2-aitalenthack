"""Build reproducible metrics and chart excerpts for intermediate FX signals."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/labels/golden_labels.parquet"
OUTPUT = ROOT / "docs/product_signal_examples"

SIGNALS = {
    "M01": {
        "name": "Заметное изменение за пять обновлений",
        "column": "m01_event",
        "magnitude_column": "ret_5",
        "direction_column": "ret_5",
    },
    "M02": {
        "name": "Заметное изменение после спокойного периода",
        "column": "m02_event",
        "magnitude_column": "ret_1",
        "direction_column": "ret_1",
    },
    "M03": {
        "name": "Возвращение к уровню пяти обновлений назад",
        "column": "m03_event",
        "magnitude_column": "ret_5",
        "direction_column": "ret_1",
    },
    "M04": {
        "name": "Пять обновлений в узком диапазоне",
        "column": "m04_event",
        "magnitude_column": "range_5",
        "direction_column": "ret_5",
    },
}

EXAMPLES = {
    "M01": ("TJS_RUB", "2026-04-07"),
    "M02": ("KGS_RUB", "2025-11-24"),
    "M03": ("TJS_RUB", "2026-04-23"),
    "M04": ("KGS_RUB", "2025-08-29"),
}


def _matched_baseline_good_rate(frame: pd.DataFrame, events: pd.DataFrame) -> float:
    """Event-weighted random baseline from the same corridor and calendar year."""
    if events.empty:
        return np.nan
    base = (
        frame.assign(calendar_year=frame.date.dt.year)
        .groupby(["corridor", "calendar_year"], sort=False)
        .good.mean()
    )
    keys = pd.MultiIndex.from_arrays([events.corridor, events.date.dt.year])
    return float(base.reindex(keys).mean())


def _wilson_interval(successes: int, observations: int, z: float = 1.96) -> tuple[float, float]:
    if observations == 0:
        return np.nan, np.nan
    proportion = successes / observations
    denominator = 1 + z**2 / observations
    center = (proportion + z**2 / (2 * observations)) / denominator
    margin = z * np.sqrt(
        proportion * (1 - proportion) / observations + z**2 / (4 * observations**2)
    ) / denominator
    return center - margin, center + margin


def _add_event_gap(frame: pd.DataFrame, mask: pd.Series) -> pd.Series:
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    for _, group in frame.loc[mask].groupby("corridor", sort=False):
        result.loc[group.index] = group.date.diff().dt.days
    return result


def build_signal_frame() -> pd.DataFrame:
    frame = pd.read_parquet(INPUT).sort_values(["corridor", "date"]).reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame.date)
    frame["target_source_quote_date"] = pd.to_datetime(frame.target_source_quote_date)

    # A Saturday quote first becomes a usable weekday observation on Monday.
    # Comparing source dates catches that update without treating every
    # forward-filled weekday as a new market observation.
    frame["effective_update"] = frame.groupby("corridor").target_source_quote_date.transform(
        lambda values: values.ne(values.shift())
    )
    frame = frame.loc[frame.effective_update].copy().reset_index(drop=True)
    grouped = frame.groupby("corridor", group_keys=False)

    frame["abs_ret5_q80_prev60"] = grouped.ret_5.transform(
        lambda values: values.abs().shift(1).rolling(60, min_periods=30).quantile(0.80)
    )
    frame["notable_5_state"] = frame.ret_5.abs().ge(frame.abs_ret5_q80_prev60) & frame.ret_5.abs().ge(0.01)
    frame["m01_event"] = frame.notable_5_state & ~grouped.notable_5_state.shift(fill_value=False)

    rolling_min_5 = grouped.rate.transform(lambda values: values.rolling(5, min_periods=5).min())
    rolling_max_5 = grouped.rate.transform(lambda values: values.rolling(5, min_periods=5).max())
    rolling_mean_5 = grouped.rate.transform(lambda values: values.rolling(5, min_periods=5).mean())
    frame["range_5"] = (rolling_max_5 - rolling_min_5) / rolling_mean_5

    frame["abs_ret1_q80_prev60"] = grouped.ret_1.transform(
        lambda values: values.abs().shift(1).rolling(60, min_periods=30).quantile(0.80)
    )
    frame["m02_event"] = (
        frame.ret_1.abs().ge(frame.abs_ret1_q80_prev60)
        & frame.ret_1.abs().ge(0.005)
        & grouped.range_5.shift(1).le(0.005)
    )

    frame["rate_lag_5"] = grouped.rate.shift(5)
    rolling_min_6 = grouped.rate.transform(lambda values: values.rolling(6, min_periods=6).min())
    rolling_max_6 = grouped.rate.transform(lambda values: values.rolling(6, min_periods=6).max())
    rolling_mean_6 = grouped.rate.transform(lambda values: values.rolling(6, min_periods=6).mean())
    frame["range_6"] = (rolling_max_6 - rolling_min_6) / rolling_mean_6
    frame["return_to_level_state"] = (
        (frame.rate / frame.rate_lag_5 - 1).abs().le(0.0025) & frame.range_6.ge(0.01)
    )
    frame["m03_event"] = frame.return_to_level_state & ~grouped.return_to_level_state.shift(fill_value=False)

    frame["stable_5_state"] = frame.range_5.le(0.005)
    frame["m04_event"] = frame.stable_5_state & ~grouped.stable_5_state.shift(fill_value=False)
    return frame


def build_metrics(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    span_years = (frame.date.max() - frame.date.min()).days / 365.25
    metric_rows = []
    corridor_rows = []
    event_parts = []

    for signal_id, config in SIGNALS.items():
        mask = frame[config["column"]].fillna(False)
        events = frame.loc[mask].copy()
        events["signal_id"] = signal_id
        events["signal_name"] = config["name"]
        events["event_gap_days"] = _add_event_gap(frame, mask).loc[events.index]
        magnitude = events[config["magnitude_column"]]
        direction = events[config["direction_column"]]
        favorable_events = events.loc[direction.lt(0)]
        matched_base = _matched_baseline_good_rate(frame, events)
        favorable_matched_base = _matched_baseline_good_rate(frame, favorable_events)
        good_ci_low, good_ci_high = _wilson_interval(int(events.good.sum()), len(events))
        events["signal_magnitude_bps"] = magnitude.abs() * 10_000
        event_parts.append(events)

        corridor_counts = events.groupby("corridor").size().reindex(sorted(frame.corridor.unique()), fill_value=0)
        yearly_counts = events.assign(year=events.date.dt.year).groupby(["corridor", "year"]).size()
        gaps = events.event_gap_days.dropna()
        metric_rows.append(
            {
                "signal_id": signal_id,
                "signal_name": config["name"],
                "events": len(events),
                "events_per_corridor_year": len(events) / (span_years * frame.corridor.nunique()),
                "events_per_corridor_week": len(events) / (span_years * 52 * frame.corridor.nunique()),
                "median_gap_days": gaps.median(),
                "p25_gap_days": gaps.quantile(0.25),
                "p75_gap_days": gaps.quantile(0.75),
                "share_gap_le_7d": gaps.le(7).mean(),
                "min_events_per_corridor": int(corridor_counts.min()),
                "max_events_per_corridor": int(corridor_counts.max()),
                "favorable_direction_share": direction.lt(0).mean(),
                "median_signal_magnitude_bps": magnitude.abs().median() * 10_000,
                "p25_signal_magnitude_bps": magnitude.abs().quantile(0.25) * 10_000,
                "p75_signal_magnitude_bps": magnitude.abs().quantile(0.75) * 10_000,
                "median_events_per_corridor_year_cell": yearly_counts.median(),
                "min_events_per_corridor_year_cell": int(yearly_counts.min()),
                "max_events_per_corridor_year_cell": int(yearly_counts.max()),
                "yearly_count_cv": yearly_counts.std() / yearly_counts.mean(),
                "good_rate": events.good.mean(),
                "good_rate_ci95_low": good_ci_low,
                "good_rate_ci95_high": good_ci_high,
                "matched_baseline_good_rate": matched_base,
                "lift_vs_matched_random_day": events.good.mean() / matched_base,
                "favorable_events": len(favorable_events),
                "favorable_good_rate": favorable_events.good.mean(),
                "favorable_matched_baseline_good_rate": favorable_matched_base,
                "favorable_lift_vs_matched_random_day": favorable_events.good.mean()
                / favorable_matched_base,
                "median_future_regret_bps": events.future_regret_bps.median(),
                "median_centered_benefit_bps": events.centered_benefit_bps.median(),
            }
        )

        for corridor, corridor_frame in frame.groupby("corridor", sort=True):
            subset = corridor_frame.loc[corridor_frame[config["column"]].fillna(False)]
            subset_direction = subset[config["direction_column"]]
            favorable_subset = subset.loc[subset_direction.lt(0)]
            corridor_span_years = (corridor_frame.date.max() - corridor_frame.date.min()).days / 365.25
            corridor_matched_base = _matched_baseline_good_rate(corridor_frame, subset)
            corridor_good_ci_low, corridor_good_ci_high = _wilson_interval(
                int(subset.good.sum()), len(subset)
            )
            corridor_rows.append(
                {
                    "signal_id": signal_id,
                    "corridor": corridor,
                    "events": len(subset),
                    "events_per_year": len(subset) / corridor_span_years,
                    "good_rate": subset.good.mean(),
                    "good_rate_ci95_low": corridor_good_ci_low,
                    "good_rate_ci95_high": corridor_good_ci_high,
                    "matched_baseline_good_rate": corridor_matched_base,
                    "lift_vs_matched_random_day": subset.good.mean() / corridor_matched_base,
                    "favorable_events": len(favorable_subset),
                    "favorable_good_rate": favorable_subset.good.mean(),
                    "favorable_lift_vs_matched_random_day": favorable_subset.good.mean()
                    / _matched_baseline_good_rate(corridor_frame, favorable_subset),
                    "median_future_regret_bps": subset.future_regret_bps.median(),
                    "median_centered_benefit_bps": subset.centered_benefit_bps.median(),
                }
            )

    metrics = pd.DataFrame(metric_rows)
    by_corridor = pd.DataFrame(corridor_rows)
    events = pd.concat(event_parts, ignore_index=True).sort_values(["date", "corridor", "signal_id"])
    return metrics, by_corridor, events


def build_portfolio_diagnostics(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Describe overlap and cadence; this is not an engagement backtest."""
    signal_ids = list(SIGNALS)
    overlap_rows = []
    for left_pos, left_id in enumerate(signal_ids):
        left_col = SIGNALS[left_id]["column"]
        for right_id in signal_ids[left_pos:]:
            right_col = SIGNALS[right_id]["column"]
            overlap_rows.append(
                {
                    "left_signal_id": left_id,
                    "right_signal_id": right_id,
                    "same_corridor_date_events": int((frame[left_col] & frame[right_col]).sum()),
                }
            )

    priority = ["M02", "M01", "M03", "M04"]
    candidates = frame.copy()
    candidates["selected_signal_id"] = ""
    for signal_id in reversed(priority):
        candidates.loc[candidates[SIGNALS[signal_id]["column"]], "selected_signal_id"] = signal_id
    candidates = candidates.loc[candidates.selected_signal_id.ne("")].sort_values(["corridor", "date"])

    selected_indices = []
    for _, corridor_events in candidates.groupby("corridor", sort=False):
        last_sent = None
        for index, event in corridor_events.iterrows():
            if last_sent is None or (event.date - last_sent).days >= 4:
                selected_indices.append(index)
                last_sent = event.date
    selected = candidates.loc[selected_indices].copy()

    span_years = (frame.date.max() - frame.date.min()).days / 365.25
    gap_days = selected.groupby("corridor").date.diff().dt.days.dropna()
    selected["calendar_week"] = selected.date.dt.to_period("W-SUN")
    all_weeks = pd.period_range(
        frame.date.min().to_period("W-SUN"), frame.date.max().to_period("W-SUN"), freq="W-SUN"
    )
    corridor_week_index = pd.MultiIndex.from_product(
        [sorted(frame.corridor.unique()), all_weeks], names=["corridor", "calendar_week"]
    )
    sends_per_corridor_week = (
        selected.groupby(["corridor", "calendar_week"]).size().reindex(corridor_week_index, fill_value=0)
    )
    policy_rows = [
        {"metric": "raw_signal_rows", "value": int(sum(frame[c["column"]].sum() for c in SIGNALS.values()))},
        {"metric": "unique_corridor_dates_with_any_signal", "value": int(frame[[c["column"] for c in SIGNALS.values()]].any(axis=1).sum())},
        {"metric": "corridor_dates_with_multiple_signals", "value": int((frame[[c["column"] for c in SIGNALS.values()]].sum(axis=1) > 1).sum())},
        {"metric": "sent_after_priority_and_4d_cooldown", "value": len(selected)},
        {"metric": "sent_per_corridor_week", "value": len(selected) / (span_years * frame.corridor.nunique() * 52)},
        {"metric": "median_gap_days_after_policy", "value": gap_days.median()},
        {"metric": "p25_gap_days_after_policy", "value": gap_days.quantile(0.25)},
        {"metric": "p75_gap_days_after_policy", "value": gap_days.quantile(0.75)},
        {"metric": "share_corridor_weeks_with_0_sends", "value": sends_per_corridor_week.eq(0).mean()},
        {"metric": "share_corridor_weeks_with_1_send", "value": sends_per_corridor_week.eq(1).mean()},
        {"metric": "share_corridor_weeks_with_2_sends", "value": sends_per_corridor_week.eq(2).mean()},
        {"metric": "share_corridor_weeks_with_more_than_2_sends", "value": sends_per_corridor_week.gt(2).mean()},
        {"metric": "max_sends_in_corridor_calendar_week", "value": int(sends_per_corridor_week.max())},
        {"metric": "offline_good_rate_after_policy", "value": selected.good.mean()},
        {"metric": "median_future_regret_bps_after_policy", "value": selected.future_regret_bps.median()},
    ]
    for signal_id in priority:
        policy_rows.append(
            {
                "metric": f"sent_{signal_id.lower()}_after_policy",
                "value": int(selected.selected_signal_id.eq(signal_id).sum()),
            }
        )
    return pd.DataFrame(overlap_rows), pd.DataFrame(policy_rows)


def build_case_signal_candidate(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate a transparent favorable-moment candidate for the core case.

    The rule uses only information available on T. Future-looking columns are
    exported exclusively as retrospective quality labels.
    """
    candidate = frame.copy()
    candidate["p0_state"] = candidate.dist_min_10.le(0.01) & candidate.favourability_percentile_20.ge(0.80)
    candidate["p0_raw_event"] = candidate.p0_state & ~candidate.groupby("corridor").p0_state.shift(
        fill_value=False
    )

    selected_indices = []
    for _, corridor_events in candidate.loc[candidate.p0_raw_event].groupby("corridor", sort=False):
        last_sent = None
        for index, event in corridor_events.sort_values("date").iterrows():
            if last_sent is None or (event.date - last_sent).days >= 4:
                selected_indices.append(index)
                last_sent = event.date
    events = candidate.loc[selected_indices].copy().sort_values(["date", "corridor"])

    rng = np.random.default_rng(42)

    def metric_row(scope: str, subset: pd.DataFrame, baseline: pd.DataFrame) -> dict[str, float | str]:
        benefits = subset.centered_benefit_bps.dropna().to_numpy()
        if len(benefits):
            boot_means = np.array(
                [rng.choice(benefits, size=len(benefits), replace=True).mean() for _ in range(5_000)]
            )
            ci_low, ci_high = np.quantile(boot_means, [0.025, 0.975])
        else:
            ci_low, ci_high = np.nan, np.nan
        span_years = max((baseline.date.max() - baseline.date.min()).days / 365.25, 1 / 365.25)
        base_rate = _matched_baseline_good_rate(baseline, subset)
        good_ci_low, good_ci_high = _wilson_interval(int(subset.good.sum()), len(subset))
        return {
            "scope": scope,
            "events": len(subset),
            "events_per_corridor_week": len(subset)
            / (span_years * max(baseline.corridor.nunique(), 1) * 52),
            "good_rate": subset.good.mean(),
            "good_rate_ci95_low": good_ci_low,
            "good_rate_ci95_high": good_ci_high,
            "matched_baseline_good_rate": base_rate,
            "lift_vs_matched_random_effective_update": subset.good.mean() / base_rate,
            "mean_centered_benefit_bps": subset.centered_benefit_bps.mean(),
            "mean_centered_benefit_bps_ci95_low": ci_low,
            "mean_centered_benefit_bps_ci95_high": ci_high,
            "median_future_regret_bps": subset.future_regret_bps.median(),
        }

    metric_rows = [metric_row("all", events, candidate)]
    for corridor, baseline in candidate.groupby("corridor", sort=True):
        metric_rows.append(metric_row(corridor, events.loc[events.corridor.eq(corridor)], baseline))

    periods = {
        "train_through_2023-12-20": (None, pd.Timestamp("2023-12-20")),
        "validation_2024-01-11_2024-12-20": (pd.Timestamp("2024-01-11"), pd.Timestamp("2024-12-20")),
        "test_from_2025-01-11": (pd.Timestamp("2025-01-11"), None),
    }
    for name, (start, stop) in periods.items():
        mask = pd.Series(True, index=candidate.index)
        if start is not None:
            mask &= candidate.date.ge(start)
        if stop is not None:
            mask &= candidate.date.le(stop)
        baseline = candidate.loc[mask]
        subset = events.loc[events.index.intersection(baseline.index)]
        metric_rows.append(metric_row(name, subset, baseline))

    event_columns = [
        "date",
        "corridor",
        "target_source_quote_date",
        "rate",
        "dist_min_10",
        "favourability_percentile_20",
        "ret_5",
        "good",
        "future_regret_bps",
        "centered_benefit_bps",
    ]
    return pd.DataFrame(metric_rows), events[event_columns]


def plot_case_signal_candidate(frame: pd.DataFrame, corridor: str = "TJS_RUB", event_date: str = "2026-04-21") -> None:
    group = frame.loc[frame.corridor.eq(corridor)].reset_index(drop=True)
    event_ts = pd.Timestamp(event_date)
    matches = group.index[group.date.eq(event_ts)]
    if len(matches) != 1:
        raise ValueError(f"Expected one P0 example row for {corridor} {event_date}")
    position = int(matches[0])
    event = group.loc[position]
    if not (event.dist_min_10 <= 0.01 and event.favourability_percentile_20 >= 0.80):
        raise ValueError("P0 example does not satisfy the causal rule")

    window = group.iloc[max(0, position - 16) : position + 1].copy()
    last_ten = group.iloc[max(0, position - 9) : position + 1]
    recent_min = last_ten.rate.min()

    fig, ax = plt.subplots(figsize=(11.5, 4.3), dpi=150)
    ax.plot(window.date, window.rate, color="#34495e", linewidth=1.9, marker="o", markersize=4)
    ax.axvspan(last_ten.date.min(), event.date, color="#2ca02c", alpha=0.10)
    ax.hlines(recent_min, last_ten.date.min(), event.date, color="#2ca02c", linestyles="--", linewidth=1.3)
    ax.scatter([event.date], [event.rate], s=90, color="#d62728", edgecolor="white", linewidth=1.2, zorder=5)
    ax.grid(axis="y", alpha=0.22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylabel(f"RUB за 1 {corridor.split('_')[0]}")
    ax.set_xlabel("Дата действующей официальной котировки")
    ax.annotate(
        f"Выше минимума 10 обновлений: {event.dist_min_10 * 100:.2f}%\n"
        f"Благоприятнее {event.favourability_percentile_20 * 100:.0f}% последних 20 обновлений",
        xy=(event.date, event.rate),
        xytext=(-310, 45),
        textcoords="offset points",
        fontsize=9.5,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "edgecolor": "#b8b8b8"},
        arrowprops={"arrowstyle": "->", "color": "#777777"},
    )
    ax.set_title(
        f"P0 · Кандидат основного сигнала · {corridor} · {event.date:%d.%m.%Y}",
        loc="left",
        fontsize=12,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.01,
        "На дату сигнала используются только уже опубликованные котировки; будущие точки на графике не показаны.",
        fontsize=8.5,
        color="#555555",
    )
    fig.autofmt_xdate(rotation=25, ha="right")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUTPUT / "p0_case_signal_example.png", bbox_inches="tight")
    plt.close(fig)


def _plot_window(frame: pd.DataFrame, signal_id: str, corridor: str, event_date: str) -> None:
    group = frame.loc[frame.corridor.eq(corridor)].reset_index(drop=True)
    event_ts = pd.Timestamp(event_date)
    matches = group.index[group.date.eq(event_ts)]
    if len(matches) != 1:
        raise ValueError(f"Expected one row for {signal_id} {corridor} {event_date}")
    position = int(matches[0])
    config = SIGNALS[signal_id]
    if not bool(group.loc[position, config["column"]]):
        raise ValueError(f"Example does not satisfy {signal_id}: {corridor} {event_date}")

    start = max(0, position - 10)
    stop = min(len(group), position + 7)
    window = group.iloc[start:stop].copy()
    event = group.loc[position]

    fig, ax = plt.subplots(figsize=(11.5, 4.3), dpi=150)
    ax.plot(window.date, window.rate, color="#34495e", linewidth=1.8, marker="o", markersize=3.8)
    ax.scatter([event.date], [event.rate], s=85, color="#d62728", edgecolor="white", linewidth=1.2, zorder=5)
    ax.axvline(event.date, color="#d62728", linewidth=1.0, alpha=0.35)
    ax.grid(axis="y", alpha=0.22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylabel(f"RUB за 1 {corridor.split('_')[0]}")
    ax.set_xlabel("Дата действующей официальной котировки")

    if signal_id == "M01":
        reference = group.loc[position - 5]
        ax.axvspan(reference.date, event.date, color="#1f77b4", alpha=0.08)
        annotation = (
            f"За 5 обновлений: {event.ret_5 * 100:+.2f}%\n"
            f"Порог необычности: {event.abs_ret5_q80_prev60 * 100:.2f}%"
        )
    elif signal_id == "M02":
        calm_start = group.loc[position - 5]
        calm_end = group.loc[position - 1]
        ax.axvspan(calm_start.date, calm_end.date, color="#2ca02c", alpha=0.10)
        annotation = (
            f"Предыдущий диапазон: {group.loc[position - 1, 'range_5'] * 100:.2f}%\n"
            f"Новое изменение: {event.ret_1 * 100:+.2f}%"
        )
    elif signal_id == "M03":
        reference = group.loc[position - 5]
        ax.scatter([reference.date], [reference.rate], s=65, color="#1f77b4", edgecolor="white", linewidth=1.0, zorder=4)
        ax.hlines(reference.rate, reference.date, event.date, color="#1f77b4", linestyles="--", linewidth=1.2)
        annotation = (
            f"Разница с уровнем 5 обновлений назад: {(event.rate / reference.rate - 1) * 100:+.2f}%\n"
            f"Промежуточный диапазон: {event.range_6 * 100:.2f}%"
        )
    elif signal_id == "M04":
        stable_start = group.loc[position - 4]
        ax.axvspan(stable_start.date, event.date, color="#2ca02c", alpha=0.10)
        annotation = f"Диапазон пяти обновлений: {event.range_5 * 100:.2f}%"
    else:
        raise ValueError(signal_id)

    ax.annotate(
        annotation,
        xy=(event.date, event.rate),
        xytext=(14, 25),
        textcoords="offset points",
        fontsize=9.5,
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "white", "edgecolor": "#b8b8b8"},
        arrowprops={"arrowstyle": "->", "color": "#777777"},
    )
    title = f"{signal_id} · {config['name']} · {corridor} · {event.date:%d.%m.%Y}"
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold")
    fig.text(
        0.01,
        0.01,
        "Красная точка — дата промежуточного события. Событие не означает «выгодно сейчас».",
        fontsize=8.5,
        color="#555555",
    )
    fig.autofmt_xdate(rotation=25, ha="right")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUTPUT / f"{signal_id.lower()}_example.png", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame = build_signal_frame()
    metrics, by_corridor, events = build_metrics(frame)
    overlap, policy_metrics = build_portfolio_diagnostics(frame)
    case_metrics, case_events = build_case_signal_candidate(frame)
    metrics.to_csv(OUTPUT / "intermediate_signal_metrics.csv", index=False)
    by_corridor.to_csv(OUTPUT / "intermediate_signal_metrics_by_corridor.csv", index=False)
    overlap.to_csv(OUTPUT / "intermediate_signal_overlap.csv", index=False)
    policy_metrics.to_csv(OUTPUT / "intermediate_signal_policy_metrics.csv", index=False)
    case_metrics.to_csv(OUTPUT / "case_signal_candidate_metrics.csv", index=False)
    case_events.to_csv(OUTPUT / "case_signal_candidate_events.csv", index=False)
    event_columns = [
        "date",
        "corridor",
        "target_source_quote_date",
        "signal_id",
        "signal_name",
        "rate",
        "ret_1",
        "ret_5",
        "abs_ret1_q80_prev60",
        "abs_ret5_q80_prev60",
        "rate_lag_5",
        "range_5",
        "range_6",
        "event_gap_days",
        "good",
        "future_regret_bps",
        "centered_benefit_bps",
        "signal_magnitude_bps",
    ]
    events[event_columns].to_csv(OUTPUT / "intermediate_signal_events.csv", index=False)
    for signal_id, (corridor, event_date) in EXAMPLES.items():
        _plot_window(frame, signal_id, corridor, event_date)
    plot_case_signal_candidate(frame)


if __name__ == "__main__":
    main()
