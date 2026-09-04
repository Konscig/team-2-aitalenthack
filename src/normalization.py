"""Offline normalization of recorded official Bank of Russia FX responses.

The canonical ``unit_rate`` is RUB per one unit of recipient currency. Thus a
lower unit_rate is better for a sender who owns RUB, while a higher unit_rate is
worse. This module never accesses the network, never invents market values and
never treats a forward-filled calendar row as a new quote.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

import pandas as pd


TARGET_CURRENCIES = ("TJS", "UZS", "KGS", "AMD", "KZT", "USD", "EUR", "CNY")
SOURCE_NAME = "Банк России"
DEFAULT_ENDPOINT = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
RATE_TOLERANCE = 1e-12
BASE_COLUMNS = [
    "date",
    "currency",
    "source_currency",
    "target_currency",
    "source_identifier",
    "nominal",
    "raw_rate",
    "unit_rate",
    "source_quote_date",
    "is_new_quote",
    "source",
    "source_endpoint",
]
NUMERIC_PATTERN = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")


class NormalizationError(RuntimeError):
    """Critical parsing or normalized-data quality failure."""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _local_name(child.tag) == name:
            value = (child.text or "").strip()
            return value or None
    return None


def _parse_number(value: str | None, *, field: str, row_context: str) -> float:
    if value is None:
        raise NormalizationError(f"Missing required {field} in {row_context}")
    compact = value.strip().replace("\u00a0", "").replace(" ", "")
    if not NUMERIC_PATTERN.fullmatch(compact):
        raise NormalizationError(f"Invalid numeric {field}={value!r} in {row_context}")
    # Official CBR XML observed in this project uses '.', while the documented
    # simple XML interface may use ','. No other locale transformations apply.
    return float(compact.replace(",", "."))


def parse_cbr_raw(
    raw_path: str | Path,
    *,
    currency: str,
    source_endpoint: str = DEFAULT_ENDPOINT,
    expected_source_identifier: str | None = None,
) -> pd.DataFrame:
    """Parse one saved SOAP response without downloading or filling dates."""
    path = Path(raw_path)
    if not path.is_file() or path.stat().st_size == 0:
        raise NormalizationError(f"Raw file is missing or empty: {path}")
    try:
        root = ET.fromstring(path.read_bytes())
    except ET.ParseError as exc:
        raise NormalizationError(f"Invalid XML in {path}: {exc}") from exc

    records: list[dict[str, object]] = []
    for element in root.iter():
        if _local_name(element.tag) != "ValuteCursDynamic":
            continue
        date_text = _child_text(element, "CursDate")
        source_identifier = _child_text(element, "Vcode")
        context = f"{currency} record {date_text or '<missing date>'}"
        if date_text is None or source_identifier is None:
            raise NormalizationError(f"Missing CursDate or Vcode in {context}")
        if expected_source_identifier and source_identifier != expected_source_identifier:
            raise NormalizationError(
                f"Unexpected source identifier in {context}: "
                f"{source_identifier}, expected {expected_source_identifier}"
            )
        nominal_float = _parse_number(_child_text(element, "Vnom"), field="Vnom", row_context=context)
        if not nominal_float.is_integer():
            raise NormalizationError(f"Non-integer nominal={nominal_float} in {context}")
        raw_rate = _parse_number(_child_text(element, "Vcurs"), field="Vcurs", row_context=context)
        source_unit_text = _child_text(element, "VunitRate")
        source_unit_rate = (
            _parse_number(source_unit_text, field="VunitRate", row_context=context)
            if source_unit_text is not None
            else math.nan
        )
        records.append(
            {
                "date_text": date_text,
                "currency": currency,
                "source_identifier": source_identifier,
                "nominal": int(nominal_float),
                "raw_rate": raw_rate,
                "source_unit_rate": source_unit_rate,
                "source": SOURCE_NAME,
                "source_endpoint": source_endpoint,
                "raw_filepath": path.as_posix(),
            }
        )
    if not records:
        raise NormalizationError(f"No ValuteCursDynamic records in {path}")
    return pd.DataFrame.from_records(records)


def normalize_currency_frame(frame: pd.DataFrame, *, tolerance: float = RATE_TOLERANCE) -> pd.DataFrame:
    """Normalize parsed CBR rows while preserving nominal and raw_rate."""
    required = {
        "date_text",
        "currency",
        "source_identifier",
        "nominal",
        "raw_rate",
        "source_unit_rate",
        "source",
        "source_endpoint",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise NormalizationError(f"Parsed frame is missing columns: {sorted(missing)}")
    result = frame.copy()
    try:
        parsed_dates = pd.to_datetime(result["date_text"], errors="raise", utc=True)
    except (ValueError, TypeError) as exc:
        raise NormalizationError(f"Invalid CBR dates: {exc}") from exc
    # CBR CursDate is +03:00. Convert back to Moscow civil date, then store a
    # timezone-naive normalized pandas datetime for calendar joins.
    result["date"] = parsed_dates.dt.tz_convert("Europe/Moscow").dt.tz_localize(None).dt.normalize()
    result["nominal"] = pd.to_numeric(result["nominal"], errors="raise").astype("Int64")
    result["raw_rate"] = pd.to_numeric(result["raw_rate"], errors="raise").astype("Float64")
    source_unit = pd.to_numeric(result["source_unit_rate"], errors="coerce").astype("Float64")
    calculated = result["raw_rate"] / result["nominal"]
    both = source_unit.notna()
    inconsistent = both & ((source_unit - calculated).abs() > (tolerance + tolerance * calculated.abs()))
    if inconsistent.any():
        examples = result.loc[inconsistent, ["date", "currency", "nominal", "raw_rate"]].head(5)
        raise NormalizationError(
            "CBR VunitRate is inconsistent with Vcurs/Vnom; examples: "
            + examples.to_dict(orient="records").__repr__()
        )
    # Prefer the official VunitRate; calculate only when the field is absent.
    result["unit_rate"] = source_unit.where(both, calculated).astype("Float64")
    result["source_currency"] = "RUB"
    result["target_currency"] = result["currency"].astype("string")
    result["source_quote_date"] = result["date"]
    result["is_new_quote"] = True
    result["currency"] = result["currency"].astype("string")
    result["source_currency"] = result["source_currency"].astype("string")
    result["target_currency"] = result["target_currency"].astype("string")
    result["source_identifier"] = result["source_identifier"].astype("string")
    result["source"] = result["source"].astype("string")
    result["source_endpoint"] = result["source_endpoint"].astype("string")
    return result[BASE_COLUMNS].sort_values(["currency", "date"], kind="stable").reset_index(drop=True)


def build_quote_time_dataset(currency_frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """Combine only real source observations; never generate calendar dates."""
    frames = list(currency_frames)
    if not frames:
        raise NormalizationError("No currency frames supplied")
    result = pd.concat(frames, ignore_index=True)
    return result.sort_values(["currency", "date"], kind="stable").reset_index(drop=True)


def build_calendar_time_dataset(quote_time: pd.DataFrame) -> pd.DataFrame:
    """Create daily rows using only an explicit last-known-quote forward fill."""
    calendar_frames: list[pd.DataFrame] = []
    for currency, group in quote_time.groupby("currency", sort=True, observed=True):
        ordered = group.sort_values("date", kind="stable").set_index("date")
        full_index = pd.date_range(ordered.index.min(), ordered.index.max(), freq="D")
        expanded = ordered.reindex(full_index)
        real_quote = expanded["source_quote_date"].notna()
        columns_to_fill = [column for column in BASE_COLUMNS if column not in {"date", "is_new_quote", "source_quote_date"}]
        expanded[columns_to_fill] = expanded[columns_to_fill].ffill()
        expanded["source_quote_date"] = expanded["source_quote_date"].ffill()
        expanded["is_new_quote"] = real_quote
        expanded.index.name = "date"
        expanded = expanded.reset_index()
        expanded["days_since_new_quote"] = (
            expanded["date"] - expanded["source_quote_date"]
        ).dt.days.astype("Int64")
        calendar_frames.append(expanded[BASE_COLUMNS + ["days_since_new_quote"]])
    return (
        pd.concat(calendar_frames, ignore_index=True)
        .sort_values(["currency", "date"], kind="stable")
        .reset_index(drop=True)
    )


def validate_normalized_data(
    frame: pd.DataFrame,
    *,
    calendar_time: bool = False,
    minimum_years: int = 5,
    tolerance: float = RATE_TOLERANCE,
) -> dict[str, dict[str, object]]:
    """Validate normalized quotes/calendar data and return per-currency stats."""
    required = set(BASE_COLUMNS)
    if calendar_time:
        required.add("days_since_new_quote")
    missing = required.difference(frame.columns)
    if missing:
        raise NormalizationError(f"Normalized frame is missing columns: {sorted(missing)}")
    mandatory = list(required)
    null_counts = frame[mandatory].isna().sum()
    bad_nulls = null_counts[null_counts > 0]
    if not bad_nulls.empty:
        raise NormalizationError(f"Nulls in mandatory normalized fields: {bad_nulls.to_dict()}")
    for column in ("nominal", "raw_rate", "unit_rate"):
        invalid = frame[column] <= 0
        if invalid.any():
            raise NormalizationError(
                f"Non-positive {column}; examples: "
                f"{frame.loc[invalid, ['date', 'currency', column]].head(5).to_dict(orient='records')}"
            )
    duplicates = frame.duplicated(["currency", "date"], keep=False)
    if duplicates.any():
        raise NormalizationError(
            "Duplicate currency+date rows; examples: "
            + repr(frame.loc[duplicates].head(5).to_dict(orient="records"))
        )
    sorted_index = frame.sort_values(["currency", "date"], kind="stable").index
    if not sorted_index.equals(frame.index):
        raise NormalizationError("Rows are not ordered by currency, date")
    calculated = frame["raw_rate"] / frame["nominal"]
    inconsistent = (frame["unit_rate"] - calculated).abs() > (tolerance + tolerance * calculated.abs())
    if inconsistent.any():
        raise NormalizationError(
            "unit_rate consistency check failed; examples: "
            + repr(frame.loc[inconsistent, ["date", "currency", "nominal", "raw_rate", "unit_rate"]].head(5).to_dict(orient="records"))
        )
    actual_currencies = set(frame["currency"].astype(str).unique())
    missing_currencies = set(TARGET_CURRENCIES).difference(actual_currencies)
    if minimum_years and missing_currencies:
        raise NormalizationError(f"Missing target currencies: {sorted(missing_currencies)}")

    summary: dict[str, dict[str, object]] = {}
    for currency, group in frame.groupby("currency", sort=True, observed=True):
        first_date = group["date"].min()
        last_date = group["date"].max()
        if minimum_years and (last_date - first_date).days < minimum_years * 365:
            raise NormalizationError(f"Less than {minimum_years} years for {currency}: {first_date}..{last_date}")
        if calendar_time:
            expected_days = (last_date - first_date).days + 1
            if len(group) != expected_days:
                raise NormalizationError(f"Calendar is incomplete for {currency}: {len(group)} != {expected_days}")
            expected_age = (group["date"] - group["source_quote_date"]).dt.days
            if not expected_age.astype("Int64").equals(group["days_since_new_quote"].astype("Int64")):
                raise NormalizationError(f"days_since_new_quote mismatch for {currency}")
            if (group["source_quote_date"] > group["date"]).any():
                raise NormalizationError(f"Future source_quote_date found for {currency}")
            if (group.loc[group["is_new_quote"], "days_since_new_quote"] != 0).any():
                raise NormalizationError(f"Real quote has non-zero age for {currency}")
        elif not group["is_new_quote"].all():
            raise NormalizationError(f"Quote-time contains generated rows for {currency}")
        summary[str(currency)] = {
            "first_date": first_date.date().isoformat(),
            "last_date": last_date.date().isoformat(),
            "rows": int(len(group)),
            "nominals_seen": sorted(int(value) for value in group["nominal"].unique()),
            "min_unit_rate": float(group["unit_rate"].min()),
            "median_unit_rate": float(group["unit_rate"].median()),
            "max_unit_rate": float(group["unit_rate"].max()),
            "duplicates": 0,
            "validation_status": "PASS",
        }
    return summary


def save_normalized_data(frame: pd.DataFrame, path: str | Path) -> Path:
    """Atomically save a typed Parquet artifact."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    frame.to_parquet(temporary, index=False, engine="pyarrow")
    temporary.replace(output)
    return output


def _find_manifest(raw_dir: Path) -> Path:
    direct = raw_dir / "download_manifest.json"
    candidates = [direct] if direct.is_file() else list(raw_dir.glob("*/download_manifest.json"))
    if not candidates:
        raise NormalizationError(f"No download_manifest.json below {raw_dir}")
    manifests = []
    for path in candidates:
        content = json.loads(path.read_text(encoding="utf-8"))
        if content.get("status") == "PASS":
            manifests.append((content.get("requested_end_date", ""), path, content))
    if not manifests:
        raise NormalizationError("No successful download manifest found")
    manifests.sort(key=lambda item: (item[0], str(item[1])))
    return manifests[-1][1]


def _report_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# Normalization report",
        "",
        f"Raw-манифест: `{summary['raw_manifest']}`",
        "",
        "Направление: `unit_rate` — количество RUB за 1 единицу валюты получателя. Для отправителя RUB меньшее значение выгоднее, большее — хуже.",
        "",
        "| Валюта | Первая дата | Последняя дата | Строки | Номиналы | Минимальный unit_rate | Медианный unit_rate | Максимальный unit_rate | Дубликаты | Статус валидации |",
        "| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for currency, item in summary["quote_time_by_currency"].items():  # type: ignore[union-attr]
        lines.append(
            f"| {currency} | {item['first_date']} | {item['last_date']} | {item['rows']} | "
            f"{', '.join(map(str, item['nominals_seen']))} | {item['min_unit_rate']:.12g} | "
            f"{item['median_unit_rate']:.12g} | {item['max_unit_rate']:.12g} | "
            f"{item['duplicates']} | {item['validation_status']} |"
        )
    lines.extend(
        [
            "",
            f"Строк в quote-time: `{summary['quote_time_rows']}`. Это только исходные наблюдения.",
            f"Строк в calendar-time: `{summary['calendar_time_rows']}`; строк с forward fill: `{summary['calendar_forward_filled_rows']}`.",
            "",
            "Строки с forward fill сохраняют последнюю официальную котировку, получают `is_new_quote=False`, хранят её дату в `source_quote_date` и календарный возраст в `days_since_new_quote`. Они не считаются новым движением рынка.",
            "",
            "В рамках этапа нормализации ML-признаки и labels не создавались; последующие feature-артефакты описаны отдельно.",
            "",
            "**NORMALIZATION STATUS: PASS**",
            "",
        ]
    )
    return "\n".join(lines)


def run_normalization(raw_dir: str, output_dir: str) -> dict:
    """Read cached CBR raw data, normalize, validate, save Parquet and summarize."""
    raw_root = Path(raw_dir)
    output_root = Path(output_dir)
    manifest_path = _find_manifest(raw_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_items = {item["currency"]: item for item in manifest.get("currencies", [])}
    missing = set(TARGET_CURRENCIES).difference(manifest_items)
    if missing:
        raise NormalizationError(f"Manifest misses currencies: {sorted(missing)}")

    frames = []
    raw_files = []
    for currency in TARGET_CURRENCIES:
        item = manifest_items[currency]
        raw_path = Path(item["raw_filepath"])
        parsed = parse_cbr_raw(
            raw_path,
            currency=currency,
            source_endpoint=item.get("source_endpoint", DEFAULT_ENDPOINT),
            expected_source_identifier=item["internal_source_identifier"],
        )
        normalized = normalize_currency_frame(parsed)
        frames.append(normalized)
        raw_files.append(raw_path.as_posix())

    quote_time = build_quote_time_dataset(frames)
    quote_summary = validate_normalized_data(quote_time, calendar_time=False)
    calendar_time = build_calendar_time_dataset(quote_time)
    validate_normalized_data(calendar_time, calendar_time=True)

    normalized_path = save_normalized_data(quote_time, output_root / "cbr_fx_normalized.parquet")
    quote_path = save_normalized_data(quote_time, output_root / "fx_quote_time.parquet")
    calendar_path = save_normalized_data(calendar_time, output_root / "fx_calendar_time.parquet")
    summary: dict[str, object] = {
        "status": "PASS",
        "raw_manifest": manifest_path.as_posix(),
        "raw_files_read": raw_files,
        "quote_time_rows": int(len(quote_time)),
        "calendar_time_rows": int(len(calendar_time)),
        "calendar_forward_filled_rows": int((~calendar_time["is_new_quote"]).sum()),
        "quote_time_by_currency": quote_summary,
        "outputs": {
            "normalized": normalized_path.as_posix(),
            "quote_time": quote_path.as_posix(),
            "calendar_time": calendar_path.as_posix(),
        },
        "quote_time_sample": quote_time.head(5).to_dict(orient="records"),
        "calendar_filled_sample": calendar_time.loc[~calendar_time["is_new_quote"]].head(5).to_dict(orient="records"),
    }
    report_path = Path("reports/normalization_report.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(_report_markdown(summary), encoding="utf-8", newline="\n")
    summary["report"] = report_path.as_posix()
    return summary


def _json_default(value: object) -> str:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default="data/raw/cbr")
    parser.add_argument("--output-dir", default="data/interim")
    args = parser.parse_args(argv)
    try:
        summary = run_normalization(args.raw_dir, args.output_dir)
    except (NormalizationError, OSError, ValueError) as exc:
        print(f"NORMALIZATION STATUS: FAIL — {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default))
    print("NORMALIZATION STATUS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
