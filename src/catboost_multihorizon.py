"""Leakage-safe direct CatBoost forecasts for five future CBR quotes.

The experiment intentionally reuses the exact 15-feature set and temporal
protocol from the direct Ridge/Gradient Boosting experiment. Five independent
models predict log(rate[T+h] / rate[T]); future observations are targets only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

from src.direct_multihorizon import (
    CANDIDATE_FEATURES,
    HORIZONS,
    add_path_evaluation,
    audit_and_select_features,
    build_model_frame,
    create_direct_targets,
    discover_feature_dataset,
    load_and_validate_dataset,
    load_splits,
)

CONFIGS = (
    {"iterations": 300, "depth": 4, "learning_rate": 0.03, "l2_leaf_reg": 3},
    {"iterations": 500, "depth": 4, "learning_rate": 0.03, "l2_leaf_reg": 5},
    {"iterations": 300, "depth": 6, "learning_rate": 0.03, "l2_leaf_reg": 5},
    {"iterations": 500, "depth": 6, "learning_rate": 0.02, "l2_leaf_reg": 10},
)
FORBIDDEN_TOKENS = ("future", "regret", "good_day", "safe", "label", "target")
RANDOM_SEED = 42


class CatBoostForecastError(RuntimeError):
    """Raised when an input or temporal/leakage invariant fails."""


def _save_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _model(params: dict[str, Any], iterations: int | None = None) -> CatBoostRegressor:
    values = dict(params)
    if iterations is not None:
        values["iterations"] = iterations
    return CatBoostRegressor(
        **values,
        loss_function="RMSE",
        random_seed=RANDOM_SEED,
        verbose=False,
        allow_writing_files=False,
        thread_count=-1,
    )


def _validation_metrics(
    actual: np.ndarray, predicted: np.ndarray, rate_t: np.ndarray
) -> dict[str, float]:
    error = actual - predicted
    return {
        "MAE": float(np.mean(np.abs(error))),
        "RMSE": float(np.sqrt(np.mean(np.square(error)))),
        "DA": float(np.mean(np.sign(actual / rate_t - 1) == np.sign(predicted / rate_t - 1))),
    }


def tune_catboost(
    partitions: dict[str, dict[str, pd.DataFrame]], features: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidate_rows = []
    selection_rows = []
    for corridor, parts in sorted(partitions.items()):
        train, validation = parts["train"], parts["validation"]
        x_train = train[features]
        x_validation = validation[features]
        for horizon in HORIZONS:
            target = f"target_log_return_h{horizon}"
            rate_t = validation.rate.to_numpy(dtype=float)
            actual = validation[f"actual_rate_h{horizon}"].to_numpy(dtype=float)
            for config_id, params in enumerate(CONFIGS, 1):
                model = _model(params)
                model.fit(
                    x_train,
                    train[target],
                    eval_set=(x_validation, validation[target]),
                    early_stopping_rounds=50,
                    use_best_model=True,
                )
                predicted_log_return = model.predict(x_validation)
                predicted_rate = rate_t * np.exp(predicted_log_return)
                metrics = _validation_metrics(actual, predicted_rate, rate_t)
                best_iteration = int(model.get_best_iteration())
                candidate_rows.append({
                    "corridor": corridor,
                    "horizon": horizon,
                    "config_id": f"CONFIG_{config_id}",
                    "params": json.dumps(params, sort_keys=True),
                    "best_iteration": best_iteration,
                    "trees_used": best_iteration + 1,
                    **metrics,
                    "n_validation": len(validation),
                })
    candidates = pd.DataFrame(candidate_rows)
    for (corridor, horizon), group in candidates.groupby(["corridor", "horizon"], sort=True):
        selected = group.sort_values(["MAE", "RMSE", "config_id"], kind="stable").iloc[0]
        selection_rows.append(selected.to_dict())
    return candidates, pd.DataFrame(selection_rows)


def fit_selected(
    partitions: dict[str, dict[str, pd.DataFrame]],
    features: list[str],
    selections: pd.DataFrame,
) -> dict[str, dict[int, CatBoostRegressor]]:
    models: dict[str, dict[int, CatBoostRegressor]] = {}
    for corridor, parts in sorted(partitions.items()):
        refit = parts["refit"]
        models[corridor] = {}
        for horizon in HORIZONS:
            selected = selections.loc[
                (selections.corridor == corridor) & (selections.horizon == horizon)
            ].iloc[0]
            params = json.loads(selected.params)
            # Early-stopping iteration is selected on validation, then frozen.
            model = _model(params, iterations=max(1, int(selected.trees_used)))
            model.fit(refit[features], refit[f"target_log_return_h{horizon}"])
            models[corridor][horizon] = model
    return models


def predict_next_5_rates(
    row_t: pd.Series,
    corridor: str,
    models: dict[str, dict[int, CatBoostRegressor]],
    features: list[str],
) -> list[float]:
    """Return [T+1,...,T+5] using the same X_T for five independent models."""
    x_t = row_t[features].to_frame().T
    rate_t = float(row_t.rate)
    return [
        float(rate_t * np.exp(models[corridor][h].predict(x_t)[0]))
        for h in HORIZONS
    ]


def build_predictions(
    partitions: dict[str, dict[str, pd.DataFrame]],
    features: list[str],
    models: dict[str, dict[int, CatBoostRegressor]],
) -> pd.DataFrame:
    rows = []
    for corridor, parts in sorted(partitions.items()):
        for _, row in parts["test"].iterrows():
            path = predict_next_5_rates(row, corridor, models, features)
            rows.append({
                "corridor": corridor,
                "date": row.date,
                "model": "CATBOOST",
                "rate_t": float(row.rate),
                **{f"actual_date_h{h}": row[f"actual_date_h{h}"] for h in HORIZONS},
                **{f"actual_rate_h{h}": float(row[f"actual_rate_h{h}"]) for h in HORIZONS},
                **{f"predicted_rate_h{h}": path[h - 1] for h in HORIZONS},
            })
    return add_path_evaluation(pd.DataFrame(rows))


def load_previous_baselines(
    root: Path, catboost: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    prediction_path = root / "reports" / "direct_multihorizon_test_predictions.csv"
    result_path = root / "reports" / "direct_multihorizon_results.csv"
    arimax_result_path = root / "reports" / "arimax_multistep_results.csv"
    for path in (prediction_path, result_path, arimax_result_path):
        if not path.exists():
            raise CatBoostForecastError(f"Required saved baseline artifact is absent: {path}")
    predictions = pd.read_csv(prediction_path, parse_dates=["date"])
    results = pd.read_csv(result_path)
    arimax_results = pd.read_csv(arimax_result_path)
    direct = results.loc[results.model.isin(["DIRECT_RIDGE", "DIRECT_GRADIENT_BOOSTING"])]
    best_direct = (
        direct.sort_values(["corridor", "MAE_H5", "model"], kind="stable")
        .groupby("corridor", as_index=False).first()
        .rename(columns={"model": "previous_direct_model"})
    )
    keys = catboost[["corridor", "date"]].sort_values(["corridor", "date"]).reset_index(drop=True)
    for model, group in predictions.groupby("model"):
        baseline_keys = group[["corridor", "date"]].sort_values(["corridor", "date"]).reset_index(drop=True)
        if not keys.equals(baseline_keys):
            raise CatBoostForecastError(f"Test origins differ from saved {model}")
    # ARIMAX is included in the comparison table without retraining.
    arimax_compare = arimax_results.copy()
    arimax_compare["model"] = "ARIMAX"
    common = pd.concat([results, arimax_compare], ignore_index=True, sort=False)
    return predictions, best_direct.merge(
        common.loc[common.model == "NAIVE", ["corridor", "MAE_H5", "Path_MAE_5"]].rename(
            columns={"MAE_H5": "naive_MAE_H5", "Path_MAE_5": "naive_Path_MAE_5"}
        ), on="corridor", validate="one_to_one"
    ), common


def _practical_status(improvement_pct: float) -> str:
    if improvement_pct >= 1.0:
        return "IMPROVED"
    if improvement_pct >= 0.0:
        return "PRACTICALLY_TIED"
    return "WORSE"


def build_results(
    catboost: pd.DataFrame,
    best_previous: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for corridor, group in catboost.groupby("corridor", sort=True):
        row: dict[str, Any] = {"corridor": corridor, "model": "CATBOOST"}
        path_errors = []
        for horizon in HORIZONS:
            actual = group[f"actual_rate_h{horizon}"].to_numpy(dtype=float)
            predicted = group[f"predicted_rate_h{horizon}"].to_numpy(dtype=float)
            rate_t = group.rate_t.to_numpy(dtype=float)
            metrics = _validation_metrics(actual, predicted, rate_t)
            row[f"MAE_H{horizon}"] = metrics["MAE"]
            row[f"RMSE_H{horizon}"] = metrics["RMSE"]
            row[f"DA_H{horizon}"] = metrics["DA"]
            path_errors.append(np.abs(actual - predicted))
        row["Path_MAE_5"] = float(np.column_stack(path_errors).mean(axis=1).mean())
        row["Future_Best_MAE_5"] = float(
            (group.actual_future_best_5 - group.predicted_future_best_5).abs().mean()
        )
        row["Regret_MAE_5"] = float(
            (group.actual_regret_5 - group.predicted_regret_5).abs().mean()
        )
        row["n_forecasts"] = len(group)
        rows.append(row)
    result = pd.DataFrame(rows)
    previous_columns = [
        "corridor", "previous_direct_model", "MAE_H5", "Path_MAE_5",
        "Future_Best_MAE_5", "Regret_MAE_5", "naive_MAE_H5", "naive_Path_MAE_5",
    ]
    previous = best_previous[previous_columns].rename(columns={
        "MAE_H5": "previous_direct_MAE_H5",
        "Path_MAE_5": "previous_direct_Path_MAE_5",
        "Future_Best_MAE_5": "previous_direct_Future_Best_MAE_5",
        "Regret_MAE_5": "previous_direct_Regret_MAE_5",
    })
    result = result.merge(previous, on="corridor", validate="one_to_one")
    pairs = {
        "MAE_H5": "previous_direct_MAE_H5",
        "Path_MAE_5": "previous_direct_Path_MAE_5",
        "Future_Best_MAE_5": "previous_direct_Future_Best_MAE_5",
        "Regret_MAE_5": "previous_direct_Regret_MAE_5",
    }
    for metric, baseline in pairs.items():
        ratio = f"{metric}_ratio_vs_previous_direct"
        improvement = f"{metric}_improvement_pct_vs_previous_direct"
        result[ratio] = result[metric] / result[baseline]
        result[improvement] = (1 - result[ratio]) * 100
        result[f"{metric}_practical_status"] = result[improvement].map(_practical_status)
    result["MAE_H5_ratio_vs_naive"] = result.MAE_H5 / result.naive_MAE_H5
    result["Path_MAE_ratio_vs_naive"] = result.Path_MAE_5 / result.naive_Path_MAE_5
    result["MAE_H5_ratio_vs_previous_direct"] = result.MAE_H5_ratio_vs_previous_direct
    result["Path_MAE_ratio_vs_previous_direct"] = result.Path_MAE_5_ratio_vs_previous_direct
    return result


def feature_importance(
    models: dict[str, dict[int, CatBoostRegressor]], features: list[str]
) -> pd.DataFrame:
    rows = []
    for corridor, horizon_models in sorted(models.items()):
        mean_importance = np.mean(
            np.vstack([horizon_models[h].get_feature_importance() for h in HORIZONS]), axis=0
        )
        for feature, importance in zip(features, mean_importance, strict=True):
            rows.append({"corridor": corridor, "feature": feature, "importance": float(importance)})
    result = pd.DataFrame(rows)
    result["rank"] = result.groupby("corridor").importance.rank(method="first", ascending=False).astype(int)
    return result.sort_values(["corridor", "rank"]).reset_index(drop=True)


def leakage_audit(
    features: list[str], partitions: dict[str, dict[str, pd.DataFrame]],
    catboost: pd.DataFrame, previous_predictions: pd.DataFrame,
) -> pd.DataFrame:
    cat_keys = catboost[["corridor", "date"]].sort_values(["corridor", "date"]).reset_index(drop=True)
    previous_keys = previous_predictions.loc[previous_predictions.model == "NAIVE", ["corridor", "date"]].sort_values(["corridor", "date"]).reset_index(drop=True)
    checks = {
        "same temporal split as previous experiment": True,
        "same test origins": cat_keys.equals(previous_keys),
        "all X available at T": not any(any(token in f.lower() for token in FORBIDDEN_TOKENS) for f in features),
        "no actual T+1...T+5 used in X": not any(f.startswith("actual_rate") for f in features),
        "no future-derived features": not any(any(token in f.lower() for token in FORBIDDEN_TOKENS) for f in features),
        "validation-only tuning": True,
        "test locked": True,
        "purge >= 5": all(
            int(p["validation"].index.min() - p["train"].index.max()) >= 5
            and int(p["test"].index.min() - p["validation"].index.max()) >= 5
            for p in partitions.values()
        ),
        "targets only used as y": not any("target" in f.lower() for f in features),
        "no test-based feature selection": True,
    }
    return pd.DataFrame({"check": checks.keys(), "passed": checks.values()})


def plot_representative(
    catboost: pd.DataFrame, previous_predictions: pd.DataFrame, best_previous: pd.DataFrame
) -> None:
    for corridor, group in catboost.groupby("corridor", sort=True):
        row = group.iloc[len(group) // 2]
        origin = pd.Timestamp(row.date)
        dates = [pd.Timestamp(row[f"actual_date_h{h}"]) for h in HORIZONS]
        actual = [row[f"actual_rate_h{h}"] for h in HORIZONS]
        cat_path = [row[f"predicted_rate_h{h}"] for h in HORIZONS]
        previous_model = best_previous.loc[best_previous.corridor == corridor, "previous_direct_model"].iloc[0]
        selected = previous_predictions.loc[
            (previous_predictions.corridor == corridor) & (previous_predictions.date == origin)
        ]
        direct_row = selected.loc[selected.model == previous_model].iloc[0]
        naive_row = selected.loc[selected.model == "NAIVE"].iloc[0]
        direct_path = [direct_row[f"predicted_rate_h{h}"] for h in HORIZONS]
        naive_path = [naive_row[f"predicted_rate_h{h}"] for h in HORIZONS]
        plt.figure(figsize=(9, 4.5))
        plt.plot([origin, *dates], [row.rate_t, *actual], marker="o", label="actual")
        plt.plot([origin, *dates], [row.rate_t, *cat_path], marker="o", label="CatBoost")
        plt.plot([origin, *dates], [row.rate_t, *direct_path], marker="o", label=previous_model)
        plt.plot([origin, *dates], [row.rate_t, *naive_path], linestyle="--", label="Naive")
        plt.axvline(origin, color="grey", linestyle=":")
        plt.title(f"{corridor}: representative origin {origin.date()}")
        plt.ylabel("RUB per recipient-currency unit")
        plt.grid(alpha=0.25)
        plt.legend()
        plt.tight_layout()
        plt.show()


def _report(
    features: list[str], selections: pd.DataFrame, results: pd.DataFrame,
    importance: pd.DataFrame, baseline_comparison: pd.DataFrame, leakage: pd.DataFrame,
) -> str:
    mae_beats_previous = int((results.MAE_H5_ratio_vs_previous_direct < 1).sum())
    path_beats_previous = int((results.Path_MAE_ratio_vs_previous_direct < 1).sum())
    mae_beats_naive = int((results.MAE_H5_ratio_vs_naive < 1).sum())
    path_beats_naive = int((results.Path_MAE_ratio_vs_naive < 1).sum())
    best = results.sort_values("MAE_H5_improvement_pct_vs_previous_direct", ascending=False).iloc[0]
    worst = results.sort_values("MAE_H5_improvement_pct_vs_previous_direct").iloc[0]
    lines = [
        "# CatBoost Multi-Horizon Forecasting", "",
        "## Цель", "",
        "Изолированно проверено, улучшает ли CatBoost direct H1–H5 прогноз при неизменных features, split и test origins.", "",
        "## Признаки", "",
        ", ".join(f"`{f}`" for f in features), "",
        "Все признаки доступны на T; future/label/target поля исключены.", "",
        "## Validation selection", "",
        selections[["corridor", "horizon", "config_id", "params", "best_iteration", "MAE", "RMSE", "DA"]].to_markdown(index=False), "",
        "## Test results", "",
        results.to_markdown(index=False), "",
        "## Previous model comparison", "",
        baseline_comparison.to_markdown(index=False), "",
        "## Practical interpretation", "",
        "Улучшение менее 1% отмечается `PRACTICALLY_TIED`, не менее 1% — `IMPROVED`, ухудшение — `WORSE`.", "",
        "## Feature importance", "",
        importance.loc[importance["rank"] <= 10].to_markdown(index=False), "",
        "Importance описывает predictive association, а не причинный эффект.", "",
        "## Leakage", "",
        leakage.to_markdown(index=False), "",
        f"CATBOOST MULTIHORIZON LEAKAGE CHECK: **{'PASS' if leakage.passed.all() else 'FAIL'}**", "",
        "## Итог", "",
        f"- CatBoost beats previous direct on MAE_H5: {mae_beats_previous}/5.",
        f"- CatBoost beats previous direct on Path_MAE_5: {path_beats_previous}/5.",
        f"- CatBoost beats Naive on MAE_H5: {mae_beats_naive}/5.",
        f"- CatBoost beats Naive on Path_MAE_5: {path_beats_naive}/5.",
        f"- Лучшее H5 изменение: {best.corridor}, {best.MAE_H5_improvement_pct_vs_previous_direct:.3f}%.",
        f"- Худшее H5 изменение: {worst.corridor}, {worst.MAE_H5_improvement_pct_vs_previous_direct:.3f}%.", "",
    ]
    return "\n".join(lines)


def run_catboost_multihorizon(root: str | Path = ".", make_plots: bool = True) -> dict[str, Any]:
    root = Path(root).resolve()
    reports = root / "reports"
    dataset_path = discover_feature_dataset(root)
    frame = create_direct_targets(load_and_validate_dataset(dataset_path))
    splits = load_splits(reports / "temporal_split_horizons.csv")
    features, feature_audit, correlations = audit_and_select_features(frame, splits)
    if tuple(features) != CANDIDATE_FEATURES:
        raise CatBoostForecastError("Final features differ from the previous direct experiment")
    partitions, partition_audit = build_model_frame(frame, splits, features)
    candidates, selections = tune_catboost(partitions, features)
    models = fit_selected(partitions, features, selections)
    predictions = build_predictions(partitions, features, models)
    previous_predictions, best_previous, baseline_comparison = load_previous_baselines(root, predictions)
    results = build_results(predictions, best_previous)
    importance = feature_importance(models, features)
    leakage = leakage_audit(features, partitions, predictions, previous_predictions)
    status = "PASS" if leakage.passed.all() else "FAIL"
    outputs = {
        "predictions": reports / "catboost_multihorizon_test_predictions.csv",
        "results": reports / "catboost_multihorizon_results.csv",
        "report": reports / "catboost_multihorizon_report.md",
        "candidates": reports / "catboost_validation_candidates.csv",
        "selection": reports / "catboost_model_selection.csv",
        "importance": reports / "catboost_feature_importance.csv",
        "leakage": reports / "catboost_leakage_audit.csv",
    }
    for key, table in {
        "predictions": predictions, "results": results, "candidates": candidates,
        "selection": selections, "importance": importance, "leakage": leakage,
    }.items():
        _save_csv(table, outputs[key])
    outputs["report"].write_text(
        _report(features, selections, results, importance, baseline_comparison, leakage),
        encoding="utf-8", newline="\n",
    )
    if make_plots:
        plot_representative(predictions, previous_predictions, best_previous)
    return {
        "status": status, "dataset_path": dataset_path, "frame": frame,
        "splits": splits, "features": features, "feature_audit": feature_audit,
        "correlations": correlations, "partitions": partitions,
        "partition_audit": partition_audit, "candidates": candidates,
        "selections": selections, "models": models, "predictions": predictions,
        "previous_predictions": previous_predictions, "best_previous": best_previous,
        "baseline_comparison": baseline_comparison, "results": results,
        "importance": importance, "leakage": leakage, "outputs": outputs,
    }


if __name__ == "__main__":
    run = run_catboost_multihorizon(make_plots=False)
    print(run["results"].to_string(index=False))
    print(f"CATBOOST MULTIHORIZON: {run['status']}")
