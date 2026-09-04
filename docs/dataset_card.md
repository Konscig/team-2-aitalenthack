# Dataset card: CBR FX market data and features

Актуально на 2026-09-03. Документ описывает фактически собранные артефакты, а не план будущей реализации.

## Назначение

Датасет подготовлен для исследования моментов трансграничного перевода RUB в TJS, UZS, KGS, AMD и KZT. USD, EUR и CNY используются как опорные валюты для cross-currency и broad RUB признаков. Labels и результаты исполнения клиентского перевода в набор не входят.

Каноническое направление курса:

```text
unit_rate / rate = RUB за 1 единицу валюты получателя
```

Меньшее значение выгоднее отправителю RUB. Курс ЦБ — официальный ориентир, а не фактический курс исполнения банка или сервиса переводов.

## Источник и snapshot

- источник: официальный SOAP web-service Банка России `DailyInfo`;
- endpoint: `https://www.cbr.ru/DailyInfoWebServ/DailyInfo.asmx`;
- справочник: `EnumValutesXML(Seld=false)`;
- история: `GetCursDynamicXML(FromDate, ToDate, ValutaCode)`;
- запрошенный период: `2019-01-01` — `2026-09-03`;
- фактический период: `2019-01-10` — `2026-09-03`;
- валюты: TJS, UZS, KGS, AMD, KZT, USD, EUR, CNY;
- реальные наблюдения: 1 889 на валюту, 15 112 суммарно;
- raw manifest: `data/raw/cbr/2019-01-01_2026-09-03/download_manifest.json`;
- raw SOAP responses: 8 файлов, 2 637 552 байта суммарно;
- timestamp загрузки, параметры, endpoint, внутренние идентификаторы, диапазоны, число строк и SHA-256 каждого ответа сохранены в manifest и request JSON.

Raw XML сохранён без преобразований. Pipeline не обращается к synthetic/mock fallback и завершает работу ошибкой при недоступных или невалидных исходных данных.

## Слои данных

| Файл | Временная ось | Строки | Столбцы | Содержание |
| --- | --- | ---: | ---: | --- |
| `data/interim/cbr_fx_normalized.parquet` | quote-time | 15 112 | 12 | Нормализованные реальные котировки восьми валют |
| `data/interim/fx_quote_time.parquet` | quote-time | 15 112 | 12 | Каноническая копия реальных source observations |
| `data/interim/fx_calendar_time.parquet` | calendar-time | 22 352 | 13 | Восемь полных календарных рядов; 7 240 строк forward fill |
| `data/features/base_market_features.parquet` | quote-time | 9 445 | 67 | 5 коридоров, `date/corridor/rate` и 64 base features |
| `data/features/fx_features_daily.parquet` | quote-time | 9 445 | 104 | Base + 37 reversal/cross-currency/freshness полей |
| `data/features/fx_features_calendar_daily.parquet` | calendar-time | 13 970 | 107 | Полный календарь пяти коридоров; 4 525 добавленных строк |

Несмотря на историческое имя `fx_features_daily.parquet`, его временная ось — реальные quote observations. Для ежедневного календаря следует использовать только `fx_features_calendar_daily.parquet`.

## Нормализация

Исходные `Vnom` и `Vcurs` сохраняются без изменения. `unit_rate` берётся из официального `VunitRate`; при отсутствии поля рассчитывается как `Vcurs / Vnom`. Для строк с обоими представлениями проверяется равенство с абсолютным/относительным допуском `1e-12`.

Фактически обнаружены изменения номиналов во времени:

- CNY: 1 и 10;
- KGS: 10 и 100;
- TJS: 1 и 10;
- UZS: 1 000 и 10 000.

Поэтому использование одного современного номинала для всей истории запрещено.

## Quote-time и calendar-time

Quote-time содержит только реальные даты официальных котировок. Calendar-time добавляет отсутствующие календарные даты causal forward fill последнего известного значения.

В календарных feature-данных:

- `is_new_quote=True` — реальная исходная котировка;
- `is_new_quote=False` — добавленная дата;
- `source_quote_date` — дата последней реальной котировки;
- `days_since_new_quote` — её возраст в календарных днях;
- рыночные признаки на добавленной дате равны последней существовавшей строке;
- freshness USD/EUR/CNY пересчитывается относительно новой календарной даты.

Forward-filled строка не считается новым движением рынка и не должна использоваться как независимое market observation.

## Feature engineering

Base layer содержит returns, log return, SMA и расстояния до SMA, rolling minima/maxima, trailing percentiles и favourability, momentum/streaks, volatility и rolling range. Advanced layer добавляет:

- расстояние в quote observations от rolling minimum;
- fast и two-step reversal для epsilon 0,2%, 0,5% и 1,0%;
- implied recipient/USD и его returns;
- равновзвешенный broad RUB factor по USD/EUR/CNY;
- corridor-specific returns;
- trailing-60 z-score broad factors;
- source quote dates и freshness reference currencies.

Все признаки на T используют только информацию с датой не позже T. Percentile reference исключает текущую строку, z-score использует только предыдущие 60 значений, centered windows и отрицательные shifts отсутствуют. Causality test пройден на 20 случайных парах для base features и на 30 — для advanced features.

## Data quality и EDA

- raw ingestion: PASS;
- normalization: PASS;
- base features: PASS;
- advanced features: PASS;
- полный тестовый набор после calendar expansion: 35 passed;
- дубликаты `currency/date` и `corridor/date`: 0;
- будущие source quote dates: 0;
- неожиданные NaN после проверенных warm-up окон: 0;
- cross-currency identity проверена без расхождения;
- EDA notebook: 37 cells, 18 выполненных code cells, 117 графиков, 0 ошибок;
- EDA выделил 224 потенциально экстремальные строки для ручной сверки с raw-источником; они не удалялись.

Подробности: `reports/raw_data_report.md`, `reports/normalization_report.md`, `reports/base_features_report.md`, `reports/advanced_features_report.md`, `reports/eda_findings.md`.

## Известная избыточность

- `ret_3/5/10/20` точно совпадают с `mom_3/5/10/20`;
- `favourability_percentile_N = 1 - percentile_N`;
- level и rolling features часто сильно коррелируют.

Признаки пока не удалялись: решение должно приниматься внутри modeling pipeline на временной validation-схеме.

## Ограничения и следующий этап

- Labels ещё не созданы, поэтому EDA не доказывает predictive power.
- Датасет не содержит комиссии, спреды, исполнимый курс или факт клиентского перевода.
- История нестационарна; особенно заметен режим высокой волатильности 2022 года.
- Train/validation/test должны делиться только по времени.
- Scaling и feature selection разрешены только на train-периоде.
- Перед моделированием нужно определить label, future horizon, purge/embargo и правила оценки regret/hit rate.
