# Favourability-30 fixed-rule visual comparison

Descriptive locked-test diagnostics; no winner is selected.

| corridor   | rule            |    F |       A |     R |   n_signals |   signal_frequency |   mean_signals_per_month |   median_signals_per_month |   months_with_zero_signals |   hit_rate |
|:-----------|:----------------|-----:|--------:|------:|------------:|-------------------:|-------------------------:|---------------------------:|---------------------------:|-----------:|
| AMD_RUB    | RULE_1_STRICT   | 0.9  |   0.002 | 0.002 |          18 |          0.0654545 |                 1.28571  |                        0   |                          9 |   0.333333 |
| AMD_RUB    | RULE_2          | 0.9  |   0     | 0.005 |          28 |          0.101818  |                 2        |                        0.5 |                          7 |   0.392857 |
| AMD_RUB    | RULE_3_BALANCED | 0.85 |   0     | 0.005 |          30 |          0.109091  |                 2.14286  |                        0.5 |                          7 |   0.4      |
| AMD_RUB    | RULE_4_SOFT     | 0.85 | nan     | 0.005 |          52 |          0.189091  |                 3.71429  |                        1   |                          7 |   0.5      |
| AMD_RUB    | RULE_5_BROAD    | 0.8  | nan     | 0.01  |          68 |          0.247273  |                 4.85714  |                        2   |                          6 |   0.382353 |
| KGS_RUB    | RULE_1_STRICT   | 0.9  |   0.002 | 0.002 |          15 |          0.0545455 |                 1.07143  |                        0   |                          8 |   0.266667 |
| KGS_RUB    | RULE_2          | 0.9  |   0     | 0.005 |          32 |          0.116364  |                 2.28571  |                        0.5 |                          7 |   0.3125   |
| KGS_RUB    | RULE_3_BALANCED | 0.85 |   0     | 0.005 |          33 |          0.12      |                 2.35714  |                        0.5 |                          7 |   0.30303  |
| KGS_RUB    | RULE_4_SOFT     | 0.85 | nan     | 0.005 |          61 |          0.221818  |                 4.35714  |                        2   |                          7 |   0.459016 |
| KGS_RUB    | RULE_5_BROAD    | 0.8  | nan     | 0.01  |          76 |          0.276364  |                 5.42857  |                        4   |                          6 |   0.368421 |
| KZT_RUB    | RULE_1_STRICT   | 0.9  |   0.002 | 0.002 |          17 |          0.0618182 |                 1.21429  |                        0   |                          9 |   0.352941 |
| KZT_RUB    | RULE_2          | 0.9  |   0     | 0.005 |          25 |          0.0909091 |                 1.78571  |                        0   |                          8 |   0.4      |
| KZT_RUB    | RULE_3_BALANCED | 0.85 |   0     | 0.005 |          27 |          0.0981818 |                 1.92857  |                        0.5 |                          7 |   0.407407 |
| KZT_RUB    | RULE_4_SOFT     | 0.85 | nan     | 0.005 |          52 |          0.189091  |                 3.71429  |                        1   |                          7 |   0.461538 |
| KZT_RUB    | RULE_5_BROAD    | 0.8  | nan     | 0.01  |          61 |          0.221818  |                 4.35714  |                        3.5 |                          6 |   0.393443 |
| TJS_RUB    | RULE_1_STRICT   | 0.9  |   0.002 | 0.002 |          26 |          0.0945455 |                 1.85714  |                        1   |                          7 |   0.346154 |
| TJS_RUB    | RULE_2          | 0.9  |   0     | 0.005 |          32 |          0.116364  |                 2.28571  |                        1   |                          7 |   0.34375  |
| TJS_RUB    | RULE_3_BALANCED | 0.85 |   0     | 0.005 |          33 |          0.12      |                 2.35714  |                        1.5 |                          6 |   0.363636 |
| TJS_RUB    | RULE_4_SOFT     | 0.85 | nan     | 0.005 |          60 |          0.218182  |                 4.28571  |                        3   |                          5 |   0.466667 |
| TJS_RUB    | RULE_5_BROAD    | 0.8  | nan     | 0.01  |          73 |          0.265455  |                 5.21429  |                        3.5 |                          5 |   0.383562 |
| UZS_RUB    | RULE_1_STRICT   | 0.9  |   0.002 | 0.002 |          11 |          0.04      |                 0.785714 |                        0   |                          8 |   0.363636 |
| UZS_RUB    | RULE_2          | 0.9  |   0     | 0.005 |          27 |          0.0981818 |                 1.92857  |                        0.5 |                          7 |   0.407407 |
| UZS_RUB    | RULE_3_BALANCED | 0.85 |   0     | 0.005 |          31 |          0.112727  |                 2.21429  |                        1   |                          7 |   0.354839 |
| UZS_RUB    | RULE_4_SOFT     | 0.85 | nan     | 0.005 |          63 |          0.229091  |                 4.5      |                        3.5 |                          6 |   0.380952 |
| UZS_RUB    | RULE_5_BROAD    | 0.8  | nan     | 0.01  |          74 |          0.269091  |                 5.28571  |                        4   |                          6 |   0.324324 |

## Leakage

| check                                 | passed   |
|:--------------------------------------|:---------|
| exactly five rules fixed in advance   | True     |
| signals use only approved live fields | True     |
| no actual future rate in signals      | True     |
| actual_regret is diagnostic only      | True     |
| no winner or optimization             | True     |

RULE VISUAL COMPARISON CHECK: **PASS**