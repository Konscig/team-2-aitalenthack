# Good-day threshold tournament

Порог выбран на этом же out-of-time наборе, поэтому результат является исследовательским и требует проверки на новом, не использованном при выборе периоде.

## Основные правила

| rule   | thresholds                                                 |   actual_regret_tolerance |   total_signals |   signal_frequency |   macro_hit_rate |   macro_uplift |   median_uplift |   corridors_uplift_gt_1 |   corridors_uplift_ge_1_3 |   mean_actual_regret_signal | status       | is_primary   |
|:-------|:-----------------------------------------------------------|--------------------------:|----------------:|-------------------:|-----------------:|---------------:|----------------:|------------------------:|--------------------------:|----------------------------:|:-------------|:-------------|
| RULE_A | fav>=0.800; past_advantage>=NONE; predicted_regret<=0.010  |                     0.005 |             432 |          0.314182  |         0.457848 |       0.96745  |        0.992862 |                       2 |                         0 |                  0.00947808 | TOO_FREQUENT | True         |
| RULE_B | fav>=0.850; past_advantage>=0.000; predicted_regret<=0.005 |                     0.005 |             148 |          0.107636  |         0.418418 |       0.895504 |        0.766479 |                       1 |                         1 |                  0.0109012  | OK           | True         |
| RULE_C | fav>=0.900; past_advantage>=0.002; predicted_regret<=0.005 |                     0.005 |             109 |          0.0792727 |         0.446803 |       0.95474  |        0.906501 |                       1 |                         1 |                  0.0103716  | OK           | True         |

## Sensitivity к realized regret tolerance

| rule   | thresholds                                                 |   actual_regret_tolerance |   total_signals |   overall_signal_frequency |   macro_hit_rate |   macro_uplift |   median_uplift |   corridors_uplift_gt_1 |   corridors_uplift_ge_1_3 |   mean_actual_regret_signal | status       | is_primary   |
|:-------|:-----------------------------------------------------------|--------------------------:|----------------:|---------------------------:|-----------------:|---------------:|----------------:|------------------------:|--------------------------:|----------------------------:|:-------------|:-------------|
| RULE_A | fav>=0.800; past_advantage>=NONE; predicted_regret<=0.010  |                     0.002 |             432 |                  0.314182  |         0.335004 |       0.889331 |        0.963684 |                       1 |                         0 |                  0.00947808 | TOO_FREQUENT | True         |
| RULE_A | fav>=0.800; past_advantage>=NONE; predicted_regret<=0.010  |                     0.005 |             432 |                  0.314182  |         0.457848 |       0.96745  |        0.992862 |                       2 |                         0 |                  0.00947808 | TOO_FREQUENT | True         |
| RULE_A | fav>=0.800; past_advantage>=NONE; predicted_regret<=0.010  |                     0.01  |             432 |                  0.314182  |         0.616863 |       1.03393  |        1.07951  |                       3 |                         0 |                  0.00947808 | TOO_FREQUENT | True         |
| RULE_B | fav>=0.850; past_advantage>=0.000; predicted_regret<=0.005 |                     0.002 |             148 |                  0.107636  |         0.322152 |       0.863377 |        0.774833 |                       2 |                         0 |                  0.0109012  | OK           | True         |
| RULE_B | fav>=0.850; past_advantage>=0.000; predicted_regret<=0.005 |                     0.005 |             148 |                  0.107636  |         0.418418 |       0.895504 |        0.766479 |                       1 |                         1 |                  0.0109012  | OK           | True         |
| RULE_B | fav>=0.850; past_advantage>=0.000; predicted_regret<=0.005 |                     0.01  |             148 |                  0.107636  |         0.540685 |       0.904688 |        0.841121 |                       2 |                         0 |                  0.0109012  | OK           | True         |
| RULE_C | fav>=0.900; past_advantage>=0.002; predicted_regret<=0.005 |                     0.002 |             109 |                  0.0792727 |         0.33301  |       0.887032 |        0.875219 |                       2 |                         0 |                  0.0103716  | OK           | True         |
| RULE_C | fav>=0.900; past_advantage>=0.002; predicted_regret<=0.005 |                     0.005 |             109 |                  0.0792727 |         0.446803 |       0.95474  |        0.906501 |                       1 |                         1 |                  0.0103716  | OK           | True         |
| RULE_C | fav>=0.900; past_advantage>=0.002; predicted_regret<=0.005 |                     0.01  |             109 |                  0.0792727 |         0.557302 |       0.933872 |        0.911162 |                       2 |                         0 |                  0.0103716  | OK           | True         |

## Leakage audit

| check                                             | passed   |
|:--------------------------------------------------|:---------|
| signals use only the three approved causal fields | True     |
| actual_regret_5 is evaluation-only                | True     |
| no actual future rate enters signal generation    | True     |
| identical rows compare all rules                  | True     |
| random baseline uses exactly n_signals            | True     |
| one row per corridor+date                         | True     |

GOOD DAY THRESHOLD LEAKAGE CHECK: **PASS**

## Winner

**WINNER: NO_STABLE_RULE**
