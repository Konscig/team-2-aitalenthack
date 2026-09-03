"""Expand quote-time FX features to calendar days by causal forward fill.

The source feature dataset is not modified. Generated dates reuse only the
latest feature row available before that date and are explicitly marked as
non-quotes, so weekends/holidays cannot be interpreted as market movements.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


TARGET_QUOTE_DATE = "source_quote_date"
REFERENCE_PREFIXES = ("usd_rub", "eur_rub", "cny_rub")
METADATA_COLUMNS = {
    "date", "is_new_quote", TARGET_QUOTE_DATE, "days_since_new_quote",
    *(f"{prefix}_freshness_days" for prefix in REFERENCE_PREFIXES),
    "broad_rub_freshness_days",
}


class CalendarExpansionError(RuntimeError):
    """Invalid quote-time input or calendar expansion result."""


def build_calendar_feature_dataset(features: pd.DataFrame) -> pd.DataFrame:
    """Create a complete daily index per corridor using past-only forward fill."""
    required = {"date", "corridor", "rate"}
    missing = required.difference(features.columns)
    if missing:
        raise CalendarExpansionError(f"Отсутствуют обязательные поля: {sorted(missing)}")
    source = features.copy()
    source["date"] = pd.to_datetime(source["date"], errors="raise")
    if source[list(required)].isna().any().any():
        raise CalendarExpansionError("Null в обязательных полях")
    if source.duplicated(["corridor", "date"]).any():
        raise CalendarExpansionError("Найдены дубликаты corridor+date")

    frames = []
    for corridor, group in source.groupby("corridor", sort=True):
        ordered = group.sort_values("date", kind="stable").set_index("date")
        full_index = pd.date_range(ordered.index.min(), ordered.index.max(), freq="D")
        real_dates = full_index.isin(ordered.index)
        expanded = ordered.reindex(full_index).ffill()
        expanded.index.name = "date"
        expanded = expanded.reset_index()
        expanded["corridor"] = corridor
        expanded["is_new_quote"] = real_dates
        expanded[TARGET_QUOTE_DATE] = expanded["date"].where(expanded["is_new_quote"]).ffill()
        expanded["days_since_new_quote"] = (
            expanded["date"] - expanded[TARGET_QUOTE_DATE]
        ).dt.days.astype("Int64")

        for prefix in REFERENCE_PREFIXES:
            quote_date = f"{prefix}_source_quote_date"
            freshness = f"{prefix}_freshness_days"
            if quote_date in expanded.columns:
                expanded[quote_date] = pd.to_datetime(expanded[quote_date], errors="raise")
                expanded[freshness] = (expanded["date"] - expanded[quote_date]).dt.days.astype("Int64")
        freshness_columns = [f"{prefix}_freshness_days" for prefix in REFERENCE_PREFIXES]
        if all(column in expanded.columns for column in freshness_columns):
            expanded["broad_rub_freshness_days"] = expanded[freshness_columns].max(axis=1).astype("Int64")
        frames.append(expanded)

    result = pd.concat(frames, ignore_index=True).sort_values(["corridor", "date"], kind="stable").reset_index(drop=True)
    validate_calendar_feature_dataset(source, result)
    return result


def validate_calendar_feature_dataset(source: pd.DataFrame, calendar: pd.DataFrame) -> None:
    """Verify completeness, causal quote dates, and unchanged forward-filled values."""
    if calendar.duplicated(["corridor", "date"]).any():
        raise CalendarExpansionError("Calendar output содержит дубликаты")
    if (calendar[TARGET_QUOTE_DATE] > calendar["date"]).any():
        raise CalendarExpansionError("Calendar output содержит будущую target-котировку")
    for prefix in REFERENCE_PREFIXES:
        column = f"{prefix}_source_quote_date"
        if column in calendar and (calendar[column] > calendar["date"]).any():
            raise CalendarExpansionError(f"Calendar output содержит будущую {prefix}-котировку")
    for corridor, group in calendar.groupby("corridor", sort=False):
        expected = (group.date.max() - group.date.min()).days + 1
        if len(group) != expected or not group.date.diff().dropna().eq(pd.Timedelta(days=1)).all():
            raise CalendarExpansionError(f"Неполный календарный индекс для {corridor}")
    real = calendar.loc[calendar["is_new_quote"]]
    original = source.sort_values(["corridor", "date"]).reset_index(drop=True)
    compare = real[source.columns].sort_values(["corridor", "date"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(original, compare, check_dtype=False)
    market_columns = [column for column in source.columns if column not in METADATA_COLUMNS]
    generated = ~calendar["is_new_quote"]
    current = calendar.loc[generated, market_columns].reset_index(drop=True)
    previous = calendar[market_columns].shift(1).loc[generated].reset_index(drop=True)
    pd.testing.assert_frame_equal(current, previous, check_dtype=False)


def run_calendar_expansion(
    input_path: str = "data/features/fx_features_daily.parquet",
    output_path: str = "data/features/fx_features_calendar_daily.parquet",
) -> dict[str, object]:
    source_path = Path(input_path)
    if not source_path.is_file():
        raise CalendarExpansionError(f"Не найден входной датасет: {source_path}")
    source = pd.read_parquet(source_path)
    calendar = build_calendar_feature_dataset(source)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    calendar.to_parquet(temporary, index=False, engine="pyarrow")
    temporary.replace(output)
    return {
        "status": "PASS",
        "input_rows": int(len(source)),
        "output_rows": int(len(calendar)),
        "added_rows": int((~calendar["is_new_quote"]).sum()),
        "output": output.as_posix(),
        "by_corridor": {
            corridor: {
                "rows": int(len(group)),
                "added_rows": int((~group["is_new_quote"]).sum()),
                "first_date": group.date.min().date().isoformat(),
                "last_date": group.date.max().date().isoformat(),
            }
            for corridor, group in calendar.groupby("corridor", sort=True)
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/features/fx_features_daily.parquet")
    parser.add_argument("--output", default="data/features/fx_features_calendar_daily.parquet")
    args = parser.parse_args(argv)
    try:
        summary = run_calendar_expansion(args.input, args.output)
    except (CalendarExpansionError, OSError, ValueError, AssertionError) as exc:
        print(f"CALENDAR EXPANSION: FAIL — {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("CALENDAR EXPANSION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
