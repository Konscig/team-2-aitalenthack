# Normalization report

Raw manifest: `data/raw/cbr/2019-01-01_2026-09-03/download_manifest.json`

Direction: `unit_rate` is RUB per 1 unit of recipient currency. Lower is better for a RUB sender; higher is worse.

| currency | first_date | last_date | rows | nominals_seen | min_unit_rate | median_unit_rate | max_unit_rate | duplicates | validation_status |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| AMD | 2019-01-10 | 2026-09-03 | 1889 | 100 | 0.124913 | 0.169786 | 0.278846 | 0 | PASS |
| CNY | 2019-01-10 | 2026-09-03 | 1889 | 1, 10 | 7.69846 | 11.2956 | 19.0415 | 0 | PASS |
| EUR | 2019-01-10 | 2026-09-03 | 1889 | 1 | 52.7379 | 88.9677 | 132.9581 | 0 | PASS |
| KGS | 2019-01-10 | 2026-09-03 | 1889 | 10, 100 | 0.643497 | 0.918935 | 1.26242 | 0 | PASS |
| KZT | 2019-01-10 | 2026-09-03 | 1889 | 100 | 0.112176 | 0.171998 | 0.231488 | 0 | PASS |
| TJS | 2019-01-10 | 2026-09-03 | 1889 | 1, 10 | 4.72982 | 7.20563 | 10.6719 | 0 | PASS |
| USD | 2019-01-10 | 2026-09-03 | 1889 | 1 | 51.158 | 75.9246 | 120.3785 | 0 | PASS |
| UZS | 2019-01-10 | 2026-09-03 | 1889 | 1000, 10000 | 0.00473661 | 0.00696259 | 0.0110589 | 0 | PASS |

Quote-time rows: `15112`. These are source observations only.
Calendar-time rows: `22352`; forward-filled rows: `7240`.

Forward-filled rows retain the last official quote, set `is_new_quote=False`, preserve its date in `source_quote_date`, and record calendar age in `days_since_new_quote`. They are not new market movements.

No ML features or labels were created.

**NORMALIZATION STATUS: PASS**
