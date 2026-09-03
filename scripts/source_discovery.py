"""Small reproducible source-discovery probe for official Bank of Russia data.

This is intentionally not the production downloader. It fetches only a currency
reference, ten calendar days of USD history, and the matching public HTML page.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


BASE = "https://www.cbr.ru"
SOAP_URL = f"{BASE}/DailyInfoWebServ/DailyInfo.asmx"
OUT = Path("data/raw/source_discovery")
TARGETS = ("TJS", "UZS", "KGS", "AMD", "KZT", "USD", "EUR", "CNY")
FROM_DATE = "2024-01-10T00:00:00"
TO_DATE = "2024-01-19T00:00:00"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def soap_envelope(method: str, fields: dict[str, str]) -> bytes:
    params = "".join(f"<{key}>{value}</{key}>" for key, value in fields.items())
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<soap:Body><{method} xmlns="http://web.cbr.ru/">{params}</{method}></soap:Body>'
        '</soap:Envelope>'
    ).encode("utf-8")


def fetch(name: str, url: str, *, method: str = "GET", body: bytes | None = None,
          headers: dict[str, str] | None = None, params: dict[str, str] | None = None) -> bytes:
    requested_at = now_utc()
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
        status = response.status
        response_headers = dict(response.headers.items())
    if status != 200 or not payload:
        raise RuntimeError(f"CBR request failed: status={status}, bytes={len(payload)}")
    OUT.mkdir(parents=True, exist_ok=True)
    raw_path = OUT / name
    metadata_path = OUT / f"{name}.metadata.json"
    if raw_path.exists() or metadata_path.exists():
        raise FileExistsError(
            f"Refusing to overwrite immutable discovery artifact: {raw_path}. "
            "Use a clean checkout or change OUT for a new discovery run."
        )
    raw_path.write_bytes(payload)
    metadata = {
        "source": "Банк России",
        "url": url,
        "http_method": method,
        "soap_action": (headers or {}).get("SOAPAction"),
        "request_parameters": params or {},
        "requested_at_utc": requested_at,
        "received_at_utc": now_utc(),
        "http_status": status,
        "response_headers": response_headers,
        "response_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "raw_file": raw_path.as_posix(),
    }
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def child_text(element: ET.Element, field: str) -> str | None:
    for child in element:
        if local_name(child.tag) == field:
            return (child.text or "").strip()
    return None


def main() -> None:
    enum_method = "EnumValutesXML"
    enum_fields = {"Seld": "false"}
    enum_payload = fetch(
        "enum_valutes.xml",
        SOAP_URL,
        method="POST",
        body=soap_envelope(enum_method, enum_fields),
        headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"http://web.cbr.ru/{enum_method}"'},
        params=enum_fields,
    )
    enum_root = ET.fromstring(enum_payload)
    mapping: dict[str, dict[str, str]] = {}
    for element in enum_root.iter():
        if local_name(element.tag) != "EnumValutes":
            continue
        char_code = child_text(element, "VcharCode")
        code = child_text(element, "Vcode")
        if char_code and code:
            mapping[char_code] = {
                "internal_code": code,
                "name": child_text(element, "Vname") or "",
                "english_name": child_text(element, "VEngname") or "",
                "nominal": child_text(element, "Vnom") or "",
                "numeric_code": child_text(element, "VnumCode") or "",
                "common_code": child_text(element, "VcommonCode") or "",
            }
    missing = [code for code in TARGETS if code not in mapping]
    if missing:
        raise RuntimeError(f"Required currencies absent from CBR EnumValutesXML: {missing}")

    selected = {code: mapping[code] for code in TARGETS}
    (OUT / "target_currency_mapping.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    usd_internal_code = mapping["USD"]["internal_code"]
    dynamic_method = "GetCursDynamicXML"
    dynamic_fields = {
        "FromDate": FROM_DATE,
        "ToDate": TO_DATE,
        "ValutaCode": usd_internal_code,
    }
    dynamic_payload = fetch(
        "usd_2024-01-10_2024-01-19.soap.xml",
        SOAP_URL,
        method="POST",
        body=soap_envelope(dynamic_method, dynamic_fields),
        headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": f'"http://web.cbr.ru/{dynamic_method}"'},
        params=dynamic_fields,
    )
    dynamic_root = ET.fromstring(dynamic_payload)
    rows = []
    for element in dynamic_root.iter():
        if local_name(element.tag) != "ValuteCursDynamic":
            continue
        row = {field: child_text(element, field) for field in ("CursDate", "Vcode", "Vnom", "Vcurs", "VunitRate")}
        if all(row.values()):
            calculated = Decimal(row["Vcurs"]) / Decimal(row["Vnom"])
            if calculated != Decimal(row["VunitRate"]):
                raise RuntimeError(f"VunitRate mismatch: {row}")
            rows.append(row)
    if len(rows) < 3:
        raise RuntimeError(f"Expected at least 3 USD observations, got {len(rows)}")
    (OUT / "usd_parsed_check.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    page_params = {
        "UniDbQuery.Posted": "True",
        "UniDbQuery.mode": "1",
        "UniDbQuery.VAL_NM_RQ": usd_internal_code,
        "UniDbQuery.From": "10.01.2024",
        "UniDbQuery.To": "19.01.2024",
    }
    page_url = f"{BASE}/currency_base/dynamics/?{urllib.parse.urlencode(page_params)}"
    html_payload = fetch("usd_public_page.html", page_url, params=page_params)
    html_text = html_payload.decode("utf-8", errors="strict")
    public_values = {}
    for row in rows:
        day = datetime.fromisoformat(row["CursDate"]).strftime("%d.%m.%Y")
        raw_value = Decimal(row["Vcurs"])
        candidates = {str(raw_value).replace(".", ","), f"{raw_value:.4f}".replace(".", ",")}
        if day in html_text and any(candidate in html_text for candidate in candidates):
            public_values[day] = str(raw_value)
    if len(public_values) < 3:
        # Keep raw HTML for diagnosis; never claim validation if the page cannot be matched.
        raise RuntimeError(f"Could not match 3 SOAP values on CBR public page; matched {public_values}")

    summary = {
        "target_currencies_found": selected,
        "usd_observation_count": len(rows),
        "usd_fields": list(rows[0]),
        "first_three_usd_rows": rows[:3],
        "public_page_matches": dict(list(public_values.items())[:3]),
    }
    (OUT / "validation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
