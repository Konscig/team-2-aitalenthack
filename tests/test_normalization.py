from __future__ import annotations

import unittest

import pandas as pd

from src.normalization import (
    BASE_COLUMNS,
    NormalizationError,
    build_calendar_time_dataset,
    build_quote_time_dataset,
    normalize_currency_frame,
    validate_normalized_data,
)


def parsed_frame(dates=("2024-01-05T00:00:00+03:00", "2024-01-08T00:00:00+03:00")) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date_text": list(dates),
            "currency": ["TJS"] * len(dates),
            "source_identifier": ["official-test-id"] * len(dates),
            "nominal": [10] * len(dates),
            "raw_rate": [100.0 + index for index in range(len(dates))],
            "source_unit_rate": [10.0 + index / 10 for index in range(len(dates))],
            "source": ["Банк России"] * len(dates),
            "source_endpoint": ["https://www.cbr.ru/test-only"] * len(dates),
        }
    )


class NormalizationTests(unittest.TestCase):
    def test_unit_rate_formula(self) -> None:
        frame = parsed_frame(("2024-01-05T00:00:00+03:00",))
        frame["source_unit_rate"] = float("nan")
        normalized = normalize_currency_frame(frame)
        self.assertEqual(normalized.loc[0, "unit_rate"], 10.0)

    def test_unique_currency_date(self) -> None:
        normalized = normalize_currency_frame(parsed_frame())
        duplicate = pd.concat([normalized, normalized.iloc[[0]]], ignore_index=True)
        duplicate = duplicate.sort_values(["currency", "date"], kind="stable").reset_index(drop=True)
        with self.assertRaisesRegex(NormalizationError, r"Duplicate currency\+date"):
            validate_normalized_data(duplicate, minimum_years=0)

    def test_positive_rates(self) -> None:
        normalized = normalize_currency_frame(parsed_frame())
        normalized.loc[0, "raw_rate"] = -1.0
        with self.assertRaisesRegex(NormalizationError, "Non-positive raw_rate"):
            validate_normalized_data(normalized, minimum_years=0)

    def test_quote_time_has_no_generated_dates(self) -> None:
        normalized = normalize_currency_frame(parsed_frame())
        quote_time = build_quote_time_dataset([normalized])
        self.assertEqual(list(quote_time["date"].dt.day), [5, 8])
        self.assertTrue(quote_time["is_new_quote"].all())

    def test_calendar_time_forward_fill(self) -> None:
        calendar = build_calendar_time_dataset(normalize_currency_frame(parsed_frame()))
        sunday = calendar.loc[calendar["date"] == pd.Timestamp("2024-01-07")].iloc[0]
        self.assertFalse(sunday["is_new_quote"])
        self.assertEqual(sunday["unit_rate"], 10.0)

    def test_calendar_time_source_quote_date(self) -> None:
        calendar = build_calendar_time_dataset(normalize_currency_frame(parsed_frame()))
        sunday = calendar.loc[calendar["date"] == pd.Timestamp("2024-01-07")].iloc[0]
        self.assertEqual(sunday["source_quote_date"], pd.Timestamp("2024-01-05"))

    def test_days_since_new_quote(self) -> None:
        calendar = build_calendar_time_dataset(normalize_currency_frame(parsed_frame()))
        ages = calendar.set_index("date")["days_since_new_quote"]
        self.assertEqual(ages[pd.Timestamp("2024-01-05")], 0)
        self.assertEqual(ages[pd.Timestamp("2024-01-07")], 2)
        self.assertEqual(ages[pd.Timestamp("2024-01-08")], 0)

    def test_currency_direction_metadata(self) -> None:
        normalized = normalize_currency_frame(parsed_frame())
        self.assertEqual(normalized.loc[0, "source_currency"], "RUB")
        self.assertEqual(normalized.loc[0, "target_currency"], "TJS")
        self.assertEqual(BASE_COLUMNS[6:8], ["raw_rate", "unit_rate"])


if __name__ == "__main__":
    unittest.main()
