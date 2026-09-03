"""Causal base market features from official CBR quote-time observations.

``rate`` is RUB per one unit of recipient currency. A lower rate is more
favourable for a sender holding RUB. Every feature at T uses observations no
later than T; percentiles explicitly exclude the current observation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


TARGET_CURRENCIES = ("TJS", "UZS", "KGS", "AMD", "KZT")
RETURN_WINDOWS = (1, 2, 3, 5, 10, 20)
SMA_WINDOWS = (5, 10, 20, 60)
MIN_MAX_WINDOWS = (10, 20, 60, 90, 180, 365)
PERCENTILE_WINDOWS = (20, 60, 90, 180, 365)
MOMENTUM_WINDOWS = (3, 5, 10, 20)
VOLATILITY_WINDOWS = (5, 10, 20, 60)
RANGE_WINDOWS = (10, 20, 60)
IDENTIFIER_COLUMNS = ("date", "corridor", "rate")


class FeatureError(RuntimeError):
    """Invalid input or a feature-generation quality failure."""


def feature_columns() -> list[str]:
    """Return the stable ordered list of generated feature columns."""
    columns = [*(f"ret_{n}" for n in RETURN_WINDOWS), "log_ret_1"]
    columns += [name for n in SMA_WINDOWS for name in (f"sma_{n}", f"dist_sma_{n}")]
    columns += ["sma_5_vs_20", "sma_20_vs_60"]
    columns += [
        name
        for n in MIN_MAX_WINDOWS
        for name in (f"rolling_min_{n}", f"rolling_max_{n}", f"dist_min_{n}", f"dist_max_{n}")
    ]
    columns += [
        name
        for n in PERCENTILE_WINDOWS
        for name in (f"percentile_{n}", f"favourability_percentile_{n}")
    ]
    columns += [*(f"mom_{n}" for n in MOMENTUM_WINDOWS), "down_streak", "up_streak"]
    columns += [*(f"vol_{n}" for n in VOLATILITY_WINDOWS)]
    columns += [*(f"rolling_range_{n}" for n in RANGE_WINDOWS)]
    return columns


def validate_quote_time_input(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and select genuine CBR quote observations for target corridors."""
    required = {"date", "currency", "unit_rate", "is_new_quote", "source_quote_date"}
    missing = required.difference(frame.columns)
    if missing:
        raise FeatureError(f"Quote-time input misses columns: {sorted(missing)}")
    selected = frame.loc[frame["currency"].astype(str).isin(TARGET_CURRENCIES)].copy()
    absent = set(TARGET_CURRENCIES).difference(selected["currency"].astype(str).unique())
    if absent:
        raise FeatureError(f"Missing target currencies: {sorted(absent)}")
    if selected[list(required)].isna().any().any():
        raise FeatureError("Null in mandatory quote-time fields")
    if not selected["is_new_quote"].astype(bool).all():
        raise FeatureError("Forward-filled/calendar rows are forbidden in base features")
    selected["date"] = pd.to_datetime(selected["date"], errors="raise")
    selected["source_quote_date"] = pd.to_datetime(selected["source_quote_date"], errors="raise")
    if not (selected["date"] == selected["source_quote_date"]).all():
        raise FeatureError("Quote date differs from source_quote_date")
    selected["unit_rate"] = pd.to_numeric(selected["unit_rate"], errors="raise").astype(float)
    if (~np.isfinite(selected["unit_rate"]) | (selected["unit_rate"] <= 0)).any():
        raise FeatureError("Rates must be finite and positive")
    duplicates = selected.duplicated(["currency", "date"], keep=False)
    if duplicates.any():
        examples = selected.loc[duplicates, ["currency", "date"]].head(5).to_dict("records")
        raise FeatureError(f"Duplicate currency/date observations: {examples}")
    return selected.sort_values(["currency", "date"], kind="stable").reset_index(drop=True)


def _streaks(rate: pd.Series) -> tuple[pd.Series, pd.Series]:
    changes = rate.diff().to_numpy()
    down = np.zeros(len(rate), dtype=np.int64)
    up = np.zeros(len(rate), dtype=np.int64)
    for index in range(1, len(rate)):
        if changes[index] < 0:
            down[index] = down[index - 1] + 1
        elif changes[index] > 0:
            up[index] = up[index - 1] + 1
    return pd.Series(down, index=rate.index), pd.Series(up, index=rate.index)


def _past_percentile(rate: pd.Series, window: int) -> pd.Series:
    """Share of the prior N rates <= current rate; current rate is excluded."""
    values = rate.to_numpy(dtype=float)
    result = np.full(len(values), np.nan)
    for index in range(window, len(values)):
        result[index] = np.mean(values[index - window:index] <= values[index])
    return pd.Series(result, index=rate.index, dtype=float)


def _features_for_series(date: pd.Series, currency: str, rate: pd.Series) -> pd.DataFrame:
    result = pd.DataFrame({"date": date.to_numpy(), "corridor": f"{currency}_RUB", "rate": rate.to_numpy()})
    price = result["rate"]
    for window in RETURN_WINDOWS:
        result[f"ret_{window}"] = price / price.shift(window) - 1.0
    result["log_ret_1"] = np.log(price / price.shift(1))
    rolling_means: dict[int, pd.Series] = {}
    for window in SMA_WINDOWS:
        rolling_means[window] = price.rolling(window, min_periods=window).mean()
        result[f"sma_{window}"] = rolling_means[window]
        result[f"dist_sma_{window}"] = price / rolling_means[window] - 1.0
    result["sma_5_vs_20"] = rolling_means[5] / rolling_means[20] - 1.0
    result["sma_20_vs_60"] = rolling_means[20] / rolling_means[60] - 1.0
    rolling_minima: dict[int, pd.Series] = {}
    rolling_maxima: dict[int, pd.Series] = {}
    for window in MIN_MAX_WINDOWS:
        rolling_minima[window] = price.rolling(window, min_periods=window).min()
        rolling_maxima[window] = price.rolling(window, min_periods=window).max()
        result[f"rolling_min_{window}"] = rolling_minima[window]
        result[f"rolling_max_{window}"] = rolling_maxima[window]
        result[f"dist_min_{window}"] = price / rolling_minima[window] - 1.0
        result[f"dist_max_{window}"] = price / rolling_maxima[window] - 1.0
    for window in PERCENTILE_WINDOWS:
        percentile = _past_percentile(price, window)
        result[f"percentile_{window}"] = percentile
        result[f"favourability_percentile_{window}"] = 1.0 - percentile
    for window in MOMENTUM_WINDOWS:
        result[f"mom_{window}"] = price / price.shift(window) - 1.0
    result["down_streak"], result["up_streak"] = _streaks(price)
    for window in VOLATILITY_WINDOWS:
        result[f"vol_{window}"] = result["log_ret_1"].rolling(window, min_periods=window).std(ddof=1)
    for window in RANGE_WINDOWS:
        mean = rolling_means[window]
        result[f"rolling_range_{window}"] = (rolling_maxima[window] - rolling_minima[window]) / mean
    return result[[*IDENTIFIER_COLUMNS, *feature_columns()]]


def build_base_market_features(quote_time: pd.DataFrame) -> pd.DataFrame:
    """Build long-form, quote-time-only features without future information."""
    source = validate_quote_time_input(quote_time)
    frames = []
    for currency in TARGET_CURRENCIES:
        group = source.loc[source["currency"].astype(str) == currency]
        frames.append(_features_for_series(group["date"], currency, group["unit_rate"]))
    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(["corridor", "date"], kind="stable").reset_index(drop=True)


def run_causality_check(
    quote_time: pd.DataFrame,
    full_features: pd.DataFrame | None = None,
    *,
    samples: int = 20,
    seed: int = 42,
) -> dict[str, object]:
    """Recompute random T rows from histories truncated at T and compare all features."""
    source = validate_quote_time_input(quote_time)
    full = full_features if full_features is not None else build_base_market_features(source)
    candidates = full.groupby("corridor", sort=False).tail(-365)
    if len(candidates) < samples:
        raise FeatureError(f"Only {len(candidates)} causality candidates for {samples} samples")
    chosen = candidates.sample(n=samples, random_state=seed)
    numeric_columns = ["rate", *feature_columns()]
    for row in chosen.itertuples(index=False):
        currency = row.corridor.removesuffix("_RUB")
        truncated = source.loc[(source["currency"].astype(str) == currency) & (source["date"] <= row.date)]
        recomputed = _features_for_series(
            truncated["date"], currency, truncated["unit_rate"]
        ).iloc[-1]
        expected = full.loc[(full["corridor"] == row.corridor) & (full["date"] == row.date)].iloc[0]
        for feature in numeric_columns:
            if not np.isclose(float(expected[feature]), float(recomputed[feature]), rtol=1e-12, atol=1e-12, equal_nan=True):
                raise FeatureError(
                    f"Causality failure: {row.corridor} {row.date.date()} feature={feature}, "
                    f"full={expected[feature]!r}, truncated={recomputed[feature]!r}"
                )
    return {"status": "PASS", "samples": samples, "seed": seed}


def _warmup_reason(name: str) -> str:
    if name in {"down_streak", "up_streak"}:
        return "none (starts at 0)"
    if name == "log_ret_1":
        return "1 prior quote required"
    if name.startswith("percentile_") or name.startswith("favourability_percentile_"):
        return f"{name.rsplit('_', 1)[-1]} prior quotes required; current quote excluded"
    if name.startswith("vol_"):
        return f"{name.rsplit('_', 1)[-1]} valid log returns required"
    if name == "sma_5_vs_20":
        return "20-quote SMA warm-up"
    if name == "sma_20_vs_60":
        return "60-quote SMA warm-up"
    return f"trailing {name.rsplit('_', 1)[-1]}-quote window/lag required"


def _report(features: pd.DataFrame, causality: dict[str, object], input_path: Path, outputs: list[Path]) -> str:
    columns = feature_columns()
    lines = [
        "# Base market features report", "",
        f"Input: `{input_path.as_posix()}` (official CBR quote-time observations only).", "",
        "`rate` is RUB per 1 unit of recipient currency; lower is more favourable for a RUB sender.", "",
        f"Rows: **{len(features)}**. Features: **{len(columns)}**. Output columns: **{len(features.columns)}**.", "",
        "## Coverage", "",
        "| corridor | rows | first_date | last_date |", "| --- | ---: | --- | --- |",
    ]
    for corridor, group in features.groupby("corridor", sort=True):
        lines.append(f"| {corridor} | {len(group)} | {group.date.min().date()} | {group.date.max().date()} |")
    lines += ["", "## Missing values and warm-up", "", "NaNs are retained: they represent insufficient trailing quote history, not missing-value imputation.", "", "| feature | NaN count | reason |", "| --- | ---: | --- |"]
    for column in columns:
        lines.append(f"| {column} | {int(features[column].isna().sum())} | {_warmup_reason(column)} |")
    lines += ["", "## Summary statistics", "", features[["rate", *columns]].describe().T.to_markdown(), "", "## Sample rows", "", features.groupby("corridor", sort=True).tail(1).to_markdown(index=False), "", "## Causality", "", f"Status: **{causality['status']}**. Compared all features after truncating source history at T for `{causality['samples']}` deterministic random date/corridor pairs (seed `{causality['seed']}`).", "", "Outputs: " + ", ".join(f"`{path.as_posix()}`" for path in outputs) + ".", "", "No labels, cross-currency features, macro data, calendar expansion, or synthetic production values were created.", "", "**BASE FEATURES STATUS: PASS**", ""]
    return "\n".join(lines)


def run_base_features(
    input_path: str = "data/interim/fx_quote_time.parquet",
    output_dir: str = "data/features",
    report_path: str = "reports/base_features_report.md",
) -> dict[str, object]:
    """Load normalized quotes, calculate, validate, persist and report features."""
    source_path = Path(input_path)
    if not source_path.is_file():
        raise FeatureError(f"Normalized quote-time file not found: {source_path}")
    quote_time = pd.read_parquet(source_path)
    features = build_base_market_features(quote_time)
    causality = run_causality_check(quote_time, features, samples=20)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    parquet_path = output_root / "base_market_features.parquet"
    csv_path = output_root / "base_market_features.csv"
    temporary = parquet_path.with_suffix(".parquet.tmp")
    features.to_parquet(temporary, index=False, engine="pyarrow")
    temporary.replace(parquet_path)
    features.to_csv(csv_path, index=False, date_format="%Y-%m-%d")
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_report(features, causality, source_path, [parquet_path, csv_path]), encoding="utf-8", newline="\n")
    return {
        "status": "PASS", "input": source_path.as_posix(), "rows": len(features),
        "feature_count": len(feature_columns()), "causality": causality,
        "outputs": [parquet_path.as_posix(), csv_path.as_posix()], "report": report.as_posix(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/interim/fx_quote_time.parquet")
    parser.add_argument("--output-dir", default="data/features")
    parser.add_argument("--report", default="reports/base_features_report.md")
    args = parser.parse_args(argv)
    try:
        summary = run_base_features(args.input, args.output_dir, args.report)
    except (FeatureError, OSError, ValueError) as exc:
        print(f"BASE FEATURES STATUS: FAIL — {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("BASE FEATURES STATUS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
