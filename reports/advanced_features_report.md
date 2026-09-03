# Advanced features report

Новых полей: **37**. Строк: **9445**.

## Новые признаки

`days_since_min_20`, `days_since_min_60`, `return_sign_reversal_up`, `reversal_strength`, `near_min_prev_002`, `near_min_prev_005`, `near_min_prev_010`, `near_min_reversal_002`, `near_min_reversal_005`, `near_min_reversal_010`, `reversal_2d_002`, `reversal_2d_005`, `reversal_2d_010`, `recipient_usd_implied`, `recipient_usd_ret_1`, `recipient_usd_ret_3`, `recipient_usd_ret_5`, `recipient_usd_ret_10`, `usd_rub_source_quote_date`, `usd_rub_freshness_days`, `eur_rub_source_quote_date`, `eur_rub_freshness_days`, `cny_rub_source_quote_date`, `cny_rub_freshness_days`, `broad_rub_freshness_days`, `broad_rub_return_1`, `broad_rub_return_3`, `broad_rub_return_5`, `broad_rub_return_10`, `broad_rub_return_20`, `corridor_specific_return_1`, `corridor_specific_return_3`, `corridor_specific_return_5`, `corridor_specific_return_10`, `broad_rub_z_1`, `broad_rub_z_3`, `broad_rub_z_5`

## Пропуски

|                             |   Количество NaN |
|:----------------------------|-----------------:|
| days_since_min_20           |               95 |
| days_since_min_60           |              295 |
| return_sign_reversal_up     |                0 |
| reversal_strength           |               10 |
| near_min_prev_002           |                0 |
| near_min_prev_005           |                0 |
| near_min_prev_010           |                0 |
| near_min_reversal_002       |                0 |
| near_min_reversal_005       |                0 |
| near_min_reversal_010       |                0 |
| reversal_2d_002             |                0 |
| reversal_2d_005             |                0 |
| reversal_2d_010             |                0 |
| recipient_usd_implied       |                0 |
| recipient_usd_ret_1         |                5 |
| recipient_usd_ret_3         |               15 |
| recipient_usd_ret_5         |               25 |
| recipient_usd_ret_10        |               50 |
| usd_rub_source_quote_date   |                0 |
| usd_rub_freshness_days      |                0 |
| eur_rub_source_quote_date   |                0 |
| eur_rub_freshness_days      |                0 |
| cny_rub_source_quote_date   |                0 |
| cny_rub_freshness_days      |                0 |
| broad_rub_freshness_days    |                0 |
| broad_rub_return_1          |                5 |
| broad_rub_return_3          |               15 |
| broad_rub_return_5          |               25 |
| broad_rub_return_10         |               50 |
| broad_rub_return_20         |              100 |
| corridor_specific_return_1  |                5 |
| corridor_specific_return_3  |               15 |
| corridor_specific_return_5  |               25 |
| corridor_specific_return_10 |               50 |
| broad_rub_z_1               |              305 |
| broad_rub_z_3               |              315 |
| broad_rub_z_5               |              325 |

Пропуски в начале рядов вызваны causal warm-up окон и лагов; они не заполнялись.

## Alignment и freshness

Опорные валюты присоединены по последней официальной котировке с датой не позже T. Backward fill и будущие значения не применялись.

| Опорная валюта   |   Точное совпадение даты |   Использована прошлая котировка |   Нет доступной котировки |
|:-----------------|-------------------------:|---------------------------------:|--------------------------:|
| USD              |                     9445 |                                0 |                         0 |
| EUR              |                     9445 |                                0 |                         0 |
| CNY              |                     9445 |                                0 |                         0 |

|                          |   count |   mean |   std |   min |   25% |   50% |   75% |   max |
|:-------------------------|--------:|-------:|------:|------:|------:|------:|------:|------:|
| usd_rub_freshness_days   |    9445 |      0 |     0 |     0 |     0 |     0 |     0 |     0 |
| eur_rub_freshness_days   |    9445 |      0 |     0 |     0 |     0 |     0 |     0 |     0 |
| cny_rub_freshness_days   |    9445 |      0 |     0 |     0 |     0 |     0 |     0 |     0 |
| broad_rub_freshness_days |    9445 |      0 |     0 |     0 |     0 |     0 |     0 |     0 |

Проверка математической identity `recipient_usd_implied = X_RUB / USD_RUB` на 10 реальных строках: **PASS**.

## Примеры reversal events

| date                | corridor   |     rate |   reversal_strength |   near_min_reversal_010 |
|:--------------------|:-----------|---------:|--------------------:|------------------------:|
| 2019-01-15 00:00:00 | AMD_RUB    | 0.138113 |          0.00347144 |                       0 |
| 2019-01-23 00:00:00 | AMD_RUB    | 0.137075 |          0.00314567 |                       0 |
| 2019-01-29 00:00:00 | AMD_RUB    | 0.135658 |          0.00414508 |                       0 |
| 2019-02-02 00:00:00 | AMD_RUB    | 0.13477  |          0.0195001  |                       0 |
| 2019-02-06 00:00:00 | AMD_RUB    | 0.134708 |          0.00138055 |                       0 |
| 2019-02-08 00:00:00 | AMD_RUB    | 0.135038 |          0.00454682 |                       1 |
| 2019-02-13 00:00:00 | AMD_RUB    | 0.134276 |          0.0129736  |                       1 |
| 2019-02-27 00:00:00 | AMD_RUB    | 0.134243 |          0.00923313 |                       1 |

## Примеры движения broad RUB factor

| date                | corridor   |   broad_rub_return_5 |
|:--------------------|:-----------|---------------------:|
| 2022-03-04 00:00:00 | AMD_RUB    |             0.280177 |
| 2022-03-04 00:00:00 | KGS_RUB    |             0.280177 |
| 2022-03-04 00:00:00 | KZT_RUB    |             0.280177 |
| 2022-03-04 00:00:00 | TJS_RUB    |             0.280177 |
| 2022-03-04 00:00:00 | UZS_RUB    |             0.280177 |
| 2022-03-03 00:00:00 | AMD_RUB    |             0.277758 |
| 2022-03-03 00:00:00 | KGS_RUB    |             0.277758 |
| 2022-03-03 00:00:00 | KZT_RUB    |             0.277758 |

## Примеры corridor-specific движения

| date                | corridor   |   corridor_specific_return_5 |
|:--------------------|:-----------|-----------------------------:|
| 2022-03-01 00:00:00 | KZT_RUB    |                    -0.163746 |
| 2022-03-10 00:00:00 | TJS_RUB    |                    -0.154293 |
| 2022-03-10 00:00:00 | KGS_RUB    |                    -0.151785 |
| 2022-03-02 00:00:00 | KZT_RUB    |                    -0.151344 |
| 2022-04-16 00:00:00 | KGS_RUB    |                     0.149644 |
| 2022-03-05 00:00:00 | KGS_RUB    |                    -0.147569 |
| 2022-03-03 00:00:00 | KZT_RUB    |                    -0.141713 |
| 2020-04-09 00:00:00 | KGS_RUB    |                    -0.140498 |

## Проверка причинности

Статус: **PASS**; проверено случайных пар дата/коридор: **30**, seed `42`.

Labels не создавались.

**ADVANCED FEATURES STATUS: PASS**
