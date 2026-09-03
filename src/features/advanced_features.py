"""Causal reversal and cross-currency features from official CBR quotes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.base_features import TARGET_CURRENCIES, build_base_market_features


REFERENCE_CURRENCIES = ("USD", "EUR", "CNY")
RETURN_WINDOWS = (1, 3, 5, 10, 20)
ZSCORE_WINDOWS = (1, 3, 5)
EPSILONS = (("002", 0.002), ("005", 0.005), ("010", 0.010))


class AdvancedFeatureError(RuntimeError):
    """Invalid source data, alignment, or causal feature calculation."""


def advanced_feature_columns() -> list[str]:
    columns = ["days_since_min_20", "days_since_min_60", "return_sign_reversal_up", "reversal_strength"]
    columns += [f"near_min_prev_{key}" for key, _ in EPSILONS]
    columns += [f"near_min_reversal_{key}" for key, _ in EPSILONS]
    columns += [f"reversal_2d_{key}" for key, _ in EPSILONS]
    columns += ["recipient_usd_implied", *(f"recipient_usd_ret_{n}" for n in (1, 3, 5, 10))]
    for ref in REFERENCE_CURRENCIES:
        prefix = ref.lower() + "_rub"
        columns += [f"{prefix}_source_quote_date", f"{prefix}_freshness_days"]
    columns += ["broad_rub_freshness_days"]
    columns += [*(f"broad_rub_return_{n}" for n in RETURN_WINDOWS)]
    columns += [*(f"corridor_specific_return_{n}" for n in (1, 3, 5, 10))]
    columns += [*(f"broad_rub_z_{n}" for n in ZSCORE_WINDOWS)]
    return columns


def _validate_source(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "currency", "unit_rate", "source_quote_date", "is_new_quote"}
    missing = required.difference(frame.columns)
    if missing:
        raise AdvancedFeatureError(f"Отсутствуют обязательные поля: {sorted(missing)}")
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise")
    result["source_quote_date"] = pd.to_datetime(result["source_quote_date"], errors="raise")
    result["currency"] = result["currency"].astype(str)
    result["unit_rate"] = pd.to_numeric(result["unit_rate"], errors="raise").astype(float)
    expected = set(TARGET_CURRENCIES) | set(REFERENCE_CURRENCIES)
    absent = expected.difference(result["currency"].unique())
    if absent:
        raise AdvancedFeatureError(f"Нет валют: {sorted(absent)}")
    result = result.loc[result["currency"].isin(expected)]
    if not result["is_new_quote"].astype(bool).all():
        raise AdvancedFeatureError("Calendar/forward-filled строки запрещены")
    if (result["source_quote_date"] > result["date"]).any():
        raise AdvancedFeatureError("Найдена котировка из будущего")
    if result.duplicated(["currency", "date"]).any():
        raise AdvancedFeatureError("Найдены дубликаты currency+date")
    return result.sort_values(["currency", "date"], kind="stable").reset_index(drop=True)


def _days_since_min(values: pd.Series, window: int) -> pd.Series:
    def age(array: np.ndarray) -> float:
        positions = np.flatnonzero(array == np.min(array))
        return float(len(array) - 1 - positions[-1])
    return values.rolling(window, min_periods=window).apply(age, raw=True)


def build_reversal_features(base: pd.DataFrame) -> pd.DataFrame:
    """Calculate reversal features independently in each target quote series."""
    frames = []
    for corridor, group in base.groupby("corridor", sort=True):
        result = group[["date", "corridor"]].copy()
        rate = group["rate"].reset_index(drop=True)
        ret = group["ret_1"].reset_index(drop=True)
        dist_min = group["dist_min_20"].reset_index(drop=True)
        result = result.reset_index(drop=True)
        result["days_since_min_20"] = _days_since_min(rate, 20)
        result["days_since_min_60"] = _days_since_min(rate, 60)
        result["return_sign_reversal_up"] = ((ret.shift(1) < 0) & (ret > 0)).astype("int8")
        result["reversal_strength"] = ret - ret.shift(1)
        for key, epsilon in EPSILONS:
            near_previous = dist_min.shift(1) < epsilon
            result[f"near_min_prev_{key}"] = near_previous.astype("int8")
            result[f"near_min_reversal_{key}"] = (near_previous & (ret.shift(1) < 0) & (ret > 0)).astype("int8")
            result[f"reversal_2d_{key}"] = (
                (rate > rate.shift(1)) & (rate.shift(1) > rate.shift(2)) & (dist_min.shift(2) < epsilon)
            ).astype("int8")
        frames.append(result)
    return pd.concat(frames, ignore_index=True).sort_values(["corridor", "date"]).reset_index(drop=True)


def _reference_features(source: pd.DataFrame) -> dict[str, pd.DataFrame]:
    references: dict[str, pd.DataFrame] = {}
    for currency in REFERENCE_CURRENCIES:
        group = source.loc[source["currency"] == currency, ["date", "unit_rate", "source_quote_date"]].copy()
        group = group.sort_values("date").reset_index(drop=True)
        for window in RETURN_WINDOWS:
            returns = group["unit_rate"] / group["unit_rate"].shift(window) - 1.0
            group[f"return_{window}"] = returns
            if window in ZSCORE_WINDOWS:
                history = returns.shift(1).rolling(60, min_periods=60)
                std = history.std(ddof=1)
                group[f"z_{window}"] = (returns - history.mean()) / std.where(std != 0)
        references[currency] = group
    return references


def build_cross_currency_features(base: pd.DataFrame, quote_time: pd.DataFrame) -> pd.DataFrame:
    """Align reference quotes as-of T, never from a date later than T."""
    source = _validate_source(quote_time)
    references = _reference_features(source)
    frames = []
    for corridor, target in base.groupby("corridor", sort=True):
        aligned = target[["date", "corridor", "rate", "ret_1", "ret_3", "ret_5", "ret_10"]].sort_values("date").copy()
        for currency, reference in references.items():
            prefix = currency.lower() + "_rub"
            rename = {"unit_rate": f"{prefix}_rate", "source_quote_date": f"{prefix}_source_quote_date"}
            rename.update({f"return_{n}": f"{prefix}_ret_{n}" for n in RETURN_WINDOWS})
            rename.update({f"z_{n}": f"{prefix}_z_{n}" for n in ZSCORE_WINDOWS})
            right = reference.rename(columns=rename)
            aligned = pd.merge_asof(aligned.sort_values("date"), right.sort_values("date"), on="date", direction="backward")
            quote_date = f"{prefix}_source_quote_date"
            aligned[f"{prefix}_freshness_days"] = (aligned["date"] - aligned[quote_date]).dt.days.astype("Int64")
            if (aligned[quote_date] > aligned["date"]).any():
                raise AdvancedFeatureError(f"Future alignment для {currency}")
        aligned["recipient_usd_implied"] = aligned["rate"] / aligned["usd_rub_rate"]
        for window in (1, 3, 5, 10):
            aligned[f"recipient_usd_ret_{window}"] = (
                aligned["recipient_usd_implied"] / aligned["recipient_usd_implied"].shift(window) - 1.0
            )
        freshness = [f"{c.lower()}_rub_freshness_days" for c in REFERENCE_CURRENCIES]
        aligned["broad_rub_freshness_days"] = aligned[freshness].max(axis=1)
        for window in RETURN_WINDOWS:
            refs = [f"{c.lower()}_rub_ret_{window}" for c in REFERENCE_CURRENCIES]
            aligned[f"broad_rub_return_{window}"] = aligned[refs].mean(axis=1, skipna=False)
        for window in (1, 3, 5, 10):
            aligned[f"corridor_specific_return_{window}"] = aligned[f"ret_{window}"] - aligned[f"broad_rub_return_{window}"]
        for window in ZSCORE_WINDOWS:
            refs = [f"{c.lower()}_rub_z_{window}" for c in REFERENCE_CURRENCIES]
            aligned[f"broad_rub_z_{window}"] = aligned[refs].mean(axis=1, skipna=False)
        frames.append(aligned[["date", "corridor", *[c for c in advanced_feature_columns() if c not in {
            "days_since_min_20", "days_since_min_60", "return_sign_reversal_up", "reversal_strength",
            *(f"near_min_prev_{k}" for k, _ in EPSILONS), *(f"near_min_reversal_{k}" for k, _ in EPSILONS),
            *(f"reversal_2d_{k}" for k, _ in EPSILONS)
        }]]])
    return pd.concat(frames, ignore_index=True).sort_values(["corridor", "date"]).reset_index(drop=True)


def build_advanced_features(quote_time: pd.DataFrame, base: pd.DataFrame | None = None) -> pd.DataFrame:
    """Merge unchanged base features with causal reversal and cross-FX features."""
    source = _validate_source(quote_time)
    baseline = build_base_market_features(source) if base is None else base.copy()
    reversal = build_reversal_features(baseline)
    cross = build_cross_currency_features(baseline, source)
    result = baseline.merge(reversal, on=["date", "corridor"], validate="one_to_one")
    result = result.merge(cross, on=["date", "corridor"], validate="one_to_one")
    if len(result) != len(baseline):
        raise AdvancedFeatureError("Merge изменил число строк base features")
    return result.sort_values(["corridor", "date"]).reset_index(drop=True)


def validate_implied_identity(features: pd.DataFrame, quote_time: pd.DataFrame, samples: int = 10) -> None:
    source = _validate_source(quote_time)
    rows = features.dropna(subset=["recipient_usd_implied"]).sample(samples, random_state=19)
    usd = source.loc[source.currency == "USD", ["date", "unit_rate"]].sort_values("date")
    checked = pd.merge_asof(rows[["date", "rate", "recipient_usd_implied"]].sort_values("date"), usd, on="date", direction="backward")
    if not np.allclose(checked["recipient_usd_implied"], checked["rate"] / checked["unit_rate"], rtol=1e-12):
        raise AdvancedFeatureError("Нарушена identity recipient/USD")


def run_causality_check(quote_time: pd.DataFrame, full: pd.DataFrame, samples: int = 30, seed: int = 42) -> dict[str, object]:
    candidates = full.groupby("corridor", sort=False).tail(-365).sample(samples, random_state=seed)
    columns = advanced_feature_columns()
    for row in candidates.itertuples(index=False):
        truncated_source = quote_time.loc[pd.to_datetime(quote_time["date"]) <= row.date]
        recalculated = build_advanced_features(truncated_source)
        actual = recalculated.loc[(recalculated.corridor == row.corridor) & (recalculated.date == row.date)].iloc[0]
        expected = full.loc[(full.corridor == row.corridor) & (full.date == row.date)].iloc[0]
        for column in columns:
            left, right = expected[column], actual[column]
            if column.endswith("source_quote_date"):
                equal = (pd.isna(left) and pd.isna(right)) or pd.Timestamp(left) == pd.Timestamp(right)
            else:
                equal = np.isclose(float(left), float(right), rtol=1e-12, atol=1e-12, equal_nan=True)
            if not equal:
                raise AdvancedFeatureError(f"Causality FAIL: {row.corridor} {row.date} {column}")
    return {"status": "PASS", "samples": samples, "seed": seed}


def _report(features: pd.DataFrame, causality: dict[str, object]) -> str:
    new = advanced_feature_columns()
    freshness = [c for c in new if c.endswith("freshness_days")]
    alignment_rows = []
    for currency in REFERENCE_CURRENCIES:
        column = f"{currency.lower()}_rub_freshness_days"
        alignment_rows.append({
            "Опорная валюта": currency,
            "Точное совпадение даты": int((features[column] == 0).sum()),
            "Использована прошлая котировка": int((features[column] > 0).sum()),
            "Нет доступной котировки": int(features[column].isna().sum()),
        })
    alignment = pd.DataFrame(alignment_rows)
    reversals = features.loc[features.return_sign_reversal_up == 1, ["date", "corridor", "rate", "reversal_strength", "near_min_reversal_010"]].head(8)
    broad = features.loc[features.broad_rub_return_5.abs().nlargest(8).index, ["date", "corridor", "broad_rub_return_5"]]
    specific = features.loc[features.corridor_specific_return_5.abs().nlargest(8).index, ["date", "corridor", "corridor_specific_return_5"]]
    missingness = features[new].isna().sum().rename("Количество NaN").to_frame()
    lines = ["# Advanced features report", "", f"Новых полей: **{len(new)}**. Строк: **{len(features)}**.", "", "## Новые признаки", "", ", ".join(f"`{c}`" for c in new), "", "## Пропуски", "", missingness.to_markdown(), "", "Пропуски в начале рядов вызваны causal warm-up окон и лагов; они не заполнялись.", "", "## Alignment и freshness", "", "Опорные валюты присоединены по последней официальной котировке с датой не позже T. Backward fill и будущие значения не применялись.", "", alignment.to_markdown(index=False), "", features[freshness].describe().T.to_markdown(), "", "Проверка математической identity `recipient_usd_implied = X_RUB / USD_RUB` на 10 реальных строках: **PASS**.", "", "## Примеры reversal events", "", reversals.to_markdown(index=False), "", "## Примеры движения broad RUB factor", "", broad.to_markdown(index=False), "", "## Примеры corridor-specific движения", "", specific.to_markdown(index=False), "", "## Проверка причинности", "", f"Статус: **{causality['status']}**; проверено случайных пар дата/коридор: **{causality['samples']}**, seed `{causality['seed']}`.", "", "Labels не создавались.", "", "**ADVANCED FEATURES STATUS: PASS**", ""]
    return "\n".join(lines)


def run_advanced_features(
    quote_path: str = "data/interim/fx_quote_time.parquet",
    base_path: str = "data/features/base_market_features.parquet",
    output_path: str = "data/features/fx_features_daily.parquet",
    report_path: str = "reports/advanced_features_report.md",
) -> dict[str, object]:
    quote_time = pd.read_parquet(quote_path)
    base = pd.read_parquet(base_path)
    features = build_advanced_features(quote_time, base)
    validate_implied_identity(features, quote_time)
    causality = run_causality_check(quote_time, features, samples=30)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    features.to_parquet(temporary, index=False)
    temporary.replace(output)
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(_report(features, causality), encoding="utf-8", newline="\n")
    return {"status": "PASS", "rows": len(features), "new_features": len(advanced_feature_columns()), "causality": causality, "output": output.as_posix(), "report": report.as_posix()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quote-path", default="data/interim/fx_quote_time.parquet")
    parser.add_argument("--base-path", default="data/features/base_market_features.parquet")
    parser.add_argument("--output", default="data/features/fx_features_daily.parquet")
    parser.add_argument("--report", default="reports/advanced_features_report.md")
    args = parser.parse_args(argv)
    try:
        summary = run_advanced_features(args.quote_path, args.base_path, args.output, args.report)
    except (AdvancedFeatureError, OSError, ValueError, KeyError) as exc:
        print(f"ADVANCED FEATURES STATUS: FAIL — {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("ADVANCED FEATURES STATUS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
