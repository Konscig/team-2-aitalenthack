# Методология и интерфейс оценки сигналов

## Какие вопросы разделяют метрики

1. Алгоритм находит golden targets `good` и `closing`.
2. После любой коммуникации клиент не увидит существенно лучший курс в ближайшем будущем.
3. Текст «окно закрывается» подтверждается последующим ростом курса.
4. Дата коммуникации экономически лучше обычной даты.
5. Итоговый поток соответствует ограничениям по частоте и кучности.

Один показатель не подменяет другой. Отчёт строится отдельно по сценарию,
коридору и `h ∈ {1, 3, 5, 10, 20}` календарных дней, а также для всего
портфеля коммуникаций.

## Classification

Для predictions `good_pred` и `closing_pred` считаются `precision`, `recall`,
`F0.5`, average precision, confusion matrix и lift precision над prevalence
соответствующего golden target. Главная метрика — precision, поскольку плохая
коммуникация дороже пропущенного хорошего момента.

`positive_market_fact` является детерминированным правилом по доступной истории,
поэтому classification-метрики для него не считаются.

## Единая безопасность коммуникации

Любой выбранный сценарий ведёт клиента к решению о переводе сейчас. Поэтому для
`good_now`, `window_closing`, factual-сценария и всего портфеля применяется один
no-regret критерий:

```text
future_regret_bps = 10 000 × (rate_T − min(rate[T+1:T+h])) / rate_T
safety_hit = future_regret_bps <= 100
safety_lift = signal_safety_hit_rate / random_safety_hit_rate
```

Курс измеряется в RUB за единицу валюты получателя: меньше — выгоднее клиенту.

Для `window_closing` дополнительно проверяется обещанный сценарием устойчивый рост:

```text
future_median_change_bps =
    10 000 × (median(rate[T+1:T+h]) − rate_T) / rate_T
closing_confirmation_hit = future_median_change_bps >= 100
```

Factual-текст истинен по построению в дату T. Его продуктовую полезность показывают
общий `safety_hit` и экономические метрики, а не тривиальная точность правила.

## Экономическая выгода

Формула соответствует требованию кейса сравнивать дату сигнала со средним курсом
в окне `±h`:

```text
benefit_bps =
    10 000 × (mean(rate[T−h:T+h]) − rate_T) / mean(rate[T−h:T+h])
```

Положительное значение означает, что дата коммуникации выгоднее локального
среднего. Помимо среднего считаются медиана, доля положительных исходов и
приблизительный рублёвый эквивалент на переводе 22 000 ₽.

## Policy-matched random

Для каждого сценария и всего портфеля генерируются случайные расписания:

- тот же коридор и evaluation-период;
- то же количество push;
- те же допустимые даты;
- cooldown четыре календарных дня;
- максимум два push в ISO-неделю.

Каждому random-расписанию назначаются те же market outcomes. В отчёте приводятся
среднее и 5–95-й процентили random, lift safety hit rate, разница в bps и
односторонний randomization p-value. Economic lift отношением не считается:
средняя выгода random находится около нуля, поэтому такое отношение нестабильно.

## Публичный интерфейс

Основной API импортируется напрямую из `src.backtest.metrics`:

```python
import pandas as pd

from src.backtest.metrics import evaluate_predictions

predictions = pd.DataFrame(
    {
        "date": [...],
        "corridor": [...],
        "good_pred": [...],
        "closing_pred": [...],
        "good_score": [...],             # optional
        "closing_score": [...],          # optional
        "positive_market_fact": [...],   # optional, default False
    }
)

result = evaluate_predictions(
    predictions=predictions,
    labels=pd.read_parquet("data/labels/golden_labels.parquet"),
    calendar=pd.read_parquet("data/interim/fx_calendar_time.parquet"),
    horizons=(1, 3, 5, 10, 20),
)

print(result.classification)
print(result.scenario_metrics)
print(result.frequency_summary)
report_path = result.save("reports/evaluation/my_model")
```

### Контракт predictions

Одна строка — одна доступная алгоритму дата одного коридора. Таблица обязана
содержать все даты evaluation-периода, включая отрицательные predictions:

| column | required | meaning |
|---|---:|---|
| `date` | да | дата сигнала |
| `corridor` | да | например `TJS_RUB` |
| `good_pred` | да | бинарное предсказание `good` |
| `closing_pred` | да | бинарное предсказание `closing` |
| `good_score` | нет | score/probability для average precision |
| `closing_score` | нет | score/probability для average precision |
| `positive_market_fact` | нет | causal factual-кандидат третьего приоритета |

Функция сама разделяет коридоры, применяет порядок
`good_now → window_closing → positive_market_fact`, cooldown и недельный лимит.
Период оценки определяется строками predictions. Каждая строка должна иметь пару
`date/corridor` в labels; будущее не должно попадать в predictions или scores.

`EvaluationResult.save()` сохраняет Markdown-отчёт и компактные исходные таблицы.
Сырые 1 000 random-прогонов по умолчанию не записываются; для диагностики нужно
передать `include_random_runs=True`.

## Готовые запуски

Oracle sanity-check, который подставляет golden labels как идеальные predictions:

```bash
.venv/bin/python -m src.backtest.evaluate
```

Воспроизводимый пример со случайными predictions:

```bash
.venv/bin/python -m src.backtest.random_demo
```

Oracle нужен только для проверки верхней границы и формул. Качеством production-
алгоритма считается только causal walk-forward прогон, где predictions даты T
построены исключительно по информации, доступной на T.
