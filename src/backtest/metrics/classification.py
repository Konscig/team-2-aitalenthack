"""Pure binary-classification metrics with precision-weighted F-beta."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def _binary(values: Sequence[object], name: str) -> np.ndarray:
    result = np.asarray(values)
    if result.ndim != 1 or result.size == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    if not np.isin(result, [False, True, 0, 1]).all():
        raise ValueError(f"{name} must contain only binary values")
    return result.astype(bool)


def _average_precision(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """Threshold-based average precision with deterministic handling of ties."""
    positives = int(y_true.sum())
    if positives == 0:
        return float("nan")
    order = np.argsort(-y_score, kind="stable")
    ordered_truth = y_true[order]
    ordered_score = y_score[order]
    threshold_ends = np.r_[np.flatnonzero(np.diff(ordered_score)), len(ordered_score) - 1]
    true_positives = np.cumsum(ordered_truth)[threshold_ends]
    predicted_positives = threshold_ends + 1
    precision = true_positives / predicted_positives
    recall = true_positives / positives
    recall_increments = np.diff(np.r_[0.0, recall])
    return float(np.sum(recall_increments * precision))


def classification_metrics(
    y_true: Sequence[object],
    y_pred: Sequence[object],
    *,
    y_score: Sequence[float] | None = None,
    beta: float = 0.5,
) -> dict[str, float | int]:
    """Return classification metrics; undefined ratios are represented by NaN."""
    truth = _binary(y_true, "y_true")
    prediction = _binary(y_pred, "y_pred")
    if len(truth) != len(prediction):
        raise ValueError("y_true and y_pred must have equal length")
    if beta <= 0:
        raise ValueError("beta must be positive")

    tp = int((truth & prediction).sum())
    fp = int((~truth & prediction).sum())
    fn = int((truth & ~prediction).sum())
    tn = int((~truth & ~prediction).sum())
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    beta_sq = beta**2
    f_beta = (
        (1 + beta_sq) * precision * recall / (beta_sq * precision + recall)
        if np.isfinite(precision) and np.isfinite(recall) and beta_sq * precision + recall > 0
        else float("nan")
    )
    prevalence = float(truth.mean())
    result: dict[str, float | int] = {
        "rows": len(truth),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "true_negative": tn,
        "predicted_positive": int(prediction.sum()),
        "actual_positive": int(truth.sum()),
        "precision": precision,
        "recall": recall,
        "f_beta": f_beta,
        "beta": beta,
        "prevalence": prevalence,
        "random_precision": prevalence,
        "classification_lift": precision / prevalence if prevalence > 0 and np.isfinite(precision) else float("nan"),
    }
    if y_score is not None:
        score = np.asarray(y_score, dtype=float)
        if score.ndim != 1 or len(score) != len(truth) or not np.isfinite(score).all():
            raise ValueError("y_score must be finite, one-dimensional, and aligned")
        result["average_precision"] = _average_precision(truth, score)
    return result


def threshold_sweep(
    y_true: Sequence[object],
    y_score: Sequence[float],
    *,
    thresholds: Sequence[float] | None = None,
    beta: float = 0.5,
) -> pd.DataFrame:
    """Evaluate probability thresholds without choosing one on the test set."""
    truth = _binary(y_true, "y_true")
    score = np.asarray(y_score, dtype=float)
    if score.ndim != 1 or len(score) != len(truth) or not np.isfinite(score).all():
        raise ValueError("y_score must be finite, one-dimensional, and aligned")
    candidates = np.unique(score)[::-1] if thresholds is None else np.asarray(thresholds, dtype=float)
    if candidates.ndim != 1 or len(candidates) == 0 or not np.isfinite(candidates).all():
        raise ValueError("thresholds must be finite and non-empty")
    rows = []
    for threshold in candidates:
        metrics = classification_metrics(truth, score >= threshold, beta=beta)
        rows.append({"threshold": float(threshold), **metrics})
    return pd.DataFrame(rows)
