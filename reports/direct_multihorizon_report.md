# Direct Multi-Horizon Forecasting

## Goal

Построен прямой прогноз полного вектора курсов T+1...T+5. Каждый горизонт — отдельная модель, а один горизонт означает следующую официальную quote observation, не календарный день.

## Previous ARIMA result

ARIMA не переобучалась: использованы сохранённые Stage 4 прогнозы на общих origin. Четыре из пяти выбранных ARIMA были эквивалентны Random Walk; устойчивого преимущества над Naive ранее не обнаружено.

| corridor   |      MAE_H5 |   MAE_ratio_vs_naive_H5 |
|:-----------|------------:|------------------------:|
| AMD_RUB    | 0.00349105  |                1        |
| KGS_RUB    | 0.0152463   |                1        |
| KZT_RUB    | 0.00288238  |                0.993455 |
| TJS_RUB    | 0.145904    |                1        |
| UZS_RUB    | 0.000119186 |                1        |

## Data

Источник feature dataset: `data/features/fx_features_daily.parquet`; SHA-256 `6737d1ebec82f66b04f431c79d79680a7d5d8b775e6a335c133ef3d49efcd131`. Строк: 9445, коридоров: 5, период: 2019-01-10 — 2026-09-03. Дубликаты corridor+date: 0.

## Targets

Для h=1...5: `target_log_return_h = ln(rate_(T+h)/rate_T)`. Последние пять котировок каждого ряда помечаются как right-censored и не используются в обучении/оценке.

## Features

`ret_1`, `ret_3`, `ret_5`, `vol_5`, `vol_20`, `dist_min_20`, `favourability_percentile_90`, `dist_sma_20`, `broad_rub_return_1`, `broad_rub_return_3`, `broad_rub_return_5`, `corridor_specific_return_1`, `return_sign_reversal_up`, `reversal_strength`, `near_min_reversal_010`

Использован компактный набор из существующего causal feature dataset. Проверки duplicate/variance/missingness/correlation выполнены только на TRAIN; PCA не применялась.

## Leakage controls

| check                                            | passed   |
|:-------------------------------------------------|:---------|
| all X known at T                                 | True     |
| no actual T+1...T+5 used as features             | True     |
| no future exogenous variables used               | True     |
| no shift(-N) features in X                       | True     |
| no future/regret/good_day/safe labels in X       | True     |
| scaler fit train only                            | True     |
| temporal split only                              | True     |
| purge >= 5                                       | True     |
| hyperparameters selected on validation only      | True     |
| test used once                                   | True     |
| actual future used only as target/evaluation     | True     |
| same forecast origin across all 5 horizon models | True     |

## Temporal split

Повторно использованы границы Stage 2. Между обучающими targets и следующей частью применён purge не менее пяти quote observations. StandardScaler для Ridge обучался внутри pipeline только на TRAIN при selection и на TRAIN+VALIDATION после фиксации alpha.

| corridor   | partition   |   rows_before_complete_case |   rows_after_complete_case |   rows_lost | start               | end                 |   train_validation_purge_observations |   validation_test_purge_observations |
|:-----------|:------------|----------------------------:|---------------------------:|------------:|:--------------------|:--------------------|--------------------------------------:|-------------------------------------:|
| AMD_RUB    | train       |                        1317 |                       1227 |          90 | 2019-05-24 00:00:00 | 2024-05-16 00:00:00 |                                     5 |                                   10 |
| AMD_RUB    | validation  |                         274 |                        274 |           0 | 2024-05-23 00:00:00 | 2025-06-28 00:00:00 |                                     5 |                                   10 |
| AMD_RUB    | refit       |                        1600 |                       1510 |          90 | 2019-05-24 00:00:00 | 2025-07-05 00:00:00 |                                     5 |                                   10 |
| AMD_RUB    | test        |                         275 |                        275 |           0 | 2025-07-12 00:00:00 | 2026-08-20 00:00:00 |                                     5 |                                   10 |
| KGS_RUB    | train       |                        1317 |                       1227 |          90 | 2019-05-24 00:00:00 | 2024-05-16 00:00:00 |                                     5 |                                   10 |
| KGS_RUB    | validation  |                         274 |                        274 |           0 | 2024-05-23 00:00:00 | 2025-06-28 00:00:00 |                                     5 |                                   10 |
| KGS_RUB    | refit       |                        1600 |                       1510 |          90 | 2019-05-24 00:00:00 | 2025-07-05 00:00:00 |                                     5 |                                   10 |
| KGS_RUB    | test        |                         275 |                        275 |           0 | 2025-07-12 00:00:00 | 2026-08-20 00:00:00 |                                     5 |                                   10 |
| KZT_RUB    | train       |                        1317 |                       1227 |          90 | 2019-05-24 00:00:00 | 2024-05-16 00:00:00 |                                     5 |                                   10 |
| KZT_RUB    | validation  |                         274 |                        274 |           0 | 2024-05-23 00:00:00 | 2025-06-28 00:00:00 |                                     5 |                                   10 |
| KZT_RUB    | refit       |                        1600 |                       1510 |          90 | 2019-05-24 00:00:00 | 2025-07-05 00:00:00 |                                     5 |                                   10 |
| KZT_RUB    | test        |                         275 |                        275 |           0 | 2025-07-12 00:00:00 | 2026-08-20 00:00:00 |                                     5 |                                   10 |
| TJS_RUB    | train       |                        1317 |                       1227 |          90 | 2019-05-24 00:00:00 | 2024-05-16 00:00:00 |                                     5 |                                   10 |
| TJS_RUB    | validation  |                         274 |                        274 |           0 | 2024-05-23 00:00:00 | 2025-06-28 00:00:00 |                                     5 |                                   10 |
| TJS_RUB    | refit       |                        1600 |                       1510 |          90 | 2019-05-24 00:00:00 | 2025-07-05 00:00:00 |                                     5 |                                   10 |
| TJS_RUB    | test        |                         275 |                        275 |           0 | 2025-07-12 00:00:00 | 2026-08-20 00:00:00 |                                     5 |                                   10 |
| UZS_RUB    | train       |                        1317 |                       1227 |          90 | 2019-05-24 00:00:00 | 2024-05-16 00:00:00 |                                     5 |                                   10 |
| UZS_RUB    | validation  |                         274 |                        274 |           0 | 2024-05-23 00:00:00 | 2025-06-28 00:00:00 |                                     5 |                                   10 |
| UZS_RUB    | refit       |                        1600 |                       1510 |          90 | 2019-05-24 00:00:00 | 2025-07-05 00:00:00 |                                     5 |                                   10 |
| UZS_RUB    | test        |                         275 |                        275 |           0 | 2025-07-12 00:00:00 | 2026-08-20 00:00:00 |                                     5 |                                   10 |

## Models

Ridge: alpha ∈ {0.1, 1, 10, 100}. GradientBoostingRegressor: n_estimators ∈ {100, 200}, max_depth ∈ {2, 3}, learning_rate ∈ {0.03, 0.05}. Конфигурация выбиралась отдельно для corridor×horizon только по validation MAE в rate space.

| corridor   |   horizon | model                    | params                                                       |         MAE |
|:-----------|----------:|:-------------------------|:-------------------------------------------------------------|------------:|
| AMD_RUB    |         1 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 100} | 0.00167358  |
| AMD_RUB    |         1 | DIRECT_RIDGE             | {"alpha": 0.1}                                               | 0.00167215  |
| AMD_RUB    |         2 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 3, "n_estimators": 100} | 0.0027342   |
| AMD_RUB    |         2 | DIRECT_RIDGE             | {"alpha": 1.0}                                               | 0.00270271  |
| AMD_RUB    |         3 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.00342168  |
| AMD_RUB    |         3 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.00342279  |
| AMD_RUB    |         4 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.0038728   |
| AMD_RUB    |         4 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.00392996  |
| AMD_RUB    |         5 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.00427937  |
| AMD_RUB    |         5 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.00430181  |
| KGS_RUB    |         1 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.00744562  |
| KGS_RUB    |         1 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.00739869  |
| KGS_RUB    |         2 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.05, "max_depth": 3, "n_estimators": 100} | 0.0119794   |
| KGS_RUB    |         2 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.0120573   |
| KGS_RUB    |         3 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.0152809   |
| KGS_RUB    |         3 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.0151785   |
| KGS_RUB    |         4 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.0173485   |
| KGS_RUB    |         4 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.0174019   |
| KGS_RUB    |         5 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.0189315   |
| KGS_RUB    |         5 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.0187885   |
| KZT_RUB    |         1 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.00155883  |
| KZT_RUB    |         1 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.00155836  |
| KZT_RUB    |         2 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.00243637  |
| KZT_RUB    |         2 | DIRECT_RIDGE             | {"alpha": 0.1}                                               | 0.00234066  |
| KZT_RUB    |         3 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 3, "n_estimators": 100} | 0.00286344  |
| KZT_RUB    |         3 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.00275261  |
| KZT_RUB    |         4 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.00317557  |
| KZT_RUB    |         4 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.00306411  |
| KZT_RUB    |         5 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.00354983  |
| KZT_RUB    |         5 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.0033013   |
| TJS_RUB    |         1 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.0635229   |
| TJS_RUB    |         1 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.0660048   |
| TJS_RUB    |         2 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.103739    |
| TJS_RUB    |         2 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.10349     |
| TJS_RUB    |         3 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.130466    |
| TJS_RUB    |         3 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.130589    |
| TJS_RUB    |         4 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.145295    |
| TJS_RUB    |         4 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.148912    |
| TJS_RUB    |         5 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.159762    |
| TJS_RUB    |         5 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.162253    |
| UZS_RUB    |         1 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.05, "max_depth": 2, "n_estimators": 100} | 5.19002e-05 |
| UZS_RUB    |         1 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 5.23251e-05 |
| UZS_RUB    |         2 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 200} | 8.47094e-05 |
| UZS_RUB    |         2 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 8.44811e-05 |
| UZS_RUB    |         3 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 3, "n_estimators": 100} | 0.000107502 |
| UZS_RUB    |         3 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.000106444 |
| UZS_RUB    |         4 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.000119534 |
| UZS_RUB    |         4 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.000121027 |
| UZS_RUB    |         5 | DIRECT_GRADIENT_BOOSTING | {"learning_rate": 0.03, "max_depth": 2, "n_estimators": 100} | 0.00012972  |
| UZS_RUB    |         5 | DIRECT_RIDGE             | {"alpha": 100.0}                                             | 0.000129979 |

## H1-H5 metrics

| corridor   | model                    |      MAE_H1 |      MAE_H2 |      MAE_H3 |      MAE_H4 |      MAE_H5 |     RMSE_H1 |     RMSE_H2 |     RMSE_H3 |     RMSE_H4 |     RMSE_H5 |      DA_H1 |    DA_H2 |    DA_H3 |    DA_H4 |    DA_H5 |
|:-----------|:-------------------------|------------:|------------:|------------:|------------:|------------:|------------:|------------:|------------:|------------:|------------:|-----------:|---------:|---------:|---------:|---------:|
| AMD_RUB    | ARIMA_RATE               | 0.00133459  | 0.00204426  | 0.00268857  | 0.00313197  | 0.00349105  | 0.00176497  | 0.00268705  | 0.00341342  | 0.00394831  | 0.00441283  | 0          | 0        | 0        | 0        | 0        |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | 0.00131055  | 0.00199167  | 0.00265248  | 0.00307821  | 0.0034355   | 0.0017432   | 0.00263734  | 0.00338438  | 0.00389981  | 0.00434369  | 0.574545   | 0.589091 | 0.527273 | 0.581818 | 0.556364 |
| AMD_RUB    | DIRECT_RIDGE             | 0.00132702  | 0.00200269  | 0.00264001  | 0.00307971  | 0.00346231  | 0.00175603  | 0.00267807  | 0.00338611  | 0.00391861  | 0.00438689  | 0.552727   | 0.578182 | 0.552727 | 0.574545 | 0.567273 |
| AMD_RUB    | NAIVE                    | 0.00133459  | 0.00204426  | 0.00268857  | 0.00313197  | 0.00349105  | 0.00176497  | 0.00268705  | 0.00341342  | 0.00394831  | 0.00441283  | 0          | 0        | 0        | 0        | 0        |
| KGS_RUB    | ARIMA_RATE               | 0.00572163  | 0.00885986  | 0.0116641   | 0.0136088   | 0.0152463   | 0.00761956  | 0.0116344   | 0.0148262   | 0.0172014   | 0.01927     | 0          | 0        | 0        | 0        | 0        |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | 0.00566377  | 0.00859246  | 0.0116019   | 0.0134625   | 0.0150697   | 0.00753583  | 0.0113707   | 0.0147387   | 0.0171011   | 0.0189889   | 0.552727   | 0.618182 | 0.56     | 0.592727 | 0.56     |
| KGS_RUB    | DIRECT_RIDGE             | 0.00577937  | 0.00885462  | 0.0116455   | 0.013552    | 0.0152281   | 0.00754575  | 0.0115883   | 0.0148267   | 0.0172666   | 0.0194239   | 0.516364   | 0.52     | 0.512727 | 0.556364 | 0.563636 |
| KGS_RUB    | NAIVE                    | 0.00572163  | 0.00885986  | 0.0116641   | 0.0136088   | 0.0152463   | 0.00761956  | 0.0116344   | 0.0148262   | 0.0172014   | 0.01927     | 0          | 0        | 0        | 0        | 0        |
| KZT_RUB    | ARIMA_RATE               | 0.0012422   | 0.00190912  | 0.00229101  | 0.00262758  | 0.00288238  | 0.00165901  | 0.0024444   | 0.00297865  | 0.00346849  | 0.00388556  | 0.541818   | 0.461818 | 0.487273 | 0.538182 | 0.523636 |
| KZT_RUB    | DIRECT_GRADIENT_BOOSTING | 0.00122865  | 0.00185307  | 0.00227251  | 0.00261759  | 0.00290853  | 0.00162641  | 0.00238303  | 0.00291386  | 0.00341966  | 0.0038653   | 0.581818   | 0.592727 | 0.476364 | 0.563636 | 0.530909 |
| KZT_RUB    | DIRECT_RIDGE             | 0.00127795  | 0.00198032  | 0.00235155  | 0.00274131  | 0.00309982  | 0.00168066  | 0.00253368  | 0.00303955  | 0.00358011  | 0.0040595   | 0.530909   | 0.483636 | 0.490909 | 0.534545 | 0.465455 |
| KZT_RUB    | NAIVE                    | 0.00124177  | 0.00188179  | 0.00228833  | 0.00264349  | 0.00290137  | 0.00165307  | 0.00242816  | 0.00296781  | 0.00345719  | 0.0038783   | 0          | 0        | 0        | 0        | 0        |
| TJS_RUB    | ARIMA_RATE               | 0.0549224   | 0.0856036   | 0.112715    | 0.131013    | 0.145904    | 0.0740897   | 0.111818    | 0.141462    | 0.16386     | 0.182237    | 0.00363636 | 0        | 0        | 0        | 0        |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | 0.0545077   | 0.0850744   | 0.113803    | 0.132167    | 0.146884    | 0.0733686   | 0.112257    | 0.14499     | 0.167351    | 0.183766    | 0.549091   | 0.570909 | 0.545455 | 0.541818 | 0.541818 |
| TJS_RUB    | DIRECT_RIDGE             | 0.0538225   | 0.0819791   | 0.108696    | 0.128413    | 0.140707    | 0.0713514   | 0.10838     | 0.138842    | 0.160161    | 0.176854    | 0.538182   | 0.621818 | 0.581818 | 0.578182 | 0.581818 |
| TJS_RUB    | NAIVE                    | 0.0549224   | 0.0856036   | 0.112715    | 0.131013    | 0.145904    | 0.0740897   | 0.111818    | 0.141462    | 0.16386     | 0.182237    | 0.00363636 | 0        | 0        | 0        | 0        |
| UZS_RUB    | ARIMA_RATE               | 4.76528e-05 | 7.5073e-05  | 9.61892e-05 | 0.000106994 | 0.000119186 | 6.1553e-05  | 9.55948e-05 | 0.000120001 | 0.000135706 | 0.000149127 | 0.00727273 | 0        | 0        | 0        | 0        |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | 4.69317e-05 | 7.27776e-05 | 9.39797e-05 | 0.000106178 | 0.000118489 | 6.12826e-05 | 9.41942e-05 | 0.000117524 | 0.000134927 | 0.000148285 | 0.585455   | 0.607273 | 0.578182 | 0.552727 | 0.563636 |
| UZS_RUB    | DIRECT_RIDGE             | 4.711e-05   | 7.38698e-05 | 9.46381e-05 | 0.000105887 | 0.00011874  | 6.082e-05   | 9.46784e-05 | 0.000119211 | 0.000135303 | 0.00014889  | 0.538182   | 0.585455 | 0.574545 | 0.596364 | 0.556364 |
| UZS_RUB    | NAIVE                    | 4.76528e-05 | 7.5073e-05  | 9.61892e-05 | 0.000106994 | 0.000119186 | 6.1553e-05  | 9.55948e-05 | 0.000120001 | 0.000135706 | 0.000149127 | 0.00727273 | 0        | 0        | 0        | 0        |

Directional Accuracy использует прежнее правило: совпадающие знаки верны, включая zero/zero; zero/non-zero неверно.

## Path metrics

| corridor   | model                    |   Path_MAE_5 |
|:-----------|:-------------------------|-------------:|
| AMD_RUB    | ARIMA_RATE               |  0.00253809  |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING |  0.00249368  |
| AMD_RUB    | DIRECT_RIDGE             |  0.00250235  |
| AMD_RUB    | NAIVE                    |  0.00253809  |
| KGS_RUB    | ARIMA_RATE               |  0.0110201   |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING |  0.0108781   |
| KGS_RUB    | DIRECT_RIDGE             |  0.0110119   |
| KGS_RUB    | NAIVE                    |  0.0110201   |
| KZT_RUB    | ARIMA_RATE               |  0.00219046  |
| KZT_RUB    | DIRECT_GRADIENT_BOOSTING |  0.00217607  |
| KZT_RUB    | DIRECT_RIDGE             |  0.00229019  |
| KZT_RUB    | NAIVE                    |  0.00219135  |
| TJS_RUB    | ARIMA_RATE               |  0.106032    |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING |  0.106487    |
| TJS_RUB    | DIRECT_RIDGE             |  0.102723    |
| TJS_RUB    | NAIVE                    |  0.106032    |
| UZS_RUB    | ARIMA_RATE               |  8.90189e-05 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING |  8.76713e-05 |
| UZS_RUB    | DIRECT_RIDGE             |  8.80488e-05 |
| UZS_RUB    | NAIVE                    |  8.90189e-05 |

## Future-best metrics

| corridor   | model                    |   Future_Best_MAE_5 |
|:-----------|:-------------------------|--------------------:|
| AMD_RUB    | ARIMA_RATE               |         0.00249215  |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING |         0.00246445  |
| AMD_RUB    | DIRECT_RIDGE             |         0.00246712  |
| AMD_RUB    | NAIVE                    |         0.00249215  |
| KGS_RUB    | ARIMA_RATE               |         0.0111221   |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING |         0.0108287   |
| KGS_RUB    | DIRECT_RIDGE             |         0.0105776   |
| KGS_RUB    | NAIVE                    |         0.0111221   |
| KZT_RUB    | ARIMA_RATE               |         0.00211277  |
| KZT_RUB    | DIRECT_GRADIENT_BOOSTING |         0.00206593  |
| KZT_RUB    | DIRECT_RIDGE             |         0.00212416  |
| KZT_RUB    | NAIVE                    |         0.0021244   |
| TJS_RUB    | ARIMA_RATE               |         0.105599    |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING |         0.105723    |
| TJS_RUB    | DIRECT_RIDGE             |         0.103784    |
| TJS_RUB    | NAIVE                    |         0.105599    |
| UZS_RUB    | ARIMA_RATE               |         8.75729e-05 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING |         8.4522e-05  |
| UZS_RUB    | DIRECT_RIDGE             |         8.50556e-05 |
| UZS_RUB    | NAIVE                    |         8.75729e-05 |

## Regret metrics

| corridor   | model                    |   Regret_MAE_5 |
|:-----------|:-------------------------|---------------:|
| AMD_RUB    | ARIMA_RATE               |     0.0100446  |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING |     0.00977502 |
| AMD_RUB    | DIRECT_RIDGE             |     0.00962674 |
| AMD_RUB    | NAIVE                    |     0.0100446  |
| KGS_RUB    | ARIMA_RATE               |     0.0105341  |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING |     0.0101231  |
| KGS_RUB    | DIRECT_RIDGE             |     0.00980544 |
| KGS_RUB    | NAIVE                    |     0.0105341  |
| KZT_RUB    | ARIMA_RATE               |     0.0110167  |
| KZT_RUB    | DIRECT_GRADIENT_BOOSTING |     0.0109455  |
| KZT_RUB    | DIRECT_RIDGE             |     0.011119   |
| KZT_RUB    | NAIVE                    |     0.011313   |
| TJS_RUB    | ARIMA_RATE               |     0.0105816  |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING |     0.0104847  |
| TJS_RUB    | DIRECT_RIDGE             |     0.0100312  |
| TJS_RUB    | NAIVE                    |     0.0105816  |
| UZS_RUB    | ARIMA_RATE               |     0.0113733  |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING |     0.0108602  |
| UZS_RUB    | DIRECT_RIDGE             |     0.0108283  |
| UZS_RUB    | NAIVE                    |     0.0113733  |

Фактические future-best/regret используются исключительно для оценки, никогда как признаки.

## Baseline comparison

| corridor   | model                    |      MAE_H5 |   MAE_ratio_vs_naive_H5 | beats_naive_H5   |
|:-----------|:-------------------------|------------:|------------------------:|:-----------------|
| AMD_RUB    | ARIMA_RATE               | 0.00349105  |                1        | False            |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | 0.0034355   |                0.984088 | True             |
| AMD_RUB    | DIRECT_RIDGE             | 0.00346231  |                0.991767 | True             |
| AMD_RUB    | NAIVE                    | 0.00349105  |                1        | False            |
| KGS_RUB    | ARIMA_RATE               | 0.0152463   |                1        | False            |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | 0.0150697   |                0.988419 | True             |
| KGS_RUB    | DIRECT_RIDGE             | 0.0152281   |                0.998804 | True             |
| KGS_RUB    | NAIVE                    | 0.0152463   |                1        | False            |
| KZT_RUB    | ARIMA_RATE               | 0.00288238  |                0.993455 | True             |
| KZT_RUB    | DIRECT_GRADIENT_BOOSTING | 0.00290853  |                1.00247  | False            |
| KZT_RUB    | DIRECT_RIDGE             | 0.00309982  |                1.0684   | False            |
| KZT_RUB    | NAIVE                    | 0.00290137  |                1        | False            |
| TJS_RUB    | ARIMA_RATE               | 0.145904    |                1        | False            |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | 0.146884    |                1.00672  | False            |
| TJS_RUB    | DIRECT_RIDGE             | 0.140707    |                0.964377 | True             |
| TJS_RUB    | NAIVE                    | 0.145904    |                1        | False            |
| UZS_RUB    | ARIMA_RATE               | 0.000119186 |                1        | False            |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | 0.000118489 |                0.994159 | True             |
| UZS_RUB    | DIRECT_RIDGE             | 0.00011874  |                0.996258 | True             |
| UZS_RUB    | NAIVE                    | 0.000119186 |                1        | False            |

Лучшая direct-family превзошла Naive по H5 в 4/5 коридоров. Это тестовое сравнение, а не новый этап выбора гиперпараметров.

## Feature importance

| corridor   | model                    | feature                     |   importance |   rank |
|:-----------|:-------------------------|:----------------------------|-------------:|-------:|
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20                      |   0.288108   |      1 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | reversal_strength           |   0.275043   |      2 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | vol_5                       |   0.0788189  |      3 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | dist_min_20                 |   0.0495105  |      4 |
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_3          |   0.0480601  |      5 |
| AMD_RUB    | DIRECT_RIDGE             | vol_5                       |   0.00556679 |      1 |
| AMD_RUB    | DIRECT_RIDGE             | vol_20                      |   0.00548283 |      2 |
| AMD_RUB    | DIRECT_RIDGE             | broad_rub_return_5          |   0.00519668 |      3 |
| AMD_RUB    | DIRECT_RIDGE             | ret_5                       |   0.00339235 |      4 |
| AMD_RUB    | DIRECT_RIDGE             | broad_rub_return_3          |   0.00331709 |      5 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20                      |   0.302121   |      1 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | dist_sma_20                 |   0.131741   |      2 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | reversal_strength           |   0.0901003  |      3 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_3          |   0.069579   |      4 |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_5                       |   0.0668885  |      5 |
| KGS_RUB    | DIRECT_RIDGE             | vol_20                      |   0.00600739 |      1 |
| KGS_RUB    | DIRECT_RIDGE             | dist_sma_20                 |   0.00565382 |      2 |
| KGS_RUB    | DIRECT_RIDGE             | broad_rub_return_5          |   0.00453337 |      3 |
| KGS_RUB    | DIRECT_RIDGE             | vol_5                       |   0.00349521 |      4 |
| KGS_RUB    | DIRECT_RIDGE             | broad_rub_return_3          |   0.00308138 |      5 |
| KZT_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20                      |   0.279581   |      1 |
| KZT_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_5          |   0.203127   |      2 |
| KZT_RUB    | DIRECT_GRADIENT_BOOSTING | dist_sma_20                 |   0.129337   |      3 |
| KZT_RUB    | DIRECT_GRADIENT_BOOSTING | reversal_strength           |   0.0703585  |      4 |
| KZT_RUB    | DIRECT_GRADIENT_BOOSTING | vol_5                       |   0.0670334  |      5 |
| KZT_RUB    | DIRECT_RIDGE             | vol_20                      |   0.00757447 |      1 |
| KZT_RUB    | DIRECT_RIDGE             | dist_sma_20                 |   0.00705933 |      2 |
| KZT_RUB    | DIRECT_RIDGE             | broad_rub_return_5          |   0.00576579 |      3 |
| KZT_RUB    | DIRECT_RIDGE             | favourability_percentile_90 |   0.00321425 |      4 |
| KZT_RUB    | DIRECT_RIDGE             | ret_5                       |   0.00292797 |      5 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20                      |   0.33071    |      1 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | corridor_specific_return_1  |   0.158616   |      2 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | reversal_strength           |   0.130489   |      3 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_1          |   0.0681047  |      4 |
| TJS_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_5          |   0.0665013  |      5 |
| TJS_RUB    | DIRECT_RIDGE             | vol_20                      |   0.00685696 |      1 |
| TJS_RUB    | DIRECT_RIDGE             | vol_5                       |   0.00363012 |      2 |
| TJS_RUB    | DIRECT_RIDGE             | ret_5                       |   0.00352768 |      3 |
| TJS_RUB    | DIRECT_RIDGE             | corridor_specific_return_1  |   0.00261802 |      4 |
| TJS_RUB    | DIRECT_RIDGE             | dist_sma_20                 |   0.00252863 |      5 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_20                      |   0.321964   |      1 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | reversal_strength           |   0.155636   |      2 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | vol_5                       |   0.0808882  |      3 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | dist_sma_20                 |   0.0743333  |      4 |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | broad_rub_return_3          |   0.068443   |      5 |
| UZS_RUB    | DIRECT_RIDGE             | vol_20                      |   0.00590747 |      1 |
| UZS_RUB    | DIRECT_RIDGE             | vol_5                       |   0.0056026  |      2 |
| UZS_RUB    | DIRECT_RIDGE             | dist_min_20                 |   0.00504561 |      3 |
| UZS_RUB    | DIRECT_RIDGE             | broad_rub_return_5          |   0.00283842 |      4 |
| UZS_RUB    | DIRECT_RIDGE             | favourability_percentile_90 |   0.00220033 |      5 |

Коэффициенты Ridge стандартизированы благодаря TRAIN-fit scaler; Gradient Boosting показывает встроенные importance. Это predictive associations, не причинные эффекты.

## Conclusions

| corridor   | best_endpoint_model_h5   | best_path_model          | best_future_best_model   | best_regret_model        |
|:-----------|:-------------------------|:-------------------------|:-------------------------|:-------------------------|
| AMD_RUB    | DIRECT_GRADIENT_BOOSTING | DIRECT_GRADIENT_BOOSTING | DIRECT_GRADIENT_BOOSTING | DIRECT_RIDGE             |
| KGS_RUB    | DIRECT_GRADIENT_BOOSTING | DIRECT_GRADIENT_BOOSTING | DIRECT_RIDGE             | DIRECT_RIDGE             |
| KZT_RUB    | ARIMA_RATE               | DIRECT_GRADIENT_BOOSTING | DIRECT_GRADIENT_BOOSTING | DIRECT_GRADIENT_BOOSTING |
| TJS_RUB    | DIRECT_RIDGE             | DIRECT_RIDGE             | DIRECT_RIDGE             | DIRECT_RIDGE             |
| UZS_RUB    | DIRECT_GRADIENT_BOOSTING | DIRECT_GRADIENT_BOOSTING | DIRECT_GRADIENT_BOOSTING | DIRECT_RIDGE             |

DIRECT MULTIHORIZON LEAKAGE CHECK: **PASS**

DIRECT MULTIHORIZON FORECASTING: **PASS**
