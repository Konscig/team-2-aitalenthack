"""Build retrospective golden labels without modifying the feature dataset.

The default output is one canonical weekday dataset. Missing weekday rows such
as Monday are forward-filled from the latest effective CBR quote and retain the
same causal feature state. Future-derived diagnostics and ``good`` are labels
for retrospective review, never model inputs at date T.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.base_features import TARGET_CURRENCIES

PERIOD_START = "2025-07-01"
PERIOD_END = "2026-07-31"
HORIZONS = (1, 3, 5, 10, 20)
REGRET_THRESHOLDS_BPS = (25, 50, 100)
FINAL_RULE = "near_local_min"
FINAL_HORIZON_DAYS = 10
FINAL_X_BPS = 100
FINAL_OUTPUT = "data/labels/golden_labels.parquet"


@dataclass(frozen=True)
class Rule:
    identifier: str
    description: str


RULES = (
    Rule("regret_max", "Максимальное future regret за h дней не превышает X bps."),
    Rule("near_local_min", "Курс T не дальше X bps от минимума в календарном окне T±h."),
    Rule("centered_mean_benefit", "Курс T лучше среднего в окне T±h минимум на X bps."),
    Rule("future_median_benefit", "Курс T лучше медианы следующих h дней минимум на X bps."),
    Rule("stable_80pct", "Не менее 80% следующих h дней не лучше T более чем на X bps."),
    Rule("no_early_better", "В первой половине горизонта нет более выгодного курса сверх X bps."),
    Rule("low_p10_30_and_regret", "Нижние 10% 30 прошлых котировок и future regret не выше X bps."),
    Rule("low_p20_60_and_regret", "Нижние 20% 60 прошлых котировок и future regret не выше X bps."),
)


def _past_percentile(rate: pd.Series, window: int) -> pd.Series:
    """Share of previous observations less than or equal to current rate."""
    values = rate.to_numpy(dtype=float)
    result = np.full(len(values), np.nan)
    for index in range(window, len(values)):
        result[index] = np.mean(values[index - window : index] <= values[index])
    return pd.Series(result, index=rate.index)


def _calendar_rates(calendar: pd.DataFrame) -> dict[str, pd.Series]:
    selected = calendar.loc[calendar.currency.isin(TARGET_CURRENCIES)].copy()
    selected["corridor"] = selected.currency.astype(str) + "_RUB"
    selected["date"] = pd.to_datetime(selected.date, errors="raise")
    selected["rate"] = pd.to_numeric(selected.unit_rate, errors="raise")
    result: dict[str, pd.Series] = {}
    for corridor, group in selected.groupby("corridor", sort=True):
        series = group.sort_values("date").set_index("date")["rate"]
        if not series.index.to_series().diff().dropna().eq(pd.Timedelta(days=1)).all():
            raise ValueError(f"Calendar dates are incomplete for {corridor}")
        result[corridor] = series
    return result


def _future_diagnostics(dates: pd.Series, rates: pd.Series, calendar: pd.Series, horizon: int) -> pd.DataFrame:
    records = []
    for date, rate in zip(dates, rates, strict=True):
        future_dates = pd.date_range(date + pd.Timedelta(days=1), periods=horizon, freq="D")
        centered_dates = pd.date_range(date - pd.Timedelta(days=horizon), periods=2 * horizon + 1, freq="D")
        future = calendar.reindex(future_dates)
        centered = calendar.reindex(centered_dates)
        if future.isna().any():
            records.append(
                {
                    "future_min_rate": np.nan,
                    "future_median_rate": np.nan,
                    "future_regret_bps": np.nan,
                    "future_safe_day_share": np.nan,
                    "early_regret_bps": np.nan,
                }
            )
            continue
        regret = max(0.0, 10_000 * (rate - future.min()) / rate)
        early = future.iloc[: max(1, int(np.ceil(horizon / 2)))]
        records.append(
            {
                "future_min_rate": future.min(),
                "future_median_rate": future.median(),
                "future_regret_bps": regret,
                "future_safe_day_share": np.nan,  # Filled after choosing X.
                "early_regret_bps": max(0.0, 10_000 * (rate - early.min()) / rate),
            }
        )
    diagnostics = pd.DataFrame(records)
    centered_means = []
    centered_mins = []
    for date in dates:
        centered_dates = pd.date_range(date - pd.Timedelta(days=horizon), periods=2 * horizon + 1, freq="D")
        centered = calendar.reindex(centered_dates)
        centered_means.append(np.nan if centered.isna().any() else centered.mean())
        centered_mins.append(np.nan if centered.isna().any() else centered.min())
    diagnostics["centered_mean_rate"] = centered_means
    diagnostics["centered_min_rate"] = centered_mins
    diagnostics["centered_benefit_bps"] = (
        10_000
        * (diagnostics.centered_mean_rate.to_numpy() - rates.to_numpy())
        / diagnostics.centered_mean_rate.to_numpy()
    )
    diagnostics["future_median_benefit_bps"] = (
        10_000
        * (diagnostics.future_median_rate.to_numpy() - rates.to_numpy())
        / diagnostics.future_median_rate.to_numpy()
    )
    return diagnostics


def _good(rule: str, frame: pd.DataFrame, x_bps: int, horizon: int, calendar: pd.Series) -> pd.Series:
    allowance = x_bps / 10_000
    if rule == "regret_max":
        return frame.future_regret_bps.le(x_bps)
    if rule == "near_local_min":
        return frame.rate.le(frame.centered_min_rate * (1 + allowance))
    if rule == "centered_mean_benefit":
        return frame.centered_benefit_bps.ge(x_bps)
    if rule == "future_median_benefit":
        return frame.future_median_benefit_bps.ge(x_bps)
    if rule == "stable_80pct":
        minimum_safe_days = int(np.ceil(horizon * 0.8))
        shares = []
        for date, rate in zip(frame.date, frame.rate, strict=True):
            future_dates = pd.date_range(date + pd.Timedelta(days=1), periods=horizon, freq="D")
            future = calendar.reindex(future_dates)
            shares.append(np.nan if future.isna().any() else (future >= rate * (1 - allowance)).mean())
        frame["future_safe_day_share"] = shares
        return frame.future_safe_day_share.ge(minimum_safe_days / horizon)
    if rule == "no_early_better":
        return frame.early_regret_bps.le(x_bps)
    if rule == "low_p10_30_and_regret":
        return frame.past_percentile_30.le(0.10) & frame.future_regret_bps.le(x_bps)
    if rule == "low_p20_60_and_regret":
        return frame.percentile_60.le(0.20) & frame.future_regret_bps.le(x_bps)
    raise ValueError(f"Unknown rule: {rule}")


def build_labels(
    features: pd.DataFrame,
    calendar: pd.DataFrame,
    *,
    start: str,
    end: str,
    horizon: int,
    x_bps: int,
    rule: str,
) -> pd.DataFrame:
    """Return a copy of the selected features plus one retrospective ``good`` label."""
    if rule not in {item.identifier for item in RULES}:
        raise ValueError(f"Unknown rule: {rule}")
    source = features.copy()
    source["date"] = pd.to_datetime(source.date, errors="raise")
    rates = _calendar_rates(calendar)
    parts = []
    for corridor, group in source.groupby("corridor", sort=True):
        group = group.sort_values("date").reset_index(drop=True).copy()
        group["past_percentile_30"] = _past_percentile(group.rate, 30)
        selected = group.loc[group.date.between(pd.Timestamp(start), pd.Timestamp(end))].copy()
        diagnostics = _future_diagnostics(selected.date, selected.rate, rates[corridor], horizon)
        selected = pd.concat([selected.reset_index(drop=True), diagnostics], axis=1)
        selected["good"] = _good(rule, selected, x_bps, horizon, rates[corridor]).fillna(False).astype(bool)
        selected["label_rule"] = rule
        selected["label_horizon_days"] = horizon
        selected["label_x_bps"] = x_bps
        parts.append(selected)
    return pd.concat(parts, ignore_index=True).sort_values(["corridor", "date"]).reset_index(drop=True)


def _prepare_horizon(
    features: pd.DataFrame, calendar: pd.DataFrame, *, start: str, end: str, horizon: int
) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """Compute expensive future diagnostics once for every rule/X at one horizon."""
    source = features.copy()
    source["date"] = pd.to_datetime(source.date, errors="raise")
    rates = _calendar_rates(calendar)
    parts = []
    for corridor, group in source.groupby("corridor", sort=True):
        group = group.sort_values("date").reset_index(drop=True).copy()
        group["past_percentile_30"] = _past_percentile(group.rate, 30)
        selected = group.loc[group.date.between(pd.Timestamp(start), pd.Timestamp(end))].copy()
        diagnostics = _future_diagnostics(selected.date, selected.rate, rates[corridor], horizon)
        parts.append(pd.concat([selected.reset_index(drop=True), diagnostics], axis=1))
    prepared = pd.concat(parts, ignore_index=True)
    return prepared.sort_values(["corridor", "date"]).reset_index(drop=True), rates


def _episodes(frame: pd.DataFrame) -> pd.Series:
    flags = frame.good.astype(bool)
    return flags & ~flags.groupby(frame.corridor).shift(1, fill_value=False)


def build_final_golden(
    features: pd.DataFrame,
    calendar: pd.DataFrame,
    *,
    start: str | None = None,
    end: str | None = None,
    horizon: int = FINAL_HORIZON_DAYS,
    x_bps: int = FINAL_X_BPS,
) -> pd.DataFrame:
    """Build the canonical weekday golden dataset.

    The CBR rate effective on Saturday remains effective through Monday. We
    therefore construct calendar rows first, forward-fill the last causal
    feature state, and only then remove Saturday and Sunday candidate dates.
    """
    source = features.copy()
    source["date"] = pd.to_datetime(source.date, errors="raise")
    calendar_source = calendar.copy()
    calendar_source["date"] = pd.to_datetime(calendar_source.date, errors="raise")
    target_calendar = calendar_source.loc[calendar_source.currency.isin(TARGET_CURRENCIES)]
    earliest_complete = max(
        source.groupby("corridor").date.min().max(),
        target_calendar.groupby("currency").date.min().max() + pd.Timedelta(days=horizon),
    )
    latest_complete = target_calendar.groupby("currency").date.max().min() - pd.Timedelta(days=horizon)
    selected_start = pd.Timestamp(start) if start is not None else earliest_complete
    selected_end = pd.Timestamp(end) if end is not None else latest_complete
    if selected_start < earliest_complete or selected_end > latest_complete:
        raise ValueError(
            "Requested final-label period has incomplete centered windows: "
            f"available {earliest_complete.date()}..{latest_complete.date()}"
        )
    if selected_start > selected_end:
        raise ValueError("Final-label start date is after end date")
    rates = _calendar_rates(calendar_source)
    parts = []
    for corridor, feature_group in source.groupby("corridor", sort=True):
        currency = corridor.removesuffix("_RUB")
        calendar_group = calendar_source.loc[
            calendar_source.currency.eq(currency) & calendar_source.date.between(selected_start, selected_end),
            ["date", "unit_rate", "is_new_quote", "source_quote_date", "days_since_new_quote"],
        ].copy()
        calendar_group = calendar_group.loc[calendar_group.date.dt.dayofweek.lt(5)]
        feature_group = feature_group.sort_values("date").set_index("date")
        aligned = feature_group.reindex(calendar_group.date, method="ffill").copy()
        aligned.index.name = "date"
        aligned = aligned.reset_index()
        aligned["rate"] = calendar_group.unit_rate.to_numpy(dtype=float)
        aligned["target_is_new_quote"] = calendar_group.is_new_quote.to_numpy(dtype=bool)
        aligned["target_source_quote_date"] = pd.to_datetime(calendar_group.source_quote_date.to_numpy())
        aligned["target_days_since_new_quote"] = calendar_group.days_since_new_quote.to_numpy(dtype=int)

        # Forward-filled feature values stay unchanged, but freshness is
        # calendar-time information and must advance on Monday/holidays.
        for prefix in ("usd_rub", "eur_rub", "cny_rub"):
            source_date_column = f"{prefix}_source_quote_date"
            freshness_column = f"{prefix}_freshness_days"
            if source_date_column in aligned:
                aligned[source_date_column] = pd.to_datetime(aligned[source_date_column])
                aligned[freshness_column] = (aligned.date - aligned[source_date_column]).dt.days
        freshness_columns = [
            column
            for column in (
                "usd_rub_freshness_days",
                "eur_rub_freshness_days",
                "cny_rub_freshness_days",
            )
            if column in aligned
        ]
        if freshness_columns:
            aligned["broad_rub_freshness_days"] = aligned[freshness_columns].max(axis=1)

        diagnostics = _future_diagnostics(aligned.date, aligned.rate, rates[corridor], horizon)
        aligned = pd.concat([aligned.reset_index(drop=True), diagnostics], axis=1)
        aligned["good"] = _good(FINAL_RULE, aligned, x_bps, horizon, rates[corridor]).fillna(False).astype(bool)
        aligned["label_rule"] = FINAL_RULE
        aligned["label_horizon_days"] = horizon
        aligned["label_x_bps"] = x_bps
        aligned["label_candidate_days"] = "monday_to_friday"
        parts.append(aligned)

    result = pd.concat(parts, ignore_index=True).sort_values(["corridor", "date"]).reset_index(drop=True)
    if result.duplicated(["date", "corridor"]).any():
        raise ValueError("Duplicate date/corridor rows in final golden dataset")
    if result.date.dt.dayofweek.ge(5).any():
        raise ValueError("Weekend candidate leaked into final golden dataset")
    if result[["date", "corridor", "rate", "good"]].isna().any().any():
        raise ValueError("Null key/rate/label in final golden dataset")
    return result


def save_final_golden(
    *,
    features_path: str = "data/features/fx_features_daily.parquet",
    calendar_path: str = "data/interim/fx_calendar_time.parquet",
    output_path: str = FINAL_OUTPUT,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Build and save the one canonical golden label table."""
    result = build_final_golden(
        pd.read_parquet(features_path),
        pd.read_parquet(calendar_path),
        start=start,
        end=end,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)
    return result


def run_review(
    *,
    features_path: str = "data/features/fx_features_daily.parquet",
    calendar_path: str = "data/interim/fx_calendar_time.parquet",
    output_dir: str = "data/labels/golden_review/2025-07-01_2026-07-31",
    start: str = PERIOD_START,
    end: str = PERIOD_END,
) -> pd.DataFrame:
    """Write one labeled feature table per rule/horizon/threshold and a manifest."""
    features = pd.read_parquet(features_path)
    calendar = pd.read_parquet(calendar_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest = []
    for horizon in HORIZONS:
        prepared, rates = _prepare_horizon(features, calendar, start=start, end=end, horizon=horizon)
        for item in RULES:
            for x_bps in REGRET_THRESHOLDS_BPS:
                labels = prepared.copy()
                parts = []
                for corridor, group in labels.groupby("corridor", sort=True):
                    group = group.copy()
                    group["good"] = (
                        _good(item.identifier, group, x_bps, horizon, rates[corridor]).fillna(False).astype(bool)
                    )
                    parts.append(group)
                labels = pd.concat(parts, ignore_index=True)
                labels["label_rule"] = item.identifier
                labels["label_horizon_days"] = horizon
                labels["label_x_bps"] = x_bps
                name = f"{item.identifier}__h-{horizon:02d}__x-{x_bps:03d}bps.parquet"
                path = output / name
                labels.to_parquet(path, index=False)
                episodes = _episodes(labels)
                for corridor, group in labels.assign(episode=episodes).groupby("corridor", sort=True):
                    manifest.append(
                        {
                            "file": name,
                            "rule": item.identifier,
                            "description": item.description,
                            "horizon_days": horizon,
                            "x_bps": x_bps,
                            "corridor": corridor,
                            "rows": len(group),
                            "good_days": int(group.good.sum()),
                            "good_share": float(group.good.mean()),
                            "good_episodes": int(group.episode.sum()),
                            "median_regret_bps": float(group.future_regret_bps.median()),
                        }
                    )
    result = pd.DataFrame(manifest)
    result.to_csv(output / "manifest.csv", index=False)
    config = {
        "period": {"start": start, "end": end},
        "features_input": features_path,
        "calendar_input": calendar_path,
        "horizons": HORIZONS,
        "horizon_unit": "calendar_days",
        "x_bps": REGRET_THRESHOLDS_BPS,
        "rules": [{"id": item.identifier, "description": item.description} for item in RULES],
        "note": "Future-derived columns and good are retrospective labels, never causal features.",
    }
    (output / "run_config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", default="data/features/fx_features_daily.parquet")
    parser.add_argument("--calendar", default="data/interim/fx_calendar_time.parquet")
    parser.add_argument("--output", default=FINAL_OUTPUT)
    parser.add_argument("--output-dir", default="data/labels/golden_review/2025-07-01_2026-07-31")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument(
        "--review-grid",
        action="store_true",
        help="Regenerate the exploratory rule/horizon/threshold grid instead of the final dataset.",
    )
    args = parser.parse_args(argv)
    if args.review_grid:
        manifest = run_review(
            features_path=args.features,
            calendar_path=args.calendar,
            output_dir=args.output_dir,
            start=args.start or PERIOD_START,
            end=args.end or PERIOD_END,
        )
        print(f"PASS: {len(manifest) // len(TARGET_CURRENCIES)} label datasets -> {args.output_dir}")
        return 0
    golden = save_final_golden(
        features_path=args.features,
        calendar_path=args.calendar,
        output_path=args.output,
        start=args.start,
        end=args.end,
    )
    counts = golden.groupby("corridor").good.agg(rows="size", good_days="sum")
    print(f"PASS: final golden dataset -> {args.output}\n{counts.to_string()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
