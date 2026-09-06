# Model tournament feature screening

Этап использует только реальные quote-time features из официальных данных Банка России. Модели и labels не создавались.

## Dataset

| dataset                                 |   rows |   columns |   numeric_columns | first_date          | last_date           |   corridors |   duplicates_date_corridor |   infinite_values |   total_missing_values |
|:----------------------------------------|-------:|----------:|------------------:|:--------------------|:--------------------|------------:|---------------------------:|------------------:|-----------------------:|
| data/features/fx_features_daily.parquet |   9445 |       104 |                99 | 2019-01-10 00:00:00 | 2026-09-03 00:00:00 |           5 |                          0 |                 0 |                  25870 |

| corridor   |   rows | first_date          | last_date           |
|:-----------|-------:|:--------------------|:--------------------|
| AMD_RUB    |   1889 | 2019-01-10 00:00:00 | 2026-09-03 00:00:00 |
| KGS_RUB    |   1889 | 2019-01-10 00:00:00 | 2026-09-03 00:00:00 |
| KZT_RUB    |   1889 | 2019-01-10 00:00:00 | 2026-09-03 00:00:00 |
| TJS_RUB    |   1889 | 2019-01-10 00:00:00 | 2026-09-03 00:00:00 |
| UZS_RUB    |   1889 | 2019-01-10 00:00:00 | 2026-09-03 00:00:00 |

## Modeling columns

- Identifiers: `['date', 'corridor']`.
- Target / series: `['rate', 'log_ret_1']`.
- Causal features: **100**, из них numeric: **97**.
- Forbidden columns: `[]`; они исключены из modeling features.

## Numeric feature audit

- Near-constant threshold: dominant share ≥ 99.5%.
- Critical missingness threshold: ≥ 50%.
- Constants: `['broad_rub_freshness_days', 'cny_rub_freshness_days', 'eur_rub_freshness_days', 'usd_rub_freshness_days']`.
- Near-constants: `[]`.
- Critical-missingness features: `[]`.

| feature                      | role            | dtype   |   missing_share |   n_unique |         mean |         std |          min |       median |        max |   dominant_value_share | is_constant   | is_near_constant   | is_critical_missingness   |
|:-----------------------------|:----------------|:--------|----------------:|-----------:|-------------:|------------:|-------------:|-------------:|-----------:|-----------------------:|:--------------|:-------------------|:--------------------------|
| broad_rub_freshness_days     | CAUSAL FEATURE  | Int64   |     0           |          1 |  0           |  0          |  0           |  0           |  0         |            1           | True          | False              | False                     |
| broad_rub_return_1           | CAUSAL FEATURE  | float64 |     0.000529381 |       1888 |  0.000215268 |  0.0117623  | -0.0780868   |  3.60835e-05 |  0.121382  |            0.000529661 | False         | False              | False                     |
| broad_rub_return_10          | CAUSAL FEATURE  | float64 |     0.00529381  |       1879 |  0.00249931  |  0.0488861  | -0.222089    |  0.000216624 |  0.491868  |            0.000532198 | False         | False              | False                     |
| broad_rub_return_20          | CAUSAL FEATURE  | float64 |     0.0105876   |       1869 |  0.00500637  |  0.0690577  | -0.370201    |  0.000779282 |  0.585634  |            0.000535045 | False         | False              | False                     |
| broad_rub_return_3           | CAUSAL FEATURE  | float64 |     0.00158814  |       1886 |  0.000688815 |  0.0228589  | -0.116721    |  0.000321632 |  0.232005  |            0.000530223 | False         | False              | False                     |
| broad_rub_return_5           | CAUSAL FEATURE  | float64 |     0.0026469   |       1884 |  0.00118093  |  0.0312405  | -0.179968    |  0.000103896 |  0.280177  |            0.000530786 | False         | False              | False                     |
| broad_rub_z_1                | CAUSAL FEATURE  | float64 |     0.0322922   |       1828 |  0.0271929   |  1.09553    | -8.87462     |  0.00490003  |  9.74362   |            0.000547046 | False         | False              | False                     |
| broad_rub_z_3                | CAUSAL FEATURE  | float64 |     0.033351    |       1826 |  0.0446414   |  1.12714    | -8.7671      |  0.00459576  |  9.00146   |            0.000547645 | False         | False              | False                     |
| broad_rub_z_5                | CAUSAL FEATURE  | float64 |     0.0344097   |       1824 |  0.062192    |  1.14353    | -7.4508      | -0.015421    |  8.29659   |            0.000548246 | False         | False              | False                     |
| cny_rub_freshness_days       | CAUSAL FEATURE  | Int64   |     0           |          1 |  0           |  0          |  0           |  0           |  0         |            1           | True          | False              | False                     |
| corridor_specific_return_1   | CAUSAL FEATURE  | float64 |     0.000529381 |       9439 | -4.58872e-05 |  0.00627072 | -0.142374    |  3.98281e-05 |  0.153453  |            0.000211864 | False         | False              | False                     |
| corridor_specific_return_10  | CAUSAL FEATURE  | float64 |     0.00529381  |       9395 | -0.000694109 |  0.0184261  | -0.251759    | -0.000112511 |  0.177623  |            0.00010644  | False         | False              | False                     |
| corridor_specific_return_3   | CAUSAL FEATURE  | float64 |     0.00158814  |       9430 | -0.000154643 |  0.00994046 | -0.140206    |  6.36309e-05 |  0.119089  |            0.000106045 | False         | False              | False                     |
| corridor_specific_return_5   | CAUSAL FEATURE  | float64 |     0.0026469   |       9420 | -0.000287417 |  0.0127167  | -0.163746    | -2.08854e-05 |  0.149644  |            0.000106157 | False         | False              | False                     |
| days_since_min_20            | CAUSAL FEATURE  | float64 |     0.0100582   |         20 | 10.1923      |  6.9362     |  0           | 11           | 19         |            0.162674    | False         | False              | False                     |
| days_since_min_60            | CAUSAL FEATURE  | float64 |     0.0312335   |         60 | 31.0562      | 21.1491     |  0           | 32           | 59         |            0.091694    | False         | False              | False                     |
| dist_max_10                  | CAUSAL FEATURE  | float64 |     0.00476443  |       7534 | -0.0191513   |  0.0266351  | -0.28207     | -0.0112914   |  0         |            0.198085    | False         | False              | False                     |
| dist_max_180                 | CAUSAL FEATURE  | float64 |     0.0947591   |       8104 | -0.128965    |  0.121161   | -0.571692    | -0.094868    |  0         |            0.0495906   | False         | False              | False                     |
| dist_max_20                  | CAUSAL FEATURE  | float64 |     0.0100582   |       8136 | -0.0311037   |  0.0404231  | -0.410882    | -0.0205166   |  0         |            0.128877    | False         | False              | False                     |
| dist_max_365                 | CAUSAL FEATURE  | float64 |     0.192695    |       7491 | -0.196893    |  0.121563   | -0.571692    | -0.175037    |  0         |            0.0131148   | False         | False              | False                     |
| dist_max_60                  | CAUSAL FEATURE  | float64 |     0.0312335   |       8371 | -0.0629293   |  0.077648   | -0.556797    | -0.039688    |  0         |            0.0838251   | False         | False              | False                     |
| dist_max_90                  | CAUSAL FEATURE  | float64 |     0.0471149   |       8324 | -0.0821828   |  0.0945252  | -0.571692    | -0.0519994   |  0         |            0.0734444   | False         | False              | False                     |
| dist_min_10                  | CAUSAL FEATURE  | float64 |     0.00476443  |       7650 |  0.0202984   |  0.0330418  |  0           |  0.0110379   |  0.475279  |            0.185426    | False         | False              | False                     |
| dist_min_180                 | CAUSAL FEATURE  | float64 |     0.0947591   |       8202 |  0.129763    |  0.140234   |  0           |  0.0811047   |  0.746107  |            0.0382456   | False         | False              | False                     |
| dist_min_20                  | CAUSAL FEATURE  | float64 |     0.0100582   |       8236 |  0.0329953   |  0.0449765  |  0           |  0.0206835   |  0.613122  |            0.117968    | False         | False              | False                     |
| dist_min_365                 | CAUSAL FEATURE  | float64 |     0.192695    |       7410 |  0.22154     |  0.233412   |  0           |  0.129607    |  1.09224   |            0.0255738   | False         | False              | False                     |
| dist_min_60                  | CAUSAL FEATURE  | float64 |     0.0312335   |       8521 |  0.0648867   |  0.0688465  |  0           |  0.0420111   |  0.646238  |            0.0669945   | False         | False              | False                     |
| dist_min_90                  | CAUSAL FEATURE  | float64 |     0.0471149   |       8477 |  0.0833282   |  0.0858604  |  0           |  0.0527405   |  0.726926  |            0.0557778   | False         | False              | False                     |
| dist_sma_10                  | CAUSAL FEATURE  | float64 |     0.00476443  |       9400 |  0.000507454 |  0.0236789  | -0.194842    | -3.30443e-05 |  0.271111  |            0.000106383 | False         | False              | False                     |
| dist_sma_20                  | CAUSAL FEATURE  | float64 |     0.0100582   |       9350 |  0.00109789  |  0.0351115  | -0.268538    | -0.000297069 |  0.367254  |            0.000106952 | False         | False              | False                     |
| dist_sma_5                   | CAUSAL FEATURE  | float64 |     0.00211752  |       9425 |  0.000211548 |  0.0148347  | -0.122978    |  4.60563e-05 |  0.155529  |            0.000106101 | False         | False              | False                     |
| dist_sma_60                  | CAUSAL FEATURE  | float64 |     0.0312335   |       9150 |  0.00296352  |  0.0617487  | -0.331554    |  0.00104364  |  0.514202  |            0.00010929  | False         | False              | False                     |
| down_streak                  | CAUSAL FEATURE  | int64   |     0           |         18 |  1.08332     |  1.59013    |  0           |  0           | 17         |            0.507253    | False         | False              | False                     |
| eur_rub_freshness_days       | CAUSAL FEATURE  | Int64   |     0           |          1 |  0           |  0          |  0           |  0           |  0         |            1           | True          | False              | False                     |
| favourability_percentile_180 | CAUSAL FEATURE  | float64 |     0.0952885   |        181 |  0.493445    |  0.354437   |  0           |  0.494444    |  1         |            0.0495026   | False         | False              | False                     |
| favourability_percentile_20  | CAUSAL FEATURE  | float64 |     0.0105876   |         21 |  0.496747    |  0.358369   |  0           |  0.5         |  1         |            0.126592    | False         | False              | False                     |
| favourability_percentile_365 | CAUSAL FEATURE  | float64 |     0.193224    |        366 |  0.506485    |  0.343492   |  0           |  0.49589     |  1         |            0.0255906   | False         | False              | False                     |
| favourability_percentile_60  | CAUSAL FEATURE  | float64 |     0.0317628   |         61 |  0.484908    |  0.365771   |  0           |  0.466667    |  1         |            0.0831055   | False         | False              | False                     |
| favourability_percentile_90  | CAUSAL FEATURE  | float64 |     0.0476443   |         91 |  0.486134    |  0.363707   |  0           |  0.477778    |  1         |            0.0732629   | False         | False              | False                     |
| mom_10                       | CAUSAL FEATURE  | float64 |     0.00529381  |       9395 |  0.0018052   |  0.0457386  | -0.296097    |  2.45755e-05 |  0.504384  |            0.00010644  | False         | False              | False                     |
| mom_20                       | CAUSAL FEATURE  | float64 |     0.0105876   |       9345 |  0.00346903  |  0.0622357  | -0.42837     |  0.000157089 |  0.600695  |            0.000107009 | False         | False              | False                     |
| mom_3                        | CAUSAL FEATURE  | float64 |     0.00158814  |       9429 |  0.000534172 |  0.0235655  | -0.198364    |  0.000111244 |  0.235738  |            0.000212089 | False         | False              | False                     |
| mom_5                        | CAUSAL FEATURE  | float64 |     0.0026469   |       9420 |  0.000893517 |  0.0309957  | -0.200127    |  0.000161921 |  0.285608  |            0.000106157 | False         | False              | False                     |
| near_min_prev_002            | CAUSAL FEATURE  | int8    |     0           |          2 |  0.161355    |  0.367878   |  0           |  0           |  1         |            0.838645    | False         | False              | False                     |
| near_min_prev_005            | CAUSAL FEATURE  | int8    |     0           |          2 |  0.226046    |  0.418291   |  0           |  0           |  1         |            0.773954    | False         | False              | False                     |
| near_min_prev_010            | CAUSAL FEATURE  | int8    |     0           |          2 |  0.328534    |  0.469705   |  0           |  0           |  1         |            0.671466    | False         | False              | False                     |
| near_min_reversal_002        | CAUSAL FEATURE  | int8    |     0           |          2 |  0.0641609   |  0.245052   |  0           |  0           |  1         |            0.935839    | False         | False              | False                     |
| near_min_reversal_005        | CAUSAL FEATURE  | int8    |     0           |          2 |  0.0802541   |  0.271701   |  0           |  0           |  1         |            0.919746    | False         | False              | False                     |
| near_min_reversal_010        | CAUSAL FEATURE  | int8    |     0           |          2 |  0.104923    |  0.306471   |  0           |  0           |  1         |            0.895077    | False         | False              | False                     |
| percentile_180               | CAUSAL FEATURE  | float64 |     0.0952885   |        181 |  0.506555    |  0.354437   |  0           |  0.505556    |  1         |            0.0495026   | False         | False              | False                     |
| percentile_20                | CAUSAL FEATURE  | float64 |     0.0105876   |         21 |  0.503253    |  0.358369   |  0           |  0.5         |  1         |            0.126592    | False         | False              | False                     |
| percentile_365               | CAUSAL FEATURE  | float64 |     0.193224    |        366 |  0.493515    |  0.343492   |  0           |  0.50411     |  1         |            0.0255906   | False         | False              | False                     |
| percentile_60                | CAUSAL FEATURE  | float64 |     0.0317628   |         61 |  0.515092    |  0.365771   |  0           |  0.533333    |  1         |            0.0831055   | False         | False              | False                     |
| percentile_90                | CAUSAL FEATURE  | float64 |     0.0476443   |         91 |  0.513866    |  0.363707   |  0           |  0.522222    |  1         |            0.0732629   | False         | False              | False                     |
| recipient_usd_implied        | CAUSAL FEATURE  | float64 |     0           |       9440 |  0.022619    |  0.0372247  |  7.68998e-05 |  0.00255611  |  0.108562  |            0.000211752 | False         | False              | False                     |
| recipient_usd_ret_1          | CAUSAL FEATURE  | float64 |     0.000529381 |       9437 | -3.31085e-05 |  0.00568725 | -0.13077     |  3.70572e-08 |  0.152488  |            0.000423729 | False         | False              | False                     |
| recipient_usd_ret_10         | CAUSAL FEATURE  | float64 |     0.00529381  |       9395 | -0.00034908  |  0.0168439  | -0.187717    | -3.05989e-07 |  0.200294  |            0.00010644  | False         | False              | False                     |
| recipient_usd_ret_3          | CAUSAL FEATURE  | float64 |     0.00158814  |       9430 | -0.000108078 |  0.00917303 | -0.14154     | -6.29841e-08 |  0.114056  |            0.000106045 | False         | False              | False                     |
| recipient_usd_ret_5          | CAUSAL FEATURE  | float64 |     0.0026469   |       9420 | -0.000179093 |  0.0117084  | -0.141538    | -1.33526e-07 |  0.152561  |            0.000106157 | False         | False              | False                     |
| ret_1                        | CAUSAL FEATURE  | float64 |     0.000529381 |       9433 |  0.000169381 |  0.0127982  | -0.137311    |  6.74044e-05 |  0.195116  |            0.000847458 | False         | False              | False                     |
| ret_10                       | CAUSAL FEATURE  | float64 |     0.00529381  |       9395 |  0.0018052   |  0.0457386  | -0.296097    |  2.45755e-05 |  0.504384  |            0.00010644  | False         | False              | False                     |
| ret_2                        | CAUSAL FEATURE  | float64 |     0.00105876  |       9434 |  0.000354153 |  0.019024   | -0.13801     |  0.000237809 |  0.21811   |            0.000211977 | False         | False              | False                     |
| ret_20                       | CAUSAL FEATURE  | float64 |     0.0105876   |       9345 |  0.00346903  |  0.0622357  | -0.42837     |  0.000157089 |  0.600695  |            0.000107009 | False         | False              | False                     |
| ret_3                        | CAUSAL FEATURE  | float64 |     0.00158814  |       9429 |  0.000534172 |  0.0235655  | -0.198364    |  0.000111244 |  0.235738  |            0.000212089 | False         | False              | False                     |
| ret_5                        | CAUSAL FEATURE  | float64 |     0.0026469   |       9420 |  0.000893517 |  0.0309957  | -0.200127    |  0.000161921 |  0.285608  |            0.000106157 | False         | False              | False                     |
| return_sign_reversal_up      | CAUSAL FEATURE  | int8    |     0           |          2 |  0.224987    |  0.417596   |  0           |  0           |  1         |            0.775013    | False         | False              | False                     |
| reversal_2d_002              | CAUSAL FEATURE  | int8    |     0           |          2 |  0.0376919   |  0.19046    |  0           |  0           |  1         |            0.962308    | False         | False              | False                     |
| reversal_2d_005              | CAUSAL FEATURE  | int8    |     0           |          2 |  0.0521969   |  0.222436   |  0           |  0           |  1         |            0.947803    | False         | False              | False                     |
| reversal_2d_010              | CAUSAL FEATURE  | int8    |     0           |          2 |  0.0797247   |  0.270881   |  0           |  0           |  1         |            0.920275    | False         | False              | False                     |
| reversal_strength            | CAUSAL FEATURE  | float64 |     0.00105876  |       9435 |  4.09522e-06 |  0.0172016  | -0.224802    |  0.000182868 |  0.241501  |            0.000105988 | False         | False              | False                     |
| rolling_max_10               | CAUSAL FEATURE  | float64 |     0.00476443  |       3638 |  1.77662     |  2.95291    |  0.00507699  |  0.206077    | 10.6719    |            0.00117021  | False         | False              | False                     |
| rolling_max_180              | CAUSAL FEATURE  | float64 |     0.0947591   |        791 |  2.04256     |  3.40035    |  0.00642913  |  0.231488    | 10.6719    |            0.0210526   | False         | False              | False                     |
| rolling_max_20               | CAUSAL FEATURE  | float64 |     0.0100582   |       2520 |  1.80097     |  2.99484    |  0.00550182  |  0.209067    | 10.6719    |            0.00213904  | False         | False              | False                     |
| rolling_max_365              | CAUSAL FEATURE  | float64 |     0.192695    |        233 |  2.23468     |  3.70283    |  0.00697189  |  0.238909    | 10.6719    |            0.0478689   | False         | False              | False                     |
| rolling_max_60               | CAUSAL FEATURE  | float64 |     0.0312335   |       1510 |  1.87346     |  3.12108    |  0.00568627  |  0.218902    | 10.6719    |            0.00655738  | False         | False              | False                     |
| rolling_max_90               | CAUSAL FEATURE  | float64 |     0.0471149   |       1260 |  1.92069     |  3.20128    |  0.00575293  |  0.22424     | 10.6719    |            0.01        | False         | False              | False                     |
| rolling_min_10               | CAUSAL FEATURE  | float64 |     0.00476443  |       3647 |  1.70673     |  2.83472    |  0.00473661  |  0.199705    |  9.46494   |            0.00180851  | False         | False              | False                     |
| rolling_min_180              | CAUSAL FEATURE  | float64 |     0.0947591   |        747 |  1.55399     |  2.58081    |  0.00473661  |  0.178486    |  8.0576    |            0.0210526   | False         | False              | False                     |
| rolling_min_20               | CAUSAL FEATURE  | float64 |     0.0100582   |       2554 |  1.68599     |  2.8        |  0.00473661  |  0.196674    |  9.17995   |            0.00224599  | False         | False              | False                     |
| rolling_min_365              | CAUSAL FEATURE  | float64 |     0.192695    |        508 |  1.46294     |  2.43814    |  0.00473661  |  0.164334    |  7.70613   |            0.0478689   | False         | False              | False                     |
| rolling_min_60               | CAUSAL FEATURE  | float64 |     0.0312335   |       1435 |  1.63707     |  2.71829    |  0.00473661  |  0.192438    |  9.01176   |            0.00655738  | False         | False              | False                     |
| rolling_min_90               | CAUSAL FEATURE  | float64 |     0.0471149   |       1159 |  1.61085     |  2.67399    |  0.00473661  |  0.189965    |  8.75276   |            0.01        | False         | False              | False                     |
| rolling_range_10             | CAUSAL FEATURE  | float64 |     0.00476443  |       9400 |  0.0393887   |  0.0385233  |  0.00251401  |  0.0278273   |  0.409504  |            0.000106383 | False         | False              | False                     |
| rolling_range_20             | CAUSAL FEATURE  | float64 |     0.0100582   |       9348 |  0.0643866   |  0.0588957  |  0.00958293  |  0.0473555   |  0.531025  |            0.000213904 | False         | False              | False                     |
| rolling_range_60             | CAUSAL FEATURE  | float64 |     0.0312335   |       9149 |  0.132172    |  0.110136   |  0.0217438   |  0.101261    |  0.915533  |            0.000218579 | False         | False              | False                     |
| sma_10                       | CAUSAL FEATURE  | float64 |     0.00476443  |       9398 |  1.74022     |  2.89039    |  0.00491527  |  0.203416    |  9.80383   |            0.000212766 | False         | False              | False                     |
| sma_20                       | CAUSAL FEATURE  | float64 |     0.0100582   |       9342 |  1.73948     |  2.8881     |  0.00509531  |  0.203587    |  9.58099   |            0.000213904 | False         | False              | False                     |
| sma_20_vs_60                 | CAUSAL FEATURE  | float64 |     0.0312335   |       9150 |  0.00130873  |  0.0411858  | -0.236259    |  0.000927763 |  0.20776   |            0.00010929  | False         | False              | False                     |
| sma_5                        | CAUSAL FEATURE  | float64 |     0.00211752  |       9401 |  1.74064     |  2.89159    |  0.00486248  |  0.203061    |  9.98958   |            0.000212202 | False         | False              | False                     |
| sma_5_vs_20                  | CAUSAL FEATURE  | float64 |     0.0100582   |       9350 |  0.000737754 |  0.0276083  | -0.203012    | -0.000329914 |  0.254432  |            0.000106952 | False         | False              | False                     |
| sma_60                       | CAUSAL FEATURE  | float64 |     0.0312335   |       9147 |  1.73772     |  2.88187    |  0.00534393  |  0.201843    |  9.34863   |            0.000218579 | False         | False              | False                     |
| up_streak                    | CAUSAL FEATURE  | int64   |     0           |         18 |  1.1747      |  1.74082    |  0           |  1           | 17         |            0.494124    | False         | False              | False                     |
| usd_rub_freshness_days       | CAUSAL FEATURE  | Int64   |     0           |          1 |  0           |  0          |  0           |  0           |  0         |            1           | True          | False              | False                     |
| vol_10                       | CAUSAL FEATURE  | float64 |     0.00529381  |       9395 |  0.00924387  |  0.00850159 |  0.00112001  |  0.00689426  |  0.0925495 |            0.00010644  | False         | False              | False                     |
| vol_20                       | CAUSAL FEATURE  | float64 |     0.0105876   |       9345 |  0.00978267  |  0.00808165 |  0.00248716  |  0.00753922  |  0.0756058 |            0.000107009 | False         | False              | False                     |
| vol_5                        | CAUSAL FEATURE  | float64 |     0.0026469   |       9420 |  0.00860499  |  0.00902937 |  0.000203615 |  0.00619124  |  0.114478  |            0.000106157 | False         | False              | False                     |
| vol_60                       | CAUSAL FEATURE  | float64 |     0.0317628   |       9145 |  0.0104998   |  0.00737899 |  0.00303228  |  0.00860435  |  0.0551938 |            0.000109349 | False         | False              | False                     |
| log_ret_1                    | TARGET / SERIES | float64 |     0.000529381 |       9433 |  8.82985e-05 |  0.0127074  | -0.147701    |  6.74021e-05 |  0.178244  |            0.000847458 | False         | False              | False                     |
| rate                         | TARGET / SERIES | float64 |     0           |       9340 |  1.74102     |  2.89265    |  0.00473661  |  0.203014    | 10.6719    |            0.000317628 | False         | False              | False                     |

## Exact duplicates

| feature_1              | feature_2                |   max_absolute_difference | EXACT_DUPLICATE   | recommended_keep   | recommended_drop                                 | reason                          |
|:-----------------------|:-------------------------|--------------------------:|:------------------|:-------------------|:-------------------------------------------------|:--------------------------------|
| cny_rub_freshness_days | broad_rub_freshness_days |                         0 | True              |                    | cny_rub_freshness_days; broad_rub_freshness_days | exclude both: constant features |
| eur_rub_freshness_days | broad_rub_freshness_days |                         0 | True              |                    | eur_rub_freshness_days; broad_rub_freshness_days | exclude both: constant features |
| eur_rub_freshness_days | cny_rub_freshness_days   |                         0 | True              |                    | eur_rub_freshness_days; cny_rub_freshness_days   | exclude both: constant features |
| ret_10                 | mom_10                   |                         0 | True              | ret_10             | mom_10                                           | prefer ret_N over mom_N         |
| ret_20                 | mom_20                   |                         0 | True              | ret_20             | mom_20                                           | prefer ret_N over mom_N         |
| ret_3                  | mom_3                    |                         0 | True              | ret_3              | mom_3                                            | prefer ret_N over mom_N         |
| ret_5                  | mom_5                    |                         0 | True              | ret_5              | mom_5                                            | prefer ret_N over mom_N         |
| usd_rub_freshness_days | broad_rub_freshness_days |                         0 | True              |                    | usd_rub_freshness_days; broad_rub_freshness_days | exclude both: constant features |
| usd_rub_freshness_days | cny_rub_freshness_days   |                         0 | True              |                    | usd_rub_freshness_days; cny_rub_freshness_days   | exclude both: constant features |
| usd_rub_freshness_days | eur_rub_freshness_days   |                         0 | True              |                    | usd_rub_freshness_days; eur_rub_freshness_days   | exclude both: constant features |

Исходный Parquet не менялся. Для будущих feature models рекомендовано сохранять `ret_N` и исключать дублирующий `mom_N`.

## Correlation analysis

| corridor   |   pairs_ge_090 |   pairs_ge_098 |
|:-----------|---------------:|---------------:|
| AMD_RUB    |             99 |             31 |
| KGS_RUB    |             66 |             14 |
| KZT_RUB    |             64 |             18 |
| TJS_RUB    |             74 |             17 |
| UZS_RUB    |             57 |             10 |

Ниже приведены 15 наиболее сильных Pearson-пар на corridor при `abs(correlation) ≥ 0.90`; полный compact pair table сохранён в выполненных outputs notebook.

| corridor   | feature_1      | feature_2                    |   pearson_corr |   spearman_corr |
|:-----------|:---------------|:-----------------------------|---------------:|----------------:|
| AMD_RUB    | percentile_180 | favourability_percentile_180 |      -1        |       -1        |
| AMD_RUB    | percentile_20  | favourability_percentile_20  |      -1        |       -1        |
| AMD_RUB    | percentile_365 | favourability_percentile_365 |      -1        |       -1        |
| AMD_RUB    | percentile_60  | favourability_percentile_60  |      -1        |       -1        |
| AMD_RUB    | percentile_90  | favourability_percentile_90  |      -1        |       -1        |
| AMD_RUB    | ret_10         | mom_10                       |       1        |        1        |
| AMD_RUB    | ret_20         | mom_20                       |       1        |        1        |
| AMD_RUB    | ret_3          | mom_3                        |       1        |        1        |
| AMD_RUB    | ret_5          | mom_5                        |       1        |        1        |
| AMD_RUB    | sma_5          | sma_10                       |       0.998289 |        0.996489 |
| AMD_RUB    | sma_10         | sma_20                       |       0.996413 |        0.992964 |
| AMD_RUB    | sma_10         | rolling_min_10               |       0.996402 |        0.993825 |
| AMD_RUB    | sma_10         | rolling_max_10               |       0.996163 |        0.992766 |
| AMD_RUB    | sma_5          | rolling_max_10               |       0.99566  |        0.992202 |
| AMD_RUB    | rolling_max_10 | rolling_max_20               |       0.994411 |        0.991554 |
| KGS_RUB    | percentile_365 | favourability_percentile_365 |      -1        |       -1        |
| KGS_RUB    | percentile_60  | favourability_percentile_60  |      -1        |       -1        |
| KGS_RUB    | percentile_90  | favourability_percentile_90  |      -1        |       -1        |
| KGS_RUB    | ret_10         | mom_10                       |       1        |        1        |
| KGS_RUB    | ret_20         | mom_20                       |       1        |        1        |
| KGS_RUB    | ret_3          | mom_3                        |       1        |        1        |
| KGS_RUB    | ret_5          | mom_5                        |       1        |        1        |
| KGS_RUB    | percentile_180 | favourability_percentile_180 |      -1        |       -1        |
| KGS_RUB    | percentile_20  | favourability_percentile_20  |      -1        |       -1        |
| KGS_RUB    | sma_5          | sma_10                       |       0.993223 |        0.990319 |
| KGS_RUB    | sma_10         | sma_20                       |       0.987722 |        0.984701 |
| KGS_RUB    | rolling_min_10 | rolling_min_20               |       0.985065 |        0.975739 |
| KGS_RUB    | sma_10         | rolling_min_10               |       0.983457 |        0.973268 |
| KGS_RUB    | sma_10         | rolling_max_10               |       0.982771 |        0.986583 |
| KGS_RUB    | sma_5          | rolling_min_10               |       0.977574 |        0.968423 |
| KZT_RUB    | percentile_60  | favourability_percentile_60  |      -1        |       -1        |
| KZT_RUB    | percentile_90  | favourability_percentile_90  |      -1        |       -1        |
| KZT_RUB    | ret_10         | mom_10                       |       1        |        1        |
| KZT_RUB    | ret_20         | mom_20                       |       1        |        1        |
| KZT_RUB    | ret_3          | mom_3                        |       1        |        1        |
| KZT_RUB    | ret_5          | mom_5                        |       1        |        1        |
| KZT_RUB    | percentile_180 | favourability_percentile_180 |      -1        |       -1        |
| KZT_RUB    | percentile_365 | favourability_percentile_365 |      -1        |       -1        |
| KZT_RUB    | percentile_20  | favourability_percentile_20  |      -1        |       -1        |
| KZT_RUB    | sma_5          | sma_10                       |       0.995144 |        0.99476  |
| KZT_RUB    | sma_10         | sma_20                       |       0.990414 |        0.990257 |
| KZT_RUB    | sma_10         | rolling_min_10               |       0.989606 |        0.987408 |
| KZT_RUB    | sma_10         | rolling_max_10               |       0.987974 |        0.990113 |
| KZT_RUB    | rolling_min_10 | rolling_min_20               |       0.987431 |        0.984929 |
| KZT_RUB    | sma_5          | rolling_min_10               |       0.984719 |        0.983848 |
| TJS_RUB    | percentile_180 | favourability_percentile_180 |      -1        |       -1        |
| TJS_RUB    | percentile_60  | favourability_percentile_60  |      -1        |       -1        |
| TJS_RUB    | ret_10         | mom_10                       |       1        |        1        |
| TJS_RUB    | ret_20         | mom_20                       |       1        |        1        |
| TJS_RUB    | ret_3          | mom_3                        |       1        |        1        |
| TJS_RUB    | ret_5          | mom_5                        |       1        |        1        |
| TJS_RUB    | percentile_20  | favourability_percentile_20  |      -1        |       -1        |
| TJS_RUB    | percentile_365 | favourability_percentile_365 |      -1        |       -1        |
| TJS_RUB    | percentile_90  | favourability_percentile_90  |      -1        |       -1        |
| TJS_RUB    | sma_5          | sma_10                       |       0.994828 |        0.99457  |
| TJS_RUB    | sma_10         | sma_20                       |       0.988494 |        0.986281 |
| TJS_RUB    | sma_10         | rolling_min_10               |       0.98806  |        0.988804 |
| TJS_RUB    | sma_10         | rolling_max_10               |       0.984629 |        0.990313 |
| TJS_RUB    | rolling_min_10 | rolling_min_20               |       0.984229 |        0.983915 |
| TJS_RUB    | sma_5          | rolling_min_10               |       0.982432 |        0.985167 |
| UZS_RUB    | percentile_365 | favourability_percentile_365 |      -1        |       -1        |
| UZS_RUB    | percentile_60  | favourability_percentile_60  |      -1        |       -1        |
| UZS_RUB    | percentile_90  | favourability_percentile_90  |      -1        |       -1        |
| UZS_RUB    | ret_10         | mom_10                       |       1        |        1        |
| UZS_RUB    | ret_20         | mom_20                       |       1        |        1        |
| UZS_RUB    | ret_3          | mom_3                        |       1        |        1        |
| UZS_RUB    | ret_5          | mom_5                        |       1        |        1        |
| UZS_RUB    | percentile_20  | favourability_percentile_20  |      -1        |       -1        |
| UZS_RUB    | percentile_180 | favourability_percentile_180 |      -1        |       -1        |
| UZS_RUB    | sma_5          | sma_10                       |       0.989329 |        0.993369 |
| UZS_RUB    | sma_10         | rolling_min_10               |       0.976029 |        0.985243 |
| UZS_RUB    | sma_10         | rolling_max_10               |       0.975957 |        0.99058  |
| UZS_RUB    | sma_10         | sma_20                       |       0.975409 |        0.985776 |
| UZS_RUB    | mom_10         | broad_rub_return_10          |       0.974639 |        0.932837 |
| UZS_RUB    | ret_10         | broad_rub_return_10          |       0.974639 |        0.932837 |

### Все пары с abs(Pearson) ≥ 0.98

| corridor   | feature_1      | feature_2                    |   pearson_corr |   spearman_corr |
|:-----------|:---------------|:-----------------------------|---------------:|----------------:|
| AMD_RUB    | percentile_180 | favourability_percentile_180 |      -1        |       -1        |
| AMD_RUB    | percentile_20  | favourability_percentile_20  |      -1        |       -1        |
| AMD_RUB    | percentile_365 | favourability_percentile_365 |      -1        |       -1        |
| AMD_RUB    | percentile_60  | favourability_percentile_60  |      -1        |       -1        |
| AMD_RUB    | percentile_90  | favourability_percentile_90  |      -1        |       -1        |
| AMD_RUB    | ret_10         | mom_10                       |       1        |        1        |
| AMD_RUB    | ret_20         | mom_20                       |       1        |        1        |
| AMD_RUB    | ret_3          | mom_3                        |       1        |        1        |
| AMD_RUB    | ret_5          | mom_5                        |       1        |        1        |
| AMD_RUB    | sma_5          | sma_10                       |       0.998289 |        0.996489 |
| AMD_RUB    | sma_10         | sma_20                       |       0.996413 |        0.992964 |
| AMD_RUB    | sma_10         | rolling_min_10               |       0.996402 |        0.993825 |
| AMD_RUB    | sma_10         | rolling_max_10               |       0.996163 |        0.992766 |
| AMD_RUB    | sma_5          | rolling_max_10               |       0.99566  |        0.992202 |
| AMD_RUB    | rolling_max_10 | rolling_max_20               |       0.994411 |        0.991554 |
| AMD_RUB    | sma_5          | rolling_min_10               |       0.994078 |        0.989531 |
| AMD_RUB    | sma_20         | rolling_min_10               |       0.993761 |        0.988314 |
| AMD_RUB    | rolling_min_10 | rolling_min_20               |       0.993535 |        0.988948 |
| AMD_RUB    | sma_20         | rolling_min_20               |       0.992153 |        0.986552 |
| AMD_RUB    | sma_5          | sma_20                       |       0.992013 |        0.985537 |
| AMD_RUB    | sma_20         | rolling_max_10               |       0.99129  |        0.984939 |
| AMD_RUB    | sma_20         | rolling_max_20               |       0.990702 |        0.98422  |
| AMD_RUB    | sma_10         | rolling_max_20               |       0.989426 |        0.982455 |
| AMD_RUB    | rolling_min_60 | rolling_min_90               |       0.98941  |        0.976618 |
| AMD_RUB    | sma_10         | rolling_min_20               |       0.988267 |        0.980872 |
| AMD_RUB    | sma_5          | rolling_max_20               |       0.986997 |        0.978976 |
| AMD_RUB    | rolling_min_10 | rolling_max_10               |       0.986631 |        0.977795 |
| AMD_RUB    | sma_5          | rolling_min_20               |       0.985117 |        0.975422 |
| AMD_RUB    | sma_60         | rolling_min_60               |       0.983016 |        0.952152 |
| AMD_RUB    | sma_20         | sma_60                       |       0.981528 |        0.964679 |
| AMD_RUB    | rolling_min_20 | rolling_min_60               |       0.980615 |        0.955631 |
| KGS_RUB    | percentile_365 | favourability_percentile_365 |      -1        |       -1        |
| KGS_RUB    | percentile_60  | favourability_percentile_60  |      -1        |       -1        |
| KGS_RUB    | percentile_90  | favourability_percentile_90  |      -1        |       -1        |
| KGS_RUB    | ret_10         | mom_10                       |       1        |        1        |
| KGS_RUB    | ret_20         | mom_20                       |       1        |        1        |
| KGS_RUB    | ret_3          | mom_3                        |       1        |        1        |
| KGS_RUB    | ret_5          | mom_5                        |       1        |        1        |
| KGS_RUB    | percentile_180 | favourability_percentile_180 |      -1        |       -1        |
| KGS_RUB    | percentile_20  | favourability_percentile_20  |      -1        |       -1        |
| KGS_RUB    | sma_5          | sma_10                       |       0.993223 |        0.990319 |
| KGS_RUB    | sma_10         | sma_20                       |       0.987722 |        0.984701 |
| KGS_RUB    | rolling_min_10 | rolling_min_20               |       0.985065 |        0.975739 |
| KGS_RUB    | sma_10         | rolling_min_10               |       0.983457 |        0.973268 |
| KGS_RUB    | sma_10         | rolling_max_10               |       0.982771 |        0.986583 |
| KZT_RUB    | percentile_60  | favourability_percentile_60  |      -1        |       -1        |
| KZT_RUB    | percentile_90  | favourability_percentile_90  |      -1        |       -1        |
| KZT_RUB    | ret_10         | mom_10                       |       1        |        1        |
| KZT_RUB    | ret_20         | mom_20                       |       1        |        1        |
| KZT_RUB    | ret_3          | mom_3                        |       1        |        1        |
| KZT_RUB    | ret_5          | mom_5                        |       1        |        1        |
| KZT_RUB    | percentile_180 | favourability_percentile_180 |      -1        |       -1        |
| KZT_RUB    | percentile_365 | favourability_percentile_365 |      -1        |       -1        |
| KZT_RUB    | percentile_20  | favourability_percentile_20  |      -1        |       -1        |
| KZT_RUB    | sma_5          | sma_10                       |       0.995144 |        0.99476  |
| KZT_RUB    | sma_10         | sma_20                       |       0.990414 |        0.990257 |
| KZT_RUB    | sma_10         | rolling_min_10               |       0.989606 |        0.987408 |
| KZT_RUB    | sma_10         | rolling_max_10               |       0.987974 |        0.990113 |
| KZT_RUB    | rolling_min_10 | rolling_min_20               |       0.987431 |        0.984929 |
| KZT_RUB    | sma_5          | rolling_min_10               |       0.984719 |        0.983848 |
| KZT_RUB    | sma_5          | rolling_max_10               |       0.984687 |        0.98624  |
| KZT_RUB    | rolling_max_10 | rolling_max_20               |       0.98163  |        0.984164 |
| KZT_RUB    | sma_20         | rolling_min_10               |       0.980967 |        0.977545 |
| TJS_RUB    | percentile_180 | favourability_percentile_180 |      -1        |       -1        |
| TJS_RUB    | percentile_60  | favourability_percentile_60  |      -1        |       -1        |
| TJS_RUB    | ret_10         | mom_10                       |       1        |        1        |
| TJS_RUB    | ret_20         | mom_20                       |       1        |        1        |
| TJS_RUB    | ret_3          | mom_3                        |       1        |        1        |
| TJS_RUB    | ret_5          | mom_5                        |       1        |        1        |
| TJS_RUB    | percentile_20  | favourability_percentile_20  |      -1        |       -1        |
| TJS_RUB    | percentile_365 | favourability_percentile_365 |      -1        |       -1        |
| TJS_RUB    | percentile_90  | favourability_percentile_90  |      -1        |       -1        |
| TJS_RUB    | sma_5          | sma_10                       |       0.994828 |        0.99457  |
| TJS_RUB    | sma_10         | sma_20                       |       0.988494 |        0.986281 |
| TJS_RUB    | sma_10         | rolling_min_10               |       0.98806  |        0.988804 |
| TJS_RUB    | sma_10         | rolling_max_10               |       0.984629 |        0.990313 |
| TJS_RUB    | rolling_min_10 | rolling_min_20               |       0.984229 |        0.983915 |
| TJS_RUB    | sma_5          | rolling_min_10               |       0.982432 |        0.985167 |
| TJS_RUB    | sma_5          | rolling_max_10               |       0.981405 |        0.986269 |
| TJS_RUB    | rolling_min_60 | rolling_min_90               |       0.980545 |        0.966024 |
| UZS_RUB    | percentile_365 | favourability_percentile_365 |      -1        |       -1        |
| UZS_RUB    | percentile_60  | favourability_percentile_60  |      -1        |       -1        |
| UZS_RUB    | percentile_90  | favourability_percentile_90  |      -1        |       -1        |
| UZS_RUB    | ret_10         | mom_10                       |       1        |        1        |
| UZS_RUB    | ret_20         | mom_20                       |       1        |        1        |
| UZS_RUB    | ret_3          | mom_3                        |       1        |        1        |
| UZS_RUB    | ret_5          | mom_5                        |       1        |        1        |
| UZS_RUB    | percentile_20  | favourability_percentile_20  |      -1        |       -1        |
| UZS_RUB    | percentile_180 | favourability_percentile_180 |      -1        |       -1        |
| UZS_RUB    | sma_5          | sma_10                       |       0.989329 |        0.993369 |

### Highly correlated groups

| corridor   |   group |   size | features                                                                                                                                                                                                                                |
|:-----------|--------:|-------:|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| AMD_RUB    |       1 |      2 | broad_rub_return_1, ret_1                                                                                                                                                                                                               |
| AMD_RUB    |       2 |      5 | broad_rub_return_10, dist_sma_20, mom_10, ret_10, sma_5_vs_20                                                                                                                                                                           |
| AMD_RUB    |       3 |      3 | broad_rub_return_20, mom_20, ret_20                                                                                                                                                                                                     |
| AMD_RUB    |       4 |      5 | broad_rub_return_3, dist_sma_5, mom_3, ret_2, ret_3                                                                                                                                                                                     |
| AMD_RUB    |       5 |      4 | broad_rub_return_5, dist_sma_10, mom_5, ret_5                                                                                                                                                                                           |
| AMD_RUB    |       6 |      2 | dist_max_60, dist_max_90                                                                                                                                                                                                                |
| AMD_RUB    |       7 |      2 | dist_min_60, dist_min_90                                                                                                                                                                                                                |
| AMD_RUB    |       8 |      2 | favourability_percentile_180, percentile_180                                                                                                                                                                                            |
| AMD_RUB    |       9 |      2 | favourability_percentile_20, percentile_20                                                                                                                                                                                              |
| AMD_RUB    |      10 |      2 | favourability_percentile_365, percentile_365                                                                                                                                                                                            |
| AMD_RUB    |      11 |      4 | favourability_percentile_60, favourability_percentile_90, percentile_60, percentile_90                                                                                                                                                  |
| AMD_RUB    |      12 |     16 | recipient_usd_implied, rolling_max_10, rolling_max_180, rolling_max_20, rolling_max_365, rolling_max_60, rolling_max_90, rolling_min_10, rolling_min_180, rolling_min_20, rolling_min_60, rolling_min_90, sma_10, sma_20, sma_5, sma_60 |
| KGS_RUB    |       1 |      2 | corridor_specific_return_1, recipient_usd_ret_1                                                                                                                                                                                         |
| KGS_RUB    |       2 |      2 | corridor_specific_return_10, recipient_usd_ret_10                                                                                                                                                                                       |
| KGS_RUB    |       3 |      2 | corridor_specific_return_3, recipient_usd_ret_3                                                                                                                                                                                         |
| KGS_RUB    |       4 |      2 | corridor_specific_return_5, recipient_usd_ret_5                                                                                                                                                                                         |
| KGS_RUB    |       5 |      2 | dist_max_60, dist_max_90                                                                                                                                                                                                                |
| KGS_RUB    |       6 |      2 | dist_min_60, dist_min_90                                                                                                                                                                                                                |
| KGS_RUB    |       7 |      3 | dist_sma_10, mom_5, ret_5                                                                                                                                                                                                               |
| KGS_RUB    |       8 |      3 | dist_sma_20, mom_10, ret_10                                                                                                                                                                                                             |
| KGS_RUB    |       9 |      4 | dist_sma_5, mom_3, ret_2, ret_3                                                                                                                                                                                                         |
| KGS_RUB    |      10 |      8 | favourability_percentile_180, favourability_percentile_365, favourability_percentile_60, favourability_percentile_90, percentile_180, percentile_365, percentile_60, percentile_90                                                      |
| KGS_RUB    |      11 |      2 | favourability_percentile_20, percentile_20                                                                                                                                                                                              |
| KGS_RUB    |      12 |      2 | mom_20, ret_20                                                                                                                                                                                                                          |
| KGS_RUB    |      13 |      2 | near_min_reversal_002, near_min_reversal_005                                                                                                                                                                                            |
| KGS_RUB    |      14 |     10 | rolling_max_10, rolling_max_20, rolling_min_10, rolling_min_20, rolling_min_60, rolling_min_90, sma_10, sma_20, sma_5, sma_60                                                                                                           |
| KGS_RUB    |      15 |      2 | rolling_max_60, rolling_max_90                                                                                                                                                                                                          |
| KGS_RUB    |      16 |      2 | rolling_range_60, vol_60                                                                                                                                                                                                                |
| KZT_RUB    |       1 |      2 | corridor_specific_return_1, recipient_usd_ret_1                                                                                                                                                                                         |
| KZT_RUB    |       2 |      2 | corridor_specific_return_10, recipient_usd_ret_10                                                                                                                                                                                       |
| KZT_RUB    |       3 |      2 | corridor_specific_return_3, recipient_usd_ret_3                                                                                                                                                                                         |
| KZT_RUB    |       4 |      2 | corridor_specific_return_5, recipient_usd_ret_5                                                                                                                                                                                         |
| KZT_RUB    |       5 |      2 | dist_max_60, dist_max_90                                                                                                                                                                                                                |
| KZT_RUB    |       6 |      2 | dist_min_60, dist_min_90                                                                                                                                                                                                                |
| KZT_RUB    |       7 |      3 | dist_sma_10, mom_5, ret_5                                                                                                                                                                                                               |
| KZT_RUB    |       8 |      4 | dist_sma_20, mom_10, ret_10, sma_5_vs_20                                                                                                                                                                                                |
| KZT_RUB    |       9 |      4 | dist_sma_5, mom_3, ret_2, ret_3                                                                                                                                                                                                         |
| KZT_RUB    |      10 |      2 | favourability_percentile_180, percentile_180                                                                                                                                                                                            |
| KZT_RUB    |      11 |      2 | favourability_percentile_20, percentile_20                                                                                                                                                                                              |
| KZT_RUB    |      12 |      2 | favourability_percentile_365, percentile_365                                                                                                                                                                                            |
| KZT_RUB    |      13 |      4 | favourability_percentile_60, favourability_percentile_90, percentile_60, percentile_90                                                                                                                                                  |
| KZT_RUB    |      14 |      2 | mom_20, ret_20                                                                                                                                                                                                                          |
| KZT_RUB    |      15 |     10 | rolling_max_10, rolling_max_20, rolling_min_10, rolling_min_20, rolling_min_60, rolling_min_90, sma_10, sma_20, sma_5, sma_60                                                                                                           |
| KZT_RUB    |      16 |      2 | rolling_max_60, rolling_max_90                                                                                                                                                                                                          |
| KZT_RUB    |      17 |      2 | rolling_range_60, vol_60                                                                                                                                                                                                                |
| TJS_RUB    |       1 |      5 | broad_rub_return_10, dist_sma_20, mom_10, ret_10, sma_5_vs_20                                                                                                                                                                           |
| TJS_RUB    |       2 |      3 | broad_rub_return_20, mom_20, ret_20                                                                                                                                                                                                     |
| TJS_RUB    |       3 |      5 | broad_rub_return_3, dist_sma_5, mom_3, ret_2, ret_3                                                                                                                                                                                     |
| TJS_RUB    |       4 |      4 | broad_rub_return_5, dist_sma_10, mom_5, ret_5                                                                                                                                                                                           |
| TJS_RUB    |       5 |      2 | corridor_specific_return_1, recipient_usd_ret_1                                                                                                                                                                                         |
| TJS_RUB    |       6 |      2 | corridor_specific_return_3, recipient_usd_ret_3                                                                                                                                                                                         |
| TJS_RUB    |       7 |      2 | dist_min_60, dist_min_90                                                                                                                                                                                                                |
| TJS_RUB    |       8 |      4 | favourability_percentile_180, favourability_percentile_365, percentile_180, percentile_365                                                                                                                                              |
| TJS_RUB    |       9 |      2 | favourability_percentile_20, percentile_20                                                                                                                                                                                              |
| TJS_RUB    |      10 |      4 | favourability_percentile_60, favourability_percentile_90, percentile_60, percentile_90                                                                                                                                                  |
| TJS_RUB    |      11 |     11 | rolling_max_10, rolling_max_20, rolling_min_10, rolling_min_180, rolling_min_20, rolling_min_60, rolling_min_90, sma_10, sma_20, sma_5, sma_60                                                                                          |
| TJS_RUB    |      12 |      2 | rolling_range_20, vol_20                                                                                                                                                                                                                |
| TJS_RUB    |      13 |      2 | rolling_range_60, vol_60                                                                                                                                                                                                                |
| UZS_RUB    |       1 |      2 | broad_rub_return_1, ret_1                                                                                                                                                                                                               |
| UZS_RUB    |       2 |      5 | broad_rub_return_10, dist_sma_20, mom_10, ret_10, sma_5_vs_20                                                                                                                                                                           |
| UZS_RUB    |       3 |      3 | broad_rub_return_20, mom_20, ret_20                                                                                                                                                                                                     |
| UZS_RUB    |       4 |      5 | broad_rub_return_3, dist_sma_5, mom_3, ret_2, ret_3                                                                                                                                                                                     |
| UZS_RUB    |       5 |      4 | broad_rub_return_5, dist_sma_10, mom_5, ret_5                                                                                                                                                                                           |
| UZS_RUB    |       6 |      2 | dist_max_60, dist_max_90                                                                                                                                                                                                                |
| UZS_RUB    |       7 |      2 | dist_min_60, dist_min_90                                                                                                                                                                                                                |
| UZS_RUB    |       8 |      2 | favourability_percentile_180, percentile_180                                                                                                                                                                                            |
| UZS_RUB    |       9 |      2 | favourability_percentile_20, percentile_20                                                                                                                                                                                              |
| UZS_RUB    |      10 |      2 | favourability_percentile_365, percentile_365                                                                                                                                                                                            |
| UZS_RUB    |      11 |      4 | favourability_percentile_60, favourability_percentile_90, percentile_60, percentile_90                                                                                                                                                  |
| UZS_RUB    |      12 |      2 | near_min_reversal_002, near_min_reversal_005                                                                                                                                                                                            |
| UZS_RUB    |      13 |      9 | rolling_max_10, rolling_max_20, rolling_min_10, rolling_min_20, rolling_min_60, rolling_min_90, sma_10, sma_20, sma_5                                                                                                                   |
| UZS_RUB    |      14 |      2 | rolling_range_60, vol_60                                                                                                                                                                                                                |

## VIF diagnostic

VIF > 10 — severe; 5 < VIF ≤ 10 — moderate. Бинарные flags исключены; VIF не используется для автоматического удаления.

| corridor   |   acceptable |   moderate |   severe |
|:-----------|-------------:|-----------:|---------:|
| AMD_RUB    |            9 |          6 |       24 |
| KGS_RUB    |            8 |          6 |       25 |
| KZT_RUB    |            8 |          6 |       25 |
| TJS_RUB    |            8 |          6 |       25 |
| UZS_RUB    |           10 |          5 |       24 |

| corridor   | feature           |      vif | status   |   complete_rows |
|:-----------|:------------------|---------:|:---------|----------------:|
| AMD_RUB    | ret_1             | 4144.02  | severe   |            1709 |
| AMD_RUB    | dist_sma_20       | 2357.62  | severe   |            1709 |
| AMD_RUB    | ret_2             | 2346.93  | severe   |            1709 |
| AMD_RUB    | reversal_strength | 1853.82  | severe   |            1709 |
| AMD_RUB    | dist_sma_60       | 1207.94  | severe   |            1709 |
| AMD_RUB    | sma_5_vs_20       | 1104.93  | severe   |            1709 |
| AMD_RUB    | rolling_range_20  |  855.391 | severe   |            1709 |
| AMD_RUB    | dist_max_20       |  535.25  | severe   |            1709 |
| AMD_RUB    | dist_min_20       |  520.116 | severe   |            1709 |
| AMD_RUB    | sma_20_vs_60      |  494.178 | severe   |            1709 |
| AMD_RUB    | dist_sma_5        |  350.274 | severe   |            1709 |
| AMD_RUB    | rolling_range_60  |  323.628 | severe   |            1709 |
| KGS_RUB    | ret_1             | 5194.25  | severe   |            1709 |
| KGS_RUB    | ret_2             | 2866.39  | severe   |            1709 |
| KGS_RUB    | dist_sma_20       | 2707.84  | severe   |            1709 |
| KGS_RUB    | reversal_strength | 2297.24  | severe   |            1709 |
| KGS_RUB    | dist_sma_60       | 1456.81  | severe   |            1709 |
| KGS_RUB    | rolling_range_20  | 1158.68  | severe   |            1709 |
| KGS_RUB    | sma_5_vs_20       | 1079.3   | severe   |            1709 |
| KGS_RUB    | dist_max_20       |  851.748 | severe   |            1709 |
| KGS_RUB    | sma_20_vs_60      |  588.872 | severe   |            1709 |
| KGS_RUB    | dist_sma_5        |  489.506 | severe   |            1709 |
| KGS_RUB    | dist_min_20       |  487.446 | severe   |            1709 |
| KGS_RUB    | rolling_range_60  |  376.4   | severe   |            1709 |
| KZT_RUB    | ret_1             | 5629.72  | severe   |            1709 |
| KZT_RUB    | dist_sma_20       | 3735.21  | severe   |            1709 |
| KZT_RUB    | ret_2             | 3220.68  | severe   |            1709 |
| KZT_RUB    | reversal_strength | 2463.66  | severe   |            1709 |
| KZT_RUB    | rolling_range_20  | 1693.18  | severe   |            1709 |
| KZT_RUB    | sma_5_vs_20       | 1634.68  | severe   |            1709 |
| KZT_RUB    | dist_sma_60       | 1551.9   | severe   |            1709 |
| KZT_RUB    | dist_max_20       | 1304.85  | severe   |            1709 |
| KZT_RUB    | dist_min_20       |  765.663 | severe   |            1709 |
| KZT_RUB    | sma_20_vs_60      |  627.41  | severe   |            1709 |
| KZT_RUB    | dist_sma_5        |  582.452 | severe   |            1709 |
| KZT_RUB    | rolling_range_60  |  457.7   | severe   |            1709 |
| TJS_RUB    | ret_1             | 3202.89  | severe   |            1709 |
| TJS_RUB    | ret_2             | 1628.82  | severe   |            1709 |
| TJS_RUB    | reversal_strength | 1593.17  | severe   |            1709 |
| TJS_RUB    | dist_sma_20       | 1202.5   | severe   |            1709 |
| TJS_RUB    | dist_sma_60       |  826.879 | severe   |            1709 |
| TJS_RUB    | sma_5_vs_20       |  600.011 | severe   |            1709 |
| TJS_RUB    | rolling_range_20  |  533.248 | severe   |            1709 |
| TJS_RUB    | dist_max_20       |  378.756 | severe   |            1709 |
| TJS_RUB    | sma_20_vs_60      |  363.704 | severe   |            1709 |
| TJS_RUB    | dist_min_20       |  250.983 | severe   |            1709 |
| TJS_RUB    | dist_sma_5        |  222.584 | severe   |            1709 |
| TJS_RUB    | rolling_range_60  |  144.254 | severe   |            1709 |
| UZS_RUB    | ret_1             | 4348.06  | severe   |            1709 |
| UZS_RUB    | ret_2             | 2525.87  | severe   |            1709 |
| UZS_RUB    | dist_sma_20       | 2295.93  | severe   |            1709 |
| UZS_RUB    | reversal_strength | 1848.98  | severe   |            1709 |
| UZS_RUB    | dist_sma_60       | 1287.64  | severe   |            1709 |
| UZS_RUB    | sma_5_vs_20       |  917.162 | severe   |            1709 |
| UZS_RUB    | rolling_range_20  |  716.849 | severe   |            1709 |
| UZS_RUB    | sma_20_vs_60      |  533.073 | severe   |            1709 |
| UZS_RUB    | dist_max_20       |  500.919 | severe   |            1709 |
| UZS_RUB    | dist_min_20       |  384.162 | severe   |            1709 |
| UZS_RUB    | dist_sma_5        |  291.511 | severe   |            1709 |
| UZS_RUB    | dist_max_60       |  158.25  | severe   |            1709 |

## Train-only PCA diagnostic

| corridor   |   source_rows |   train_rows_before_complete_case |   train_complete_rows | train_last_date     |   input_features |   components_80pct |   components_90pct |   components_95pct |
|:-----------|--------------:|----------------------------------:|----------------------:|:--------------------|-----------------:|-------------------:|-------------------:|-------------------:|
| AMD_RUB    |          1889 |                              1322 |                   957 | 2024-05-23 00:00:00 |               79 |                  7 |                 12 |                 18 |
| KGS_RUB    |          1889 |                              1322 |                   957 | 2024-05-23 00:00:00 |               79 |                  7 |                 12 |                 18 |
| KZT_RUB    |          1889 |                              1322 |                   957 | 2024-05-23 00:00:00 |               79 |                  7 |                 11 |                 17 |
| TJS_RUB    |          1889 |                              1322 |                   957 | 2024-05-23 00:00:00 |               79 |                  7 |                 12 |                 18 |
| UZS_RUB    |          1889 |                              1322 |                   957 | 2024-05-23 00:00:00 |               79 |                  7 |                 12 |                 19 |

StandardScaler и PCA fitted отдельно на первых 70% каждого corridor после complete-case отбора. Validation/test не участвовали в fit.

### Top loadings первых трёх components

| corridor   |   component | feature                      |   loading |   absolute_loading |
|:-----------|------------:|:-----------------------------|----------:|-------------------:|
| AMD_RUB    |           1 | dist_sma_60                  |  0.18616  |           0.18616  |
| AMD_RUB    |           1 | dist_sma_20                  |  0.174791 |           0.174791 |
| AMD_RUB    |           1 | percentile_60                |  0.168497 |           0.168497 |
| AMD_RUB    |           1 | favourability_percentile_60  | -0.168497 |           0.168497 |
| AMD_RUB    |           1 | percentile_90                |  0.162776 |           0.162776 |
| AMD_RUB    |           1 | favourability_percentile_90  | -0.162776 |           0.162776 |
| AMD_RUB    |           1 | percentile_365               |  0.162231 |           0.162231 |
| AMD_RUB    |           1 | favourability_percentile_365 | -0.162231 |           0.162231 |
| AMD_RUB    |           2 | sma_60                       |  0.233373 |           0.233373 |
| AMD_RUB    |           2 | sma_20                       |  0.230254 |           0.230254 |
| AMD_RUB    |           2 | rolling_min_20               |  0.223577 |           0.223577 |
| AMD_RUB    |           2 | rolling_max_20               |  0.222942 |           0.222942 |
| AMD_RUB    |           2 | rolling_max_60               |  0.222784 |           0.222784 |
| AMD_RUB    |           2 | sma_10                       |  0.222748 |           0.222748 |
| AMD_RUB    |           2 | rolling_min_10               |  0.222453 |           0.222453 |
| AMD_RUB    |           2 | rolling_min_60               |  0.222413 |           0.222413 |
| AMD_RUB    |           3 | rolling_range_60             |  0.281773 |           0.281773 |
| AMD_RUB    |           3 | rolling_range_20             |  0.279522 |           0.279522 |
| AMD_RUB    |           3 | vol_60                       |  0.276742 |           0.276742 |
| AMD_RUB    |           3 | vol_20                       |  0.273471 |           0.273471 |
| AMD_RUB    |           3 | rolling_range_10             |  0.268454 |           0.268454 |
| AMD_RUB    |           3 | vol_10                       |  0.266655 |           0.266655 |
| AMD_RUB    |           3 | vol_5                        |  0.233856 |           0.233856 |
| AMD_RUB    |           3 | dist_max_90                  | -0.206412 |           0.206412 |
| KGS_RUB    |           1 | dist_sma_60                  |  0.194213 |           0.194213 |
| KGS_RUB    |           1 | dist_sma_20                  |  0.182121 |           0.182121 |
| KGS_RUB    |           1 | percentile_60                |  0.1766   |           0.1766   |
| KGS_RUB    |           1 | favourability_percentile_60  | -0.1766   |           0.1766   |
| KGS_RUB    |           1 | percentile_90                |  0.173602 |           0.173602 |
| KGS_RUB    |           1 | favourability_percentile_90  | -0.173602 |           0.173602 |
| KGS_RUB    |           1 | ret_20                       |  0.170558 |           0.170558 |
| KGS_RUB    |           1 | percentile_180               |  0.165998 |           0.165998 |
| KGS_RUB    |           2 | sma_20                       |  0.239178 |           0.239178 |
| KGS_RUB    |           2 | rolling_min_20               |  0.236867 |           0.236867 |
| KGS_RUB    |           2 | rolling_min_60               |  0.236437 |           0.236437 |
| KGS_RUB    |           2 | rolling_min_10               |  0.233872 |           0.233872 |
| KGS_RUB    |           2 | sma_60                       |  0.23183  |           0.23183  |
| KGS_RUB    |           2 | sma_10                       |  0.229321 |           0.229321 |
| KGS_RUB    |           2 | rolling_min_90               |  0.227867 |           0.227867 |
| KGS_RUB    |           2 | sma_5                        |  0.217049 |           0.217049 |
| KGS_RUB    |           3 | rolling_range_20             |  0.271305 |           0.271305 |
| KGS_RUB    |           3 | rolling_range_60             |  0.262945 |           0.262945 |
| KGS_RUB    |           3 | vol_20                       |  0.260852 |           0.260852 |
| KGS_RUB    |           3 | rolling_range_10             |  0.260387 |           0.260387 |
| KGS_RUB    |           3 | vol_10                       |  0.249922 |           0.249922 |
| KGS_RUB    |           3 | vol_60                       |  0.23634  |           0.23634  |
| KGS_RUB    |           3 | vol_5                        |  0.221985 |           0.221985 |
| KGS_RUB    |           3 | rolling_max_90               |  0.21978  |           0.21978  |
| KZT_RUB    |           1 | dist_sma_60                  |  0.19129  |           0.19129  |
| KZT_RUB    |           1 | dist_sma_20                  |  0.185725 |           0.185725 |
| KZT_RUB    |           1 | percentile_60                |  0.172162 |           0.172162 |
| KZT_RUB    |           1 | favourability_percentile_60  | -0.172162 |           0.172162 |
| KZT_RUB    |           1 | ret_20                       |  0.168438 |           0.168438 |
| KZT_RUB    |           1 | percentile_90                |  0.168119 |           0.168119 |
| KZT_RUB    |           1 | favourability_percentile_90  | -0.168119 |           0.168119 |
| KZT_RUB    |           1 | dist_sma_10                  |  0.166108 |           0.166108 |
| KZT_RUB    |           2 | rolling_min_60               |  0.224672 |           0.224672 |
| KZT_RUB    |           2 | rolling_min_90               |  0.224651 |           0.224651 |
| KZT_RUB    |           2 | rolling_min_20               |  0.215816 |           0.215816 |
| KZT_RUB    |           2 | rolling_min_10               |  0.208708 |           0.208708 |
| KZT_RUB    |           2 | sma_20                       |  0.205027 |           0.205027 |
| KZT_RUB    |           2 | sma_60                       |  0.204277 |           0.204277 |
| KZT_RUB    |           2 | dist_max_365                 |  0.201828 |           0.201828 |
| KZT_RUB    |           2 | sma_10                       |  0.197527 |           0.197527 |
| KZT_RUB    |           3 | rolling_max_90               |  0.225192 |           0.225192 |
| KZT_RUB    |           3 | rolling_max_60               |  0.224131 |           0.224131 |
| KZT_RUB    |           3 | rolling_max_365              |  0.221005 |           0.221005 |
| KZT_RUB    |           3 | rolling_range_20             |  0.208226 |           0.208226 |
| KZT_RUB    |           3 | vol_20                       |  0.205222 |           0.205222 |
| KZT_RUB    |           3 | dist_min_365                 |  0.192709 |           0.192709 |
| KZT_RUB    |           3 | rolling_range_60             |  0.190378 |           0.190378 |
| KZT_RUB    |           3 | rolling_range_10             |  0.187827 |           0.187827 |
| TJS_RUB    |           1 | dist_sma_60                  |  0.188073 |           0.188073 |
| TJS_RUB    |           1 | dist_sma_20                  |  0.175192 |           0.175192 |
| TJS_RUB    |           1 | percentile_60                |  0.174739 |           0.174739 |
| TJS_RUB    |           1 | favourability_percentile_60  | -0.174739 |           0.174739 |
| TJS_RUB    |           1 | favourability_percentile_90  | -0.171625 |           0.171625 |
| TJS_RUB    |           1 | percentile_90                |  0.171625 |           0.171625 |
| TJS_RUB    |           1 | percentile_180               |  0.169091 |           0.169091 |
| TJS_RUB    |           1 | favourability_percentile_180 | -0.169091 |           0.169091 |
| TJS_RUB    |           2 | sma_20                       |  0.228466 |           0.228466 |
| TJS_RUB    |           2 | rolling_min_60               |  0.226607 |           0.226607 |
| TJS_RUB    |           2 | rolling_min_20               |  0.225822 |           0.225822 |
| TJS_RUB    |           2 | rolling_min_10               |  0.222531 |           0.222531 |
| TJS_RUB    |           2 | rolling_min_90               |  0.221018 |           0.221018 |
| TJS_RUB    |           2 | sma_10                       |  0.217289 |           0.217289 |
| TJS_RUB    |           2 | sma_60                       |  0.21516  |           0.21516  |
| TJS_RUB    |           2 | sma_5                        |  0.203208 |           0.203208 |
| TJS_RUB    |           3 | rolling_range_20             |  0.268371 |           0.268371 |
| TJS_RUB    |           3 | vol_20                       |  0.258699 |           0.258699 |
| TJS_RUB    |           3 | vol_10                       |  0.254958 |           0.254958 |
| TJS_RUB    |           3 | rolling_range_10             |  0.251145 |           0.251145 |
| TJS_RUB    |           3 | vol_5                        |  0.232532 |           0.232532 |
| TJS_RUB    |           3 | rolling_range_60             |  0.230396 |           0.230396 |
| TJS_RUB    |           3 | vol_60                       |  0.224019 |           0.224019 |
| TJS_RUB    |           3 | dist_max_10                  | -0.214003 |           0.214003 |
| UZS_RUB    |           1 | dist_sma_60                  |  0.194278 |           0.194278 |
| UZS_RUB    |           1 | dist_sma_20                  |  0.187752 |           0.187752 |
| UZS_RUB    |           1 | broad_rub_return_10          |  0.176535 |           0.176535 |
| UZS_RUB    |           1 | broad_rub_return_20          |  0.173383 |           0.173383 |
| UZS_RUB    |           1 | percentile_60                |  0.17283  |           0.17283  |
| UZS_RUB    |           1 | favourability_percentile_60  | -0.17283  |           0.17283  |
| UZS_RUB    |           1 | ret_20                       |  0.172626 |           0.172626 |
| UZS_RUB    |           1 | ret_10                       |  0.170038 |           0.170038 |
| UZS_RUB    |           2 | rolling_min_20               |  0.24418  |           0.24418  |
| UZS_RUB    |           2 | rolling_min_10               |  0.239878 |           0.239878 |
| UZS_RUB    |           2 | rolling_min_60               |  0.239473 |           0.239473 |
| UZS_RUB    |           2 | rolling_min_90               |  0.232198 |           0.232198 |
| UZS_RUB    |           2 | sma_20                       |  0.228045 |           0.228045 |
| UZS_RUB    |           2 | sma_10                       |  0.220255 |           0.220255 |
| UZS_RUB    |           2 | dist_max_365                 |  0.209934 |           0.209934 |
| UZS_RUB    |           2 | sma_5                        |  0.2068   |           0.2068   |
| UZS_RUB    |           3 | rolling_range_20             |  0.256965 |           0.256965 |
| UZS_RUB    |           3 | vol_20                       |  0.251584 |           0.251584 |
| UZS_RUB    |           3 | rolling_range_10             |  0.234332 |           0.234332 |
| UZS_RUB    |           3 | vol_10                       |  0.229702 |           0.229702 |
| UZS_RUB    |           3 | dist_max_10                  | -0.221414 |           0.221414 |
| UZS_RUB    |           3 | rolling_range_60             |  0.215741 |           0.215741 |
| UZS_RUB    |           3 | rolling_max_60               |  0.214877 |           0.214877 |
| UZS_RUB    |           3 | vol_60                       |  0.206368 |           0.206368 |

## FEATURE SCREENING SUMMARY

1. Исходное число numeric columns: **99**; causal numeric features: **97**.
2. Exact duplicate pairs: **10**; рекомендуемые duplicate drops: `['mom_10', 'mom_20', 'mom_3', 'mom_5']`.
3. High-correlation pairs: **360** при `abs(Pearson) ≥ 0.90`, из них **90** при `≥ 0.98`.
4. VIF issues: **123** severe rows и **29** moderate rows в corridor-level diagnostic.
5. PCA components for 90% variance: `{'AMD_RUB': 12, 'KGS_RUB': 12, 'KZT_RUB': 11, 'TJS_RUB': 12, 'UZS_RUB': 12}`.
6. Structural reduced set после constants/exact duplicates/critical missingness: **89** features.
7. Предварительный compact candidate set (worst-corridor VIF ≤ 10 на representative subset + binary events): `['broad_rub_z_1', 'broad_rub_z_3', 'broad_rub_z_5', 'days_since_min_20', 'days_since_min_60', 'dist_max_180', 'dist_min_180', 'down_streak', 'near_min_prev_002', 'near_min_prev_005', 'near_min_prev_010', 'near_min_reversal_002', 'near_min_reversal_005', 'near_min_reversal_010', 'percentile_180', 'percentile_20', 'recipient_usd_ret_10', 'return_sign_reversal_up', 'reversal_2d_002', 'reversal_2d_005', 'reversal_2d_010', 'up_streak', 'vol_5']`.

Этот candidate set является диагностическим shortlist без target-based selection. Перед ARIMAX/ML требуется temporal validation, lag alignment и train-only selection.

Для текущих трёх моделей — Naive / ARIMA(rate) / ARIMA(log_return) — feature selection и PCA непосредственно не используются, потому что модели используют собственную историю ряда. Screening предназначен для следующих ARIMAX/ML моделей tournament.

**STAGE 1 — DATA & FEATURE SCREENING: PASS**
