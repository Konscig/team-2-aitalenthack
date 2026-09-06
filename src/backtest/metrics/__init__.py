"""Metrics for signal classification, market outcomes, and communication policy."""

from src.backtest.metrics.api import EvaluationResult, evaluate_predictions
from src.backtest.metrics.classification import classification_metrics, threshold_sweep
from src.backtest.metrics.legacy import frequency_metrics, quality_metrics
from src.backtest.metrics.outcomes import HORIZONS, build_outcomes
from src.backtest.metrics.random_baseline import random_legal_schedules

__all__ = [
    "HORIZONS",
    "EvaluationResult",
    "build_outcomes",
    "classification_metrics",
    "evaluate_predictions",
    "frequency_metrics",
    "quality_metrics",
    "random_legal_schedules",
    "threshold_sweep",
]
