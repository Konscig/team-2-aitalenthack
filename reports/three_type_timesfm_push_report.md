# Three-type TimesFM push policy report

## Frozen policy

- GOOD_DAY and POSITIVE_MARKET_FACT are reused unchanged from notebook 22.
- WINDOW_CLOSING uses TimesFM rule: mean_change_h5_bps >= 25 and n_worse_days_h5 >= 3, plus methodology historical eligibility.
- Priority: good_day > window_closing > positive_market_fact; cooldown=4 calendar days; weekly cap=2; deferral disabled as frozen in Stage 22.

## Locked 2026 micro metrics

| signal_type          |   signals |   precision |    recall |     F0_5 |   hit_rate |   random_hit_rate |   uplift |
|:---------------------|----------:|------------:|----------:|---------:|-----------:|------------------:|---------:|
| GOOD_DAY             |       114 |    0.605263 | 0.339901  | 0.52352  |   0.605263 |          0.244825 |  2.47223 |
| WINDOW_CLOSING       |         2 |    0        | 0         | 0        |   0        |          0.075    |  0       |
| POSITIVE_MARKET_FACT |        18 |    1        | 0.0640569 | 0.254958 |   1        |          0.335611 |  2.97964 |

## Combined policy

|   total_pushes |   correct_pushes |   false_pushes |   combined_precision |   mean_pushes_per_month |   median_pushes_per_month |   share_months_with_3plus |   months_below_3 |   zero_push_months |
|---------------:|-----------------:|---------------:|---------------------:|------------------------:|--------------------------:|--------------------------:|-----------------:|-------------------:|
|            134 |               87 |             47 |             0.649254 |                    3.35 |                         3 |                     0.825 |                7 |                  0 |

## Old vs new WINDOW_CLOSING

| policy                     |   signals |   precision |   recall |   F0_5 |   hit_rate |   uplift |
|:---------------------------|----------:|------------:|---------:|-------:|-----------:|---------:|
| OLD_CHRONOS_WINDOW_CLOSING |         0 |           0 |        0 |      0 |          0 |      nan |
| NEW_TIMESFM_WINDOW_CLOSING |         2 |           0 |        0 |      0 |          0 |        0 |

## Old vs new combined policy

| policy      |   total_pushes |   combined_precision |   mean_pushes_per_month |   share_months_with_3plus |
|:------------|---------------:|---------------------:|------------------------:|--------------------------:|
| OLD_CHRONOS |            138 |             0.673913 |                    3.45 |                     0.825 |
| NEW_TIMESFM |            134 |             0.649254 |                    3.35 |                     0.825 |

## Leakage audit

| check                             | passed   |
|:----------------------------------|:---------|
| TimesFM at T uses only <=T        | True     |
| T+10 calendar aligned             | True     |
| actual future only evaluation     | True     |
| golden labels not rule inputs     | True     |
| window rule selected only on 2025 | True     |
| 2026 never tuned                  | True     |
| positive_market_fact factual only | True     |
| deferral never uses actual T+1    | True     |

LEAKAGE CHECK: **PASS**

## Conclusions

- Window closing usable: NO; 2 pushes, precision=0.000.
- Golden closing found: 0 of 52.
- F0.5 improved vs Chronos: NO (0.000 -> 0.000).
- Window uplift > 1: NO (uplift=0.000).
- Combined precision not degraded: NO (0.674 -> 0.649).
- Target >=3 pushes/month: mean MET (3.35); every corridor-month NOT MET (82.5%).