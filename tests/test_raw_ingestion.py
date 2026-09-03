from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path

from src.pipeline.download import (
    IngestionError,
    parse_latest_date,
    parse_reference,
    select_target_codes,
    validate_history,
)


DISCOVERY = Path("data/raw/source_discovery")


class RecordedOfficialRawTests(unittest.TestCase):
    """Tests use only recorded official CBR responses from source discovery."""

    def test_reference_resolves_all_target_codes(self) -> None:
        payload = (DISCOVERY / "enum_valutes.xml").read_bytes()
        mapping = select_target_codes(parse_reference(payload))
        self.assertEqual(set(mapping), {"TJS", "UZS", "KGS", "AMD", "KZT", "USD", "EUR", "CNY"})

    def test_short_history_fails_five_year_coverage_check(self) -> None:
        payload = (DISCOVERY / "availability_USD_2024-01-10_2024-01-12.soap.xml").read_bytes()
        with self.assertRaisesRegex(IngestionError, "Less than five years"):
            validate_history(
                payload,
                currency="USD",
                expected_code="R01235",
                requested_start=date(2024, 1, 10),
                requested_end=date(2024, 1, 12),
                allowed_codes={"R01235"},
            )

    def test_latest_date_parser_rejects_wrong_payload(self) -> None:
        payload = (DISCOVERY / "availability_USD_2024-01-10_2024-01-12.soap.xml").read_bytes()
        with self.assertRaisesRegex(IngestionError, "Expected one latest-date"):
            parse_latest_date(payload)


if __name__ == "__main__":
    unittest.main()
