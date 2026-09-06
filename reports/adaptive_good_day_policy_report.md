# Adaptive good-day policy

Both full and simple causal scores are saved; policies use the full score and no winner is selected.

| corridor   | policy   |   n_signals |   mean_signals_per_month |   median_signals_per_month |   months_with_zero_signals |   share_months_with_1plus |   share_months_with_2plus |   max_gap_quote_observations |   mean_gap_quote_observations |   hit_rate |   random_hit_rate |   uplift |   mean_actual_regret_signal |
|:-----------|:---------|------------:|-------------------------:|---------------------------:|---------------------------:|--------------------------:|--------------------------:|-----------------------------:|------------------------------:|-----------:|------------------:|---------:|----------------------------:|
| AMD_RUB    | POLICY_A |          35 |                  2.5     |                        0   |                          8 |                  0.428571 |                  0.428571 |                           45 |                       4.5     |  0.257143  |         0.0946667 |  2.7163  |                   0.015154  |
| AMD_RUB    | POLICY_B |          39 |                  2.78571 |                        1   |                          6 |                  0.571429 |                  0.428571 |                           26 |                       4.07895 |  0.230769  |         0.0976923 |  2.3622  |                   0.014951  |
| AMD_RUB    | POLICY_C |          15 |                  1.07143 |                        1   |                          6 |                  0.571429 |                  0.357143 |                           26 |                      10.8571  |  0.0666667 |         0.0937778 |  0.7109  |                   0.0157566 |
| KGS_RUB    | POLICY_A |          32 |                  2.28571 |                        1   |                          6 |                  0.571429 |                  0.428571 |                           58 |                       6.80645 |  0.25      |         0.0929167 |  2.69058 |                   0.0162853 |
| KGS_RUB    | POLICY_B |          36 |                  2.57143 |                        1   |                          5 |                  0.642857 |                  0.428571 |                           56 |                       6.02857 |  0.222222  |         0.0965741 |  2.30105 |                   0.0160607 |
| KGS_RUB    | POLICY_C |          16 |                  1.14286 |                        1   |                          6 |                  0.571429 |                  0.357143 |                           25 |                      10.3333  |  0.1875    |         0.0970833 |  1.93133 |                   0.015965  |
| KZT_RUB    | POLICY_A |          26 |                  1.85714 |                        1   |                          7 |                  0.5      |                  0.5      |                           53 |                       8.32    |  0.423077  |         0.111538  |  3.7931  |                   0.0125556 |
| KZT_RUB    | POLICY_B |          32 |                  2.28571 |                        1.5 |                          4 |                  0.714286 |                  0.5      |                           34 |                       6.70968 |  0.34375   |         0.102396  |  3.35707 |                   0.0141987 |
| KZT_RUB    | POLICY_C |          17 |                  1.21429 |                        1   |                          4 |                  0.714286 |                  0.428571 |                           34 |                      12.9375  |  0.235294  |         0.0986275 |  2.38569 |                   0.0146404 |
| TJS_RUB    | POLICY_A |          32 |                  2.28571 |                        1.5 |                          6 |                  0.571429 |                  0.5      |                           48 |                       5.77419 |  0.34375   |         0.108333  |  3.17308 |                   0.0135469 |
| TJS_RUB    | POLICY_B |          38 |                  2.71429 |                        1.5 |                          5 |                  0.642857 |                  0.5      |                           26 |                       4.83784 |  0.315789  |         0.112632  |  2.80374 |                   0.0130017 |
| TJS_RUB    | POLICY_C |          17 |                  1.21429 |                        1   |                          6 |                  0.571429 |                  0.428571 |                           27 |                      11.0625  |  0.294118  |         0.116078  |  2.53378 |                   0.0112944 |
| UZS_RUB    | POLICY_A |          37 |                  2.64286 |                        1.5 |                          7 |                  0.5      |                  0.5      |                           60 |                       5.86111 |  0.243243  |         0.0781081 |  3.11419 |                   0.0150187 |
| UZS_RUB    | POLICY_B |          41 |                  2.92857 |                        2.5 |                          6 |                  0.571429 |                  0.5      |                           54 |                       5.625   |  0.219512  |         0.0768293 |  2.85714 |                   0.0148074 |
| UZS_RUB    | POLICY_C |          18 |                  1.28571 |                        1.5 |                          6 |                  0.571429 |                  0.5      |                           54 |                      13.2353  |  0.166667  |         0.0735185 |  2.267   |                   0.0155232 |

## POLICY_C monthly

| corridor   | month   |   n_signals |   n_hits |   hit_rate | policy   |
|:-----------|:--------|------------:|---------:|-----------:|:---------|
| AMD_RUB    | 2025-07 |           0 |        0 | nan        | POLICY_C |
| AMD_RUB    | 2025-08 |           0 |        0 | nan        | POLICY_C |
| AMD_RUB    | 2025-09 |           1 |        0 |   0        | POLICY_C |
| AMD_RUB    | 2025-10 |           1 |        0 |   0        | POLICY_C |
| AMD_RUB    | 2025-11 |           3 |        0 |   0        | POLICY_C |
| AMD_RUB    | 2025-12 |           2 |        1 |   0.5      | POLICY_C |
| AMD_RUB    | 2026-01 |           2 |        0 |   0        | POLICY_C |
| AMD_RUB    | 2026-02 |           1 |        0 |   0        | POLICY_C |
| AMD_RUB    | 2026-03 |           0 |        0 | nan        | POLICY_C |
| AMD_RUB    | 2026-04 |           3 |        0 |   0        | POLICY_C |
| AMD_RUB    | 2026-05 |           2 |        0 |   0        | POLICY_C |
| AMD_RUB    | 2026-06 |           0 |        0 | nan        | POLICY_C |
| AMD_RUB    | 2026-07 |           0 |        0 | nan        | POLICY_C |
| AMD_RUB    | 2026-08 |           0 |        0 | nan        | POLICY_C |
| KGS_RUB    | 2025-07 |           0 |        0 | nan        | POLICY_C |
| KGS_RUB    | 2025-08 |           0 |        0 | nan        | POLICY_C |
| KGS_RUB    | 2025-09 |           1 |        0 |   0        | POLICY_C |
| KGS_RUB    | 2025-10 |           2 |        1 |   0.5      | POLICY_C |
| KGS_RUB    | 2025-11 |           3 |        0 |   0        | POLICY_C |
| KGS_RUB    | 2025-12 |           1 |        0 |   0        | POLICY_C |
| KGS_RUB    | 2026-01 |           2 |        1 |   0.5      | POLICY_C |
| KGS_RUB    | 2026-02 |           1 |        0 |   0        | POLICY_C |
| KGS_RUB    | 2026-03 |           0 |        0 | nan        | POLICY_C |
| KGS_RUB    | 2026-04 |           3 |        0 |   0        | POLICY_C |
| KGS_RUB    | 2026-05 |           3 |        1 |   0.333333 | POLICY_C |
| KGS_RUB    | 2026-06 |           0 |        0 | nan        | POLICY_C |
| KGS_RUB    | 2026-07 |           0 |        0 | nan        | POLICY_C |
| KGS_RUB    | 2026-08 |           0 |        0 | nan        | POLICY_C |
| KZT_RUB    | 2025-07 |           2 |        1 |   0.5      | POLICY_C |
| KZT_RUB    | 2025-08 |           1 |        0 |   0        | POLICY_C |
| KZT_RUB    | 2025-09 |           1 |        0 |   0        | POLICY_C |
| KZT_RUB    | 2025-10 |           1 |        0 |   0        | POLICY_C |
| KZT_RUB    | 2025-11 |           2 |        1 |   0.5      | POLICY_C |
| KZT_RUB    | 2025-12 |           2 |        1 |   0.5      | POLICY_C |
| KZT_RUB    | 2026-01 |           2 |        1 |   0.5      | POLICY_C |
| KZT_RUB    | 2026-02 |           1 |        0 |   0        | POLICY_C |
| KZT_RUB    | 2026-03 |           0 |        0 | nan        | POLICY_C |
| KZT_RUB    | 2026-04 |           2 |        0 |   0        | POLICY_C |
| KZT_RUB    | 2026-05 |           3 |        0 |   0        | POLICY_C |
| KZT_RUB    | 2026-06 |           0 |        0 | nan        | POLICY_C |
| KZT_RUB    | 2026-07 |           0 |        0 | nan        | POLICY_C |
| KZT_RUB    | 2026-08 |           0 |        0 | nan        | POLICY_C |
| TJS_RUB    | 2025-07 |           0 |        0 | nan        | POLICY_C |
| TJS_RUB    | 2025-08 |           1 |        0 |   0        | POLICY_C |
| TJS_RUB    | 2025-09 |           0 |        0 | nan        | POLICY_C |
| TJS_RUB    | 2025-10 |           3 |        2 |   0.666667 | POLICY_C |
| TJS_RUB    | 2025-11 |           3 |        0 |   0        | POLICY_C |
| TJS_RUB    | 2025-12 |           2 |        1 |   0.5      | POLICY_C |
| TJS_RUB    | 2026-01 |           3 |        1 |   0.333333 | POLICY_C |
| TJS_RUB    | 2026-02 |           2 |        1 |   0.5      | POLICY_C |
| TJS_RUB    | 2026-03 |           0 |        0 | nan        | POLICY_C |
| TJS_RUB    | 2026-04 |           1 |        0 |   0        | POLICY_C |
| TJS_RUB    | 2026-05 |           2 |        0 |   0        | POLICY_C |
| TJS_RUB    | 2026-06 |           0 |        0 | nan        | POLICY_C |
| TJS_RUB    | 2026-07 |           0 |        0 | nan        | POLICY_C |
| TJS_RUB    | 2026-08 |           0 |        0 | nan        | POLICY_C |
| UZS_RUB    | 2025-07 |           2 |        1 |   0.5      | POLICY_C |
| UZS_RUB    | 2025-08 |           0 |        0 | nan        | POLICY_C |
| UZS_RUB    | 2025-09 |           0 |        0 | nan        | POLICY_C |
| UZS_RUB    | 2025-10 |           3 |        1 |   0.333333 | POLICY_C |
| UZS_RUB    | 2025-11 |           2 |        0 |   0        | POLICY_C |
| UZS_RUB    | 2025-12 |           2 |        1 |   0.5      | POLICY_C |
| UZS_RUB    | 2026-01 |           3 |        0 |   0        | POLICY_C |
| UZS_RUB    | 2026-02 |           0 |        0 | nan        | POLICY_C |
| UZS_RUB    | 2026-03 |           0 |        0 | nan        | POLICY_C |
| UZS_RUB    | 2026-04 |           3 |        0 |   0        | POLICY_C |
| UZS_RUB    | 2026-05 |           2 |        0 |   0        | POLICY_C |
| UZS_RUB    | 2026-06 |           1 |        0 |   0        | POLICY_C |
| UZS_RUB    | 2026-07 |           0 |        0 | nan        | POLICY_C |
| UZS_RUB    | 2026-08 |           0 |        0 | nan        | POLICY_C |

## Leakage

| check                                         | passed   |
|:----------------------------------------------|:---------|
| rolling thresholds use past observations only | True     |
| current T excluded                            | True     |
| no actual future in signal generation         | True     |
| actual regret evaluation only                 | True     |
| fallback state causal                         | True     |
| cooldown causal                               | True     |
| processing separated by corridor              | True     |

ADAPTIVE GOOD DAY POLICY LEAKAGE CHECK: **PASS**