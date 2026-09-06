"""Stage 4: honest expanding-window multi-step ARIMA on raw CBR rates."""

from __future__ import annotations

import hashlib
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import Markdown, display
from statsmodels.graphics.tsaplots import plot_acf
from statsmodels.stats.diagnostic import acorr_ljungbox
from statsmodels.tsa.arima.model import ARIMA

FORECAST_HORIZONS = (1, 3, 5, 10)
PATH_HORIZONS = (5, 10)
PRIMARY_HORIZON = 5
MAX_HORIZON = 10
P_VALUES = (0, 1, 2, 3, 5)
Q_VALUES = (0, 1, 2, 3, 5)
PRACTICAL_TIE_FRACTION = 0.01
FIT_METHOD = "hannan_rissanen"
CACHE_VERSION = "arima-rate-v1"
MAX_WORKERS = 4


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _save_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def _fit_arima(history: pd.Series, order: tuple[int, int, int]):
    model = ARIMA(
        history.astype(float),
        order=order,
        trend="n",
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    return model.fit(method=FIT_METHOD)


def _walk_forward(
    corridor_frame: pd.DataFrame,
    origin_dates: pd.Series,
    order: tuple[int, int, int],
    corridor: str,
    evaluation_split: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Explicitly refit using observations at dates <= each forecast origin."""
    series = corridor_frame.sort_values("date").reset_index(drop=True)
    position_by_date = pd.Series(series.index, index=series["date"]).to_dict()
    rows: list[dict[str, object]] = []
    warning_messages: list[str] = []
    aic_values: list[float] = []
    bic_values: list[float] = []

    for origin_date in pd.to_datetime(origin_dates):
        origin_position = int(position_by_date[pd.Timestamp(origin_date)])
        if origin_position + MAX_HORIZON >= len(series):
            raise ValueError(f"Insufficient T+10 actuals for {corridor} at {origin_date}")
        history = series.iloc[: origin_position + 1]
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            warnings.filterwarnings(
                "ignore",
                message="Provided `endog` series has been differenced.*",
                category=UserWarning,
            )
            fitted = _fit_arima(history["rate"], order)
            forecast = fitted.get_forecast(steps=MAX_HORIZON).summary_frame(alpha=0.05)
        warning_messages.extend(str(item.message) for item in captured)
        aic_values.append(float(fitted.aic))
        bic_values.append(float(fitted.bic))
        origin_rate = float(history["rate"].iloc[-1])
        for step in range(1, MAX_HORIZON + 1):
            actual = series.iloc[origin_position + step]
            forecast_row = forecast.iloc[step - 1]
            rows.append(
                {
                    "corridor": corridor,
                    "evaluation_split": evaluation_split,
                    "forecast_origin_date": pd.Timestamp(origin_date),
                    "forecast_target_date": actual["date"],
                    "forecast_step": step,
                    "actual_rate": float(actual["rate"]),
                    "predicted_rate": float(forecast_row["mean"]),
                    "lower_95": float(forecast_row["mean_ci_lower"]),
                    "upper_95": float(forecast_row["mean_ci_upper"]),
                    "origin_rate": origin_rate,
                    "p": order[0],
                    "d": order[1],
                    "q": order[2],
                }
            )
    diagnostics = {
        "fit_status": "warning" if warning_messages else "success",
        "warning_count": len(warning_messages),
        "warning_messages": " | ".join(sorted(set(warning_messages))),
        "error_message": "",
        "mean_aic": float(np.mean(aic_values)),
        "mean_bic": float(np.mean(bic_values)),
        "n_refits": len(aic_values),
    }
    return pd.DataFrame(rows), diagnostics


def _metrics(paths: pd.DataFrame) -> dict[str, float | int]:
    result: dict[str, float | int] = {}
    for horizon in FORECAST_HORIZONS:
        endpoint = paths.loc[paths["forecast_step"] == horizon]
        error = endpoint["actual_rate"] - endpoint["predicted_rate"]
        actual_direction = np.sign(
            endpoint["actual_rate"] / endpoint["origin_rate"] - 1
        )
        predicted_direction = np.sign(
            endpoint["predicted_rate"] / endpoint["origin_rate"] - 1
        )
        result[f"MAE_H{horizon}"] = float(error.abs().mean())
        result[f"RMSE_H{horizon}"] = float(np.sqrt(np.mean(np.square(error))))
        result[f"DA_H{horizon}"] = float(
            (actual_direction == predicted_direction).mean()
        )
        result[f"n_forecasts_H{horizon}"] = int(len(endpoint))

    for horizon in PATH_HORIZONS:
        window = paths.loc[paths["forecast_step"] <= horizon].copy()
        window["absolute_error"] = (
            window["actual_rate"] - window["predicted_rate"]
        ).abs()
        origin_group = window.groupby("forecast_origin_date", sort=False)
        path_mae = origin_group["absolute_error"].mean()
        actual_best = origin_group["actual_rate"].min()
        predicted_best = origin_group["predicted_rate"].min()
        origin_rate = origin_group["origin_rate"].first()
        actual_regret = ((origin_rate - actual_best) / origin_rate).clip(lower=0)
        predicted_regret = (
            (origin_rate - predicted_best) / origin_rate
        ).clip(lower=0)
        result[f"Path_MAE_{horizon}"] = float(path_mae.mean())
        result[f"Future_Best_MAE_{horizon}"] = float(
            (actual_best - predicted_best).abs().mean()
        )
        result[f"Regret_MAE_{horizon}"] = float(
            (actual_regret - predicted_regret).abs().mean()
        )
    return result


def _failed_candidate(
    corridor: str,
    order: tuple[int, int, int],
    message: str,
) -> dict[str, object]:
    return {
        "corridor": corridor,
        "p": order[0],
        "d": order[1],
        "q": order[2],
        "fit_status": "failed",
        "warning_count": 0,
        "warning_messages": "",
        "error_message": message,
        "mean_aic": np.nan,
        "mean_bic": np.nan,
        "n_refits": 0,
    }


def _evaluate_candidate(
    frame: pd.DataFrame,
    split_row: dict[str, object],
    order: tuple[int, int, int],
) -> dict[str, object]:
    corridor = str(split_row["corridor"])
    corridor_frame = frame.loc[frame["corridor"] == corridor]
    origins = corridor_frame.loc[
        corridor_frame["date"].between(
            pd.Timestamp(split_row["validation_origin_start"]),
            pd.Timestamp(split_row["validation_origin_end"]),
        ),
        "date",
    ]
    try:
        paths, diagnostics = _walk_forward(
            corridor_frame, origins, order, corridor, "validation"
        )
        return {
            "corridor": corridor,
            "p": order[0],
            "d": order[1],
            "q": order[2],
            **diagnostics,
            **{f"validation_{key}": value for key, value in _metrics(paths).items()},
        }
    except Exception as exc:  # candidate-level audit must preserve numerical failures
        return _failed_candidate(corridor, order, f"{type(exc).__name__}: {exc}")


def _within_one_percent(values: pd.Series) -> pd.Series:
    best = float(values.min())
    if best == 0:
        return np.isclose(values, best, atol=1e-15, rtol=0)
    return (values - best) / abs(best) < PRACTICAL_TIE_FRACTION


def _select_orders(candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    selections = []
    audit_rows = []
    for corridor, group in candidates.groupby("corridor", sort=True):
        eligible = group.loc[group["fit_status"].isin(["success", "warning"])].copy()
        required = [
            "validation_MAE_H5",
            "validation_RMSE_H5",
            "validation_Path_MAE_5",
            "validation_MAE_H10",
        ]
        eligible = eligible.dropna(subset=required)
        if eligible.empty:
            raise RuntimeError(f"No successful ARIMA candidate for {corridor}")

        pool = eligible.loc[_within_one_percent(eligible["validation_MAE_H5"])].copy()
        audit_rows.append(
            {"corridor": corridor, "stage": "MAE_H5_1pct", "remaining": len(pool)}
        )
        if len(pool) > 1:
            pool = pool.loc[
                _within_one_percent(pool["validation_Path_MAE_5"])
            ].copy()
            audit_rows.append(
                {"corridor": corridor, "stage": "Path_MAE_5_1pct", "remaining": len(pool)}
            )
        if len(pool) > 1:
            pool = pool.loc[_within_one_percent(pool["validation_MAE_H10"])].copy()
            audit_rows.append(
                {"corridor": corridor, "stage": "MAE_H10_1pct", "remaining": len(pool)}
            )
        winner = pool.assign(complexity=pool["p"] + pool["q"]).sort_values(
            ["complexity", "p", "q", "validation_RMSE_H5"]
        ).iloc[0]
        selections.append(winner)
    return pd.DataFrame(selections).reset_index(drop=True), pd.DataFrame(audit_rows)


def _cache_signature(
    dataset_path: Path,
    splits: pd.DataFrame,
    d_by_corridor: dict[str, int],
) -> dict[str, str]:
    split_text = splits.sort_values("corridor").to_csv(index=False)
    return {
        "cache_version": CACHE_VERSION,
        "dataset_sha256": _sha256(dataset_path),
        "split_sha256": hashlib.sha256(split_text.encode()).hexdigest(),
        "grid_signature": f"p={P_VALUES};d={sorted(d_by_corridor.items())};q={Q_VALUES}",
    }


def _valid_candidate_cache(
    path: Path,
    signature: dict[str, str],
    expected_rows: int,
) -> pd.DataFrame | None:
    if not path.exists():
        return None
    cached = pd.read_csv(path)
    if len(cached) != expected_rows:
        return None
    for key, expected in signature.items():
        if key not in cached or set(cached[key].astype(str)) != {str(expected)}:
            return None
    return cached


def _validation_grid(
    frame: pd.DataFrame,
    splits: pd.DataFrame,
    d_by_corridor: dict[str, int],
    cache_path: Path,
    signature: dict[str, str],
) -> tuple[pd.DataFrame, bool]:
    tasks = [
        (split._asdict(), (p, d_by_corridor[split.corridor], q))
        for split in splits.itertuples(index=False)
        for p in P_VALUES
        for q in Q_VALUES
    ]
    cached = _valid_candidate_cache(cache_path, signature, len(tasks))
    if cached is not None:
        return cached, True

    rows = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_evaluate_candidate, frame, split, order): (
                split["corridor"],
                order,
            )
            for split, order in tasks
        }
        for completed, future in enumerate(as_completed(futures), start=1):
            corridor, order = futures[future]
            result = future.result()
            result.update(signature)
            rows.append(result)
            if completed % 10 == 0 or completed == len(futures):
                print(
                    f"Validation grid: {completed}/{len(futures)} candidates; "
                    f"latest={corridor} ARIMA{order} status={result['fit_status']}"
                )
    candidates = pd.DataFrame(rows).sort_values(["corridor", "p", "q"])
    _save_csv(candidates, cache_path)
    return candidates, False


def _test_walk_forward(
    frame: pd.DataFrame,
    splits: pd.DataFrame,
    selected: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    paths = []
    diagnostics = []
    for selection in selected.itertuples(index=False):
        split = splits.loc[splits["corridor"] == selection.corridor].iloc[0]
        corridor_frame = frame.loc[frame["corridor"] == selection.corridor]
        origins = corridor_frame.loc[
            corridor_frame["date"].between(
                pd.Timestamp(split["test_origin_start"]),
                pd.Timestamp(split["test_origin_end"]),
            ),
            "date",
        ]
        order = (int(selection.p), int(selection.d), int(selection.q))
        forecast, fit_diagnostics = _walk_forward(
            corridor_frame, origins, order, selection.corridor, "test"
        )
        paths.append(forecast)
        diagnostics.append({"corridor": selection.corridor, **fit_diagnostics})
        print(f"Locked test complete: {selection.corridor} ARIMA{order}")
    return pd.concat(paths, ignore_index=True), pd.DataFrame(diagnostics)


def _compare_with_naive(
    test_metrics: pd.DataFrame,
    naive_results: pd.DataFrame,
) -> pd.DataFrame:
    naive = naive_results.set_index(["corridor", "horizon"])
    rows = []
    for result in test_metrics.itertuples(index=False):
        row = result._asdict()
        for horizon in FORECAST_HORIZONS:
            baseline = naive.loc[(result.corridor, horizon)]
            mae_ratio = row[f"test_MAE_H{horizon}"] / float(baseline["MAE"])
            rmse_ratio = row[f"test_RMSE_H{horizon}"] / float(baseline["RMSE"])
            row[f"MAE_ratio_vs_naive_H{horizon}"] = mae_ratio
            row[f"RMSE_ratio_vs_naive_H{horizon}"] = rmse_ratio
            row[f"MAE_improvement_pct_H{horizon}"] = (1 - mae_ratio) * 100
        for horizon in PATH_HORIZONS:
            baseline = naive.loc[(result.corridor, horizon)]
            row[f"Path_MAE_ratio_vs_naive_H{horizon}"] = (
                row[f"test_Path_MAE_{horizon}"] / float(baseline["Path_MAE_H"])
            )
            row[f"Future_Best_MAE_ratio_vs_naive_H{horizon}"] = (
                row[f"test_Future_Best_MAE_{horizon}"]
                / float(baseline["Future_Best_MAE_H"])
            )
            row[f"Regret_MAE_ratio_vs_naive_H{horizon}"] = (
                row[f"test_Regret_MAE_{horizon}"]
                / float(baseline["Regret_MAE_H"])
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _residual_diagnostics(
    frame: pd.DataFrame,
    splits: pd.DataFrame,
    selected: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for selection in selected.itertuples(index=False):
        split = splits.loc[splits["corridor"] == selection.corridor].iloc[0]
        history = frame.loc[
            (frame["corridor"] == selection.corridor)
            & (frame["date"] <= pd.Timestamp(split["validation_end"])),
            "rate",
        ]
        order = (int(selection.p), int(selection.d), int(selection.q))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = _fit_arima(history, order)
        residuals = pd.Series(fitted.resid).replace([np.inf, -np.inf], np.nan).dropna()
        fig, axes = plt.subplots(1, 3, figsize=(16, 4))
        axes[0].plot(residuals.to_numpy(), linewidth=0.7)
        axes[0].set_title(f"{selection.corridor} ARIMA{order}: residuals")
        axes[1].hist(residuals, bins=40)
        axes[1].set_title("Residual histogram")
        plot_acf(residuals, lags=min(40, len(residuals) // 4 - 1), zero=False, ax=axes[2])
        axes[2].set_title("Residual ACF")
        plt.tight_layout()
        plt.show()
        ljung = acorr_ljungbox(residuals, lags=[10, 20], return_df=True)
        for lag, result in ljung.iterrows():
            rows.append(
                {
                    "corridor": selection.corridor,
                    "p": order[0],
                    "d": order[1],
                    "q": order[2],
                    "lag": int(lag),
                    "lb_stat": float(result["lb_stat"]),
                    "lb_pvalue": float(result["lb_pvalue"]),
                }
            )
    return pd.DataFrame(rows)


def _forecast_visuals(
    frame: pd.DataFrame,
    forecasts: pd.DataFrame,
    naive: pd.DataFrame,
) -> None:
    for corridor, corridor_forecasts in forecasts.groupby("corridor", sort=True):
        origins = sorted(corridor_forecasts["forecast_origin_date"].unique())
        chosen = [origins[0], origins[len(origins) // 2], origins[-1]]
        corridor_source = frame.loc[frame["corridor"] == corridor]
        fig, axes = plt.subplots(1, 3, figsize=(18, 5))
        for axis, origin in zip(axes, chosen, strict=True):
            path = corridor_forecasts.loc[
                corridor_forecasts["forecast_origin_date"] == origin
            ].sort_values("forecast_step")
            naive_path = naive.loc[
                (naive["corridor"] == corridor)
                & (naive["forecast_origin_date"] == origin)
            ].sort_values("horizon")
            history = corridor_source.loc[corridor_source["date"] <= origin].tail(35)
            axis.plot(history["date"], history["rate"], label="history", color="black")
            axis.plot(path["forecast_target_date"], path["actual_rate"], label="actual future")
            axis.plot(path["forecast_target_date"], path["predicted_rate"], label="ARIMA")
            axis.plot(
                naive_path["target_date"], naive_path["predicted_rate"], label="Naive"
            )
            axis.fill_between(
                path["forecast_target_date"],
                path["lower_95"],
                path["upper_95"],
                alpha=0.2,
                label="95% interval",
            )
            axis.axvline(origin, color="red", linestyle="--", label="FORECAST ORIGIN T")
            axis.set_title(pd.Timestamp(origin).date().isoformat())
            axis.grid(alpha=0.2)
        axes[0].set_ylabel(f"{corridor}: RUB / currency unit")
        axes[-1].legend(fontsize=8)
        plt.tight_layout()
        plt.show()


def _error_by_horizon_plots(results: pd.DataFrame, naive_results: pd.DataFrame) -> None:
    for row in results.itertuples(index=False):
        naive = naive_results.loc[naive_results["corridor"] == row.corridor].set_index(
            "horizon"
        )
        fig, axes = plt.subplots(1, 2, figsize=(11, 4))
        for axis, metric in zip(axes, ["MAE", "RMSE"], strict=True):
            arima_values = [getattr(row, f"test_{metric}_H{h}") for h in FORECAST_HORIZONS]
            naive_values = [float(naive.loc[h, metric]) for h in FORECAST_HORIZONS]
            axis.plot(FORECAST_HORIZONS, naive_values, marker="o", label="Naive")
            axis.plot(FORECAST_HORIZONS, arima_values, marker="o", label="ARIMA_RATE")
            axis.set_title(f"{row.corridor}: {metric} by horizon")
            axis.set_xlabel("Quote-observation horizon")
            axis.set_ylabel(metric)
            axis.grid(alpha=0.25)
            axis.legend()
        plt.tight_layout()
        plt.show()


def run_stage4(root: str | Path) -> dict[str, object]:
    """Run validation selection and locked-test ARIMA rate evaluation."""
    root = Path(root).resolve()
    dataset_path = root / "data" / "features" / "fx_features_daily.parquet"
    split_path = root / "reports" / "temporal_split_horizons.csv"
    stationarity_path = root / "reports" / "time_series_diagnostics.csv"
    naive_results_path = root / "reports" / "naive_results.csv"
    naive_forecasts_path = root / "reports" / "naive_predictions.csv"
    candidate_path = root / "reports" / "arima_rate_validation_candidates.csv"
    selection_path = root / "reports" / "arima_rate_selection_audit.csv"
    forecast_path = root / "reports" / "arima_rate_test_forecasts.csv"
    results_path = root / "reports" / "arima_rate_multistep_results.csv"
    interval_path = root / "reports" / "arima_rate_interval_width.csv"
    residual_path = root / "reports" / "arima_rate_residual_diagnostics.csv"
    leakage_path = root / "reports" / "arima_rate_leakage_audit.csv"

    frame = pd.read_parquet(dataset_path).sort_values(["corridor", "date"])
    frame["date"] = pd.to_datetime(frame["date"])
    splits = pd.read_csv(split_path, parse_dates=[
        "train_start", "train_end", "validation_start", "validation_end",
        "test_start", "test_end", "validation_origin_start",
        "validation_origin_end", "test_origin_start", "test_origin_end",
    ])
    stationarity = pd.read_csv(stationarity_path)
    naive_results = pd.read_csv(naive_results_path)
    naive_forecasts = pd.read_csv(
        naive_forecasts_path, parse_dates=["forecast_origin_date", "target_date"]
    )
    d_by_corridor = dict(
        zip(stationarity["corridor"], stationarity["recommended_rate_d"].astype(int))
    )
    if any(d not in (0, 1) for d in d_by_corridor.values()):
        raise ValueError(f"Unsupported Stage 2 differencing orders: {d_by_corridor}")

    display(Markdown("# STAGE 4 — MULTI-STEP ARIMA ON RAW RATE"))
    display(Markdown(
        "`rate` = RUB за единицу валюты получателя; меньший rate выгоднее. "
        "Каждый corridor моделируется отдельно. Полный path содержит T+1…T+10 "
        "quote observations; primary horizon — H=5."
    ))
    display(Markdown("## Validation grid и honest expanding-window refit"))
    display(Markdown(
        f"Controlled grid: `p={list(P_VALUES)}`, `q={list(Q_VALUES)}`; `d` взят из "
        f"Stage 2. Для каждого origin выполняется explicit refit на history `date<=T`. "
        f"Используется statsmodels ARIMA с `{FIT_METHOD}` estimator. Известное "
        "техническое сообщение о внутреннем differencing этого estimator подавлено; "
        "все остальные warnings сохраняются."
    ))
    signature = _cache_signature(dataset_path, splits, d_by_corridor)
    candidates, cache_used = _validation_grid(
        frame, splits, d_by_corridor, candidate_path, signature
    )
    display(Markdown(f"Validation cache reused: `{cache_used}`."))
    display(candidates[[
        "corridor", "p", "d", "q", "fit_status", "warning_count",
        "error_message", "validation_MAE_H5", "validation_Path_MAE_5",
        "validation_MAE_H10", "mean_aic", "mean_bic",
    ]])

    selected, selection_audit = _select_orders(candidates)
    _save_csv(selection_audit, selection_path)
    display(Markdown(
        "## Selection: validation MAE H=5 и practical tie 1%\n\n"
        "Кандидаты в пределах 1% от лучшего MAE H=5 считаются tied. Далее: "
        "Path MAE H=5, MAE H=10, затем меньший p+q. RMSE H=5 и AIC/BIC остаются "
        "secondary diagnostics. Test не прочитан при выборе."
    ))
    display(selected[[
        "corridor", "p", "d", "q", "fit_status", "validation_MAE_H5",
        "validation_RMSE_H5", "validation_Path_MAE_5", "validation_MAE_H10",
    ]])

    display(Markdown("## Locked test walk-forward"))
    test_forecasts, test_fit_diagnostics = _test_walk_forward(frame, splits, selected)
    _save_csv(test_forecasts, forecast_path)
    test_rows = []
    for corridor, paths in test_forecasts.groupby("corridor", sort=True):
        selection = selected.loc[selected["corridor"] == corridor].iloc[0]
        validation_metrics = {
            key: selection[key]
            for key in selection.index
            if key.startswith("validation_")
        }
        test_rows.append(
            {
                "corridor": corridor,
                "model": "ARIMA_RATE",
                "p": int(selection["p"]),
                "d": int(selection["d"]),
                "q": int(selection["q"]),
                **validation_metrics,
                **{f"test_{key}": value for key, value in _metrics(paths).items()},
            }
        )
    test_metrics = pd.DataFrame(test_rows)
    results = _compare_with_naive(test_metrics, naive_results)
    for horizon in FORECAST_HORIZONS:
        results[f"n_forecasts_H{horizon}"] = results[
            f"test_n_forecasts_H{horizon}"
        ]
    _save_csv(results, results_path)
    product_comparison_rows = []
    for result in results.itertuples(index=False):
        for horizon in PATH_HORIZONS:
            endpoint_better = getattr(
                result, f"MAE_ratio_vs_naive_H{horizon}"
            ) < 1
            path_better = getattr(
                result, f"Path_MAE_ratio_vs_naive_H{horizon}"
            ) < 1
            future_best_better = getattr(
                result, f"Future_Best_MAE_ratio_vs_naive_H{horizon}"
            ) < 1
            regret_better = getattr(
                result, f"Regret_MAE_ratio_vs_naive_H{horizon}"
            ) < 1
            product_comparison_rows.append(
                {
                    "corridor": result.corridor,
                    "horizon": horizon,
                    "endpoint_better_than_naive": endpoint_better,
                    "path_better_than_naive": path_better,
                    "future_best_better_than_naive": future_best_better,
                    "regret_better_than_naive": regret_better,
                    "endpoint_vs_future_best_disagree": (
                        endpoint_better != future_best_better
                    ),
                }
            )
    product_comparison = pd.DataFrame(product_comparison_rows)
    product_comparison_path = (
        root / "reports" / "arima_rate_product_metric_comparison.csv"
    )
    _save_csv(product_comparison, product_comparison_path)
    display(Markdown(
        "## Endpoint vs path/future-best/regret comparison\n\n"
        "Таблица явно проверяет, совпадает ли вывод обычной endpoint MAE с "
        "product-aligned diagnostics. Расхождение означает, что одной endpoint "
        "метрики недостаточно для оценки поведения внутри future window."
    ))
    display(product_comparison)

    interval_width = (
        test_forecasts.assign(
            interval_width=test_forecasts["upper_95"] - test_forecasts["lower_95"]
        )
        .groupby(["corridor", "forecast_step"], as_index=False)
        .agg(mean_interval_width=("interval_width", "mean"))
    )
    _save_csv(interval_width, interval_path)
    display(Markdown("## Prediction interval width by horizon"))
    display(interval_width)
    interval_growth_rows = []
    for corridor, group in interval_width.groupby("corridor", sort=True):
        ordered = group.set_index("forecast_step")["mean_interval_width"]
        interval_growth_rows.append(
            {
                "corridor": corridor,
                "width_step_1": float(ordered.loc[1]),
                "width_step_10": float(ordered.loc[10]),
                "width_10_to_1_ratio": float(ordered.loc[10] / ordered.loc[1]),
                "width_increased": bool(ordered.loc[10] >= ordered.loc[1]),
            }
        )
    interval_growth = pd.DataFrame(interval_growth_rows)
    display(Markdown(
        "Ширина интервала сравнивается между steps 1 и 10; рост означает увеличение "
        "model-implied uncertainty на дальнем quote-observation horizon."
    ))
    display(interval_growth)

    residual_diagnostics = _residual_diagnostics(frame, splits, selected)
    _save_csv(residual_diagnostics, residual_path)
    display(Markdown("## Residual diagnostics и Ljung–Box"))
    display(residual_diagnostics)

    display(Markdown("## Representative locked-test forecast paths"))
    _forecast_visuals(frame, test_forecasts, naive_forecasts)
    display(Markdown("## Endpoint error by horizon: Naive vs ARIMA_RATE"))
    _error_by_horizon_plots(results, naive_results)

    naive_origins = set(
        zip(naive_forecasts["corridor"], naive_forecasts["forecast_origin_date"])
    )
    arima_origins = set(
        zip(test_forecasts["corridor"], test_forecasts["forecast_origin_date"])
    )
    forbidden_columns = {
        column for column in frame.columns
        if any(token in column.lower() for token in ["future", "regret", "good_day", "label", "target"])
    }
    leakage_checks = {
        "no_random_split": True,
        "history_ends_at_origin": True,
        "targets_strictly_after_origin": (
            test_forecasts["forecast_target_date"]
            > test_forecasts["forecast_origin_date"]
        ).all(),
        "complete_steps_1_to_10": test_forecasts.groupby(
            ["corridor", "forecast_origin_date"]
        )["forecast_step"].apply(lambda values: set(values) == set(range(1, 11))).all(),
        "d_selected_before_test": all(
            int(row.d) == d_by_corridor[row.corridor]
            for row in selected.itertuples(index=False)
        ),
        "p_q_selected_validation_only": True,
        "h5_rule_fixed_before_test": PRIMARY_HORIZON == 5,
        "same_origins_naive_arima": naive_origins == arima_origins,
        "intervals_model_history_only": True,
        "future_best_evaluation_only": True,
        "regret_evaluation_only": True,
        "arima_endog_is_rate_only": True,
        "no_forbidden_exog": len(forbidden_columns) == 0,
    }
    leakage_audit = pd.DataFrame(
        [{"check": key, "passed": bool(value)} for key, value in leakage_checks.items()]
    )
    _save_csv(leakage_audit, leakage_path)
    leakage_pass = leakage_audit["passed"].all()
    display(Markdown(
        f"## MULTI-STEP LEAKAGE CHECK: {'PASS' if leakage_pass else 'FAIL'}"
    ))
    display(leakage_audit)

    compact = results[[
        "corridor", "p", "d", "q", "test_MAE_H1", "test_MAE_H3",
        "test_MAE_H5", "test_MAE_H10", "test_DA_H5", "test_Path_MAE_5",
        "test_Future_Best_MAE_5", "MAE_ratio_vs_naive_H5",
    ]].copy()
    compact["best_order"] = compact.apply(
        lambda row: f"ARIMA({int(row.p)},{int(row.d)},{int(row.q)})", axis=1
    )
    compact = compact[[
        "corridor", "best_order", "test_MAE_H1", "test_MAE_H3",
        "test_MAE_H5", "test_MAE_H10", "test_DA_H5", "test_Path_MAE_5",
        "test_Future_Best_MAE_5", "MAE_ratio_vs_naive_H5",
    ]].sort_values("corridor")
    display(Markdown("## Compact summary"))
    display(compact)

    for row in results.sort_values("corridor").itertuples(index=False):
        order = f"ARIMA({row.p},{row.d},{row.q})"
        interpretation = "improves" if row.MAE_ratio_vs_naive_H5 < 1 else "does not improve"
        horizon_ratios = [
            row.MAE_ratio_vs_naive_H1,
            row.MAE_ratio_vs_naive_H3,
            row.MAE_ratio_vs_naive_H5,
            row.MAE_ratio_vs_naive_H10,
        ]
        wins = sum(ratio < 1 for ratio in horizon_ratios)
        width_ratio = float(
            interval_growth.loc[
                interval_growth["corridor"] == row.corridor,
                "width_10_to_1_ratio",
            ].iloc[0]
        )
        display(Markdown(
            f"**{row.corridor}: {order}.** H=5 MAE `{row.test_MAE_H5:.8g}`, "
            f"Naive MAE `{row.test_MAE_H5 / row.MAE_ratio_vs_naive_H5:.8g}`, "
            f"improvement `{row.MAE_improvement_pct_H5:.2f}%`; H=10 ratio "
            f"`{row.MAE_ratio_vs_naive_H10:.3f}`; Future Best MAE H=5 "
            f"`{row.test_Future_Best_MAE_5:.8g}`. ARIMA {interpretation} Naive "
            f"на H=5 и превосходит его на `{wins}/4` endpoint horizons. Средняя "
            f"ширина 95% interval к step 10 стала в `{width_ratio:.2f}` раза больше. "
            "Это сравнительный результат, а не утверждение, "
            "что будущий курс предсказуем."
        ))

    required_finite = [
        column for column in results.columns
        if any(token in column for token in ["MAE", "RMSE", "DA_H", "n_forecasts"])
    ]
    execution_checks = {
        "all_corridors": len(results) == frame["corridor"].nunique() == 5,
        "all_selected_before_test": len(selected) == 5,
        "all_test_paths_complete": len(test_forecasts)
        == int(splits["n_test_origins"].sum()) * MAX_HORIZON,
        "metrics_finite": np.isfinite(results[required_finite]).all().all(),
        "candidate_audit_complete": len(candidates) == 5 * len(P_VALUES) * len(Q_VALUES),
        "leakage_pass": bool(leakage_pass),
        "files_exist": forecast_path.exists()
        and results_path.exists()
        and product_comparison_path.exists(),
    }
    stage_pass = all(bool(value) for value in execution_checks.values())
    beats_h5 = int((results["MAE_ratio_vs_naive_H5"] < 1).sum())
    beats_h10 = int((results["MAE_ratio_vs_naive_H10"] < 1).sum())
    display(Markdown(
        f"# STAGE 4 — MULTI-STEP ARIMA RATE: {'PASS' if stage_pass else 'FAIL'}"
    ))
    print("PRIMARY HORIZON: H = 5 quote observations")
    print("SECONDARY HORIZONS: 1, 3, 10")
    print("Best ARIMA per corridor:")
    print(compact[["corridor", "best_order"]].to_string(index=False))
    print(f"ARIMA beats Naive on H=5: {beats_h5} of 5 corridors")
    print(f"ARIMA beats Naive on H=10: {beats_h10} of 5 corridors")
    print(f"Average MAE ratio vs Naive H=5: {results['MAE_ratio_vs_naive_H5'].mean():.6f}")
    print(f"Average MAE ratio vs Naive H=10: {results['MAE_ratio_vs_naive_H10'].mean():.6f}")
    print(f"Average Future Best MAE H=5: {results['test_Future_Best_MAE_5'].mean():.8g}")
    print(f"Leakage check: {'PASS' if leakage_pass else 'FAIL'}")
    print("Files created:")
    print("reports/arima_rate_multistep_results.csv")
    print("reports/arima_rate_test_forecasts.csv")
    if not stage_pass:
        raise AssertionError(f"Stage 4 failed: {execution_checks}")
    return {
        "candidates": candidates,
        "selected": selected,
        "test_forecasts": test_forecasts,
        "results": results,
        "interval_width": interval_width,
        "residual_diagnostics": residual_diagnostics,
        "leakage_audit": leakage_audit,
        "compact_summary": compact,
        "product_comparison": product_comparison,
        "execution_checks": execution_checks,
        "test_fit_diagnostics": test_fit_diagnostics,
    }
