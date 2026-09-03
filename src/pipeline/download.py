from __future__ import annotations

import csv
import hashlib
import json
import logging
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from . import __version__


LOGGER = logging.getLogger(__name__)
SOAP_ENDPOINT = "https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx"
SOAP_NAMESPACE = "http://web.cbr.ru/"
TARGET_CURRENCIES = ("TJS", "UZS", "KGS", "AMD", "KZT", "USD", "EUR", "CNY")
REFERENCE_FIELDS = (
    "internal_code",
    "name",
    "english_name",
    "nominal",
    "common_code",
    "iso_numeric_code",
    "iso_char_code",
)
HISTORY_FIELDS = ("CursDate", "Vcode", "Vnom", "Vcurs", "VunitRate")
UNIT_RATE_TOLERANCE = Decimal("1e-12")


class IngestionError(RuntimeError):
    """Fatal ingestion or raw-data validation failure."""


@dataclass(frozen=True)
class DownloadConfig:
    start_date: date
    end_date: date | None
    raw_root: Path
    reference_file: Path
    report_file: Path
    timeout_seconds: float
    max_attempts: int
    backoff_seconds: float
    force_download: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if local_name(child.tag) == name:
            return (child.text or "").strip()
    return None


def soap_envelope(method: str, parameters: dict[str, str]) -> bytes:
    serialized = "".join(f"<{key}>{value}</{key}>" for key, value in parameters.items())
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<soap:Body><{method} xmlns="{SOAP_NAMESPACE}">{serialized}</{method}></soap:Body>'
        '</soap:Envelope>'
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def fetch_soap(
    *,
    method: str,
    parameters: dict[str, str],
    raw_path: Path,
    metadata_path: Path,
    config: DownloadConfig,
) -> tuple[bytes, dict[str, object]]:
    if raw_path.exists() and not config.force_download:
        if not metadata_path.exists():
            raise IngestionError(f"Cached raw file has no metadata: {raw_path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        actual_checksum = sha256_file(raw_path)
        if actual_checksum != metadata.get("checksum_sha256"):
            raise IngestionError(f"Cached checksum mismatch: {raw_path}")
        if metadata.get("request_parameters") != parameters or metadata.get("soap_method") != method:
            raise IngestionError(f"Cached request metadata does not match requested call: {raw_path}")
        LOGGER.info("cache_hit path=%s bytes=%d", raw_path, raw_path.stat().st_size)
        return raw_path.read_bytes(), metadata

    request_body = soap_envelope(method, parameters)
    request = urllib.request.Request(
        SOAP_ENDPOINT,
        data=request_body,
        method="POST",
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{SOAP_NAMESPACE}{method}"',
            "User-Agent": f"aitalenthack-cbr-pipeline/{__version__}",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, config.max_attempts + 1):
        requested_at = utc_now()
        try:
            LOGGER.info("download_start method=%s attempt=%d parameters=%s", method, attempt, parameters)
            with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
                payload = response.read()
                status = response.status
                response_headers = dict(response.headers.items())
            if status != 200:
                raise IngestionError(f"CBR returned HTTP {status} for {method}")
            if not payload:
                raise IngestionError(f"CBR returned empty response for {method}")
            # Store the exact response bytes before any XML parsing.
            atomic_write_bytes(raw_path, payload)
            checksum = sha256_file(raw_path)
            metadata: dict[str, object] = {
                "source": "Банк России",
                "source_endpoint": SOAP_ENDPOINT,
                "http_method": "POST",
                "soap_method": method,
                "soap_action": f"{SOAP_NAMESPACE}{method}",
                "request_parameters": parameters,
                "requested_at_utc": requested_at,
                "download_timestamp_utc": utc_now(),
                "http_status": status,
                "response_headers": response_headers,
                "response_bytes": len(payload),
                "raw_filepath": raw_path.as_posix(),
                "checksum_sha256": checksum,
            }
            atomic_write_text(metadata_path, json.dumps(metadata, ensure_ascii=False, indent=2))
            LOGGER.info("download_complete method=%s path=%s bytes=%d", method, raw_path, len(payload))
            return payload, metadata
        except (urllib.error.URLError, TimeoutError, OSError, IngestionError) as exc:
            last_error = exc
            LOGGER.warning("download_attempt_failed method=%s attempt=%d error=%s", method, attempt, exc)
            if attempt < config.max_attempts:
                delay = config.backoff_seconds * (2 ** (attempt - 1))
                LOGGER.info("retry_backoff method=%s seconds=%.2f", method, delay)
                time.sleep(delay)
    raise IngestionError(f"CBR request {method} failed after {config.max_attempts} attempts: {last_error}")


def parse_xml(payload: bytes, context: str) -> ET.Element:
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise IngestionError(f"Invalid XML in {context}: {exc}") from exc


def parse_latest_date(payload: bytes) -> date:
    root = parse_xml(payload, "GetLatestDateTime")
    values = [
        (element.text or "").strip()
        for element in root.iter()
        if local_name(element.tag) == "GetLatestDateTimeResult"
    ]
    if len(values) != 1:
        raise IngestionError(f"Expected one latest-date value, got {values}")
    try:
        return datetime.fromisoformat(values[0]).date()
    except ValueError as exc:
        raise IngestionError(f"Invalid latest date returned by CBR: {values[0]!r}") from exc


def parse_reference(payload: bytes) -> list[dict[str, str]]:
    root = parse_xml(payload, "EnumValutesXML")
    rows: list[dict[str, str]] = []
    source_names = {
        "Vcode": "internal_code",
        "Vname": "name",
        "VEngname": "english_name",
        "Vnom": "nominal",
        "VcommonCode": "common_code",
        "VnumCode": "iso_numeric_code",
        "VcharCode": "iso_char_code",
    }
    for element in root.iter():
        if local_name(element.tag) != "EnumValutes":
            continue
        row = {target: child_text(element, source) or "" for source, target in source_names.items()}
        if all(row[field] for field in REFERENCE_FIELDS):
            rows.append(row)
    if not rows:
        raise IngestionError("EnumValutesXML returned no complete currency records")
    return rows


def select_target_codes(reference: Iterable[dict[str, str]]) -> dict[str, str]:
    by_iso: dict[str, list[dict[str, str]]] = {code: [] for code in TARGET_CURRENCIES}
    for row in reference:
        if row["iso_char_code"] in by_iso:
            by_iso[row["iso_char_code"]].append(row)
    selected: dict[str, str] = {}
    for iso_code, candidates in by_iso.items():
        if not candidates:
            raise IngestionError(f"Currency {iso_code} absent from official CBR reference")
        canonical = [row for row in candidates if row["internal_code"] == row["common_code"]]
        choices = canonical or candidates
        unique = sorted({row["internal_code"] for row in choices})
        if len(unique) != 1:
            raise IngestionError(f"Ambiguous current CBR mapping for {iso_code}: {unique}")
        selected[iso_code] = unique[0]
    return selected


def write_reference_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REFERENCE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def positive_decimal(text: str | None, field: str, currency: str, row_date: str) -> Decimal:
    if text is None:
        raise IngestionError(f"Missing {field} for {currency} on {row_date}")
    try:
        value = Decimal(text.replace(",", "."))
    except InvalidOperation as exc:
        raise IngestionError(f"Invalid {field} for {currency} on {row_date}: {text!r}") from exc
    if not value.is_finite() or value <= 0:
        raise IngestionError(f"Non-positive {field} for {currency} on {row_date}: {text!r}")
    return value


def validate_history(
    payload: bytes,
    *,
    currency: str,
    expected_code: str,
    requested_start: date,
    requested_end: date,
    allowed_codes: set[str],
) -> dict[str, object]:
    root = parse_xml(payload, currency)
    parsed_rows: list[tuple[date, str]] = []
    for element in root.iter():
        if local_name(element.tag) != "ValuteCursDynamic":
            continue
        values = {field: child_text(element, field) for field in HISTORY_FIELDS}
        missing = [field for field, value in values.items() if not value]
        if missing:
            raise IngestionError(f"Missing fields {missing} in {currency} history")
        try:
            row_datetime = datetime.fromisoformat(values["CursDate"] or "")
        except ValueError as exc:
            raise IngestionError(f"Invalid CursDate for {currency}: {values['CursDate']!r}") from exc
        row_date = row_datetime.date()
        if not requested_start <= row_date <= requested_end:
            raise IngestionError(f"Out-of-range date for {currency}: {row_date}")
        row_code = values["Vcode"] or ""
        if row_code not in allowed_codes:
            raise IngestionError(
                f"Unexpected source identifier for {currency}: {row_code}; requested {expected_code}"
            )
        nominal = positive_decimal(values["Vnom"], "Vnom", currency, str(row_date))
        raw_rate = positive_decimal(values["Vcurs"], "Vcurs", currency, str(row_date))
        unit_rate = positive_decimal(values["VunitRate"], "VunitRate", currency, str(row_date))
        calculated_unit_rate = raw_rate / nominal
        allowed_difference = max(UNIT_RATE_TOLERANCE, abs(calculated_unit_rate) * UNIT_RATE_TOLERANCE)
        if abs(calculated_unit_rate - unit_rate) > allowed_difference:
            raise IngestionError(
                f"VunitRate != Vcurs/Vnom for {currency} on {row_date}: "
                f"{unit_rate} != {raw_rate}/{nominal} within tolerance {allowed_difference}"
            )
        parsed_rows.append((row_date, row_code))
    if not parsed_rows:
        raise IngestionError(f"No records returned for {currency}")
    dates = [item[0] for item in parsed_rows]
    if len(dates) != len(set(dates)):
        raise IngestionError(f"Duplicate dates in {currency} raw response")
    if dates != sorted(dates):
        raise IngestionError(f"Dates are not sorted for {currency}")
    if (dates[-1] - dates[0]).days < 5 * 365:
        raise IngestionError(
            f"Less than five years for {currency}: {dates[0]}..{dates[-1]}"
        )
    return {
        "actual_first_date": dates[0].isoformat(),
        "actual_last_date": dates[-1].isoformat(),
        "row_count": len(dates),
        "observed_internal_codes": sorted({item[1] for item in parsed_rows}),
    }


def reference_codes_for_currency(reference: Iterable[dict[str, str]], currency: str, common_code: str) -> set[str]:
    codes = {
        row["internal_code"]
        for row in reference
        if row["iso_char_code"] == currency or row["common_code"] == common_code
    }
    codes.add(common_code)
    return codes


def write_report(path: Path, manifest: dict[str, object]) -> None:
    lines = [
        "# Raw data ingestion report",
        "",
        f"Сформирован (UTC): `{manifest['created_at_utc']}`",
        f"Источник: `{manifest['source_endpoint']}`",
        f"Запрошенный период: `{manifest['requested_start_date']}` — `{manifest['requested_end_date']}`",
        "",
        "| Валюта | Внутренний ID | Фактический период | Строки | Байты | SHA-256 | Raw-файл |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for item in manifest["currencies"]:  # type: ignore[index]
        lines.append(
            "| {currency} | {internal_source_identifier} | {actual_first_date} — {actual_last_date} | "
            "{row_count} | {file_size_bytes} | `{checksum_sha256}` | `{raw_filepath}` |".format(**item)
        )
    lines.extend(
        [
            "",
            "## Проверки raw-данных",
            "",
            "- Все файлы непустые; после побайтового сохранения для них рассчитаны контрольные суммы.",
            "- Идентификаторы валют соответствуют динамически полученному официальному справочнику.",
            "- Даты присутствуют, уникальны, упорядочены и находятся внутри запрошенного периода.",
            "- Значения `Vnom`, `Vcurs` и `VunitRate` положительны во всех строках.",
            "- Для каждой валюты доступно не менее пяти лет истории.",
            "- `VunitRate` равен `Vcurs / Vnom` в пределах абсолютного/относительного допуска `1e-12`;",
            "  допуск учитывает только погрешность представления чисел в SOAP и не изменяет raw-значения.",
            "- На этом этапе не создавались нормализованные наборы, признаки или labels.",
            "",
            "**RAW INGESTION: PASS**",
        ]
    )
    atomic_write_text(path, "\n".join(lines) + "\n")


def run_download(config: DownloadConfig) -> Path:
    if config.start_date > date.today():
        raise IngestionError("start date cannot be in the future")
    if config.end_date and config.end_date < config.start_date:
        raise IngestionError("end date must be on or after start date")
    if config.timeout_seconds <= 0 or config.max_attempts < 1 or config.backoff_seconds < 0:
        raise IngestionError("invalid retry/timeout configuration")

    config.raw_root.mkdir(parents=True, exist_ok=True)
    latest_payload, _ = fetch_soap(
        method="GetLatestDateTime",
        parameters={},
        raw_path=config.raw_root / "latest_date.response.xml",
        metadata_path=config.raw_root / "latest_date.request.json",
        config=config,
    )
    latest_date = parse_latest_date(latest_payload)
    requested_end = config.end_date or latest_date
    if requested_end > latest_date:
        raise IngestionError(
            f"requested end {requested_end} is after latest CBR date {latest_date}"
        )

    reference_payload, _ = fetch_soap(
        method="EnumValutesXML",
        parameters={"Seld": "false"},
        raw_path=config.raw_root / "currency_reference.response.xml",
        metadata_path=config.raw_root / "currency_reference.request.json",
        config=config,
    )
    reference = parse_reference(reference_payload)
    target_codes = select_target_codes(reference)
    write_reference_csv(config.reference_file, reference)

    snapshot_dir = config.raw_root / f"{config.start_date}_{requested_end}"
    manifest_items: list[dict[str, object]] = []
    for currency in TARGET_CURRENCIES:
        internal_code = target_codes[currency]
        parameters = {
            "FromDate": f"{config.start_date.isoformat()}T00:00:00",
            "ToDate": f"{requested_end.isoformat()}T00:00:00",
            "ValutaCode": internal_code,
        }
        raw_path = snapshot_dir / f"{currency}.response.xml"
        metadata_path = snapshot_dir / f"{currency}.request.json"
        payload, metadata = fetch_soap(
            method="GetCursDynamicXML",
            parameters=parameters,
            raw_path=raw_path,
            metadata_path=metadata_path,
            config=config,
        )
        checks = validate_history(
            payload,
            currency=currency,
            expected_code=internal_code,
            requested_start=config.start_date,
            requested_end=requested_end,
            allowed_codes=reference_codes_for_currency(reference, currency, internal_code),
        )
        manifest_items.append(
            {
                "currency": currency,
                "internal_source_identifier": internal_code,
                "requested_start_date": config.start_date.isoformat(),
                "requested_end_date": requested_end.isoformat(),
                **checks,
                "source_endpoint": SOAP_ENDPOINT,
                "request_parameters": parameters,
                "raw_filepath": raw_path.as_posix(),
                "download_timestamp_utc": metadata["download_timestamp_utc"],
                "row_count": checks["row_count"],
                "file_size_bytes": raw_path.stat().st_size,
                "checksum_sha256": metadata["checksum_sha256"],
            }
        )
        LOGGER.info(
            "raw_check_pass currency=%s rows=%s range=%s..%s",
            currency,
            checks["row_count"],
            checks["actual_first_date"],
            checks["actual_last_date"],
        )

    manifest: dict[str, object] = {
        "manifest_version": "1.0",
        "pipeline_version": __version__,
        "status": "PASS",
        "created_at_utc": utc_now(),
        "source": "Банк России",
        "source_endpoint": SOAP_ENDPOINT,
        "reference_method": "EnumValutesXML",
        "history_method": "GetCursDynamicXML",
        "requested_start_date": config.start_date.isoformat(),
        "requested_end_date": requested_end.isoformat(),
        "latest_cbr_date_at_download": latest_date.isoformat(),
        "currency_reference_file": config.reference_file.as_posix(),
        "currencies": manifest_items,
    }
    manifest_path = snapshot_dir / "download_manifest.json"
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    write_report(config.report_file, manifest)
    return manifest_path
