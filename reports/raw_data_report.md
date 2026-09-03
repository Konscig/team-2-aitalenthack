# Raw data ingestion report

Generated UTC: `2026-09-03T09:49:37.155602+00:00`  
Source: `https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx`  
Requested range: `2019-01-01` — `2026-09-03`

| Currency | Internal ID | Actual range | Rows | Bytes | SHA-256 | Raw file |
| --- | --- | --- | ---: | ---: | --- | --- |
| TJS | R01670 | 2019-01-10 — 2026-09-03 | 1889 | 330636 | `3429cbd9f246a5f14c8c4fd9f9c37312d3bea34e082b5c8022ea5dbbcc732652` | `data/raw/cbr/2019-01-01_2026-09-03/TJS.response.xml` |
| UZS | R01717 | 2019-01-10 — 2026-09-03 | 1889 | 338300 | `14afbb2314f3b547c0b42fd2894bbf4d4608209092f67a081e8a29b4a43f423d` | `data/raw/cbr/2019-01-01_2026-09-03/UZS.response.xml` |
| KGS | R01370 | 2019-01-10 — 2026-09-03 | 1889 | 329913 | `942735ebd615fade772585fc74a2948274bb340167779d4d617338f28a438419` | `data/raw/cbr/2019-01-01_2026-09-03/KGS.response.xml` |
| AMD | R01060 | 2019-01-10 — 2026-09-03 | 1889 | 330783 | `72b8b9faae82387e53704e15298abb9a678e3d5d8bd0e6ef74c0cf0069426ed1` | `data/raw/cbr/2019-01-01_2026-09-03/AMD.response.xml` |
| KZT | R01335 | 2019-01-10 — 2026-09-03 | 1889 | 330837 | `af9424e3a06daac96a349c9eab2aad898c6d66a84c0ea307ead60b8e366dfa25` | `data/raw/cbr/2019-01-01_2026-09-03/KZT.response.xml` |
| USD | R01235 | 2019-01-10 — 2026-09-03 | 1889 | 325191 | `a15af1f12f9efa710af335bbfa69369bd7f2a03e85b56eb69edcb4c0aa7979cd` | `data/raw/cbr/2019-01-01_2026-09-03/USD.response.xml` |
| EUR | R01239 | 2019-01-10 — 2026-09-03 | 1889 | 325585 | `a39c2afec94b1bb10c5787868dd7b17f83ac514777d4ab6137340cd564929114` | `data/raw/cbr/2019-01-01_2026-09-03/EUR.response.xml` |
| CNY | R01375 | 2019-01-10 — 2026-09-03 | 1889 | 326307 | `905ff3989cf578f6e47581c3057bcc540144b7c47468fda033536822206359a5` | `data/raw/cbr/2019-01-01_2026-09-03/CNY.response.xml` |

## Raw checks

- All files are non-empty and checksummed after byte-for-byte storage.
- Currency identifiers match the dynamic official reference mapping.
- Dates are present, unique, ordered and inside the requested interval.
- `Vnom`, `Vcurs` and `VunitRate` are positive in every row.
- Every currency covers at least five years.
- `VunitRate` equals `Vcurs / Vnom` within absolute/relative tolerance `1e-12`; 
  this permits only SOAP floating-representation tails and does not alter raw values.
- No normalization dataset, features or labels were created in this stage.

**RAW INGESTION: PASS**
