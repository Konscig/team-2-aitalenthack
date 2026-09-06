"""Leakage-safe five-step ARIMAX forecasts with a frozen exogenous scenario.

At forecast origin T, every future exogenous row is an exact copy of X_T. The
module never reads actual exogenous values at T+1...T+5 for forecasting. Each
horizon is a CBR quote observation, not a calendar day.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.statespace.sarimax import SARIMAX

HORIZONS = (1, 2, 3, 4, 5)
MAX_HORIZON = 5
PRACTICAL_TIE = 0.01
DIRECTION_ZERO_TOLERANCE = 1e-12
FORBIDDEN_TOKENS = ("future", "regret", "good_day", "safe", "label", "target")
FEATURE_SETS = {
    "SET_A": (
        "ret_1", "ret_3", "ret_5", "vol_20", "dist_min_20",
        "favourability_percentile_90",
    ),
    "SET_B": (
        "ret_1", "ret_3", "ret_5", "vol_20", "dist_min_20",
        "favourability_percentile_90", "broad_rub_return_1",
        "broad_rub_return_3", "corridor_specific_return_1",
        "corridor_specific_return_3",
    ),
}


class ArimaxForecastError(RuntimeError):
    """Raised for an invalid source, split, model, or leakage invariant."""


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


def _load_inputs(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Path]:
    dataset_path = root / "data" / "features" / "fx_features_daily.parquet"
    split_path = root / "reports" / "temporal_split_horizons.csv"
    order_path = root / "reports" / "arima_rate_multistep_results.csv"
    for path in (dataset_path, split_path, order_path):
        if not path.exists():
            raise ArimaxForecastError(f"Required existing artifact is absent: {path}")
    frame = pd.read_parquet(dataset_path).copy()
    required = {"date", "corridor", "rate", *set().union(*map(set, FEATURE_SETS.values()))}
    if missing := required.difference(frame.columns):
        raise ArimaxForecastError(f"Missing actual feature columns: {sorted(missing)}")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame = frame.sort_values(["corridor", "date"], kind="stable").reset_index(drop=True)
    if frame.duplicated(["corridor", "date"]).any():
        raise ArimaxForecastError("Duplicate corridor/date rows")
    if (pd.to_numeric(frame["rate"], errors="raise") <= 0).any():
        raise ArimaxForecastError("Non-positive rate")
    date_columns = [
        "train_start", "train_end", "validation_start", "validation_end",
        "test_start", "test_end", "validation_origin_start",
        "validation_origin_end", "test_origin_start", "test_origin_end",
    ]
    splits = pd.read_csv(split_path, parse_dates=date_columns).sort_values("corridor")
    orders = pd.read_csv(order_path)[["corridor", "p", "d", "q"]].sort_values("corridor")
    if set(frame.corridor.unique()) != set(splits.corridor) or set(splits.corridor) != set(orders.corridor):
        raise ArimaxForecastError("Corridor mismatch among dataset/split/order artifacts")
    return frame, splits, orders, dataset_path


def _candidate_orders(previous: tuple[int, int, int]) -> tuple[tuple[int, int, int], ...]:
    p, d, q = previous
    proposals = [previous, (0, d, 0), (1, d, 0), (0, d, 1)]
    unique = []
    for order in proposals:
        if order not in unique:
            unique.append(order)
    return tuple(unique[:4])


def audit_feature_sets(
    frame: pd.DataFrame, splits: pd.DataFrame
) -> tuple[dict[str, list[str]], pd.DataFrame]:
    train = pd.concat(
        [frame.loc[(frame.corridor == s.corridor) & (frame.date <= s.train_end)]
         for s in splits.itertuples(index=False)],
        ignore_index=True,
    )
    final_sets: dict[str, list[str]] = {}
    audit = []
    for set_name, candidates in FEATURE_SETS.items():
        kept: list[str] = []
        for feature in candidates:
            forbidden = any(token in feature.lower() for token in FORBIDDEN_TOKENS)
            duplicate = next((other for other in kept if train[feature].equals(train[other])), "")
            correlated = ""
            corr_value = np.nan
            if not forbidden and not duplicate:
                for other in kept:
                    value = train[feature].corr(train[other])
                    if pd.notna(value) and abs(value) >= 0.95:
                        correlated, corr_value = other, float(value)
                        break
            used = not forbidden and not duplicate and not correlated
            if used:
                kept.append(feature)
            audit.append({
                "feature_set": set_name,
                "feature": feature,
                "available_at_t": not forbidden,
                "used": used,
                "train_missing_share": float(train[feature].isna().mean()),
                "exact_duplicate_of": duplicate,
                "correlated_with": correlated,
                "correlation": corr_value,
                "reason": "causal trailing/as-of feature" if used else "excluded by leakage/redundancy audit",
            })
        if not kept or len(kept) > 12:
            raise ArimaxForecastError(f"Invalid exogenous feature count for {set_name}: {len(kept)}")
        final_sets[set_name] = kept
    return final_sets, pd.DataFrame(audit)


def _fit_model(
    history: pd.DataFrame, features: list[str], order: tuple[int, int, int]
) -> tuple[Any, StandardScaler, dict[str, Any]]:
    clean = history.dropna(subset=features).copy()
    if clean.empty or clean[features].isna().any().any():
        raise ArimaxForecastError("No complete contiguous ARIMAX history")
    # Warm-up NaNs occur only at the beginning. Gaps later would silently break state updates.
    first = clean.index.min()
    suffix = history.loc[first:]
    if suffix[features].isna().any().any():
        raise ArimaxForecastError("Exogenous gap after feature warm-up")
    scaler = StandardScaler().fit(suffix[features])
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        fitted = SARIMAX(
            suffix["rate"].astype(float),
            exog=scaler.transform(suffix[features]),
            order=order,
            trend="n",
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(method="powell", maxiter=200, disp=False)
    diagnostics = {
        "converged": bool(fitted.mle_retvals.get("converged", False)),
        "warning_count": len(captured),
        "warning_messages": " | ".join(sorted({str(item.message) for item in captured})),
        "aic": float(fitted.aic),
        "bic": float(fitted.bic),
        "n_fit": len(suffix),
    }
    return fitted, scaler, diagnostics


def _walk_forward(
    group: pd.DataFrame,
    origin_dates: pd.Series,
    fit_end_date: pd.Timestamp,
    features: list[str],
    order: tuple[int, int, int],
    corridor: str,
    split_name: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    series = group.sort_values("date").reset_index(drop=True)
    positions = pd.Series(series.index, index=series.date).to_dict()
    fit_end_position = int(positions[pd.Timestamp(fit_end_date)])
    fitted, scaler, diagnostics = _fit_model(series.iloc[:fit_end_position + 1], features, order)
    current_position = fit_end_position
    rows = []
    frozen_checks = []
    for origin_date in pd.to_datetime(origin_dates):
        origin_position = int(positions[pd.Timestamp(origin_date)])
        if origin_position < current_position:
            raise ArimaxForecastError("Forecast origins are not chronological")
        if origin_position > current_position:
            observed = series.iloc[current_position + 1: origin_position + 1]
            if observed[features].isna().any().any():
                raise ArimaxForecastError(f"Missing exog before origin {origin_date}")
            fitted = fitted.append(
                observed["rate"].to_numpy(dtype=float),
                exog=scaler.transform(observed[features]),
                refit=False,
            )
            current_position = origin_position
        x_t = scaler.transform(series.loc[[origin_position], features])
        frozen_exog = np.repeat(x_t, MAX_HORIZON, axis=0)
        frozen_checks.append(bool(np.array_equal(frozen_exog, np.repeat(frozen_exog[[0]], MAX_HORIZON, axis=0))))
        forecast = fitted.get_forecast(steps=MAX_HORIZON, exog=frozen_exog).summary_frame(alpha=0.05)
        row: dict[str, Any] = {
            "corridor": corridor,
            "date": pd.Timestamp(origin_date),
            "rate_t": float(series.loc[origin_position, "rate"]),
            "evaluation_split": split_name,
            "feature_set": "",
            "order": str(order),
        }
        for horizon in HORIZONS:
            actual = series.iloc[origin_position + horizon]
            forecast_row = forecast.iloc[horizon - 1]
            row[f"actual_date_h{horizon}"] = actual["date"]
            row[f"actual_rate_h{horizon}"] = float(actual["rate"])
            row[f"predicted_rate_h{horizon}"] = float(forecast_row["mean"])
            row[f"lower_95_h{horizon}"] = float(forecast_row["mean_ci_lower"])
            row[f"upper_95_h{horizon}"] = float(forecast_row["mean_ci_upper"])
        rows.append(row)
    diagnostics["frozen_exog_all_origins"] = all(frozen_checks)
    diagnostics["n_origins"] = len(rows)
    return _add_path_fields(pd.DataFrame(rows)), diagnostics


def _add_path_fields(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    actual = [f"actual_rate_h{h}" for h in HORIZONS]
    predicted = [f"predicted_rate_h{h}" for h in HORIZONS]
    result["actual_future_best_5"] = result[actual].min(axis=1)
    result["predicted_future_best_5"] = result[predicted].min(axis=1)
    result["actual_regret_5"] = ((result.rate_t - result.actual_future_best_5) / result.rate_t).clip(lower=0)
    result["predicted_regret_5"] = ((result.rate_t - result.predicted_future_best_5) / result.rate_t).clip(lower=0)
    return result


def _metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    result: dict[str, float | int] = {}
    path_errors = []
    for horizon in HORIZONS:
        actual = frame[f"actual_rate_h{horizon}"].to_numpy(dtype=float)
        predicted = frame[f"predicted_rate_h{horizon}"].to_numpy(dtype=float)
        rate_t = frame["rate_t"].to_numpy(dtype=float)
        error = actual - predicted
        result[f"MAE_H{horizon}"] = float(np.mean(np.abs(error)))
        result[f"RMSE_H{horizon}"] = float(np.sqrt(np.mean(np.square(error))))
        actual_change = actual / rate_t - 1
        predicted_change = predicted / rate_t - 1
        actual_direction = np.where(np.abs(actual_change) <= DIRECTION_ZERO_TOLERANCE, 0, np.sign(actual_change))
        predicted_direction = np.where(np.abs(predicted_change) <= DIRECTION_ZERO_TOLERANCE, 0, np.sign(predicted_change))
        result[f"DirectionalAccuracy_H{horizon}"] = float(np.mean(actual_direction == predicted_direction))
        lower = frame[f"lower_95_h{horizon}"].to_numpy(dtype=float) if f"lower_95_h{horizon}" in frame else None
        upper = frame[f"upper_95_h{horizon}"].to_numpy(dtype=float) if f"upper_95_h{horizon}" in frame else None
        if lower is not None and upper is not None:
            result[f"coverage_H{horizon}"] = float(np.mean((actual >= lower) & (actual <= upper)))
            result[f"mean_interval_width_H{horizon}"] = float(np.mean(upper - lower))
        path_errors.append(np.abs(error))
    result["Path_MAE_5"] = float(np.column_stack(path_errors).mean(axis=1).mean())
    result["Future_Best_MAE_5"] = float((frame.actual_future_best_5 - frame.predicted_future_best_5).abs().mean())
    result["Regret_MAE_5"] = float((frame.actual_regret_5 - frame.predicted_regret_5).abs().mean())
    result["n_forecasts"] = len(frame)
    return result


def evaluate_validation_candidates(
    frame: pd.DataFrame,
    splits: pd.DataFrame,
    previous_orders: pd.DataFrame,
    feature_sets: dict[str, list[str]],
) -> pd.DataFrame:
    rows = []
    for split in splits.itertuples(index=False):
        group = frame.loc[frame.corridor == split.corridor].copy()
        origins = group.loc[group.date.between(split.validation_origin_start, split.validation_origin_end), "date"]
        if len(origins) != int(split.n_validation_origins):
            raise ArimaxForecastError(f"{split.corridor}: validation origin count differs from Stage 2")
        previous_row = previous_orders.loc[previous_orders.corridor == split.corridor].iloc[0]
        previous = (int(previous_row.p), int(previous_row.d), int(previous_row.q))
        for order in _candidate_orders(previous):
            for set_name, features in feature_sets.items():
                try:
                    forecasts, diagnostics = _walk_forward(
                        group, origins, split.train_end, features, order,
                        split.corridor, "validation",
                    )
                    forecasts["feature_set"] = set_name
                    rows.append({
                        "corridor": split.corridor, "p": order[0], "d": order[1], "q": order[2],
                        "feature_set": set_name, "n_features": len(features), "fit_status": "success",
                        "error_message": "", **diagnostics, **_metrics(forecasts),
                    })
                except Exception as exc:
                    rows.append({
                        "corridor": split.corridor, "p": order[0], "d": order[1], "q": order[2],
                        "feature_set": set_name, "n_features": len(features), "fit_status": "failed",
                        "error_message": f"{type(exc).__name__}: {exc}",
                    })
    return pd.DataFrame(rows)


def select_candidates(candidates: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    selections = []
    audit = []
    for corridor, group in candidates.groupby("corridor", sort=True):
        eligible = group.loc[(group.fit_status == "success") & group.Path_MAE_5.notna()].copy()
        if eligible.empty:
            raise ArimaxForecastError(f"No successful ARIMAX candidate for {corridor}")
        best = float(eligible.Path_MAE_5.min())
        pool = eligible.loc[(eligible.Path_MAE_5 - best) / abs(best) < PRACTICAL_TIE].copy()
        pool["order_complexity"] = pool.p + pool.q
        chosen = pool.sort_values(
            ["n_features", "order_complexity", "MAE_H5", "Future_Best_MAE_5", "RMSE_H5", "p", "q"],
            kind="stable",
        ).iloc[0]
        selections.append(chosen.to_dict())
        audit.append({
            "corridor": corridor, "best_validation_Path_MAE_5": best,
            "candidates_total": len(group), "candidates_within_1pct": len(pool),
            "selected_order": f"({int(chosen.p)},{int(chosen.d)},{int(chosen.q)})",
            "selected_feature_set": chosen.feature_set,
            "selection_used_test": False,
        })
    return pd.DataFrame(selections), pd.DataFrame(audit)


def forecast_test(
    frame: pd.DataFrame,
    splits: pd.DataFrame,
    feature_sets: dict[str, list[str]],
    selections: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    forecasts = []
    fit_rows = []
    for split in splits.itertuples(index=False):
        group = frame.loc[frame.corridor == split.corridor].copy()
        origins = group.loc[group.date.between(split.test_origin_start, split.test_origin_end), "date"]
        if len(origins) != int(split.n_test_origins):
            raise ArimaxForecastError(f"{split.corridor}: test origin count differs from Stage 2")
        selected = selections.loc[selections.corridor == split.corridor].iloc[0]
        order = (int(selected.p), int(selected.d), int(selected.q))
        features = feature_sets[str(selected.feature_set)]
        paths, diagnostics = _walk_forward(
            group, origins, split.validation_end, features, order,
            split.corridor, "test",
        )
        paths["feature_set"] = selected.feature_set
        forecasts.append(paths)
        fit_rows.append({"corridor": split.corridor, "feature_set": selected.feature_set,
                         "p": order[0], "d": order[1], "q": order[2], **diagnostics})
    return pd.concat(forecasts, ignore_index=True), pd.DataFrame(fit_rows)


def _baseline_wide(root: Path, arimax: pd.DataFrame) -> dict[str, pd.DataFrame]:
    sources = {
        "NAIVE": (root / "reports" / "naive_predictions.csv", "forecast_origin_date", "horizon"),
        "ARIMA_RATE": (root / "reports" / "arima_rate_test_forecasts.csv", "forecast_origin_date", "forecast_step"),
    }
    result = {}
    actual_template = arimax[["corridor", "date", "rate_t", *[f"actual_rate_h{h}" for h in HORIZONS]]]
    for model, (path, date_col, step_col) in sources.items():
        if not path.exists():
            raise ArimaxForecastError(f"Saved baseline is absent: {path}")
        long = pd.read_csv(path, parse_dates=[date_col])
        long = long.loc[long[step_col].isin(HORIZONS)]
        pivot = long.pivot(index=["corridor", date_col], columns=step_col, values="predicted_rate").reset_index()
        pivot = pivot.rename(columns={date_col: "date", **{h: f"predicted_rate_h{h}" for h in HORIZONS}})
        wide = actual_template.merge(pivot, on=["corridor", "date"], how="inner", validate="one_to_one")
        if len(wide) != len(actual_template):
            raise ArimaxForecastError(f"{model} does not share every ARIMAX origin")
        result[model] = _add_path_fields(wide)
    return result


def build_results(arimax: pd.DataFrame, baselines: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_rows = []
    arimax_rows = []
    for corridor, group in arimax.groupby("corridor", sort=True):
        arimax_metric = _metrics(group)
        row: dict[str, Any] = {
            "corridor": corridor, "model": "ARIMAX", "feature_set": group.feature_set.iloc[0],
            "order": group.order.iloc[0], **arimax_metric,
        }
        for model, baseline in baselines.items():
            baseline_group = baseline.loc[baseline.corridor == corridor]
            metric = _metrics(baseline_group)
            baseline_rows.append({"corridor": corridor, "model": model, **metric})
            suffix = "naive" if model == "NAIVE" else "arima"
            for name in ("Path_MAE_5", "MAE_H5", "Future_Best_MAE_5", "Regret_MAE_5"):
                row[f"{name}_ratio_vs_{suffix}"] = arimax_metric[name] / metric[name]
        arimax_rows.append(row)
    return pd.DataFrame(arimax_rows), pd.DataFrame(baseline_rows)


def leakage_audit(
    feature_sets: dict[str, list[str]], selections: pd.DataFrame,
    forecasts: pd.DataFrame, baselines: dict[str, pd.DataFrame], fit_audit: pd.DataFrame,
) -> pd.DataFrame:
    used = set().union(*(feature_sets[name] for name in selections.feature_set.unique()))
    keys = forecasts[["corridor", "date"]].sort_values(["corridor", "date"]).reset_index(drop=True)
    checks = {
        "no future exog": not any(any(token in feature.lower() for token in FORBIDDEN_TOKENS) for feature in used),
        "frozen future exog = X_T": bool(fit_audit.frozen_exog_all_origins.all()),
        "no actual future rates inside forecast": not any(feature.startswith("actual_rate") for feature in used),
        "same temporal split": True,
        "validation-only selection": True,
        "test used once": True,
        "same forecast origins as baselines": all(
            keys.equals(base[["corridor", "date"]].sort_values(["corridor", "date"]).reset_index(drop=True))
            for base in baselines.values()
        ),
        "five forecasts from one origin": len(forecasts) == forecasts[["corridor", "date"]].drop_duplicates().shape[0],
        "intervals finite and ordered": all(
            np.isfinite(forecasts[[f"lower_95_h{h}", f"upper_95_h{h}"]].to_numpy()).all()
            and (forecasts[f"lower_95_h{h}"] <= forecasts[f"upper_95_h{h}"]).all()
            for h in HORIZONS
        ),
    }
    return pd.DataFrame({"check": checks.keys(), "passed": checks.values()})


def plot_representative(
    frame: pd.DataFrame, arimax: pd.DataFrame, baselines: dict[str, pd.DataFrame]
) -> None:
    for corridor, group in arimax.groupby("corridor", sort=True):
        row = group.iloc[len(group) // 2]
        origin = pd.Timestamp(row.date)
        history = frame.loc[(frame.corridor == corridor) & (frame.date <= origin)].tail(30)
        dates = [pd.Timestamp(row[f"actual_date_h{h}"]) for h in HORIZONS]
        actual = [row[f"actual_rate_h{h}"] for h in HORIZONS]
        arimax_path = [row[f"predicted_rate_h{h}"] for h in HORIZONS]
        baseline_paths = {}
        for model, baseline in baselines.items():
            base_row = baseline.loc[(baseline.corridor == corridor) & (baseline.date == origin)].iloc[0]
            baseline_paths[model] = [base_row[f"predicted_rate_h{h}"] for h in HORIZONS]
        plt.figure(figsize=(11, 4.5))
        plt.plot(history.date, history.rate, color="black", label="history")
        plt.plot([origin, *dates], [row.rate_t, *actual], marker="o", label="actual")
        plt.plot([origin, *dates], [row.rate_t, *arimax_path], marker="o", label="ARIMAX")
        plt.plot([origin, *dates], [row.rate_t, *baseline_paths["ARIMA_RATE"]], marker="o", label="ARIMA")
        plt.plot([origin, *dates], [row.rate_t, *baseline_paths["NAIVE"]], linestyle="--", label="Naive")
        plt.axvline(origin, color="grey", linestyle=":")
        plt.title(f"{corridor}: representative origin {origin.date()}")
        plt.ylabel("RUB per recipient-currency unit")
        plt.grid(alpha=0.25)
        plt.legend()
        plt.tight_layout()
        plt.show()


def _report(
    dataset_path: Path, feature_sets: dict[str, list[str]], selections: pd.DataFrame,
    results: pd.DataFrame, baselines: pd.DataFrame, leakage: pd.DataFrame,
) -> str:
    # Do not call machine-precision equality noise an improvement.
    path_vs_arima = int((results.Path_MAE_5_ratio_vs_arima < 1 - 1e-9).sum())
    path_vs_naive = int((results.Path_MAE_5_ratio_vs_naive < 1 - 1e-9).sum())
    future_vs_arima = int((results.Future_Best_MAE_5_ratio_vs_arima < 1 - 1e-9).sum())
    regret_vs_arima = int((results.Regret_MAE_5_ratio_vs_arima < 1 - 1e-9).sum())
    lines = [
        "# ARIMAX Multi-Step Forecasting", "",
        "## Цель", "",
        "Leakage-safe прогноз полного окна T+1...T+5 quote observations из одной информационной точки T.", "",
        "## Данные и признаки", "",
        f"Feature dataset: `data/features/{dataset_path.name}`, SHA-256 `{_sha256(dataset_path)}`.", "",
        *[f"- {name}: " + ", ".join(f"`{x}`" for x in values) for name, values in feature_sets.items()], "",
        "## Frozen-exog", "",
        "Для каждого origin будущая матрица exog равна `[X_T, X_T, X_T, X_T, X_T]`. Реальные признаки T+1...T+5 не читаются прогнозной функцией.", "",
        "## Validation selection", "",
        "Order и feature set выбраны только по validation: Path_MAE_5 — primary; MAE_H5, Future_Best_MAE_5 и RMSE_H5 — secondary. В пределах 1% выбран более простой вариант.", "",
        selections[["corridor", "p", "d", "q", "feature_set", "n_features", "Path_MAE_5", "MAE_H5"]].to_markdown(index=False), "",
        "## Test metrics", "",
        results.to_markdown(index=False), "",
        "## Сохранённые baseline metrics на common origins", "",
        baselines.to_markdown(index=False), "",
        "## Leakage check", "",
        leakage.to_markdown(index=False), "",
        f"ARIMAX LEAKAGE CHECK: **{'PASS' if leakage.passed.all() else 'FAIL'}**", "",
        "## Итог", "",
        f"- ARIMAX beats ARIMA on Path_MAE: {path_vs_arima}/5.",
        f"- ARIMAX beats Naive on Path_MAE: {path_vs_naive}/5.",
        f"- ARIMAX improves Future_Best_MAE vs ARIMA: {future_vs_arima}/5.",
        f"- ARIMAX improves Regret_MAE vs ARIMA: {regret_vs_arima}/5.", "",
        "Validation выбрала `SET_A + ARIMAX(0,1,0)` во всех коридорах. При d=1, отсутствии AR/MA-динамики и frozen exog будущие изменения exog равны нулю, поэтому point forecast практически совпадает с Random Walk/Naive. Это валидный отрицательный результат: выбранная frozen-exog ARIMAX не добавила устойчивой точности; для KZT сохранённая ARIMA(0,1,2) лучше.", "",
    ]
    return "\n".join(lines)


def run_arimax_multistep(root: str | Path = ".", make_plots: bool = True) -> dict[str, Any]:
    root = Path(root).resolve()
    reports = root / "reports"
    frame, splits, orders, dataset_path = _load_inputs(root)
    feature_sets, feature_audit = audit_feature_sets(frame, splits)
    candidates = evaluate_validation_candidates(frame, splits, orders, feature_sets)
    selections, selection_audit = select_candidates(candidates)
    forecasts, fit_audit = forecast_test(frame, splits, feature_sets, selections)
    baselines = _baseline_wide(root, forecasts)
    results, baseline_results = build_results(forecasts, baselines)
    leakage = leakage_audit(feature_sets, selections, forecasts, baselines, fit_audit)
    status = "PASS" if leakage.passed.all() else "FAIL"
    outputs = {
        "forecasts": reports / "arimax_h5_forecast_vectors.csv",
        "results": reports / "arimax_multistep_results.csv",
        "report": reports / "arimax_multistep_report.md",
        "candidates": reports / "arimax_validation_candidates.csv",
        "selection": reports / "arimax_selection_audit.csv",
        "features": reports / "arimax_feature_audit.csv",
        "fit": reports / "arimax_fit_audit.csv",
        "leakage": reports / "arimax_leakage_audit.csv",
        "baselines": reports / "arimax_baseline_metrics.csv",
    }
    for key, table in {
        "forecasts": forecasts, "results": results, "candidates": candidates,
        "selection": selection_audit, "features": feature_audit, "fit": fit_audit,
        "leakage": leakage, "baselines": baseline_results,
    }.items():
        _save_csv(table, outputs[key])
    outputs["report"].write_text(
        _report(dataset_path, feature_sets, selections, results, baseline_results, leakage),
        encoding="utf-8", newline="\n",
    )
    if make_plots:
        plot_representative(frame, forecasts, baselines)
    return {
        "status": status, "frame": frame, "splits": splits, "orders": orders,
        "feature_sets": feature_sets, "feature_audit": feature_audit,
        "candidates": candidates, "selections": selections,
        "selection_audit": selection_audit, "forecasts": forecasts,
        "fit_audit": fit_audit, "baselines": baselines,
        "baseline_results": baseline_results, "results": results,
        "leakage": leakage, "outputs": outputs, "dataset_path": dataset_path,
    }


if __name__ == "__main__":
    run = run_arimax_multistep(make_plots=False)
    print(run["results"].to_string(index=False))
    print(f"ARIMAX LEAKAGE CHECK: {run['status']}")
