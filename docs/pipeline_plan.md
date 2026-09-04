# План воспроизводимого FX pipeline

Документ первоначально описывал целевую архитектуру. На 2026-09-03 реализованы
source discovery, production ingestion, нормализация, base features, reversal и
cross-currency features, календарное расширение и EDA. Labels, temporal split,
backtest и модели пока не создавались. Фактический паспорт артефактов находится
в [`dataset_card.md`](dataset_card.md).

## Реализованная структура

Data/ML-контур добавлен рядом с продуктовыми документами без перемещения
существующих артефактов:

```text
data/
  raw/cbr/         # неизменённые SOAP responses, requests и manifest
  reference/       # справочник валют ЦБ
  interim/         # quote-time и calendar-time нормализованные данные
  features/        # base, advanced и calendar-expanded features
src/
  pipeline/        # CLI и ingestion
  normalization.py
  features/
    base_features.py
    advanced_features.py
    calendar_features.py
tests/
  test_raw_ingestion.py
  test_normalization.py
  test_base_features.py
  test_advanced_features.py
  test_calendar_features.py
reports/
  raw_data_report.md
  normalization_report.md
  base_features_report.md
  advanced_features_report.md
  eda_findings.md
notebooks/
  01_fx_features_eda.ipynb
docs/
  source_research.md
  pipeline_plan.md
  dataset_card.md
scripts/
  source_discovery.py
  validate_target_history.py
```

`data/raw/source_discovery/` содержит ограниченные проверочные артефакты этапа
discovery. Полный production snapshot хранится отдельно в
`data/raw/cbr/2019-01-01_2026-09-03/` и покрывает более семи с половиной лет.

## Этапы и зависимости

1. **Конфигурация запуска.** Явные start/end, ISO-коды, версия схемы, run ID и
   output root. Даты не должны неявно зависеть от «сегодня», если нужен
   повторяемый snapshot.
2. **Reference discovery.** Вызвать `EnumValutesXML(Seld=false)`, сохранить raw
   XML и provenance, затем разрешить ISO → `Vcode`. Если код не найден или
   неоднозначен — fail fast.
3. **Raw ingestion.** Для каждого полученного `Vcode` вызвать
   `GetCursDynamicXML` за заданный интервал. Ответ сначала атомарно сохранить
   byte-for-byte вместе с SHA-256 и metadata; только затем парсить. Нет
   HTML-scraping и нет synthetic fallback.
4. **Schema/data-quality validation.** Проверить HTTP status, XML, обязательные
   поля, типы, диапазон дат, положительные `Vnom/Vcurs/VunitRate`, уникальность
   `(currency, date)`, монотонность дат и тождество
   `VunitRate = Vcurs / Vnom` с абсолютным/относительным допуском `1e-12`
   только для хвостов числового представления SOAP. Пустой ряд — ошибка.
5. **Normalization.** Сформировать tidy table, сохранив raw rate и nominal:
   `rub_per_fx = VunitRate`; при необходимости `fx_per_rub = 1 / VunitRate`.
   Канонический quote-time ряд не расширять. Отдельно сформировать calendar-time
   представление causal forward fill с `is_new_quote`, `source_quote_date` и
   `days_since_new_quote`. Результаты сохраняются в `data/interim/`.
6. **Feature engineering — реализовано.** Base, reversal и cross-currency
   признаки рассчитаны по quote-time. Любая строка T использует только значения
   с timestamp `<= T`; rolling только trailing, `center=False`. Causality tests
   пройдены. Scaling пока не применяется.
7. **Labels — отдельный будущий этап.** Future horizon разрешен только здесь.
   Labels сохраняются физически отдельно и присоединяются к features после
   temporal split. Хвост без полного горизонта исключается, а не заполняется.
8. **Temporal validation — следующий этап.** Разбиение train/validation/test только по времени,
   желательно с purge/embargo размером не меньше label horizon. Метрики и DQ
   reports сохраняются с manifest запуска.

Зависимости образуют направленный граф:

```text
config
  -> reference raw -> reference mapping
  -> FX raw -> validation -> interim normalized
  -> features -------------------------------> temporal dataset
  -> labels (future only) -> temporal split --^
```

Ни один downstream-этап не должен обращаться к сети: он читает immutable raw
snapshot выбранного run. Это позволяет повторить transformation независимо от
изменений внешнего источника.

## Реализованные файлы и контракты

Текущий зафиксированный production run:

```text
data/raw/cbr/2019-01-01_2026-09-03/download_manifest.json
data/raw/cbr/2019-01-01_2026-09-03/<ISO>.response.xml
data/raw/cbr/2019-01-01_2026-09-03/<ISO>.request.json
data/reference/cbr_currency_codes.csv
data/interim/cbr_fx_normalized.parquet
data/interim/fx_quote_time.parquet
data/interim/fx_calendar_time.parquet
data/features/base_market_features.parquet
data/features/fx_features_daily.parquet
data/features/fx_features_calendar_daily.parquet
```

Request metadata должны включать source, endpoint, method/SOAPAction, параметры,
время запроса/получения UTC, HTTP status, response headers, размер и SHA-256.
Manifest связывает hashes raw-файлов, версию кода/config и все производные
артефакты. Формат Parquet предлагается для typed schema; CSV может создаваться
только как экспорт, не как каноническое хранилище типов.

## Data quality risks

- изменение внутреннего `Vcode`, названия, ISO-кода или `Vnom`;
- несколько исторических версий одной валюты — учитывать `VcommonCode` и
  проверять покрытие интервала, а не подменять код вручную;
- даты действия курса не образуют ежедневный календарь; отсутствие даты не
  равно отсутствующему случайному значению и не должно автоматически
  forward-fill'иться;
- ревизия исторических данных ЦБ: raw snapshots и SHA-256 обязательны;
- decimal comma/point, timezone `+03:00`, XML namespaces и кодировка;
- дубликаты или частичный ответ при сетевой ошибке;
- `VunitRate` и `Vcurs/Vnom` могут иметь различный scale представления при
  одинаковом числовом значении; фактически встречается, например,
  `7.1096400000000006` вместо `7.10964`;
- официальный курс ЦБ может отличаться от клиентского курса банка.

При любом нарушении обязательного контракта pipeline завершается явной ошибкой.
Ни среднее, ни случайное значение, ни mock dataset не используются как замена.

## Leakage risks и защиты

- **Centered rolling / future window:** запрещены; граница окна заканчивается T.
- **Global scaling:** scaler fit только на train-period, параметры сохраняются.
- **Полный-период percentile/quantile:** запрещен; только expanding/trailing до T
  либо параметры, обученные на прошлом train-period.
- **Backfill:** перенос будущего курса назад запрещен. Решение об использовании
  последнего опубликованного курса для календарной даты требует отдельной
  модели `available_at` и не считается заполнением raw-ряда.
- **Labels рядом с features:** физически раздельные таблицы и строгий allowlist
  feature columns.
- **Пересекающийся label horizon:** temporal split с purge/embargo.
- **Публикационное время:** `CursDate` не обязательно равно моменту, когда курс
  стал доступен пользователю. До моделирования сигналов необходимо определить
  и документировать `available_at`; иначе возможно скрытое использование еще
  не опубликованного на момент решения значения.
- **Ревизии источника:** воспроизводить обучение по зафиксированному raw snapshot,
  а не заново скачанному изменяемому ответу.

## Проверки будущих этапов

- unit tests формул на малых фрагментах записанных официальных ответов;
- integration smoke test официального endpoint, запускаемый отдельно;
- schema, uniqueness, coverage, nominal-change и cross-field checks;
- тест-инвариант: изменение строк после T не меняет features на T;
- тест-инвариант: label-колонки отсутствуют в feature artifact;
- повторный transformation одного raw snapshot дает те же hashes outputs.

Синтетические числовые курсы не нужны даже для тестов: fixtures следует вырезать
из сохраненных официальных raw-ответов с обязательной ссылкой на источник и
hash исходного файла.
