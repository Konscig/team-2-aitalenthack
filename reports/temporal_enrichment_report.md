# Temporal Feature Enrichment

## Гипотеза

Проверяется incremental signal короткой истории ключевых causal-признаков и компактного regime context при неизменных targets, split, model families и предыдущих configurations.

## Features

Итоговое число: 28. `ret_1`, `ret_3`, `ret_5`, `vol_5`, `vol_20`, `dist_min_20`, `favourability_percentile_90`, `dist_sma_20`, `broad_rub_return_1`, `broad_rub_return_3`, `broad_rub_return_5`, `corridor_specific_return_1`, `return_sign_reversal_up`, `reversal_strength`, `near_min_reversal_010`, `ret_1_lag1`, `ret_1_lag2`, `ret_1_lag3`, `vol_20_lag3`, `broad_rub_return_1_lag1`, `broad_rub_return_1_lag2`, `broad_rub_return_1_lag3`, `corridor_specific_return_1_lag1`, `corridor_specific_return_1_lag2`, `corridor_specific_return_1_lag3`, `vol_ratio_20_60`, `vol_20_change_3`, `momentum_spread`

| feature                         | kind   | formula                              | source_feature             |   lag | available_at_t   |
|:--------------------------------|:-------|:-------------------------------------|:---------------------------|------:|:-----------------|
| ret_1_lag1                      | lag    | ret_1.shift(+1)                      | ret_1                      |     1 | True             |
| ret_1_lag2                      | lag    | ret_1.shift(+2)                      | ret_1                      |     2 | True             |
| ret_1_lag3                      | lag    | ret_1.shift(+3)                      | ret_1                      |     3 | True             |
| vol_20_lag1                     | lag    | vol_20.shift(+1)                     | vol_20                     |     1 | True             |
| vol_20_lag2                     | lag    | vol_20.shift(+2)                     | vol_20                     |     2 | True             |
| vol_20_lag3                     | lag    | vol_20.shift(+3)                     | vol_20                     |     3 | True             |
| broad_rub_return_1_lag1         | lag    | broad_rub_return_1.shift(+1)         | broad_rub_return_1         |     1 | True             |
| broad_rub_return_1_lag2         | lag    | broad_rub_return_1.shift(+2)         | broad_rub_return_1         |     2 | True             |
| broad_rub_return_1_lag3         | lag    | broad_rub_return_1.shift(+3)         | broad_rub_return_1         |     3 | True             |
| corridor_specific_return_1_lag1 | lag    | corridor_specific_return_1.shift(+1) | corridor_specific_return_1 |     1 | True             |
| corridor_specific_return_1_lag2 | lag    | corridor_specific_return_1.shift(+2) | corridor_specific_return_1 |     2 | True             |
| corridor_specific_return_1_lag3 | lag    | corridor_specific_return_1.shift(+3) | corridor_specific_return_1 |     3 | True             |
| vol_ratio_20_60                 | regime | vol_20 / vol_60                      | vol_20,vol_60              |     0 | True             |
| vol_20_change_3                 | regime | vol_20 / vol_20.shift(+3) - 1        | vol_20                     |     3 | True             |
| momentum_spread                 | regime | ret_3 - ret_10                       | ret_3,ret_10               |     0 | True             |

## Cleanup на TRAIN

| feature                         | feature_group   | available_at_t   | used   |   train_missing_share |   train_variance | exact_duplicate_of   | correlated_with   |   correlation |
|:--------------------------------|:----------------|:-----------------|:-------|----------------------:|-----------------:|:---------------------|:------------------|--------------:|
| ret_1                           | BASE            | True             | True   |            0.00075643 |      0.000191018 |                      |                   |    nan        |
| ret_3                           | BASE            | True             | True   |            0.00226929 |      0.000643848 |                      |                   |    nan        |
| ret_5                           | BASE            | True             | True   |            0.00378215 |      0.00113376  |                      |                   |    nan        |
| vol_5                           | BASE            | True             | True   |            0.00378215 |      0.000104599 |                      |                   |    nan        |
| vol_20                          | BASE            | True             | True   |            0.0151286  |      8.79716e-05 |                      |                   |    nan        |
| dist_min_20                     | BASE            | True             | True   |            0.0143722  |      0.00260172  |                      |                   |    nan        |
| favourability_percentile_90     | BASE            | True             | True   |            0.0680787  |      0.125108    |                      |                   |    nan        |
| dist_sma_20                     | BASE            | True             | True   |            0.0143722  |      0.00149427  |                      |                   |    nan        |
| broad_rub_return_1              | BASE            | True             | True   |            0.00075643 |      0.000162247 |                      |                   |    nan        |
| broad_rub_return_3              | BASE            | True             | True   |            0.00226929 |      0.000619677 |                      |                   |    nan        |
| broad_rub_return_5              | BASE            | True             | True   |            0.00378215 |      0.00118711  |                      |                   |    nan        |
| corridor_specific_return_1      | BASE            | True             | True   |            0.00075643 |      4.73958e-05 |                      |                   |    nan        |
| return_sign_reversal_up         | BASE            | True             | True   |            0          |      0.174687    |                      |                   |    nan        |
| reversal_strength               | BASE            | True             | True   |            0.00151286 |      0.000349523 |                      |                   |    nan        |
| near_min_reversal_010           | BASE            | True             | True   |            0          |      0.0977702   |                      |                   |    nan        |
| ret_1_lag1                      | NEW_TEMPORAL    | True             | True   |            0.00151286 |      0.000191158 |                      |                   |    nan        |
| ret_1_lag2                      | NEW_TEMPORAL    | True             | True   |            0.00226929 |      0.000191297 |                      |                   |    nan        |
| ret_1_lag3                      | NEW_TEMPORAL    | True             | True   |            0.00302572 |      0.000191425 |                      |                   |    nan        |
| vol_20_lag1                     | NEW_TEMPORAL    | True             | False  |            0.015885   |      8.80093e-05 |                      | vol_20            |      0.991611 |
| vol_20_lag2                     | NEW_TEMPORAL    | True             | False  |            0.0166415  |      8.80469e-05 |                      | vol_20            |      0.979493 |
| vol_20_lag3                     | NEW_TEMPORAL    | True             | True   |            0.0173979  |      8.80855e-05 |                      |                   |    nan        |
| broad_rub_return_1_lag1         | NEW_TEMPORAL    | True             | True   |            0.00151286 |      0.000162361 |                      |                   |    nan        |
| broad_rub_return_1_lag2         | NEW_TEMPORAL    | True             | True   |            0.00226929 |      0.000162475 |                      |                   |    nan        |
| broad_rub_return_1_lag3         | NEW_TEMPORAL    | True             | True   |            0.00302572 |      0.000162587 |                      |                   |    nan        |
| corridor_specific_return_1_lag1 | NEW_TEMPORAL    | True             | True   |            0.00151286 |      4.74266e-05 |                      |                   |    nan        |
| corridor_specific_return_1_lag2 | NEW_TEMPORAL    | True             | True   |            0.00226929 |      4.74617e-05 |                      |                   |    nan        |
| corridor_specific_return_1_lag3 | NEW_TEMPORAL    | True             | True   |            0.00302572 |      4.74942e-05 |                      |                   |    nan        |
| vol_ratio_20_60                 | NEW_TEMPORAL    | True             | True   |            0.0453858  |      0.0866001   |                      |                   |    nan        |
| vol_20_change_3                 | NEW_TEMPORAL    | True             | True   |            0.0173979  |      0.0386856   |                      |                   |    nan        |
| momentum_spread                 | NEW_TEMPORAL    | True             | True   |            0.0075643  |      0.00170292  |                      |                   |    nan        |

## Validation comparison

| corridor   |   horizon | model_family             | params                                                       |   base_validation_MAE |   enriched_validation_MAE |   enriched_validation_RMSE |   enriched_validation_DA | validation_preferred_feature_set   | selection_used_test   |
|:-----------|----------:|:-------------------------|:-------------------------------------------------------------|----------------------:|--------------------------:|---------------------------:|-------------------------:|:-----------------------------------|:----------------------|
| AMD_RUB    |         1 | DIRECT_RIDGE             | {"alpha": 0.1}                                               |           0.00167215  |               0.00166802  |                0.00242212  |                 0.587591 | ENRICHED                           | False                 |
| AMD_RUB    |         2 | DIRECT_RIDGE             | {"alpha": 1.0}                                               |           0.00270271  |               0.00268196  |                0.0038499   |                 0.60219  | ENRICHED                           | False                 |
| AMD_RUB    |         3 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} |           0.00342168  |               0.00345066  |                0.0050365   |                 0.459854 | BASE                               | False                 |
| AMD_RUB    |         4 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} |           0.0038728   |               0.0039035   |                0.00564324  |                 0.492701 | BASE                               | False                 |
| AMD_RUB    |         5 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} |           0.00427937  |               0.00435918  |                0.0064681   |                 0.492701 | BASE                               | False                 |
| KGS_RUB    |         1 | DIRECT_RIDGE             | {"alpha": 100.0}                                             |           0.00739869  |               0.00751998  |                0.010901    |                 0.540146 | BASE                               | False                 |
| KGS_RUB    |         2 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 100} |           0.0119794   |               0.0120263   |                0.0170749   |                 0.478102 | BASE                               | False                 |
| KGS_RUB    |         3 | DIRECT_RIDGE             | {"alpha": 100.0}                                             |           0.0151785   |               0.0152103   |                0.0205356   |                 0.525547 | BASE                               | False                 |
| KGS_RUB    |         4 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} |           0.0173485   |               0.017049    |                0.0239916   |                 0.441606 | ENRICHED                           | False                 |
| KGS_RUB    |         5 | DIRECT_RIDGE             | {"alpha": 100.0}                                             |           0.0187885   |               0.0190283   |                0.0262206   |                 0.514599 | BASE                               | False                 |
| KZT_RUB    |         1 | DIRECT_RIDGE             | {"alpha": 100.0}                                             |           0.00155836  |               0.00160441  |                0.00233879  |                 0.591241 | BASE                               | False                 |
| KZT_RUB    |         2 | DIRECT_RIDGE             | {"alpha": 0.1}                                               |           0.00234066  |               0.00236867  |                0.00339102  |                 0.620438 | BASE                               | False                 |
| KZT_RUB    |         3 | DIRECT_RIDGE             | {"alpha": 100.0}                                             |           0.00275261  |               0.00274427  |                0.00399182  |                 0.616788 | ENRICHED                           | False                 |
| KZT_RUB    |         4 | DIRECT_RIDGE             | {"alpha": 100.0}                                             |           0.00306411  |               0.00305825  |                0.00443286  |                 0.638686 | ENRICHED                           | False                 |
| KZT_RUB    |         5 | DIRECT_RIDGE             | {"alpha": 100.0}                                             |           0.0033013   |               0.00332412  |                0.00474277  |                 0.642336 | BASE                               | False                 |
| TJS_RUB    |         1 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} |           0.0635229   |               0.0641541   |                0.0946715   |                 0.543796 | BASE                               | False                 |
| TJS_RUB    |         2 | DIRECT_RIDGE             | {"alpha": 100.0}                                             |           0.10349     |               0.103547    |                0.145823    |                 0.562044 | BASE                               | False                 |
| TJS_RUB    |         3 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} |           0.130466    |               0.131406    |                0.183652    |                 0.50365  | BASE                               | False                 |
| TJS_RUB    |         4 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} |           0.145295    |               0.146662    |                0.211742    |                 0.525547 | BASE                               | False                 |
| TJS_RUB    |         5 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} |           0.159762    |               0.165617    |                0.250258    |                 0.551095 | BASE                               | False                 |
| UZS_RUB    |         1 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 100} |           5.19002e-05 |               5.49354e-05 |                8.00461e-05 |                 0.565693 | BASE                               | False                 |
| UZS_RUB    |         2 | DIRECT_RIDGE             | {"alpha": 100.0}                                             |           8.44811e-05 |               8.42045e-05 |                0.000117817 |                 0.594891 | ENRICHED                           | False                 |
| UZS_RUB    |         3 | DIRECT_RIDGE             | {"alpha": 100.0}                                             |           0.000106444 |               0.000105516 |                0.000145223 |                 0.576642 | ENRICHED                           | False                 |
| UZS_RUB    |         4 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} |           0.000119534 |               0.000144292 |                0.000207964 |                 0.478102 | BASE                               | False                 |
| UZS_RUB    |         5 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} |           0.00012972  |               0.000153151 |                0.000221302 |                 0.49635  | BASE                               | False                 |

## Locked-test results

| corridor   | model    |      MAE_H1 |     RMSE_H1 |    DA_H1 |      MAE_H2 |     RMSE_H2 |    DA_H2 |      MAE_H3 |     RMSE_H3 |    DA_H3 |      MAE_H4 |    RMSE_H4 |    DA_H4 |      MAE_H5 |     RMSE_H5 |    DA_H5 |   Path_MAE_5 |   Future_Best_MAE_5 |   Regret_MAE_5 |   n_forecasts |   previous_MAE_H5 |   previous_Path_MAE_5 |   previous_Future_Best_MAE_5 |   previous_Regret_MAE_5 |   MAE_H5_ratio |   MAE_H5_improvement_pct | MAE_H5_status    |   Path_MAE_5_ratio |   Path_MAE_5_improvement_pct | Path_MAE_5_status   |   Future_Best_MAE_5_ratio |   Future_Best_MAE_5_improvement_pct | Future_Best_MAE_5_status   |   Regret_MAE_5_ratio |   Regret_MAE_5_improvement_pct | Regret_MAE_5_status   |
|:-----------|:---------|------------:|------------:|---------:|------------:|------------:|---------:|------------:|------------:|---------:|------------:|-----------:|---------:|------------:|------------:|---------:|-------------:|--------------------:|---------------:|--------------:|------------------:|----------------------:|-----------------------------:|------------------------:|---------------:|-------------------------:|:-----------------|-------------------:|-----------------------------:|:--------------------|--------------------------:|------------------------------------:|:---------------------------|---------------------:|-------------------------------:|:----------------------|
| AMD_RUB    | ENRICHED | 0.00133655  | 0.0017617   | 0.574545 | 0.00200784  | 0.00270353  | 0.614545 | 0.00264364  | 0.00337204  | 0.585455 | 0.003087    | 0.00389249 | 0.603636 | 0.00342226  | 0.00430975  | 0.614545 |  0.00249946  |         0.00242721  |     0.0096317  |           275 |       0.0034355   |           0.00249918  |                  0.00243246  |              0.00969101 |       0.996145 |                 0.385527 | PRACTICALLY_TIED |           1.00011  |                   -0.0110558 | WORSE               |                  0.997842 |                            0.215777 | PRACTICALLY_TIED           |             0.99388  |                       0.612032 | PRACTICALLY_TIED      |
| KGS_RUB    | ENRICHED | 0.00590997  | 0.00771301  | 0.509091 | 0.00875374  | 0.0116254   | 0.6      | 0.0117444   | 0.0149866   | 0.501818 | 0.0135068   | 0.01715    | 0.567273 | 0.0153722   | 0.019569    | 0.541818 |  0.0110574   |         0.0104221   |     0.00970215 |           275 |       0.0152281   |           0.0109416   |                  0.0103452   |              0.00966412 |       1.00946  |                -0.94636  | WORSE            |           1.01059  |                   -1.05862   | WORSE               |                  1.00744  |                           -0.744103 | WORSE                      |             1.00393  |                      -0.393498 | WORSE                 |
| KZT_RUB    | ENRICHED | 0.00129132  | 0.00169921  | 0.523636 | 0.0020177   | 0.00256896  | 0.465455 | 0.00240704  | 0.00310691  | 0.461818 | 0.0028148   | 0.003667   | 0.512727 | 0.00322157  | 0.00417671  | 0.458182 |  0.00235049  |         0.00219628  |     0.0115226  |           275 |       0.00309982  |           0.00229019  |                  0.00212416  |              0.011119   |       1.03928  |                -3.92772  | WORSE            |           1.02633  |                   -2.63275   | WORSE               |                  1.03395  |                           -3.39509  | WORSE                      |             1.0363   |                      -3.63018  | WORSE                 |
| TJS_RUB    | ENRICHED | 0.05462     | 0.0734887   | 0.549091 | 0.082417    | 0.108973    | 0.625455 | 0.11403     | 0.146305    | 0.545455 | 0.131964    | 0.167596   | 0.552727 | 0.145115    | 0.181927    | 0.56     |  0.105629    |         0.102718    |     0.0101689  |           275 |       0.146884    |           0.105868    |                  0.103405    |              0.0102364  |       0.987954 |                 1.20465  | IMPROVED         |           0.997744 |                    0.225644  | PRACTICALLY_TIED    |                  0.993356 |                            0.664431 | PRACTICALLY_TIED           |             0.993405 |                       0.659543 | PRACTICALLY_TIED      |
| UZS_RUB    | ENRICHED | 4.65199e-05 | 6.04991e-05 | 0.610909 | 7.34637e-05 | 9.47219e-05 | 0.574545 | 9.54436e-05 | 0.000119766 | 0.556364 | 0.000106299 | 0.00013482 | 0.538182 | 0.000118678 | 0.000148829 | 0.574545 |  8.80807e-05 |         8.38975e-05 |     0.0107466  |           275 |       0.000118489 |           8.80214e-05 |                  8.42824e-05 |              0.0108234  |       1.00159  |                -0.158834 | WORSE            |           1.00067  |                   -0.067316  | WORSE               |                  0.995433 |                            0.456718 | PRACTICALLY_TIED           |             0.992903 |                       0.709691 | PRACTICALLY_TIED      |

## Feature signal

| corridor   | model_family             | feature                         | is_temporal_enrichment   |   importance |   rank |
|:-----------|:-------------------------|:--------------------------------|:-------------------------|-------------:|-------:|
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20                          | False                    |  0.202573    |      1 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | reversal_strength               | False                    |  0.183417    |      2 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20_lag3                     | True                     |  0.171775    |      3 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20_change_3                 | True                     |  0.0855112   |      4 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | vol_ratio_20_60                 | True                     |  0.0687169   |      5 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | ret_1                           | False                    |  0.0368853   |      6 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | dist_min_20                     | False                    |  0.0351868   |      7 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_1              | False                    |  0.0330688   |      8 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | dist_sma_20                     | False                    |  0.0327125   |      9 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | ret_3                           | False                    |  0.0241519   |     10 |
| AMD_RUB    | DIRECT_RIDGE             | ret_3                           | False                    |  0.0470565   |      1 |
| AMD_RUB    | DIRECT_RIDGE             | broad_rub_return_3              | False                    |  0.0242788   |      2 |
| AMD_RUB    | DIRECT_RIDGE             | ret_1                           | False                    |  0.0189825   |      3 |
| AMD_RUB    | DIRECT_RIDGE             | ret_1_lag2                      | True                     |  0.0186891   |      4 |
| AMD_RUB    | DIRECT_RIDGE             | broad_rub_return_1              | False                    |  0.0186682   |      5 |
| AMD_RUB    | DIRECT_RIDGE             | ret_1_lag1                      | True                     |  0.0184019   |      6 |
| AMD_RUB    | DIRECT_RIDGE             | broad_rub_return_1_lag2         | True                     |  0.018272    |      7 |
| AMD_RUB    | DIRECT_RIDGE             | broad_rub_return_1_lag1         | True                     |  0.0178551   |      8 |
| AMD_RUB    | DIRECT_RIDGE             | broad_rub_return_5              | False                    |  0.011635    |      9 |
| AMD_RUB    | DIRECT_RIDGE             | ret_5                           | False                    |  0.010012    |     10 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20                          | False                    |  0.162732    |      1 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | dist_sma_20                     | False                    |  0.120942    |      2 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20_lag3                     | True                     |  0.0984925   |      3 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | momentum_spread                 | True                     |  0.0797878   |      4 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | reversal_strength               | False                    |  0.0699771   |      5 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | dist_min_20                     | False                    |  0.0444266   |      6 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | corridor_specific_return_1_lag2 | True                     |  0.0371664   |      7 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | ret_5                           | False                    |  0.0352043   |      8 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | corridor_specific_return_1_lag3 | True                     |  0.0340192   |      9 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20_change_3                 | True                     |  0.0307945   |     10 |
| KGS_RUB    | DIRECT_RIDGE             | dist_sma_20                     | False                    |  0.00580651  |      1 |
| KGS_RUB    | DIRECT_RIDGE             | vol_20                          | False                    |  0.0042685   |      2 |
| KGS_RUB    | DIRECT_RIDGE             | favourability_percentile_90     | False                    |  0.0032718   |      3 |
| KGS_RUB    | DIRECT_RIDGE             | vol_5                           | False                    |  0.00270502  |      4 |
| KGS_RUB    | DIRECT_RIDGE             | dist_min_20                     | False                    |  0.00217545  |      5 |
| KGS_RUB    | DIRECT_RIDGE             | corridor_specific_return_1_lag2 | True                     |  0.00214745  |      6 |
| KGS_RUB    | DIRECT_RIDGE             | corridor_specific_return_1_lag3 | True                     |  0.00194835  |      7 |
| KGS_RUB    | DIRECT_RIDGE             | vol_20_change_3                 | True                     |  0.0015153   |      8 |
| KGS_RUB    | DIRECT_RIDGE             | corridor_specific_return_1_lag1 | True                     |  0.00148654  |      9 |
| KGS_RUB    | DIRECT_RIDGE             | near_min_reversal_010           | False                    |  0.00147179  |     10 |
| KZT_RUB    | DIRECT_RIDGE             | ret_3                           | False                    |  0.0109066   |      1 |
| KZT_RUB    | DIRECT_RIDGE             | broad_rub_return_3              | False                    |  0.00632256  |      2 |
| KZT_RUB    | DIRECT_RIDGE             | broad_rub_return_5              | False                    |  0.00539655  |      3 |
| KZT_RUB    | DIRECT_RIDGE             | vol_20_lag3                     | True                     |  0.00538024  |      4 |
| KZT_RUB    | DIRECT_RIDGE             | ret_1_lag1                      | True                     |  0.00510057  |      5 |
| KZT_RUB    | DIRECT_RIDGE             | dist_sma_20                     | False                    |  0.00503061  |      6 |
| KZT_RUB    | DIRECT_RIDGE             | ret_1                           | False                    |  0.00467515  |      7 |
| KZT_RUB    | DIRECT_RIDGE             | ret_1_lag2                      | True                     |  0.00459703  |      8 |
| KZT_RUB    | DIRECT_RIDGE             | broad_rub_return_1_lag2         | True                     |  0.0044932   |      9 |
| KZT_RUB    | DIRECT_RIDGE             | broad_rub_return_1_lag1         | True                     |  0.00422186  |     10 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20                          | False                    |  0.222336    |      1 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | corridor_specific_return_1      | False                    |  0.162453    |      2 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | reversal_strength               | False                    |  0.112061    |      3 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20_lag3                     | True                     |  0.104545    |      4 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_1              | False                    |  0.0542298   |      5 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | ret_1                           | False                    |  0.0392399   |      6 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | dist_sma_20                     | False                    |  0.0340554   |      7 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_1_lag1         | True                     |  0.0330018   |      8 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20_change_3                 | True                     |  0.0319839   |      9 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | dist_min_20                     | False                    |  0.0219232   |     10 |
| TJS_RUB    | DIRECT_RIDGE             | ret_5                           | False                    |  0.00315974  |      1 |
| TJS_RUB    | DIRECT_RIDGE             | vol_20_lag3                     | True                     |  0.00298215  |      2 |
| TJS_RUB    | DIRECT_RIDGE             | vol_20                          | False                    |  0.00245617  |      3 |
| TJS_RUB    | DIRECT_RIDGE             | vol_5                           | False                    |  0.00241402  |      4 |
| TJS_RUB    | DIRECT_RIDGE             | corridor_specific_return_1      | False                    |  0.00229527  |      5 |
| TJS_RUB    | DIRECT_RIDGE             | broad_rub_return_1              | False                    |  0.00165021  |      6 |
| TJS_RUB    | DIRECT_RIDGE             | momentum_spread                 | True                     |  0.00156068  |      7 |
| TJS_RUB    | DIRECT_RIDGE             | broad_rub_return_5              | False                    |  0.00120546  |      8 |
| TJS_RUB    | DIRECT_RIDGE             | broad_rub_return_1_lag2         | True                     |  0.000935332 |      9 |
| TJS_RUB    | DIRECT_RIDGE             | broad_rub_return_3              | False                    |  0.000903071 |     10 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20_lag3                     | True                     |  0.254642    |      1 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20_change_3                 | True                     |  0.101468    |      2 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | reversal_strength               | False                    |  0.0828814   |      3 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20                          | False                    |  0.0771223   |      4 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_5                           | False                    |  0.0576955   |      5 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | dist_sma_20                     | False                    |  0.0515752   |      6 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_ratio_20_60                 | True                     |  0.046139    |      7 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_3              | False                    |  0.0364824   |      8 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | dist_min_20                     | False                    |  0.0360565   |      9 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_1_lag1         | True                     |  0.034739    |     10 |
| UZS_RUB    | DIRECT_RIDGE             | vol_5                           | False                    |  0.00493112  |      1 |
| UZS_RUB    | DIRECT_RIDGE             | vol_20_lag3                     | True                     |  0.00399853  |      2 |
| UZS_RUB    | DIRECT_RIDGE             | dist_min_20                     | False                    |  0.00289468  |      3 |
| UZS_RUB    | DIRECT_RIDGE             | broad_rub_return_5              | False                    |  0.00257028  |      4 |
| UZS_RUB    | DIRECT_RIDGE             | vol_20                          | False                    |  0.00213373  |      5 |
| UZS_RUB    | DIRECT_RIDGE             | favourability_percentile_90     | False                    |  0.00177962  |      6 |
| UZS_RUB    | DIRECT_RIDGE             | momentum_spread                 | True                     |  0.00128334  |      7 |
| UZS_RUB    | DIRECT_RIDGE             | ret_5                           | False                    |  0.000947316 |      8 |
| UZS_RUB    | DIRECT_RIDGE             | near_min_reversal_010           | False                    |  0.000910528 |      9 |
| UZS_RUB    | DIRECT_RIDGE             | vol_20_change_3                 | True                     |  0.000890318 |     10 |

Importance/standardized coefficients не являются causal effects.

## Leakage

| check                             | passed   |
|:----------------------------------|:---------|
| all lagged features use shift(+N) | True     |
| no future features                | True     |
| same temporal split               | True     |
| same test origins                 | True     |
| validation-only model selection   | True     |
| test locked                       | True     |
| purge >= 5                        | True     |
| targets only used as y            | True     |

TEMPORAL ENRICHMENT LEAKAGE CHECK: **PASS**

## Decision

Полезные temporal/regime признаки в top-10: vol_20_lag3, vol_20_change_3, broad_rub_return_1_lag1, broad_rub_return_1_lag2, momentum_spread, vol_ratio_20_60, ret_1_lag2, ret_1_lag1, corridor_specific_return_1_lag2, corridor_specific_return_1_lag3, corridor_specific_return_1_lag1.

**EXACT_PATH_FORECASTING_PLATEAU**

При `EXACT_PATH_FORECASTING_PLATEAU` рекомендуется остановить дальнейшее усложнение exact H1...H5 и перейти к direct prediction `future_best_5` или `regret_5`.
