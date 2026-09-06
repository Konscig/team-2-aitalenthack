"""Public, model-agnostic interface for evaluating daily signal predictions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.metrics.classification import classification_metrics
from src.backtest.metrics.evaluation import evaluate_schedule, frequency_tables
from src.backtest.metrics.outcomes import HORIZONS, build_outcomes
from src.backtest.policy import select_scenario_pushes

KEYS = ("date", "corridor")
TARGETS = ("good", "closing")
PREDICTION_COLUMNS = ("good_pred", "closing_pred")


def _require_columns(frame: pd.DataFrame, columns: set[str], name: str) -> None:
    missing = columns - set(frame.columns)
    if missing:
        raise ValueError(f"{name} is missing columns: {sorted(missing)}")


def _normalise_keys(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result.date, errors="raise")
    if result[list(KEYS)].isna().any().any():
        raise ValueError(f"{name} has missing keys")
    if result.duplicated(list(KEYS)).any():
        raise ValueError(f"{name} has duplicate date/corridor rows")
    return result.sort_values(list(KEYS)).reset_index(drop=True)


def _validate_binary(frame: pd.DataFrame, columns: list[str], name: str) -> None:
    for column in columns:
        if not frame[column].isin([False, True, 0, 1]).all():
            raise ValueError(f"{name}.{column} must contain only 0/1 or bool")


def _classification_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for corridor, group in frame.groupby("corridor", sort=True):
        for target in TARGETS:
            score_column = f"{target}_score"
            metrics = classification_metrics(
                group[target],
                group[f"{target}_pred"],
                y_score=group[score_column] if score_column in group else None,
            )
            rows.append({"corridor": corridor, "target": target, **metrics})
    return pd.DataFrame(rows)


def _markdown_report(result: EvaluationResult, description: str | None = None) -> str:
    quality_columns = [
        "corridor",
        "scenario",
        "h_days",
        "signal_count",
        "safety_hit_rate",
        "random_safety_hit_rate_mean",
        "safety_lift",
        "benefit_mean_bps",
        "random_benefit_mean_bps",
        "incremental_benefit_bps",
        "benefit_randomization_p",
    ]
    classification_columns = [
        "corridor",
        "target",
        "predicted_positive",
        "precision",
        "recall",
        "f_beta",
        "classification_lift",
        "average_precision",
    ]
    classification_columns = [column for column in classification_columns if column in result.classification]
    quality_table = (
        result.scenario_metrics[quality_columns].to_markdown(index=False, floatfmt=".3f")
        if not result.scenario_metrics.empty
        else "Алгоритм не сформировал ни одного push."
    )
    lines = [
        "# Оценка сигнального слоя",
        "",
        description
        or (
            "Отчёт построен публичным `evaluate_predictions`. Для честного backtest автор predictions обязан "
            "использовать только информацию, доступную алгоритму на дату T; будущее используется только при оценке."
        ),
        "",
        f"Горизонты оценки: `{list(result.horizons)}` календарных дней. "
        f"Random-прогонов: {result.replicates}. Cooldown: {result.cooldown_days} дня; "
        f"лимит: {result.weekly_cap} push в неделю.",
        "",
        "`safety_hit`: после любой коммуникации в следующие h дней не появился курс выгоднее "
        "более чем на заданный допуск. `safety_lift` сравнивает этот hit rate с policy-matched random.",
        "",
        "`benefit_mean_bps`: насколько даты коммуникаций лучше среднего курса в окне ±h. "
        "`incremental_benefit_bps` — разница с тем же показателем случайного расписания.",
        "",
        "## Классификация golden targets",
        "",
        result.classification[classification_columns].to_markdown(index=False, floatfmt=".3f"),
        "",
        "## Рыночные outcomes и экономика",
        "",
        quality_table,
        "",
        "## Частота итогового потока",
        "",
        result.frequency_summary.to_markdown(index=False, floatfmt=".3f"),
        "",
        "`window_closing` дополнительно проверяется колонками `closing_confirmation_*` в CSV: "
        "медиана будущих h дней должна быть хуже даты сигнала минимум на заданный порог.",
        "",
    ]
    return "\n".join(lines)


@dataclass(frozen=True)
class EvaluationResult:
    """All evaluation artifacts returned by :func:`evaluate_predictions`."""

    classification: pd.DataFrame
    scenario_metrics: pd.DataFrame
    frequency_summary: pd.DataFrame
    weekly_frequency: pd.DataFrame
    pushes: pd.DataFrame
    outcomes: pd.DataFrame
    random_runs: pd.DataFrame
    horizons: tuple[int, ...]
    replicates: int
    cooldown_days: int
    weekly_cap: int

    def save(
        self,
        output_dir: str | Path,
        *,
        include_random_runs: bool = False,
        description: str | None = None,
    ) -> Path:
        """Write a compact reproducible report and its source tables."""
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        self.classification.to_csv(output / "classification_metrics.csv", index=False)
        self.scenario_metrics.to_csv(output / "scenario_metrics.csv", index=False)
        self.frequency_summary.to_csv(output / "frequency_summary.csv", index=False)
        self.weekly_frequency.to_csv(output / "weekly_frequency.csv", index=False)
        self.pushes.to_csv(output / "pushes.csv", index=False)
        self.outcomes.to_csv(output / "outcomes.csv", index=False)
        if include_random_runs:
            self.random_runs.to_csv(output / "random_runs.csv", index=False)
        report = output / "summary.md"
        report.write_text(_markdown_report(self, description), encoding="utf-8")
        return report


def evaluate_predictions(
    predictions: pd.DataFrame,
    labels: pd.DataFrame,
    calendar: pd.DataFrame,
    *,
    horizons: tuple[int, ...] = HORIZONS,
    replicates: int = 1_000,
    cooldown_days: int = 4,
    weekly_cap: int = 2,
    seed: int = 42,
    average_transfer_rub: float = 22_000,
) -> EvaluationResult:
    """Evaluate causal daily predictions for every supplied corridor.

    ``predictions`` must contain one row per evaluated date/corridor and the
    binary columns ``good_pred`` and ``closing_pred``. Optional probability
    columns are ``good_score`` and ``closing_score``. An optional
    ``positive_market_fact`` column participates in the third-priority push
    scenario but has no classification target.

    ``labels`` supplies ``rate``, ``good`` and ``closing`` on the same keys.
    The prediction rows define the evaluation period; every one must have a
    matching label. Policy priority is good -> closing -> factual, followed by
    cooldown and weekly-cap filtering independently for each corridor.
    """
    _require_columns(predictions, {*KEYS, *PREDICTION_COLUMNS}, "predictions")
    _require_columns(labels, {*KEYS, "rate", *TARGETS}, "labels")
    if not horizons or len(set(horizons)) != len(horizons) or any(type(h) is not int or h <= 0 for h in horizons):
        raise ValueError("horizons must contain unique positive integers")
    if replicates < 1:
        raise ValueError("replicates must be positive")

    predicted = _normalise_keys(predictions, "predictions")
    truth = _normalise_keys(labels, "labels")
    _validate_binary(predicted, list(PREDICTION_COLUMNS), "predictions")
    _validate_binary(truth, list(TARGETS), "labels")
    if "positive_market_fact" not in predicted:
        predicted["positive_market_fact"] = False
    _validate_binary(predicted, ["positive_market_fact"], "predictions")
    for score_column in ("good_score", "closing_score"):
        if score_column in predicted:
            score = pd.to_numeric(predicted[score_column], errors="raise")
            if not np.isfinite(score).all():
                raise ValueError(f"predictions.{score_column} must be finite")
            predicted[score_column] = score

    label_columns = [*KEYS, "rate", *TARGETS]
    daily = predicted.merge(truth[label_columns], on=list(KEYS), how="left", validate="one_to_one")
    if daily[["rate", *TARGETS]].isna().any().any():
        raise ValueError("Every prediction row must have a matching complete label row")

    classification = _classification_table(daily)
    pushes_parts: list[pd.DataFrame] = []
    outcome_parts: list[pd.DataFrame] = []
    metric_parts: list[pd.DataFrame] = []
    random_parts: list[pd.DataFrame] = []
    weekly_parts: list[pd.DataFrame] = []
    frequency_parts: list[pd.DataFrame] = []
    for offset, (corridor, group) in enumerate(daily.groupby("corridor", sort=True)):
        group = group.sort_values("date").copy()
        policy_input = group.assign(good=group.good_pred, closing=group.closing_pred)
        group["push"], group["push_scenario"] = select_scenario_pushes(
            policy_input,
            cooldown_days=cooldown_days,
            weekly_cap=weekly_cap,
        )
        corridor_pushes = group.loc[group.push].copy()
        pushes_parts.append(corridor_pushes)
        outcomes = build_outcomes(
            group[["date", "corridor", "rate"]],
            calendar,
            horizons=horizons,
        )
        outcome_parts.append(outcomes)
        if not corridor_pushes.empty:
            metrics, random = evaluate_schedule(
                corridor_pushes,
                outcomes,
                group.date,
                replicates=replicates,
                cooldown_days=cooldown_days,
                weekly_cap=weekly_cap,
                seed=seed + offset * 10_000,
                average_transfer_rub=average_transfer_rub,
            )
            metrics.insert(0, "corridor", corridor)
            random.insert(0, "corridor", corridor)
            metric_parts.append(metrics)
            random_parts.append(random)
        weekly, frequency = frequency_tables(
            corridor_pushes,
            start=group.date.min(),
            end=group.date.max(),
        )
        weekly.insert(0, "corridor", corridor)
        frequency.insert(0, "corridor", corridor)
        weekly_parts.append(weekly)
        frequency_parts.append(frequency)

    return EvaluationResult(
        classification=classification,
        scenario_metrics=pd.concat(metric_parts, ignore_index=True) if metric_parts else pd.DataFrame(),
        frequency_summary=pd.concat(frequency_parts, ignore_index=True),
        weekly_frequency=pd.concat(weekly_parts, ignore_index=True),
        pushes=pd.concat(pushes_parts, ignore_index=True),
        outcomes=pd.concat(outcome_parts, ignore_index=True),
        random_runs=pd.concat(random_parts, ignore_index=True) if random_parts else pd.DataFrame(),
        horizons=tuple(horizons),
        replicates=replicates,
        cooldown_days=cooldown_days,
        weekly_cap=weekly_cap,
    )
