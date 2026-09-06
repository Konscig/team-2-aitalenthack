# Favourability-30 good-day rules

30-observation thresholds выбраны только на validation; locked test не участвовал в выборе.

## Selection

| corridor   | selected_rule           |    F |     A |     R |   validation_frequency |   validation_hit_rate |   validation_uplift | status         |
|:-----------|:------------------------|-----:|------:|------:|-----------------------:|----------------------:|--------------------:|:---------------|
| AMD_RUB    | F=0.900|A=0.002|R=0.002 | 0.9  | 0.002 | 0.002 |              0.0948905 |              0.461538 |             3.0303  | VALIDATED_RULE |
| KGS_RUB    | F=0.900|A=0.002|R=0.002 | 0.9  | 0.002 | 0.002 |              0.109489  |              0.4      |             2.9316  | VALIDATED_RULE |
| KZT_RUB    | F=0.800|A=0.005|R=0.002 | 0.8  | 0.005 | 0.002 |              0.0948905 |              0.461538 |             2.8125  | VALIDATED_RULE |
| TJS_RUB    | F=0.850|A=0.005|R=0.002 | 0.85 | 0.005 | 0.002 |              0.0547445 |              0.6      |             5.73248 | VALIDATED_RULE |
| UZS_RUB    | F=0.900|A=0.002|R=0.002 | 0.9  | 0.002 | 0.002 |              0.0620438 |              0.411765 |             3.44828 | VALIDATED_RULE |

## Locked test

| corridor   | selected_rule           |    F |     A |     R | status         |   n_rows |   n_signals |   signal_frequency |   hit_rate |   recall |   random_hit_rate |   uplift |   mean_actual_regret_signal |   median_actual_regret_signal |   mean_signals_per_month |   median_signals_per_month |   months_with_zero_signals |   share_months_with_2plus |
|:-----------|:------------------------|-----:|------:|------:|:---------------|---------:|------------:|-------------------:|-----------:|---------:|------------------:|---------:|----------------------------:|------------------------------:|-------------------------:|---------------------------:|---------------------------:|--------------------------:|
| AMD_RUB    | F=0.900|A=0.002|R=0.002 | 0.9  | 0.002 | 0.002 | VALIDATED_RULE |      275 |          18 |          0.0654545 |   0.333333 | 0.230769 |         0.0966667 |  3.44828 |                   0.0111306 |                    0.0118802  |                 1.28571  |                          0 |                          9 |                  0.357143 |
| KGS_RUB    | F=0.900|A=0.002|R=0.002 | 0.9  | 0.002 | 0.002 | VALIDATED_RULE |      275 |          15 |          0.0545455 |   0.266667 | 0.142857 |         0.100667  |  2.64901 |                   0.0142533 |                    0.0163511  |                 1.07143  |                          0 |                          8 |                  0.285714 |
| KZT_RUB    | F=0.800|A=0.005|R=0.002 | 0.8  | 0.005 | 0.002 | VALIDATED_RULE |      275 |          12 |          0.0436364 |   0.333333 | 0.166667 |         0.0883333 |  3.77358 |                   0.0148025 |                    0.0126116  |                 0.857143 |                          0 |                          8 |                  0.214286 |
| TJS_RUB    | F=0.850|A=0.005|R=0.002 | 0.85 | 0.005 | 0.002 | VALIDATED_RULE |      275 |          14 |          0.0509091 |   0.428571 | 0.214286 |         0.0997619 |  4.29594 |                   0.0105452 |                    0.00598617 |                 1        |                          0 |                          8 |                  0.285714 |
| UZS_RUB    | F=0.900|A=0.002|R=0.002 | 0.9  | 0.002 | 0.002 | VALIDATED_RULE |      275 |          11 |          0.04      |   0.363636 | 0.166667 |         0.0963636 |  3.77358 |                   0.010686  |                    0.0121457  |                 0.785714 |                          0 |                          8 |                  0.142857 |

## 30 vs 90

| corridor   |   old_test_signals |   new_test_signals |   old_signal_frequency |   new_signal_frequency |   old_hit_rate |   new_hit_rate |   old_uplift |   new_uplift |   old_mean_signals_per_month |   new_mean_signals_per_month |   old_months_with_zero_signals |   new_months_with_zero_signals |   old_mean_actual_regret_signal |   new_mean_actual_regret_signal |   signal_count_change_pct |   uplift_change |   hit_rate_change |
|:-----------|-------------------:|-------------------:|-----------------------:|-----------------------:|---------------:|---------------:|-------------:|-------------:|-----------------------------:|-----------------------------:|-------------------------------:|-------------------------------:|--------------------------------:|--------------------------------:|--------------------------:|----------------:|------------------:|
| AMD_RUB    |                 22 |                 18 |              0.08      |              0.0654545 |       0.5      |       0.333333 |      3.67075 |      3.44828 |                     1.57143  |                     1.28571  |                              7 |                              9 |                      0.00899637 |                       0.0111306 |                  -18.1818 |       -0.222469 |       -0.166667   |
| KGS_RUB    |                 31 |                 15 |              0.112727  |              0.0545455 |       0.322581 |       0.266667 |      2.20103 |      2.64901 |                     2.21429  |                     1.07143  |                              7 |                              8 |                      0.0122658  |                       0.0142533 |                  -51.6129 |        0.447979 |       -0.055914   |
| KZT_RUB    |                 10 |                 12 |              0.0363636 |              0.0436364 |       0.6      |       0.333333 |      6.61765 |      3.77358 |                     0.714286 |                     0.857143 |                             10 |                              8 |                      0.00545002 |                       0.0148025 |                   20      |       -2.84406  |       -0.266667   |
| TJS_RUB    |                 81 |                 14 |              0.294545  |              0.0509091 |       0.419753 |       0.428571 |      3.27763 |      4.29594 |                     5.78571  |                     1        |                              6 |                              8 |                      0.00972764 |                       0.0105452 |                  -82.716  |        1.01831  |        0.00881834 |
| UZS_RUB    |                 19 |                 11 |              0.0690909 |              0.04      |       0.421053 |       0.363636 |      3.88979 |      3.77358 |                     1.35714  |                     0.785714 |                              7 |                              8 |                      0.0108298  |                       0.010686  |                  -42.1053 |       -0.116204 |       -0.0574163  |

Сравнение использует соответствующий ground truth каждой версии (GT_30 против Stage-08 GT_B), поэтому это продуктовый вариант определения, а не чистая feature ablation при неизменной label.

## Leakage

| check                                     | passed   |
|:------------------------------------------|:---------|
| favourability_30 uses only T-30...T-1     | True     |
| current T excluded from percentile window | True     |
| threshold selection validation only       | True     |
| test thresholds fixed                     | True     |
| signal uses only approved live fields     | True     |
| actual regret only for GT/evaluation      | True     |
| no actual future rate in signal logic     | True     |
| one rule selected separately per corridor | True     |

FAVOURABILITY 30 LEAKAGE CHECK: **PASS**