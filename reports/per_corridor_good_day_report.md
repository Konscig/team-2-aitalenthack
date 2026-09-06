# Per-corridor good-day rules

Thresholds выбраны только на validation и без изменений применены к locked test.

## Frozen Stage-04 restoration

| corridor   |   horizon | config_id   |   trees_used |   saved_MAE |   restored_MAE |   absolute_MAE_difference | same_config_reused   | trained_on_train_only   |
|:-----------|----------:|:------------|-------------:|------------:|---------------:|--------------------------:|:---------------------|:------------------------|
| AMD_RUB    |         1 | CONFIG_2    |          108 | 0.00165699  |    0.00165699  |               4.98733e-18 | True                 | True                    |
| AMD_RUB    |         2 | CONFIG_3    |           67 | 0.0026897   |    0.0026897   |               3.59955e-17 | True                 | True                    |
| AMD_RUB    |         3 | CONFIG_3    |           33 | 0.00335988  |    0.00335988  |               3.85976e-17 | True                 | True                    |
| AMD_RUB    |         4 | CONFIG_1    |           31 | 0.00382434  |    0.00382434  |               6.72205e-17 | True                 | True                    |
| AMD_RUB    |         5 | CONFIG_3    |           11 | 0.00421404  |    0.00421404  |               7.54605e-17 | True                 | True                    |
| KGS_RUB    |         1 | CONFIG_4    |          498 | 0.00737989  |    0.00737989  |               1.21431e-17 | True                 | True                    |
| KGS_RUB    |         2 | CONFIG_2    |           13 | 0.0119092   |    0.0119092   |               3.64292e-17 | True                 | True                    |
| KGS_RUB    |         3 | CONFIG_4    |           24 | 0.01479     |    0.01479     |               9.02056e-17 | True                 | True                    |
| KGS_RUB    |         4 | CONFIG_1    |            4 | 0.0166721   |    0.0166721   |               4.51028e-17 | True                 | True                    |
| KGS_RUB    |         5 | CONFIG_4    |            6 | 0.0181339   |    0.0181339   |               3.81639e-17 | True                 | True                    |
| KZT_RUB    |         1 | CONFIG_4    |          343 | 0.0015388   |    0.0015388   |               6.93889e-17 | True                 | True                    |
| KZT_RUB    |         2 | CONFIG_2    |            1 | 0.00238737  |    0.00238737  |               1.60462e-17 | True                 | True                    |
| KZT_RUB    |         3 | CONFIG_1    |            1 | 0.00280133  |    0.00280133  |               4.81386e-17 | True                 | True                    |
| KZT_RUB    |         4 | CONFIG_4    |            2 | 0.0031451   |    0.0031451   |               8.67362e-19 | True                 | True                    |
| KZT_RUB    |         5 | CONFIG_3    |            1 | 0.00344851  |    0.00344851  |               5.1608e-17  | True                 | True                    |
| TJS_RUB    |         1 | CONFIG_4    |          318 | 0.0632319   |    0.0632319   |               2.77556e-17 | True                 | True                    |
| TJS_RUB    |         2 | CONFIG_3    |           23 | 0.101133    |    0.101133    |               1.38778e-17 | True                 | True                    |
| TJS_RUB    |         3 | CONFIG_3    |           23 | 0.126636    |    0.126636    |               0           | True                 | True                    |
| TJS_RUB    |         4 | CONFIG_4    |           36 | 0.142653    |    0.142653    |               8.32667e-17 | True                 | True                    |
| TJS_RUB    |         5 | CONFIG_3    |            2 | 0.15636     |    0.15636     |               0           | True                 | True                    |
| UZS_RUB    |         1 | CONFIG_4    |          251 | 5.1971e-05  |    5.1971e-05  |               0           | True                 | True                    |
| UZS_RUB    |         2 | CONFIG_4    |          124 | 8.32344e-05 |    8.32344e-05 |               0           | True                 | True                    |
| UZS_RUB    |         3 | CONFIG_2    |            6 | 0.000104363 |    0.000104363 |               9.35124e-18 | True                 | True                    |
| UZS_RUB    |         4 | CONFIG_3    |           37 | 0.000117914 |    0.000117914 |               4.05221e-18 | True                 | True                    |
| UZS_RUB    |         5 | CONFIG_3    |           33 | 0.000127175 |    0.000127175 |               2.53161e-17 | True                 | True                    |

VALIDATION GOOD DAY FEATURES: **PASS**

## Selection

| corridor   | selected_rule           |    F |       A |     R |   validation_frequency |   validation_hit_rate |   validation_uplift | status         |
|:-----------|:------------------------|-----:|--------:|------:|-----------------------:|----------------------:|--------------------:|:---------------|
| AMD_RUB    | F=0.900|A=0.000|R=0.002 | 0.9  |   0     | 0.002 |              0.0985401 |              0.407407 |             2.77544 | VALIDATED_RULE |
| KGS_RUB    | F=0.850|A=0.002|R=0.010 | 0.85 |   0.002 | 0.01  |              0.109489  |              0.333333 |             2.40577 | VALIDATED_RULE |
| KZT_RUB    | F=0.900|A=0.002|R=0.002 | 0.9  |   0.002 | 0.002 |              0.0985401 |              0.518519 |             3.0479  | VALIDATED_RULE |
| TJS_RUB    | F=0.850|A=NONE|R=0.002  | 0.85 | nan     | 0.002 |              0.281022  |              0.428571 |             3.44948 | VALIDATED_RULE |
| UZS_RUB    | F=0.800|A=0.000|R=0.002 | 0.8  |   0     | 0.002 |              0.10219   |              0.392857 |             2.39651 | VALIDATED_RULE |

## Locked test — GT_B

| corridor   | ground_truth   | selected_rule           |   selected_F |   selected_A |   selected_R | status         |   n_rows |   n_signals |   signal_frequency |   hit_rate |   precision |   recall |   random_hit_rate |   uplift |   mean_actual_regret_signal |   median_actual_regret_signal | frequency_status   |
|:-----------|:---------------|:------------------------|-------------:|-------------:|-------------:|:---------------|---------:|------------:|-------------------:|-----------:|------------:|---------:|------------------:|---------:|----------------------------:|------------------------------:|:-------------------|
| AMD_RUB    | GT_B           | F=0.900|A=0.000|R=0.002 |         0.9  |        0     |        0.002 | VALIDATED_RULE |      275 |          22 |          0.08      |   0.5      |    0.5      | 0.289474 |         0.136212  |  3.67075 |                  0.00899637 |                    0.00451755 | OK                 |
| KGS_RUB    | GT_B           | F=0.850|A=0.002|R=0.010 |         0.85 |        0.002 |        0.01  | VALIDATED_RULE |      275 |          31 |          0.112727  |   0.322581 |    0.322581 | 0.243902 |         0.146559  |  2.20103 |                  0.0122658  |                    0.0113944  | OK                 |
| KZT_RUB    | GT_B           | F=0.900|A=0.002|R=0.002 |         0.9  |        0.002 |        0.002 | VALIDATED_RULE |      275 |          10 |          0.0363636 |   0.6      |    0.6      | 0.272727 |         0.0906667 |  6.61765 |                  0.00545002 |                    0.00334525 | OK                 |
| TJS_RUB    | GT_B           | F=0.850|A=NONE|R=0.002  |         0.85 |      nan     |        0.002 | VALIDATED_RULE |      275 |          81 |          0.294545  |   0.419753 |    0.419753 | 0.944444 |         0.128066  |  3.27763 |                  0.00972764 |                    0.00644674 | OK                 |
| UZS_RUB    | GT_B           | F=0.800|A=0.000|R=0.002 |         0.8  |        0     |        0.002 | VALIDATED_RULE |      275 |          19 |          0.0690909 |   0.421053 |    0.421053 | 0.258065 |         0.108246  |  3.88979 |                  0.0108298  |                    0.00617866 | OK                 |

## Sensitivity GT_A/B/C

| corridor   | ground_truth   | selected_rule           |   selected_F |   selected_A |   selected_R | status         |   n_rows |   n_signals |   signal_frequency |   hit_rate |   precision |   recall |   random_hit_rate |   uplift |   mean_actual_regret_signal |   median_actual_regret_signal | frequency_status   |
|:-----------|:---------------|:------------------------|-------------:|-------------:|-------------:|:---------------|---------:|------------:|-------------------:|-----------:|------------:|---------:|------------------:|---------:|----------------------------:|------------------------------:|:-------------------|
| AMD_RUB    | GT_A           | F=0.900|A=0.000|R=0.002 |         0.9  |        0     |        0.002 | VALIDATED_RULE |      275 |          22 |          0.08      |   0.5      |    0.5      | 0.23913  |         0.166061  |  3.01095 |                  0.00899637 |                    0.00451755 | OK                 |
| AMD_RUB    | GT_B           | F=0.900|A=0.000|R=0.002 |         0.9  |        0     |        0.002 | VALIDATED_RULE |      275 |          22 |          0.08      |   0.5      |    0.5      | 0.289474 |         0.136212  |  3.67075 |                  0.00899637 |                    0.00451755 | OK                 |
| AMD_RUB    | GT_C           | F=0.900|A=0.000|R=0.002 |         0.9  |        0     |        0.002 | VALIDATED_RULE |      275 |          22 |          0.08      |   0.5      |    0.5      | 0.846154 |         0.0534848 |  9.34844 |                  0.00899637 |                    0.00451755 | OK                 |
| KGS_RUB    | GT_A           | F=0.850|A=0.002|R=0.010 |         0.85 |        0.002 |        0.01  | VALIDATED_RULE |      275 |          31 |          0.112727  |   0.322581 |    0.322581 | 0.217391 |         0.169032  |  1.9084  |                  0.0122658  |                    0.0113944  | OK                 |
| KGS_RUB    | GT_B           | F=0.850|A=0.002|R=0.010 |         0.85 |        0.002 |        0.01  | VALIDATED_RULE |      275 |          31 |          0.112727  |   0.322581 |    0.322581 | 0.243902 |         0.146559  |  2.20103 |                  0.0122658  |                    0.0113944  | OK                 |
| KGS_RUB    | GT_C           | F=0.850|A=0.002|R=0.010 |         0.85 |        0.002 |        0.01  | VALIDATED_RULE |      275 |          31 |          0.112727  |   0.322581 |    0.322581 | 0.833333 |         0.0452688 |  7.12589 |                  0.0122658  |                    0.0113944  | OK                 |
| KZT_RUB    | GT_A           | F=0.900|A=0.002|R=0.002 |         0.9  |        0.002 |        0.002 | VALIDATED_RULE |      275 |          10 |          0.0363636 |   0.6      |    0.6      | 0.230769 |         0.101667  |  5.90164 |                  0.00545002 |                    0.00334525 | OK                 |
| KZT_RUB    | GT_B           | F=0.900|A=0.002|R=0.002 |         0.9  |        0.002 |        0.002 | VALIDATED_RULE |      275 |          10 |          0.0363636 |   0.6      |    0.6      | 0.272727 |         0.0906667 |  6.61765 |                  0.00545002 |                    0.00334525 | OK                 |
| KZT_RUB    | GT_C           | F=0.900|A=0.002|R=0.002 |         0.9  |        0.002 |        0.002 | VALIDATED_RULE |      275 |          10 |          0.0363636 |   0.6      |    0.6      | 0.545455 |         0.0416667 | 14.4     |                  0.00545002 |                    0.00334525 | OK                 |
| TJS_RUB    | GT_A           | F=0.850|A=NONE|R=0.002  |         0.85 |      nan     |        0.002 | VALIDATED_RULE |      275 |          81 |          0.294545  |   0.419753 |    0.419753 | 0.829268 |         0.148724  |  2.82236 |                  0.00972764 |                    0.00644674 | OK                 |
| TJS_RUB    | GT_B           | F=0.850|A=NONE|R=0.002  |         0.85 |      nan     |        0.002 | VALIDATED_RULE |      275 |          81 |          0.294545  |   0.419753 |    0.419753 | 0.944444 |         0.128066  |  3.27763 |                  0.00972764 |                    0.00644674 | OK                 |
| TJS_RUB    | GT_C           | F=0.850|A=NONE|R=0.002  |         0.85 |      nan     |        0.002 | VALIDATED_RULE |      275 |          81 |          0.294545  |   0.123457 |    0.123457 | 0.833333 |         0.0447325 |  2.75989 |                  0.00972764 |                    0.00644674 | OK                 |
| UZS_RUB    | GT_A           | F=0.800|A=0.000|R=0.002 |         0.8  |        0     |        0.002 | VALIDATED_RULE |      275 |          19 |          0.0690909 |   0.421053 |    0.421053 | 0.216216 |         0.132807  |  3.17041 |                  0.0108298  |                    0.00617866 | OK                 |
| UZS_RUB    | GT_B           | F=0.800|A=0.000|R=0.002 |         0.8  |        0     |        0.002 | VALIDATED_RULE |      275 |          19 |          0.0690909 |   0.421053 |    0.421053 | 0.258065 |         0.108246  |  3.88979 |                  0.0108298  |                    0.00617866 | OK                 |
| UZS_RUB    | GT_C           | F=0.800|A=0.000|R=0.002 |         0.8  |        0     |        0.002 | VALIDATED_RULE |      275 |          19 |          0.0690909 |   0.421053 |    0.421053 | 0.727273 |         0.0373684 | 11.2676  |                  0.0108298  |                    0.00617866 | OK                 |

## Leakage

| check                                      | passed   |
|:-------------------------------------------|:---------|
| no test data in threshold selection        | True     |
| no new CatBoost tuning                     | True     |
| exact Stage-04 configs reused              | True     |
| restored Stage-04 validation metrics match | True     |
| validation models trained on TRAIN only    | True     |
| validation origins match approved split    | True     |
| actual regret is labels/evaluation only    | True     |
| test used only after rule fixation         | True     |
| rules selected separately per corridor     | True     |

STAGE 08 LEAKAGE CHECK: **PASS**
