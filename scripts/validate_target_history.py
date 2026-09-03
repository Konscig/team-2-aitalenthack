"""Minimal history-availability smoke test for all required currencies."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from source_discovery import OUT, SOAP_URL, child_text, fetch, local_name, soap_envelope


FROM_DATE = "2024-01-10T00:00:00"
TO_DATE = "2024-01-12T00:00:00"


def main() -> None:
    mapping = json.loads((OUT / "target_currency_mapping.json").read_text(encoding="utf-8"))
    summary = {}
    for iso_code, reference in mapping.items():
        fields = {
            "FromDate": FROM_DATE,
            "ToDate": TO_DATE,
            "ValutaCode": reference["internal_code"],
        }
        method = "GetCursDynamicXML"
        payload = fetch(
            f"availability_{iso_code}_2024-01-10_2024-01-12.soap.xml",
            SOAP_URL,
            method="POST",
            body=soap_envelope(method, fields),
            headers={
                "Content-Type": "text/xml; charset=utf-8",
                "SOAPAction": f'"http://web.cbr.ru/{method}"',
            },
            params=fields,
        )
        root = ET.fromstring(payload)
        rows = [element for element in root.iter() if local_name(element.tag) == "ValuteCursDynamic"]
        if not rows:
            raise RuntimeError(f"No historical observations returned for {iso_code}")
        required = ("CursDate", "Vcode", "Vnom", "Vcurs", "VunitRate")
        missing = [field for field in required if child_text(rows[0], field) is None]
        if missing:
            raise RuntimeError(f"Missing fields for {iso_code}: {missing}")
        summary[iso_code] = {
            "observation_count": len(rows),
            "first_date": child_text(rows[0], "CursDate"),
            "last_date": child_text(rows[-1], "CursDate"),
            "fields": list(required),
        }
    path = OUT / "target_history_availability.json"
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite {path}")
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
