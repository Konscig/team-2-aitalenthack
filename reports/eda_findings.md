# EDA findings

## 1. Dataset status

- Использован `data/features/fx_features_daily.parquet`: 9445 строк, 104 столбца, 99 числовых полей.
- Коридоры: AMD_RUB, KGS_RUB, KZT_RUB, TJS_RUB, UZS_RUB.
- Период: 2019-01-10 — 2026-09-03.
- Дубликаты date/corridor: 0; неизвестные corridors: нет; одинаковый период: True.

## 2. Critical observations

- Начальные NaN соответствуют causal warm-up. Неожиданных NaN по проверенным зрелым окнам: 0.
- Объединённая таблица подозрительных наблюдений содержит 224 строк; они не удалены и требуют raw-source verification.

## 3. Corridor differences

- Наблюдаются различия в `ret_1`, `vol_20`, `rolling_range_20`, частотах reversal и связи с broad RUB. Это основание проверять отдельную calibration после появления labels.

## 4. Feature quality

- Семантика favourability, distance-to-average/minimum и freshness согласуется с формулами.
- Cross identity: max absolute error 0, max relative error 0.
- Будущие значения не создавались; notebook только читает production Parquet.

## 5. Redundant features

- Exact duplicates: ret_3=mom_3, ret_5=mom_5, ret_10=mom_10, ret_20=mom_20 (max difference 0).
- Numeric-пар с abs correlation >0.995: 70. Автоматическое удаление не выполнялось.
- Основные strongly correlated группы: percentile ↔ favourability (корреляция -1); rate ↔ короткие SMA/rolling extrema; соседние SMA и rolling extrema; ret_1 ↔ log_ret_1.
- Примеры пар: percentile_90 ↔ favourability_percentile_90 (-1.0000); percentile_60 ↔ favourability_percentile_60 (-1.0000); ret_20 ↔ mom_20 (1.0000); ret_3 ↔ mom_3 (1.0000); ret_10 ↔ mom_10 (1.0000); ret_5 ↔ mom_5 (1.0000); percentile_180 ↔ favourability_percentile_180 (-1.0000); percentile_20 ↔ favourability_percentile_20 (-1.0000); percentile_365 ↔ favourability_percentile_365 (-1.0000); sma_5 ↔ sma_10 (0.9999); rate ↔ sma_5 (0.9998); sma_10 ↔ sma_20 (0.9997).

## 6. Reversal findings

- Fast reversal и 2d confirmation различаются частотой и задержкой; визуально встречаются как выраженные повороты, так и слабый шум.
- Всего `near_min_reversal_005`: 758; `reversal_2d_005`: 493; смен знака `return_sign_reversal_up`: 2125.
- Без labels нельзя утверждать, какой сигнал лучше.

## 7. Cross-currency findings

- Корреляции corridor ret_1 с broad RUB: {'AMD_RUB': 0.9385604720868775, 'KGS_RUB': 0.845384893097291, 'KZT_RUB': 0.8371667844585864, 'TJS_RUB': 0.8104127216710074, 'UZS_RUB': 0.9502903386172823}.
- Крупные corridor-specific остатки отмечают кандидатов на локальные события, но не устанавливают их причины.

## 8. Risks

- Warm-up missingness, redundant features, correlation, structural drift, extreme observations и as-of freshness.
- Любой preprocessing должен обучаться только на прошлом внутри time split.

## 9. Questions for labels/modeling

- Как определить label через future regret без попадания future values в признаки?
- Нужны ли corridor-specific модели или достаточно взаимодействий с corridor?
- Как обрабатывать warm-up NaN без leakage?
- Удалять ли exact duplicate momentum/return до обучения?
- Насколько устойчивы thresholds reversal на time-based validation?
- Как учитывать event clustering и ограничение 1–2 push в неделю?
- Нужна ли отдельная ручная верификация экстремальных raw observations?
