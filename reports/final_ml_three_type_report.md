# Финальная трёхтиповая ML push policy

## Frozen configuration

- GOOD_DAY: CatBoost probability >= 0.8
- WINDOW_CLOSING: CatBoost probability >= 0.8
- POSITIVE_MARKET_FACT: точный causal OR factual flags из golden methodology
- Priority: good_day > window_closing > positive_market_fact
- Cooldown: 4 календарных дня; cap: 2 push/ISO-неделю; adaptive ranking: none

## Classification (final delivered ML pushes)

| signal_type          |   predicted_positive |   actual_positive |   true_positive |   false_positive |   false_negative |   precision |      recall |     f_beta |   average_precision |   classification_lift |
|:---------------------|---------------------:|------------------:|----------------:|-----------------:|-----------------:|------------:|------------:|-----------:|--------------------:|----------------------:|
| GOOD_DAY             |                   47 |               203 |              20 |               27 |              183 |    0.425532 |   0.0985222 |   0.255754 |            0.50514  |               1.76082 |
| WINDOW_CLOSING       |                    7 |                52 |               1 |                6 |               51 |    0.142857 |   0.0192308 |   0.0625   |            0.140667 |               2.30769 |
| POSITIVE_MARKET_FACT |                   66 |               281 |              66 |              nan |              nan |  nan        | nan         | nan        |          nan        |             nan       |

POSITIVE_MARKET_FACT не получает classification precision/recall: согласно metrics methodology это детерминированный наблюдаемый факт, а не прогноз.

## Frequency

- total_pushes: 120
- mean_pushes_per_corridor_month: 3.0
- median_pushes_per_corridor_month: 3.0
- share_corridor_months_ge_3: 0.625
- zero_push_months: 1
- suppressed_by_priority_rows: 87
- suppressed_by_cooldown_only: 210
- suppressed_by_weekly_cap: 0

## Leakage audit

- Frozen notebook 28 TEST probabilities read from disk; no fitting or threshold selection.
- Golden labels and future outcomes are used only for plots/evaluation.
- Factual candidates use only flags available at T.
- Priority/cooldown/weekly cap are frozen and not optimized on TEST.
- Deferral is disabled; actual T+1 is never used.

**LEAKAGE CHECK: PASS**