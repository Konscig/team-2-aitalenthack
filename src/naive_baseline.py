"""Leakage-safe multi-horizon Naive Random Walk baseline for Stage 3.

For every eligible origin T and horizon H, the forecast is the rate observed at T.
Horizons count quote observations, not calendar days. No ARIMA model is trained.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import Markdown, display

PREDICTION_COLUMNS = [
    "forecast_origin_date",
    "target_date",
    "corridor",
    "horizon",
    "is_evaluation_horizon",
    "is_primary_horizon",
    "actual_rate",
    "predicted_rate",
    "actual_return",
    "predicted_return",
]
RESULT_COLUMNS = [
    "corridor",
    "model",
    "horizon",
    "is_primary_horizon",
    "MAE",
    "RMSE",
    "directional_accuracy",
    "normalized_MAE",
    "Path_MAE_H",
    "Future_Best_MAE_H",
    "Regret_MAE_H",
    "n_forecasts",
]
FORECAST_HORIZONS = (1, 3, 5, 10)
PRIMARY_PRODUCT_HORIZON = 5
MAX_FORECAST_HORIZON = max(FORECAST_HORIZONS)
FORECAST_PATH_STEPS = tuple(range(1, MAX_FORECAST_HORIZON + 1))
PATH_METRIC_HORIZONS = (5, 10)


def build_naive_predictions(
    frame: pd.DataFrame,
    split_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Build multi-step forecasts from origins with complete T+10 actuals."""
    required = {"date", "corridor", "rate", "log_ret_1"}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing columns: {sorted(missing)}")
    split_required = {
        "corridor",
        "test_origin_start",
        "test_origin_end",
        "n_test_origins",
        "max_horizon",
    }
    if missing := split_required.difference(split_summary.columns):
        raise ValueError(f"Missing split columns: {sorted(missing)}")

    source = frame.copy()
    source["date"] = pd.to_datetime(source["date"], errors="raise")
    source = source.sort_values(["corridor", "date"]).reset_index(drop=True)
    if source.duplicated(["corridor", "date"]).any():
        raise ValueError("Duplicate corridor/date rows are not allowed")
    predictions = []
    for split in split_summary.itertuples(index=False):
        if int(split.max_horizon) != MAX_FORECAST_HORIZON:
            raise AssertionError(f"Unexpected max horizon for {split.corridor}")
        corridor = (
            source.loc[source["corridor"] == split.corridor]
            .sort_values("date")
            .reset_index(drop=True)
        )
        origin_mask = corridor["date"].between(
            pd.Timestamp(split.test_origin_start),
            pd.Timestamp(split.test_origin_end),
        )
        origin_positions = corridor.index[origin_mask].to_numpy()
        if len(origin_positions) != int(split.n_test_origins):
            raise AssertionError(
                f"{split.corridor}: expected {split.n_test_origins} origins, "
                f"got {len(origin_positions)}"
            )
        if origin_positions.max() + MAX_FORECAST_HORIZON >= len(corridor):
            raise AssertionError(f"Right-censored origin included for {split.corridor}")

        for origin_position in origin_positions:
            origin = corridor.iloc[origin_position]
            for horizon in FORECAST_PATH_STEPS:
                target = corridor.iloc[origin_position + horizon]
                predictions.append(
                    {
                        "forecast_origin_date": origin["date"],
                        "target_date": target["date"],
                        "corridor": split.corridor,
                        "horizon": horizon,
                        "is_evaluation_horizon": horizon in FORECAST_HORIZONS,
                        "is_primary_horizon": horizon == PRIMARY_PRODUCT_HORIZON,
                        "actual_rate": float(target["rate"]),
                        "predicted_rate": float(origin["rate"]),
                        "actual_return": float(np.log(target["rate"] / origin["rate"])),
                        "predicted_return": 0.0,
                    }
                )

    output = pd.DataFrame(predictions)
    return output.sort_values(
        ["corridor", "horizon", "forecast_origin_date"]
    ).reset_index(drop=True)[
        PREDICTION_COLUMNS
    ]


def calculate_path_metrics(
    predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate per-origin path and future-best errors for H=5 and H=10."""
    rows = []
    group_columns = ["corridor", "forecast_origin_date"]
    for (corridor, origin_date), origin_path in predictions.groupby(
        group_columns, sort=True
    ):
        ordered = origin_path.sort_values("horizon")
        if tuple(ordered["horizon"]) != FORECAST_PATH_STEPS:
            raise AssertionError(f"Incomplete forecast path for {corridor} at {origin_date}")
        for horizon in PATH_METRIC_HORIZONS:
            path = ordered.loc[ordered["horizon"] <= horizon]
            actual_future_best = float(path["actual_rate"].min())
            predicted_future_best = float(path["predicted_rate"].min())
            origin_rate = float(path["predicted_rate"].iloc[0])
            actual_regret = max(
                0.0, (origin_rate - actual_future_best) / origin_rate
            )
            predicted_regret = max(
                0.0, (origin_rate - predicted_future_best) / origin_rate
            )
            rows.append(
                {
                    "forecast_origin_date": origin_date,
                    "corridor": corridor,
                    "horizon": horizon,
                    "Path_MAE_H": float(
                        (path["actual_rate"] - path["predicted_rate"]).abs().mean()
                    ),
                    "Actual_Future_Best_H": actual_future_best,
                    "Predicted_Future_Best_H": predicted_future_best,
                    "Future_Best_Absolute_Error_H": abs(
                        actual_future_best - predicted_future_best
                    ),
                    "Actual_Regret_H": actual_regret,
                    "Predicted_Regret_H": predicted_regret,
                    "Regret_Absolute_Error_H": abs(
                        actual_regret - predicted_regret
                    ),
                }
            )
    details = pd.DataFrame(rows)
    summary = (
        details.groupby(["corridor", "horizon"], as_index=False)
        .agg(
            Path_MAE_H=("Path_MAE_H", "mean"),
            Future_Best_MAE_H=("Future_Best_Absolute_Error_H", "mean"),
            Regret_MAE_H=("Regret_Absolute_Error_H", "mean"),
            n_paths=("forecast_origin_date", "nunique"),
        )
    )
    return details, summary


def calculate_naive_metrics(
    predictions: pd.DataFrame,
    path_summary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calculate rate-space metrics with a shared zero-direction convention."""
    rows = []
    endpoints = predictions.loc[predictions["is_evaluation_horizon"]]
    for (corridor, horizon), group in endpoints.groupby(
        ["corridor", "horizon"], sort=True
    ):
        error = group["actual_rate"] - group["predicted_rate"]
        actual_direction = np.sign(group["actual_return"].to_numpy())
        predicted_direction = np.sign(group["predicted_return"].to_numpy())
        direction_correct = actual_direction == predicted_direction
        rows.append(
            {
                "corridor": corridor,
                "model": "NAIVE",
                "horizon": int(horizon),
                "is_primary_horizon": horizon == PRIMARY_PRODUCT_HORIZON,
                "MAE": float(error.abs().mean()),
                "RMSE": float(np.sqrt(np.mean(np.square(error)))),
                "directional_accuracy": float(direction_correct.mean()),
                "normalized_MAE": float(
                    (error.abs() / group["actual_rate"]).mean()
                ),
                "Path_MAE_H": np.nan,
                "Future_Best_MAE_H": np.nan,
                "Regret_MAE_H": np.nan,
                "n_forecasts": int(len(group)),
            }
        )
    result = pd.DataFrame(rows)
    if path_summary is None:
        _, path_summary = calculate_path_metrics(predictions)
    for path_row in path_summary.itertuples(index=False):
        mask = (result["corridor"] == path_row.corridor) & (
            result["horizon"] == path_row.horizon
        )
        result.loc[mask, "Path_MAE_H"] = path_row.Path_MAE_H
        result.loc[mask, "Future_Best_MAE_H"] = path_row.Future_Best_MAE_H
        result.loc[mask, "Regret_MAE_H"] = path_row.Regret_MAE_H
    return result[RESULT_COLUMNS]


def _plot_predictions(predictions: pd.DataFrame) -> None:
    display(Markdown("## 7. Primary H=5 actual rate vs Naive prediction"))
    for corridor, group in predictions.groupby("corridor", sort=True):
        ordered = (
            group.loc[group["horizon"] == PRIMARY_PRODUCT_HORIZON]
            .sort_values("forecast_origin_date")
            .reset_index(drop=True)
        )
        zoom_width = min(60, len(ordered))
        zoom_start = (len(ordered) - zoom_width) // 2
        zoom = ordered.iloc[zoom_start : zoom_start + zoom_width]
        fig, axes = plt.subplots(2, 1, figsize=(14, 8))
        axes[0].plot(
            ordered["target_date"], ordered["actual_rate"], label="actual", linewidth=1
        )
        axes[0].plot(
            ordered["target_date"],
            ordered["predicted_rate"],
            label="naive prediction",
            linewidth=1,
            alpha=0.85,
        )
        axes[0].set_title(f"{corridor}: locked test origins, primary H=5")
        axes[1].plot(
            zoom["target_date"], zoom["actual_rate"], label="actual", marker="."
        )
        axes[1].plot(
            zoom["target_date"],
            zoom["predicted_rate"],
            label="naive prediction",
            marker=".",
        )
        axes[1].set_title(
            f"Representative middle {zoom_width}-observation interval"
        )
        for axis in axes:
            axis.set_ylabel("RUB / currency unit")
            axis.grid(alpha=0.25)
            axis.legend()
        axes[1].set_xlabel("Quote date")
        plt.tight_layout()
        plt.show()
        display(
            Markdown(
                f"**{corridor}.** Для primary `H=5` Naive переносит rate из origin T "
                "на target T+5. Zoom выбран детерминированно из середины допустимых "
                "test origins, без поиска наиболее удачного интервала."
            )
        )


def _save_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _build_wide_results(metrics: pd.DataFrame) -> pd.DataFrame:
    """Expose explicitly named MAE_H/RMSE_H/direction and path metrics."""
    rows = []
    for corridor, group in metrics.groupby("corridor", sort=True):
        row: dict[str, object] = {"corridor": corridor, "model": "NAIVE"}
        for metric in group.itertuples(index=False):
            horizon = int(metric.horizon)
            row[f"MAE_{horizon}"] = metric.MAE
            row[f"RMSE_{horizon}"] = metric.RMSE
            row[f"Directional_Accuracy_{horizon}"] = metric.directional_accuracy
            row[f"Normalized_MAE_{horizon}"] = metric.normalized_MAE
            row[f"n_forecasts_{horizon}"] = metric.n_forecasts
            if horizon in PATH_METRIC_HORIZONS:
                row[f"Path_MAE_{horizon}"] = metric.Path_MAE_H
                row[f"Future_Best_MAE_{horizon}"] = metric.Future_Best_MAE_H
                row[f"Regret_MAE_{horizon}"] = metric.Regret_MAE_H
        rows.append(row)
    return pd.DataFrame(rows)


def run_stage3(
    root: str | Path,
    split_summary: pd.DataFrame,
) -> dict[str, object]:
    """Execute and display Stage 3 without fitting any ARIMA model."""
    root = Path(root).resolve()
    dataset_path = root / "data" / "features" / "fx_features_daily.parquet"
    results_path = root / "reports" / "naive_results.csv"
    predictions_path = root / "reports" / "naive_predictions.csv"
    path_results_path = root / "reports" / "naive_path_results.csv"
    future_best_path = root / "reports" / "naive_future_best_predictions.csv"
    wide_results_path = root / "reports" / "naive_results_wide.csv"
    frame = pd.read_parquet(dataset_path)

    display(Markdown("# STAGE 3 — NAIVE BASELINE"))
    display(
        Markdown(
            "## 1–2. Model definition и walk-forward\n\n"
            "Для каждого origin строится полный путь: `P_hat_(T+1)=...="
            "P_hat_(T+10)=P_T`. Endpoint-метрики считаются на quote-observation "
            "horizons `H=[1,3,5,10]`, где `H=5` — PRIMARY PRODUCT HORIZON. "
            "Predicted cumulative log return равен 0. Используются только origins, "
            "для которых известны все actual values до T+10."
        )
    )
    predictions = build_naive_predictions(frame, split_summary)
    display(predictions.head(10))

    display(Markdown("## 3–6. Endpoint, path и future-best metrics"))
    display(
        Markdown(
            "`MAE` и `RMSE` считаются в единицах rate. `normalized_MAE` — "
            "дополнительная относительная метрика и не заменяет основные. Для всех "
            "моделей используется единое правило направления: прогноз корректен, "
            "когда знаки actual и predicted return совпадают, включая случай, когда "
            "оба равны нулю. Если predicted return равен 0, а actual return не равен "
            "0, направление считается неверным."
        )
    )
    future_best_details, path_summary = calculate_path_metrics(predictions)
    metrics = calculate_naive_metrics(predictions, path_summary)
    wide_results = _build_wide_results(metrics)
    display(metrics)
    display(Markdown("**Wide result table с явными именами метрик по H:**"))
    display(wide_results)
    display(
        Markdown(
            "Для `H=5/10`: `Path_MAE_H` усредняет абсолютную ошибку по всем шагам "
            "пути `T+1...T+H`. `Actual_Future_Best_H` — минимальный фактический rate "
            "на этом пути, `Predicted_Future_Best_H` — минимум forecast path; у Naive "
            "он равен `P_T`. `Future_Best_MAE_H` — средняя абсолютная ошибка между "
            "этими минимумами по forecast origins. `Regret_MAE_H` сравнивает actual "
            "и predicted относительную выгоду ожидания; future используется только "
            "как evaluation target."
        )
    )
    display(path_summary)
    display(future_best_details.head(10))
    primary_metrics = metrics.loc[metrics["is_primary_horizon"]].copy()
    product_horizon_metrics = metrics.loc[metrics["horizon"].isin([5, 10])].copy()
    display(
        Markdown(
            "**Product-selection view:** будущие `p,d,q` сравниваются прежде всего "
            "с этим Naive на `H=5`, а `H=10` используется как обязательный "
            "long-horizon guardrail. Хороший результат только на `H=1` не считается "
            "победой в model tournament."
        )
    )
    display(product_horizon_metrics)
    macro = primary_metrics[
        ["MAE", "RMSE", "directional_accuracy", "normalized_MAE"]
    ].mean()
    weighted_normalized_mae = np.average(
        primary_metrics["normalized_MAE"], weights=primary_metrics["n_forecasts"]
    )
    display(Markdown("**Primary H=5 macro average по пяти коридорам:**"))
    display(macro.to_frame("macro_average").T)
    display(
        Markdown(
            f"Weighted normalized MAE: `{weighted_normalized_mae:.8f}`. "
            "При одинаковом числе прогнозов он совпадает с macro normalized MAE."
        )
    )
    _plot_predictions(predictions)

    _save_csv(predictions, predictions_path)
    _save_csv(metrics, results_path)
    _save_csv(path_summary, path_results_path)
    _save_csv(future_best_details, future_best_path)
    _save_csv(wide_results, wide_results_path)
    checks = {
        "prediction_schema_exact": list(predictions.columns) == PREDICTION_COLUMNS,
        "result_schema_exact": list(metrics.columns) == RESULT_COLUMNS,
        "all_corridors_present": metrics["corridor"].nunique()
        == frame["corridor"].nunique()
        == 5,
        "all_horizons_present": set(metrics["horizon"]) == set(FORECAST_HORIZONS),
        "full_paths_present": set(predictions["horizon"])
        == set(FORECAST_PATH_STEPS),
        "primary_horizon_fixed": set(
            metrics.loc[metrics["is_primary_horizon"], "horizon"]
        )
        == {PRIMARY_PRODUCT_HORIZON},
        "forecast_counts_match_split": metrics["n_forecasts"].sum()
        == split_summary["n_test_origins"].sum() * len(FORECAST_HORIZONS),
        "common_origin_count_per_horizon": (
            metrics["n_forecasts"] == split_summary["n_test_origins"].iloc[0]
        ).all(),
        "predicted_returns_zero": (predictions["predicted_return"] == 0).all(),
        "naive_paths_constant": predictions.groupby(
            ["corridor", "forecast_origin_date"]
        )["predicted_rate"].nunique().eq(1).all(),
        "path_metrics_only_h5_h10": set(path_summary["horizon"])
        == set(PATH_METRIC_HORIZONS),
        "wide_metrics_complete": len(wide_results) == 5
        and all(
            f"MAE_{horizon}" in wide_results
            and f"RMSE_{horizon}" in wide_results
            and f"Directional_Accuracy_{horizon}" in wide_results
            for horizon in FORECAST_HORIZONS
        )
        and all(
            f"Path_MAE_{horizon}" in wide_results
            and f"Future_Best_MAE_{horizon}" in wide_results
            and f"Regret_MAE_{horizon}" in wide_results
            for horizon in PATH_METRIC_HORIZONS
        ),
        "future_best_formula_valid": np.allclose(
            future_best_details["Future_Best_Absolute_Error_H"],
            (
                future_best_details["Actual_Future_Best_H"]
                - future_best_details["Predicted_Future_Best_H"]
            ).abs(),
        ),
        "regret_formula_valid": np.allclose(
            future_best_details["Regret_Absolute_Error_H"],
            (
                future_best_details["Actual_Regret_H"]
                - future_best_details["Predicted_Regret_H"]
            ).abs(),
        ),
        "rates_positive": (
            predictions[["actual_rate", "predicted_rate"]] > 0
        ).all().all(),
        "metrics_finite": np.isfinite(
            metrics[["MAE", "RMSE", "directional_accuracy", "normalized_MAE"]]
        ).all().all(),
        "files_saved": results_path.exists()
        and predictions_path.exists()
        and path_results_path.exists()
        and future_best_path.exists()
        and wide_results_path.exists(),
        "arima_models_trained": 0,
    }
    passed = all(
        bool(value) for key, value in checks.items() if key != "arima_models_trained"
    ) and checks["arima_models_trained"] == 0
    display(Markdown(f"# STAGE 3 — NAIVE BASELINE: {'PASS' if passed else 'FAIL'}"))
    display(metrics)
    print(f"Results: {results_path.relative_to(root).as_posix()}")
    print(f"Predictions: {predictions_path.relative_to(root).as_posix()}")
    print(f"Path metrics: {path_results_path.relative_to(root).as_posix()}")
    print(f"Future best: {future_best_path.relative_to(root).as_posix()}")
    print(f"Wide results: {wide_results_path.relative_to(root).as_posix()}")
    print("ARIMA models trained: 0")
    if not passed:
        raise AssertionError(f"Stage 3 checks failed: {checks}")
    return {
        "predictions": predictions,
        "metrics": metrics,
        "path_summary": path_summary,
        "future_best_details": future_best_details,
        "wide_results": wide_results,
        "macro_metrics": macro,
        "primary_metrics": primary_metrics,
        "product_horizon_metrics": product_horizon_metrics,
        "checks": checks,
    }
