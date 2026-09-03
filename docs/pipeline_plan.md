# План воспроизводимого FX pipeline

Документ описывает целевую архитектуру. На этапе 1 реализован только
source-discovery probe; production ingestion, normalization, features и labels
еще не создавались.

## Почему нужна новая структура

Текущий repository содержит продуктовый brief, context pack, интервью, персоны,
user story map и скриншоты, но не имеет data/ML-кода и соглашений о хранении
данных. Эти артефакты остаются на верхнем уровне без перемещения, чтобы не
ломать существующие ссылки и работу команды. Новый pipeline добавляется рядом
как изолированный контур.

```text
data/
  raw/             # immutable byte-for-byte responses + request metadata
  reference/       # versioned parsed currency mappings
  interim/         # validated and normalized observations
  features/        # past/current-only feature tables
  labels/          # future-dependent targets, physically separate
src/
  cbr_fx/
    config.py
    cbr_client.py
    provenance.py
    schemas.py
    validate.py
    normalize.py
    features.py
    labels.py
    cli.py
tests/
  unit/
  integration/
  fixtures/        # small recorded official responses, never invented rates
reports/
  data_quality/
  validation/
docs/
  source_research.md
  pipeline_plan.md
scripts/
  source_discovery.py
  validate_target_history.py
```

`data/raw/source_discovery/` уже содержит только ограниченные raw-артефакты
этапа 1. Полный пятилетний набор не загружен.

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
   Календарные пропуски не заполнять. Результат идет в `data/interim/`.
6. **Feature engineering — отдельный будущий этап.** Сортировать внутри каждой
   валюты по доступному времени. Любая строка T использует только значения с
   timestamp `<= T`; rolling только trailing, `center=False`. Scaling обучается
   только на train-period и затем применяется к validation/test.
7. **Labels — отдельный будущий этап.** Future horizon разрешен только здесь.
   Labels сохраняются физически отдельно и присоединяются к features после
   temporal split. Хвост без полного горизонта исключается, а не заполняется.
8. **Temporal validation.** Разбиение train/validation/test только по времени,
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

## Планируемые файлы и контракты

На один production run с ID `<run_id>`:

```text
data/raw/<run_id>/manifest.json
data/raw/<run_id>/currency_reference.response.xml
data/raw/<run_id>/currency_reference.request.json
data/raw/<run_id>/<ISO>.response.xml
data/raw/<run_id>/<ISO>.request.json
data/reference/<run_id>/currencies.parquet
data/interim/<run_id>/rates.parquet
data/features/<run_id>/features.parquet
data/labels/<run_id>/labels.parquet
reports/data_quality/<run_id>.json
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
