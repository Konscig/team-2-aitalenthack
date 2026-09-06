# Experiments Summary

## 1. Executive summary

- Исходная задача: находить удачный момент трансграничного перевода RUB→AMD/KGS/KZT/TJS/UZS; чем ниже RUB за единицу валюты получателя, тем лучше отправителю.
- Основа исследования — 9 445 официальных quote-time наблюдений ЦБ РФ за 2019-01-10—2026-09-03, по 1 889 строк на коридор.
- Подготовлены 64 базовых и 37 расширенных causal-признаков; итоговый modeling dataset содержит 104 столбца.
- Во всех modeling-экспериментах использован chronological train/validation/test split; test locked, selection выполняется на validation, максимальный горизонт учитывается purge.
- Raw rates диагностически нестационарны; первые разности и log returns дают согласованное основание использовать `d=1` для rate и `d=0` для returns.
- Random Walk — сильный baseline: ARIMA практически повторяет его, а frozen-exog ARIMAX не добавляет точности.
- Direct Ridge/Gradient Boosting улучшили Naive по H5 MAE в 4/5 коридоров, но выигрыш мал; exact-path forecasting достигло плато.
- CatBoost сложнее, но улучшил предыдущую direct-модель по H5 только в 1/5 коридоров и по Path MAE — в 0/5.
- Exact FX forecast оказался недостаточно сильным самостоятельным основанием для продукта; исследование перешло к сигналу «хороший день» через historical favourability и predicted regret.
- Универсальные thresholds нестабильны между коридорами; единого победителя нет.
- Per-corridor thresholds, выбранные на validation, дали locked-test uplift ≥1.3 во всех 5 коридорах (средний uplift 3.93), но от 10 до 81 сигнала на коридор.
- Окна favourability 30/20 и адаптивные правила проверялись для повышения локальности и частоты; улучшение качества оказалось неоднородным.
- Adaptive ranking повысил покрытие до 175–188 сигналов суммарно и почти устранил нулевые месяцы, но снизил средний uplift до 1.27–1.43 без абсолютного attractiveness floor.
- Conservative adaptive selection восстановил `F≥0.70` и uplift 2.61–3.14, но вернул 34 нулевых corridor-months и gaps до 55 котировок.
- Текущий нерешенный вопрос: как обеспечить достаточную ежемесячную частоту, не теряя смысл «действительно выгодного дня» и out-of-time качество.

## 2. Experiment timeline

| Stage | Experiment | What was tested | Main result | Decision |
|---|---|---|---|---|
| 01 | Features + EDA | Causal market, reversal and cross-FX features | 9 445×104; 70 highly correlated pairs; causality PASS | KEEP, control redundancy |
| 02/S2 | Time-series diagnostics | ADF/KPSS, rolling stats, ACF/PACF | Rate: `d=1`; returns: `d=0` for 5/5 | KEEP specifications |
| 02/S3 | Naive baseline | Multi-step Random Walk, H=1/3/5/10 | Strong reference for all corridors | KEEP baseline |
| 02/S4 | ARIMA rate | Univariate multi-step rate forecast | H5 beats Naive 1/5; H10 0/5 | REJECT as main model |
| 03A | Direct multi-horizon | Ridge and Gradient Boosting, H1…H5 | Best direct beats Naive H5 in 4/5 | KEEP as reference |
| 03B | ARIMAX | Frozen exogenous features | Beats ARIMA/Naive 0/5 on H5/path | REJECT setup |
| 04 | CatBoost multi-horizon | Corridor×horizon nonlinear models | Beats prior direct H5 1/5; path 0/5 | REJECT added complexity |
| 05 | Temporal enrichment | Lag/regime enrichment of direct models | Material H5 gain only TJS; plateau | PARTIAL; stop exact-path expansion |
| 06 | Good-day representation | Favourability, past advantage, predicted/actual regret | Causal signal/evaluation frame built | KEEP |
| 07 | Universal rules | Common F/A/R thresholds | Macro uplift <1 for primary rules | REJECT universal rule |
| 08 | Per-corridor rules | Validation selection, locked test | Uplift 2.20–6.62; frequency 3.6–29.5% | KEEP, frequency risk |
| 09A | Frequency calibration | Relaxed rules and cooldown | Target reached only for KZT; gaps 39–143 calendar days | INCONCLUSIVE |
| 09B–11 | Favourability 30/20 + visuals | Shorter context and fixed rules | 30 often reduced signals; 20 raised local frequency but gaps remained | PARTIAL |
| 12 | Adaptive policies | Strong/fallback/cooldown state logic | Good uplift, but 26–34 zero corridor-months | PARTIAL |
| 13 | Adaptive ranking | FULL vs SIMPLE rolling ranks | More regular: 2–3 zero corridor-months; uplift 1.27–1.43 | PARTIAL; semantic floor needed |
| 14 | Conservative adaptive | Absolute floor + adaptive score | No bad-F signals; uplift 2.61–3.14, but 34 zero months | PARTIAL |
| 02B | Intermediate FX dynamics | Extra push rules for unusual moves | MVP: 686 events, median gap 14 days; descriptive only | KEEP as separate product hypothesis |

## 3. Details by experiment

### Experiment 1 — Feature engineering and EDA

**Goal.** Представить quote-time рынок causal-признаками и проверить качество набора.  
**Setup.** Returns, momentum, volatility, rolling extrema/percentiles, reversal, broad-RUB and corridor-specific factors; только история до T.  
**Result.** 64 base + 37 advanced features; 9 445 строк, 104 итоговых столбца; 70 numeric-пар с `|corr|>0.995`, четыре exact duplicate return/momentum пары.  
**Interpretation.** Сигналов много, но выраженная мультиколлинеарность требует validation-only selection; 224 suspicious rows оставлены для source verification.  
**Decision.** **KEEP** — dataset и causality checks готовы; redundant features учитывать в моделях.

### Experiment 2 — Time-series diagnostics

**Goal.** Выбрать корректное differencing для ARIMA без выводов только по графикам.  
**Setup.** Rate, first difference и `log_ret_1`; ADF+KPSS, rolling mean/std, ACF/PACF по каждому коридору.  
**Result.** Для raw rate ADF p-value 0.068–0.868 и KPSS 0.010–0.023; для diff/log-return ADF крайне мал, KPSS 0.1 во всех 5.  
**Interpretation.** Тесты согласованно поддерживают `rate d=1`, `log-return d=0`, не доказывая стационарность абсолютно.  
**Decision.** **KEEP** — эти спецификации использованы далее.

### Experiment 3 — Naive Random Walk

**Goal.** Получить обязательный leakage-safe baseline для H=1/3/5/10 quote observations.  
**Setup.** В origin T весь forecast path равен `P_T`; primary product horizon — H5.  
**Result.** Сформированы endpoint, path, future-best и regret metrics на одинаковых locked-test origins.  
**Interpretation.** На FX levels последняя известная цена оказалась труднопобедимым baseline.  
**Decision.** **KEEP** — все последующие forecast-модели сравниваются с ним.

### Experiment 4 — ARIMA multi-step

**Goal.** Проверить univariate forecast raw rate с validation-selected `(p,d,q)`.  
**Setup.** Walk-forward; selection учитывает primary H5, test locked.  
**Result.** Четыре коридора выбрали `(0,1,0)` и точно повторили Naive; KZT `(0,1,2)` улучшил H5 MAE на 0.65%, но ухудшил H10 на 0.36%.  
**Interpretation.** Устойчивая предсказуемая динамика уровня сверх Random Walk не найдена.  
**Decision.** **REJECT** как основную forecast-family; сохранить как baseline/reference.

### Experiment 5 — ARIMAX with frozen exogenous features

**Goal.** Проверить, добавляют ли доступные в T market features пользу ARIMA.  
**Setup.** Validation выбрала SET_A + ARIMAX(0,1,0); будущие exog заморожены на T.  
**Result.** Beats ARIMA: 0/5; beats Naive: 0/5 по H5/path; Future-Best и Regret также 0/5 против ARIMA.  
**Interpretation.** При `d=1`, без AR/MA и неизменных future exog прогноз вырождается почти в Random Walk.  
**Decision.** **REJECT** именно frozen-exog setup.

### Experiment 6 — Direct Ridge / Gradient Boosting

**Goal.** Предсказывать H1…H5 напрямую, не рекурсивно.  
**Setup.** Отдельная corridor×horizon модель; Ridge со TRAIN-fit scaling и Gradient Boosting; validation-only selection.  
**Result.** Лучший direct H5 превзошел Naive в AMD, KGS, TJS, UZS — 4/5; относительный выигрыш H5 примерно 0.6–3.6%, KZT хуже.  
**Interpretation.** Direct formulation полезнее ARIMA, но выигрыш exact-rate forecast остается небольшим и неоднородным.  
**Decision.** **KEEP** как лучший classical exact-forecast reference.

### Experiment 7 — CatBoost multi-horizon

**Goal.** Проверить, оправдана ли более сложная nonlinear model family.  
**Setup.** Отдельные corridor×H1…H5 модели, те же splits/origins и validation-only configs.  
**Result.** Лучше предыдущей direct-модели по H5 в 1/5 и Path MAE в 0/5; лучше Naive по H5 в 4/5 и path в 5/5.  
**Interpretation.** CatBoost в основном сохраняет небольшой выигрыш над Naive, но не окупает сложность относительно Ridge/GB.  
**Decision.** **REJECT** усложнение как источник устойчивого прироста; predictions сохранены для good-day research.

### Experiment 8 — Temporal feature enrichment

**Goal.** Проверить дополнительные lag/regime признаки на тех же direct-моделях.  
**Setup.** Lagged returns, volatility changes/ratios, momentum spread; тот же locked test.  
**Result.** H5 улучшен только для TJS на 1.20%; AMD практически tied, KGS/KZT/UZS хуже.  
**Interpretation.** Полезные признаки входят в top importance, но не дают устойчивого aggregate improvement.  
**Decision.** **PARTIAL** — признаки информативны, дальнейшее усложнение exact H1…H5 остановлено (`EXACT_PATH_FORECASTING_PLATEAU`).

### Experiment 9 — Good-day features

**Goal.** Перевести rate forecasts в продуктовые признаки качества текущего момента.  
**Setup.** `favourability_percentile_90`, `past_best_5`, `past_advantage_5`, predicted future best/regret; actual future best/regret только для evaluation.  
**Result.** Созданы согласованные validation/test row-level datasets; validation predictions восстановлены с точными Stage-04 configs без нового tuning.  
**Interpretation.** Product decision можно оценивать отдельно от слабой точности каждого будущего rate.  
**Decision.** **KEEP** — основа последующих rules experiments.

### Experiment 10 — Universal threshold rules

**Goal.** Найти единые F/A/R thresholds для всех коридоров.  
**Setup.** Три primary rules и sensitivity; первоначальный search оценивался на том же OOT-наборе и помечен exploratory.  
**Result.** Macro uplift primary rules 0.90–0.97; `WINNER: NO_STABLE_RULE`; broad rule дал 432 сигнала, но был too frequent.  
**Interpretation.** Различия коридоров не позволяют надежно использовать один универсальный threshold.  
**Decision.** **REJECT** универсальную calibration.

### Experiment 11 — Per-corridor threshold selection

**Goal.** Выбирать rule отдельно по коридору только на validation и один раз проверять на locked test.  
**Setup.** F/A/R grid, frozen thresholds, GT_B для основного сравнения.  
**Result.** Test uplift: AMD 3.67, KGS 2.20, KZT 6.62, TJS 3.28, UZS 3.89; среднее 3.93; сигналов 10–81.  
**Interpretation.** Corridor-specific rules дают сильный OOT enrichment, но частота и coverage крайне неоднородны.  
**Decision.** **KEEP**, одновременно признать frequency problem.

### Experiment 12 — Frequency calibration and cooldown

**Goal.** Увеличить регулярность сигналов, не подбирая правила по test.  
**Setup.** Validation-selected relaxed rules; сравнение before/after cooldown=3.  
**Result.** Frequency target достигнут только KZT; после cooldown осталось 10–22 сигнала на коридор, calendar gaps 44–143 дней.  
**Interpretation.** Cooldown уменьшает clustering, но усиливает уже существующую проблему редкости.  
**Decision.** **INCONCLUSIVE** — качество сохраняется, целевая регулярность не достигнута.

### Experiment 13 — Favourability windows 30 and 20; fixed-rule visuals

**Goal.** Проверить, повышает ли более локальный percentile частоту и визуальную осмысленность сигналов.  
**Setup.** Validation selection для F30; фиксированные rules для сравнений F30/F20, без test optimization.  
**Result.** F30 против F90 уменьшил signals в 4/5 коридоров (до −83% для TJS); F20 broad rules дали 66–78 сигналов, но 4–7 месяцев без сигналов.  
**Interpretation.** Короткое окно меняет локальную семантику, но само по себе не решает coverage; F30/90 сравнивает также разные GT definitions.  
**Decision.** **PARTIAL** — F20 полезно для локальности, не как самостоятельное решение частоты.

### Experiment 14 — Adaptive good-day policy

**Goal.** Добавить strong/fallback logic и cooldown в causal state machine.  
**Setup.** Три заранее заданные policy, отдельное состояние по corridor; actual regret только evaluation.  
**Result.** Суммарно 83–186 сигналов; macro-average uplift 1.97–3.10, но 26–34 нулевых corridor-months и max gap 54–60 observations.  
**Interpretation.** Качество выше random, но fallback/cooldown не устраняют длинные периоды молчания.  
**Decision.** **PARTIAL**.

### Experiment 15 — Adaptive ranking

**Goal.** Регулировать порог по давности последнего сигнала и относительным F/A/R scores.  
**Setup.** FULL=(F+A+R)/3, SIMPLE=(F+R)/2; trailing 20, adaptive 80/65/50 percentile, cooldown=3.  
**Result.** FULL: 175 signals, mean uplift 1.27, 2 zero months; SIMPLE: 188, uplift 1.43, 3 zero months; эффект `A_score` зависит от corridor.  
**Interpretation.** Ranking резко улучшает регулярность, но без абсолютного floor может выдавать относительно лучшие, однако семантически слабые дни; uplift снижается.  
**Decision.** **PARTIAL** — частота лучше, safety semantics недостаточна.

### Experiment 16 — Conservative adaptive selection

**Goal.** Вернуть абсолютную привлекательность и future-safety, сохранив адаптивность среди eligible days.  
**Setup.** `F≥0.70`, predicted regret ≤1%; score 60% F + 40% regret quality; adaptive 80/70/60 percentile; cooldown=3.  
**Result.** 94–95 signals суммарно; mean uplift 2.61–3.14; 0 нарушений F/regret invariants, но 34 zero corridor-months и max gap 55.  
**Interpretation.** Семантическое качество восстановлено ценой низкой частоты. Из-за обязательного F≥0.70 policy B/C фактически совпадают.  
**Decision.** **PARTIAL** — безопаснее, frequency problem остается.

### Experiment 17 — Intermediate FX dynamics push hypothesis

**Goal.** Найти отдельный повод для коммуникации между редкими основными good-day сигналами.  
**Setup.** Causal fixed rules: unusual 5-observation move, jump after calm, reversal, broad-vs-local context; без forecast retraining.  
**Result.** MVP «необычное движение за 5 обновлений»: 686 событий, median gap 14 дней; по коридорам 132–142 события.  
**Interpretation.** Дает более регулярный информационный сигнал, но направление почти сбалансировано и experiment не доказывает пользовательскую ценность или forecast quality.  
**Decision.** **KEEP** как отдельную продуктовую гипотезу, не замену good-day signal.

## Modeling conclusions

- Raw-rate ARIMA практически равна Random Walk: H5 лучше только в 1/5 и на 0.65%; H10 — 0/5.
- Frozen-exog ARIMAX не улучшила ни ARIMA, ни Naive; механически выбранная `(0,1,0)` с frozen exog повторяет Random Walk.
- Direct Ridge/Gradient Boosting — лучший из проверенных exact-rate подходов: H5 лучше Naive в 4/5, но прирост небольшой.
- CatBoost не улучшил classical direct baseline устойчиво: H5 1/5, Path MAE 0/5.
- Temporal enrichment не снял plateau: заметный H5 gain найден только для TJS.
- Поэтому exact FX forecasting недостаточно надежно для прямого обещания будущего курса; полезнее использовать прогноз как один из компонентов opportunity/regret policy.
- Все итоговые conclusions основаны на chronological selection и locked test; leakage audits в соответствующих артефактах имеют PASS.

## Good-day signal evolution

1. **Initial definition.** Favourability-90 описывала историческую привлекательность, predicted regret — forecast safety, actual regret — только ground truth.
2. **Universal thresholds.** Появились как простая единая rule; нестабильность между коридорами и macro uplift <1 потребовали corridor-specific calibration.
3. **Per-corridor rules.** Validation-selected rules дали сильный locked-test uplift, но обнаружили разброс от 10 до 81 сигнала и длинные периоды тишины.
4. **Frequency calibration.** Relaxation и cooldown проверяли управляемую регулярность; target достигнут лишь для одного коридора, поэтому понадобилась адаптивность.
5. **Favourability 30/20.** Более короткие окна проверяли локальность; F30 часто снизило частоту, F20 повысило ее для broad rules, но не убрало нулевые месяцы.
6. **Adaptive policy.** Strong/fallback state logic сохранила uplift, однако оставила много нулевых месяцев.
7. **Adaptive ranking.** Порог смягчался при долгом отсутствии сигнала; регулярность резко выросла, но без абсолютного floor появились семантически слабые дни и снизился uplift.
8. **Conservative adaptive selection.** Absolute floor `F≥0.70` устранил явно плохие сигналы, но вернул low-frequency проблему.
9. **Intermediate dynamics.** Возник как отдельный информационный push, чтобы не подменять «хороший день» слабым сигналом только ради частоты.

## Key numbers

- Dataset: **9 445 rows**, **5 corridors**, **2019-01-10—2026-09-03**, **104 columns**.
- ARIMA: H5 beats Naive **1/5**; H10 **0/5**.
- ARIMAX: beats ARIMA **0/5**; beats Naive **0/5** по H5/path.
- Direct ML: best H5 beats Naive **4/5**; лучший relative gain около **3.6%** (TJS Ridge).
- CatBoost: beats previous direct H5 **1/5**, Path MAE **0/5**; beats Naive H5 **4/5**.
- Per-corridor good-day: uplift ≥1.3 **5/5**, average uplift **3.93**, **10–81** test signals.
- Adaptive ranking: FULL/SIMPLE **175/188** signals, mean uplift **1.27/1.43**, **2/3** zero corridor-months.
- Conservative adaptive: **94–95** signals, mean uplift **2.61–3.14**, minimum signal F **0.70/0.75**, но **34** zero corridor-months.
- Intermediate dynamics MVP: **686** events, median gap **14 days**.

## What did not work

| Approach | Problem | What we learned |
|---|---|---|
| ARIMA | В основном выбрала Random Walk specification; нет устойчивого H5/H10 gain | Level dynamics почти не дают exploitable univariate signal |
| Frozen-exog ARIMAX | Future exog не прогнозируются и замораживаются; модель вырождается в Naive | Exogenous features полезны только при корректной future trajectory или direct target |
| CatBoost complexity | 1/5 H5 wins vs direct, 0/5 path wins | Более сложная family не компенсирует слабый predictability signal |
| Temporal feature expansion | Improvement только TJS, остальные tied/worse | Новые lags/regimes не снимают exact-path plateau |
| Universal thresholds | Одни правила дают разное качество по corridor; macro uplift <1 | Calibration должна учитывать corridor и выполняться до locked test |
| Overly strict favourability rules | Мало сигналов и длинные gaps/нулевые месяцы | Высокий precision/uplift недостаточен без product coverage |
| Favourability-30 | В 4/5 снизило количество сигналов против F90 | Более короткое окно не гарантирует большую frequency |
| Adaptive ranking without absolute floor | Частота выросла, uplift снизился до 1.27–1.43 | Relative-best день может оставаться абсолютно непривлекательным |
| Conservative adaptive rules | Вернули смысл, но 34 zero corridor-months | Safety/frequency trade-off пока не разрешен |

## Current state

- Официальные CBR raw, normalized quote-time и calendar-time datasets готовы.
- Base/advanced market features готовы; warm-up NaN сохранены, causality checks PASS.
- Temporal diagnostics и единый locked-test protocol готовы.
- Naive, ARIMA, ARIMAX, direct Ridge/GB, CatBoost forecasts и row-level predictions сохранены.
- Validation/test good-day feature datasets готовы; actual future fields отделены как evaluation-only.
- Универсальные rules отклонены; corridor-specific rules показывают сильный OOT uplift.
- Adaptive ranking показывает технически достижимую регулярность, но ухудшает смысл/качество без floor.
- Conservative policy соблюдает attractiveness/regret invariants, но остается редкой.
- Дополнительный dynamics push подготовлен как независимая коммуникационная гипотеза, не как прогноз «хорошего дня».
- Leakage audits для основных modeling и policy stages — PASS; production winner не зафиксирован.

**Главная нерешенная проблема:** signal quality может быть высокой, но достаточная ежемесячная частота без потери семантического смысла «выгодного дня» пока не достигнута.

## Open questions

1. Сколько good days физически существует в каждом corridor при текущем GT и достаточно ли этого для требуемой product frequency?
2. Следует ли заменить бинарный GT непрерывным opportunity/regret score?
3. Стоит ли моделировать `future_best_5` или `regret_5` напрямую вместо полного exact-rate path?
4. Нужна ли отдельная policy и отдельная operational frequency target для каждого corridor?
5. Следует ли разделить продуктовые сообщения на «выгодный день», «заметное движение» и «риск подорожания», не смешивая их ground truth?
6. Сохраняется ли uplift corridor-specific rules на новом полностью невидимом временном периоде?

## Experiment sources

- **Feature engineering / EDA:** `notebooks/01_fx_features_eda.ipynb`; `reports/base_features_report.md`; `reports/advanced_features_report.md`; `reports/eda_findings.md`.
- **Diagnostics / Naive / ARIMA:** `notebooks/02_model_tournament.ipynb`; `reports/time_series_diagnostics.csv`; `reports/naive_results.csv`; `reports/naive_path_results.csv`; `reports/arima_rate_multistep_results.csv`.
- **ARIMAX:** `notebooks/03_arimax_multistep_forecasting.ipynb`; `reports/arimax_multistep_results.csv`; `reports/arimax_multistep_report.md`.
- **Direct multi-horizon:** `notebooks/03_direct_multihorizon_forecasting.ipynb`; `reports/direct_multihorizon_results.csv`; `reports/direct_multihorizon_winners.csv`; `reports/direct_multihorizon_report.md`.
- **CatBoost:** `notebooks/04_catboost_multihorizon_forecasting.ipynb`; `reports/catboost_multihorizon_results.csv`; `reports/catboost_multihorizon_report.md`.
- **Temporal enrichment:** `notebooks/05_temporal_feature_enrichment.ipynb`; `reports/temporal_enrichment_results.csv`; `reports/temporal_enrichment_report.md`.
- **Good-day features:** `notebooks/06_good_day_features.ipynb`; `reports/good_day_features_validation.csv`; `reports/good_day_features.csv`.
- **Universal thresholds:** `notebooks/07_good_day_threshold_tournament.ipynb`; `reports/good_day_threshold_tournament.csv`; `reports/good_day_threshold_report.md`.
- **Per-corridor rules:** `notebooks/08_per_corridor_good_day_rules.ipynb`; `reports/per_corridor_rule_selection.csv`; `reports/per_corridor_good_day_test_results.csv`; `reports/per_corridor_good_day_report.md`.
- **Frequency calibration:** `notebooks/09_signal_frequency_calibration.ipynb`; `reports/frequency_calibration_test_results.csv`; `reports/frequency_calibration_report.md`.
- **Favourability-30:** `notebooks/09_favourability_30_rules.ipynb`; `reports/favourability_30_test_results.csv`; `reports/favourability_30_vs_90.csv`; `reports/favourability_30_report.md`.
- **Fixed-rule visuals F30/F20:** `notebooks/10_favourability30_rule_visual_comparison.ipynb`; `notebooks/11_favourability20_rule_visual_comparison.ipynb`; `reports/favourability30_rule_visual_comparison.csv`; `reports/favourability20_rule_visual_comparison.csv`.
- **Adaptive good-day policy:** `notebooks/12_adaptive_good_day_policy.ipynb`; `reports/adaptive_good_day_policy_results.csv`; `reports/adaptive_good_day_policy_report.md`.
- **Adaptive ranking:** `notebooks/13_adaptive_ranking_good_day.ipynb`; `reports/adaptive_ranking_results.csv`; `reports/adaptive_ranking_report.md`.
- **Conservative adaptive selection:** `notebooks/14_conservative_adaptive_selection.ipynb`; `reports/conservative_adaptive_results.csv`; `reports/conservative_adaptive_report.md`.
- **Intermediate dynamics push:** `notebooks/02_fx_dynamics_push_hypothesis.ipynb`; `reports/intermediate_dynamics/candidate_comparison.csv`; `reports/intermediate_dynamics/mvp_by_corridor.csv`; `reports/intermediate_dynamics/mvp_signal_events.csv`.

## One-paragraph project status

Проект располагает воспроизводимым набором официальных CBR FX-данных, causal feature pipeline и единой locked-test инфраструктурой. Univariate ARIMA и frozen-exog ARIMAX не превзошли сильный Random Walk baseline, а direct ML дал лишь небольшой и неоднородный прирост; CatBoost и temporal enrichment не сняли plateau exact forecasting. Наиболее убедительный результат получен у validation-selected per-corridor good-day rules: все пять коридоров превысили random baseline на locked test, но частота сигналов сильно различается. Adaptive ranking сделал сигналы регулярнее, однако ослабил абсолютный смысл «выгодного дня», а conservative floor восстановил смысл ценой новых длинных пауз. Поэтому production winner пока не выбран. Исследование находится на границе между улучшением direct opportunity modeling и продуктовым разделением редкого good-day сигнала с более частыми информационными уведомлениями о движении курса.
