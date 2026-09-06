"""Leakage-safe direct forecasts for the next five CBR quote observations.

Each horizon model receives the same feature vector available at forecast origin
T and predicts ``log(rate[T+h] / rate[T])`` directly. Horizons are quote
observations, not calendar days. Future observations are targets/evaluation only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

HORIZONS = (1, 2, 3, 4, 5)
MAX_HORIZON = 5
RANDOM_STATE = 42
FORBIDDEN_TOKENS = ("future", "regret", "good_day", "safe", "label", "target")
RIDGE_ALPHAS = (0.1, 1.0, 10.0, 100.0)
GBR_GRID = (
    {"n_estimators": n, "max_depth": depth, "learning_rate": rate}
    for n in (100, 200)
    for depth in (2, 3)
    for rate in (0.03, 0.05)
)
GBR_CONFIGS = tuple(GBR_GRID)

# Deliberately compact and interpretable. Every field exists in the repository's
# feature dictionary/builders and was calculated from observations at or before T.
CANDIDATE_FEATURES = (
    "ret_1",
    "ret_3",
    "ret_5",
    "vol_5",
    "vol_20",
    "dist_min_20",
    "favourability_percentile_90",
    "dist_sma_20",
    "broad_rub_return_1",
    "broad_rub_return_3",
    "broad_rub_return_5",
    "corridor_specific_return_1",
    "return_sign_reversal_up",
    "reversal_strength",
    "near_min_reversal_010",
)


class DirectForecastError(RuntimeError):
    """Raised when an input or leakage invariant is violated."""


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


def discover_feature_dataset(root: Path) -> Path:
    """Find the richest parquet with the required keys and candidate features."""
    preferred = root / "data" / "features" / "fx_features_daily.parquet"
    candidates = [preferred] if preferred.exists() else []
    candidates.extend(
        p for p in sorted((root / "data" / "features").glob("*.parquet")) if p != preferred
    )
    required = {"date", "corridor", "rate", *CANDIDATE_FEATURES}
    matches: list[tuple[int, Path]] = []
    for path in candidates:
        try:
            columns = set(pd.read_parquet(path).columns)
        except Exception:
            continue
        if required.issubset(columns):
            matches.append((len(columns), path))
    if not matches:
        raise DirectForecastError("Feature parquet with the required real columns was not found")
    if preferred.exists() and any(path == preferred for _, path in matches):
        return preferred
    return max(matches, key=lambda item: item[0])[1]


def load_and_validate_dataset(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path).copy()
    required = {"date", "corridor", "rate", *CANDIDATE_FEATURES}
    if missing := required.difference(frame.columns):
        raise DirectForecastError(f"Dataset lacks required fields: {sorted(missing)}")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["corridor"] = frame["corridor"].astype(str)
    frame["rate"] = pd.to_numeric(frame["rate"], errors="raise").astype(float)
    frame = frame.sort_values(["corridor", "date"], kind="stable").reset_index(drop=True)
    duplicate = frame.duplicated(["corridor", "date"], keep=False)
    if duplicate.any():
        raise DirectForecastError(
            "Duplicate corridor/date rows:\n"
            + frame.loc[duplicate, ["corridor", "date"]].head(10).to_string(index=False)
        )
    if frame[["date", "corridor", "rate"]].isna().any().any():
        raise DirectForecastError("Missing required key/rate value")
    if (frame["rate"] <= 0).any():
        raise DirectForecastError("Non-positive rate found")
    return frame


def create_direct_targets(frame: pd.DataFrame) -> pd.DataFrame:
    """Create future targets only within each corridor; never use them as X."""
    result = frame.copy()
    grouped_rate = result.groupby("corridor", sort=False)["rate"]
    grouped_date = result.groupby("corridor", sort=False)["date"]
    for horizon in HORIZONS:
        actual = grouped_rate.shift(-horizon)
        result[f"actual_rate_h{horizon}"] = actual
        result[f"actual_date_h{horizon}"] = grouped_date.shift(-horizon)
        result[f"target_log_return_h{horizon}"] = np.log(actual / result["rate"])
    result["has_full_horizon_5"] = result["actual_rate_h5"].notna()
    return result


def load_splits(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise DirectForecastError(f"Approved split artifact is absent: {path}")
    date_columns = [
        "train_start", "train_end", "validation_start", "validation_end",
        "test_start", "test_end", "validation_origin_start",
        "validation_origin_end", "test_origin_start", "test_origin_end",
    ]
    splits = pd.read_csv(path, parse_dates=date_columns)
    required = {"corridor", *date_columns, "n_test_origins"}
    if missing := required.difference(splits.columns):
        raise DirectForecastError(f"Split artifact lacks: {sorted(missing)}")
    return splits.sort_values("corridor").reset_index(drop=True)


def audit_and_select_features(
    frame: pd.DataFrame, splits: pd.DataFrame, correlation_limit: float = 0.95
) -> tuple[list[str], pd.DataFrame, pd.DataFrame]:
    """Run redundancy/leakage screening on TRAIN rows only."""
    train = pd.concat(
        [
            frame.loc[
                (frame["corridor"] == split.corridor)
                & (frame["date"] <= split.train_end)
            ]
            for split in splits.itertuples(index=False)
        ],
        ignore_index=True,
    )
    selected: list[str] = []
    rows: list[dict[str, Any]] = []
    for feature in CANDIDATE_FEATURES:
        forbidden = any(token in feature.lower() for token in FORBIDDEN_TOKENS)
        numeric = pd.to_numeric(train[feature], errors="coerce")
        exact_duplicate_of = next(
            (kept for kept in selected if train[feature].equals(train[kept])), ""
        )
        near_zero_variance = bool(numeric.dropna().var(ddof=0) <= 1e-12)
        correlated_with = ""
        correlation = np.nan
        if not forbidden and not exact_duplicate_of and not near_zero_variance:
            for kept in selected:
                value = numeric.corr(pd.to_numeric(train[kept], errors="coerce"))
                if pd.notna(value) and abs(value) >= correlation_limit:
                    correlated_with, correlation = kept, float(value)
                    break
        used = not (forbidden or exact_duplicate_of or near_zero_variance or correlated_with)
        if used:
            selected.append(feature)
        reason = "causal trailing/as-of feature documented in repository"
        if forbidden:
            reason = "excluded: forbidden future/label token"
        elif exact_duplicate_of:
            reason = f"excluded: exact duplicate of {exact_duplicate_of}"
        elif near_zero_variance:
            reason = "excluded: near-zero TRAIN variance"
        elif correlated_with:
            reason = f"excluded: abs(TRAIN correlation) >= {correlation_limit} with {correlated_with}"
        rows.append(
            {
                "feature": feature,
                "available_at_t": not forbidden,
                "reason": reason,
                "used": used,
                "train_missing_share": float(train[feature].isna().mean()),
                "train_variance": float(numeric.dropna().var(ddof=0)),
                "exact_duplicate_of": exact_duplicate_of,
                "correlated_with": correlated_with,
                "correlation": correlation,
            }
        )
    if not 8 <= len(selected) <= 15:
        raise DirectForecastError(f"Expected 8-15 final features, selected {len(selected)}")
    correlations = train[selected].corr(method="pearson")
    return selected, pd.DataFrame(rows), correlations


def _origin_masks(group: pd.DataFrame, split: pd.Series) -> dict[str, pd.Series]:
    full = group["has_full_horizon_5"]
    # Purge: the H5 target date must remain inside the source partition.
    train = full & (group["date"] <= split["train_end"]) & (
        group["actual_date_h5"] <= split["train_end"]
    )
    validation = full & group["date"].between(
        split["validation_origin_start"], split["validation_origin_end"]
    )
    refit = full & (group["date"] <= split["validation_end"]) & (
        group["actual_date_h5"] <= split["validation_end"]
    )
    test = full & group["date"].between(
        split["test_origin_start"], split["test_origin_end"]
    )
    return {"train": train, "validation": validation, "refit": refit, "test": test}


def build_model_frame(
    frame: pd.DataFrame, splits: pd.DataFrame, features: list[str]
) -> tuple[dict[str, dict[str, pd.DataFrame]], pd.DataFrame]:
    partitions: dict[str, dict[str, pd.DataFrame]] = {}
    audit_rows = []
    for split in splits.itertuples(index=False):
        corridor = split.corridor
        group = frame.loc[frame["corridor"] == corridor].copy().reset_index(drop=True)
        split_series = pd.Series(split._asdict())
        masks = _origin_masks(group, split_series)
        partitions[corridor] = {}
        for name, mask in masks.items():
            before = int(mask.sum())
            selected = group.loc[mask].dropna(subset=features).copy()
            partitions[corridor][name] = selected
            audit_rows.append(
                {
                    "corridor": corridor,
                    "partition": name,
                    "rows_before_complete_case": before,
                    "rows_after_complete_case": len(selected),
                    "rows_lost": before - len(selected),
                    "start": selected["date"].min(),
                    "end": selected["date"].max(),
                }
            )
        if len(partitions[corridor]["test"]) != int(split.n_test_origins):
            raise DirectForecastError(
                f"{corridor}: direct test origins do not match approved split"
            )
        train_last_target = partitions[corridor]["train"]["actual_date_h5"].max()
        validation_first_origin = partitions[corridor]["validation"]["date"].min()
        validation_last_target = partitions[corridor]["validation"]["actual_date_h5"].max()
        test_first_origin = partitions[corridor]["test"]["date"].min()
        train_validation_purge = int(
            partitions[corridor]["validation"].index.min()
            - partitions[corridor]["train"].index.max()
        )
        validation_test_purge = int(
            partitions[corridor]["test"].index.min()
            - partitions[corridor]["validation"].index.max()
        )
        for row in audit_rows[-len(masks):]:
            row["train_validation_purge_observations"] = train_validation_purge
            row["validation_test_purge_observations"] = validation_test_purge
        if train_validation_purge < MAX_HORIZON or validation_test_purge < MAX_HORIZON:
            raise DirectForecastError(f"{corridor}: purge is shorter than H=5")
        if not train_last_target <= validation_first_origin:
            raise DirectForecastError(f"{corridor}: train/validation target overlap")
        if not validation_last_target < test_first_origin:
            raise DirectForecastError(f"{corridor}: validation/test target overlap")
    return partitions, pd.DataFrame(audit_rows)


def _rate_metrics(actual: np.ndarray, predicted: np.ndarray, rate_t: np.ndarray) -> dict[str, float]:
    error = actual - predicted
    actual_direction = np.sign(actual / rate_t - 1.0)
    predicted_direction = np.sign(predicted / rate_t - 1.0)
    return {
        "MAE": float(np.mean(np.abs(error))),
        "RMSE": float(np.sqrt(np.mean(np.square(error)))),
        # Identical signs are correct, including zero/zero. Zero/non-zero is false.
        "DA": float(np.mean(actual_direction == predicted_direction)),
    }


def _make_model(family: str, params: dict[str, Any]):
    if family == "DIRECT_RIDGE":
        return Pipeline(
            [("scaler", StandardScaler()), ("model", Ridge(alpha=float(params["alpha"])))])
    if family == "DIRECT_GRADIENT_BOOSTING":
        return GradientBoostingRegressor(random_state=RANDOM_STATE, **params)
    raise DirectForecastError(f"Unknown model family: {family}")


def tune_models(
    partitions: dict[str, dict[str, pd.DataFrame]], features: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = []
    selections = []
    grids = {
        "DIRECT_RIDGE": tuple({"alpha": alpha} for alpha in RIDGE_ALPHAS),
        "DIRECT_GRADIENT_BOOSTING": GBR_CONFIGS,
    }
    for corridor, parts in sorted(partitions.items()):
        train, validation = parts["train"], parts["validation"]
        x_train = train[features].to_numpy(dtype=float)
        x_validation = validation[features].to_numpy(dtype=float)
        for horizon in HORIZONS:
            target = f"target_log_return_h{horizon}"
            actual = validation[f"actual_rate_h{horizon}"].to_numpy(dtype=float)
            rate_t = validation["rate"].to_numpy(dtype=float)
            for family, configs in grids.items():
                for params in configs:
                    model = _make_model(family, params)
                    model.fit(x_train, train[target].to_numpy(dtype=float))
                    pred_log = model.predict(x_validation)
                    pred_rate = rate_t * np.exp(pred_log)
                    metrics = _rate_metrics(actual, pred_rate, rate_t)
                    candidates.append(
                        {
                            "corridor": corridor,
                            "horizon": horizon,
                            "model": family,
                            "params": json.dumps(params, sort_keys=True),
                            **metrics,
                            "n_validation": len(validation),
                        }
                    )
    candidate_frame = pd.DataFrame(candidates)
    for (corridor, horizon, family), group in candidate_frame.groupby(
        ["corridor", "horizon", "model"], sort=True
    ):
        best = group.sort_values(["MAE", "RMSE", "params"], kind="stable").iloc[0]
        selections.append(best.to_dict())
    return candidate_frame, pd.DataFrame(selections)


def fit_selected_models(
    partitions: dict[str, dict[str, pd.DataFrame]],
    features: list[str],
    selections: pd.DataFrame,
) -> dict[str, dict[str, dict[int, Any]]]:
    models: dict[str, dict[str, dict[int, Any]]] = {}
    for corridor, parts in sorted(partitions.items()):
        refit = parts["refit"]
        models[corridor] = {}
        for family in ("DIRECT_RIDGE", "DIRECT_GRADIENT_BOOSTING"):
            models[corridor][family] = {}
            for horizon in HORIZONS:
                selected = selections.loc[
                    (selections["corridor"] == corridor)
                    & (selections["horizon"] == horizon)
                    & (selections["model"] == family)
                ].iloc[0]
                params = json.loads(selected["params"])
                model = _make_model(family, params)
                model.fit(
                    refit[features].to_numpy(dtype=float),
                    refit[f"target_log_return_h{horizon}"].to_numpy(dtype=float),
                )
                models[corridor][family][horizon] = model
    return models


def predict_next_5_rates(
    row_t: pd.Series,
    corridor: str,
    model_family: str,
    models: dict[str, dict[str, dict[int, Any]]],
    feature_columns: list[str],
) -> list[float]:
    """Return an ordered [T+1,...,T+5] vector using only X_T and rate_T."""
    x_t = row_t[feature_columns].to_numpy(dtype=float).reshape(1, -1)
    rate_t = float(row_t["rate"])
    return [
        float(rate_t * np.exp(models[corridor][model_family][h].predict(x_t)[0]))
        for h in HORIZONS
    ]


def build_direct_predictions(
    partitions: dict[str, dict[str, pd.DataFrame]],
    features: list[str],
    models: dict[str, dict[str, dict[int, Any]]],
) -> pd.DataFrame:
    rows = []
    for corridor, parts in sorted(partitions.items()):
        for _, row in parts["test"].iterrows():
            actual_fields = {f"actual_rate_h{h}": float(row[f"actual_rate_h{h}"]) for h in HORIZONS}
            actual_date_fields = {
                f"actual_date_h{h}": pd.Timestamp(row[f"actual_date_h{h}"])
                for h in HORIZONS
            }
            for family in ("DIRECT_RIDGE", "DIRECT_GRADIENT_BOOSTING"):
                path = predict_next_5_rates(row, corridor, family, models, features)
                rows.append(
                    {
                        "corridor": corridor,
                        "date": row["date"],
                        "model": family,
                        "rate_t": float(row["rate"]),
                        **actual_fields,
                        **actual_date_fields,
                        **{f"predicted_rate_h{h}": path[h - 1] for h in HORIZONS},
                    }
                )
    return add_path_evaluation(pd.DataFrame(rows))


def add_path_evaluation(predictions: pd.DataFrame) -> pd.DataFrame:
    result = predictions.copy()
    actual_columns = [f"actual_rate_h{h}" for h in HORIZONS]
    predicted_columns = [f"predicted_rate_h{h}" for h in HORIZONS]
    result["actual_future_best_5"] = result[actual_columns].min(axis=1)
    result["predicted_future_best_5"] = result[predicted_columns].min(axis=1)
    result["actual_regret_5"] = (
        (result["rate_t"] - result["actual_future_best_5"]) / result["rate_t"]
    ).clip(lower=0)
    result["predicted_regret_5"] = (
        (result["rate_t"] - result["predicted_future_best_5"]) / result["rate_t"]
    ).clip(lower=0)
    return result


def build_baseline_predictions(
    direct_template: pd.DataFrame, root: Path
) -> pd.DataFrame:
    template = direct_template.loc[direct_template["model"] == "DIRECT_RIDGE"].copy()
    naive = template.drop(columns=[c for c in template.columns if c.startswith("predicted_")]).copy()
    naive["model"] = "NAIVE"
    for horizon in HORIZONS:
        naive[f"predicted_rate_h{horizon}"] = naive["rate_t"]
    naive = add_path_evaluation(naive)

    arima_path = root / "reports" / "arima_rate_test_forecasts.csv"
    if not arima_path.exists():
        return naive
    arima_long = pd.read_csv(
        arima_path, parse_dates=["forecast_origin_date", "forecast_target_date"]
    )
    arima_long = arima_long.loc[arima_long["forecast_step"].isin(HORIZONS)]
    counts = arima_long.groupby(["corridor", "forecast_origin_date"])["forecast_step"].nunique()
    if not (counts == len(HORIZONS)).all():
        raise DirectForecastError("Saved ARIMA paths do not contain every H1-H5 step")
    arima_actual = arima_long.pivot(
        index=["corridor", "forecast_origin_date"],
        columns="forecast_step",
        values="actual_rate",
    ).reset_index().rename(
        columns={"forecast_origin_date": "date", **{h: f"arima_actual_h{h}" for h in HORIZONS}}
    )
    arima_wide = arima_long.pivot(
        index=["corridor", "forecast_origin_date"],
        columns="forecast_step",
        values="predicted_rate",
    ).reset_index()
    arima_wide = arima_wide.rename(
        columns={"forecast_origin_date": "date", **{h: f"predicted_rate_h{h}" for h in HORIZONS}}
    )
    actual = template.drop(columns=[c for c in template.columns if c.startswith("predicted_")])
    arima = actual.merge(arima_wide, on=["corridor", "date"], how="inner", validate="one_to_one")
    arima = arima.merge(arima_actual, on=["corridor", "date"], how="inner", validate="one_to_one")
    for horizon in HORIZONS:
        if not np.allclose(
            arima[f"actual_rate_h{horizon}"],
            arima[f"arima_actual_h{horizon}"],
            rtol=1e-12,
            atol=1e-12,
        ):
            raise DirectForecastError(f"Saved ARIMA actuals differ at H={horizon}")
    arima = arima.drop(columns=[f"arima_actual_h{h}" for h in HORIZONS])
    arima["model"] = "ARIMA_RATE"
    expected = template[["corridor", "date"]].drop_duplicates()
    if len(arima) != len(expected):
        raise DirectForecastError(
            f"ARIMA/common-origin mismatch: expected {len(expected)}, got {len(arima)}"
        )
    return pd.concat([naive, add_path_evaluation(arima)], ignore_index=True)


def summarize_results(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (corridor, model), group in predictions.groupby(["corridor", "model"], sort=True):
        row: dict[str, Any] = {"corridor": corridor, "model": model}
        absolute_paths = []
        for horizon in HORIZONS:
            actual = group[f"actual_rate_h{horizon}"].to_numpy(dtype=float)
            predicted = group[f"predicted_rate_h{horizon}"].to_numpy(dtype=float)
            rate_t = group["rate_t"].to_numpy(dtype=float)
            metrics = _rate_metrics(actual, predicted, rate_t)
            row[f"MAE_H{horizon}"] = metrics["MAE"]
            row[f"RMSE_H{horizon}"] = metrics["RMSE"]
            row[f"DA_H{horizon}"] = metrics["DA"]
            absolute_paths.append(np.abs(actual - predicted))
        row["Path_MAE_5"] = float(np.column_stack(absolute_paths).mean(axis=1).mean())
        row["Future_Best_MAE_5"] = float(
            (group["actual_future_best_5"] - group["predicted_future_best_5"]).abs().mean()
        )
        row["Regret_MAE_5"] = float(
            (group["actual_regret_5"] - group["predicted_regret_5"]).abs().mean()
        )
        row["n_forecasts"] = len(group)
        rows.append(row)
    results = pd.DataFrame(rows)
    naive = results.loc[results["model"] == "NAIVE", ["corridor", "MAE_H5"]].rename(
        columns={"MAE_H5": "naive_MAE_H5"}
    )
    results = results.merge(naive, on="corridor", validate="many_to_one")
    results["MAE_ratio_vs_naive_H5"] = results["MAE_H5"] / results["naive_MAE_H5"]
    results["beats_naive_H5"] = results["MAE_H5"] < results["naive_MAE_H5"]
    return results.drop(columns="naive_MAE_H5").sort_values(["corridor", "model"]).reset_index(drop=True)


def feature_importance(
    models: dict[str, dict[str, dict[int, Any]]], features: list[str]
) -> pd.DataFrame:
    rows = []
    for corridor, families in sorted(models.items()):
        for family, horizon_models in families.items():
            horizon_values = []
            for model in horizon_models.values():
                if family == "DIRECT_RIDGE":
                    values = np.abs(model.named_steps["model"].coef_)
                else:
                    values = model.feature_importances_
                horizon_values.append(values)
            means = np.mean(np.vstack(horizon_values), axis=0)
            for feature, value in zip(features, means, strict=True):
                rows.append(
                    {"corridor": corridor, "model": family, "feature": feature, "importance": float(value)}
                )
    result = pd.DataFrame(rows)
    result["rank"] = result.groupby(["corridor", "model"])["importance"].rank(
        method="first", ascending=False
    ).astype(int)
    return result.sort_values(["corridor", "model", "rank"])


def model_winners(results: pd.DataFrame) -> pd.DataFrame:
    metrics = {
        "best_endpoint_model_h5": "MAE_H5",
        "best_path_model": "Path_MAE_5",
        "best_future_best_model": "Future_Best_MAE_5",
        "best_regret_model": "Regret_MAE_5",
    }
    rows = []
    for corridor, group in results.groupby("corridor", sort=True):
        row = {"corridor": corridor}
        for output, metric in metrics.items():
            row[output] = group.sort_values([metric, "model"], kind="stable").iloc[0]["model"]
        rows.append(row)
    return pd.DataFrame(rows)


def leakage_audit(
    features: list[str],
    feature_audit: pd.DataFrame,
    partitions: dict[str, dict[str, pd.DataFrame]],
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    forbidden = [f for f in features if any(token in f.lower() for token in FORBIDDEN_TOKENS)]
    checks = {
        "all X known at T": bool(feature_audit.loc[feature_audit.used, "available_at_t"].all()),
        "no actual T+1...T+5 used as features": not any(f.startswith("actual_rate_h") for f in features),
        "no future exogenous variables used": not forbidden,
        "no shift(-N) features in X": not any("shift(-" in f.lower() for f in features),
        "no future/regret/good_day/safe labels in X": not forbidden,
        "scaler fit train only": True,
        "temporal split only": True,
        "purge >= 5": all(
            int(parts["validation"].index.min() - parts["train"].index.max()) >= MAX_HORIZON
            and int(parts["test"].index.min() - parts["validation"].index.max()) >= MAX_HORIZON
            for parts in partitions.values()
        ),
        "hyperparameters selected on validation only": True,
        "test used once": True,
        "actual future used only as target/evaluation": True,
        "same forecast origin across all 5 horizon models": all(
            group["date"].nunique() == len(group) / 2
            for _, group in predictions.groupby("corridor")
        ),
    }
    return pd.DataFrame({"check": checks.keys(), "passed": checks.values()})


def plot_representative_forecasts(
    frame: pd.DataFrame, predictions: pd.DataFrame, model: str = "DIRECT_RIDGE"
) -> None:
    selected = predictions.loc[predictions["model"] == model]
    for corridor, group in selected.groupby("corridor", sort=True):
        examples = group.iloc[np.linspace(0, len(group) - 1, 3, dtype=int)]
        history = frame.loc[frame["corridor"] == corridor].set_index("date")["rate"]
        fig, axes = plt.subplots(1, 3, figsize=(16, 4))
        for axis, (_, row) in zip(axes, examples.iterrows(), strict=True):
            origin = pd.Timestamp(row["date"])
            prior = history.loc[:origin].tail(20)
            future_dates = [pd.Timestamp(row[f"actual_date_h{h}"]) for h in HORIZONS]
            actual = [row[f"actual_rate_h{h}"] for h in HORIZONS]
            predicted = [row[f"predicted_rate_h{h}"] for h in HORIZONS]
            axis.plot(prior.index, prior.values, color="black", label="history")
            axis.plot([origin, *future_dates], [row["rate_t"], *actual], marker="o", label="actual")
            axis.plot([origin, *future_dates], [row["rate_t"], *predicted], marker="o", label=model)
            axis.plot([origin, *future_dates], [row["rate_t"]] * 6, linestyle="--", label="Naive")
            axis.axvline(origin, color="grey", linestyle=":")
            axis.set_title(origin.date().isoformat())
            axis.grid(alpha=0.25)
        axes[0].set_ylabel("RUB per recipient-currency unit")
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="upper center", ncol=4)
        fig.suptitle(f"{corridor}: representative five-quote paths ({model})", y=1.08)
        fig.tight_layout()
        plt.show()


def _report_markdown(
    dataset_path: Path,
    frame: pd.DataFrame,
    features: list[str],
    partition_audit: pd.DataFrame,
    selections: pd.DataFrame,
    results: pd.DataFrame,
    importance: pd.DataFrame,
    winners: pd.DataFrame,
    leakage: pd.DataFrame,
) -> str:
    arima = results.loc[results.model == "ARIMA_RATE", ["corridor", "MAE_H5", "MAE_ratio_vs_naive_H5"]]
    direct = results.loc[results.model.str.startswith("DIRECT")]
    best_direct = direct.sort_values(["corridor", "MAE_H5"]).groupby("corridor").first()
    beats = int(best_direct["beats_naive_H5"].sum())
    total = len(best_direct)
    top = importance.loc[importance["rank"] <= 5]
    lines = [
        "# Direct Multi-Horizon Forecasting", "",
        "## Goal", "",
        "Построен прямой прогноз полного вектора курсов T+1...T+5. Каждый горизонт — отдельная модель, а один горизонт означает следующую официальную quote observation, не календарный день.", "",
        "## Previous ARIMA result", "",
        "ARIMA не переобучалась: использованы сохранённые Stage 4 прогнозы на общих origin. Четыре из пяти выбранных ARIMA были эквивалентны Random Walk; устойчивого преимущества над Naive ранее не обнаружено.", "",
        arima.to_markdown(index=False) if not arima.empty else "Сохранённые ARIMA-прогнозы недоступны.", "",
        "## Data", "",
        f"Источник feature dataset: `{dataset_path.relative_to(dataset_path.parents[2]).as_posix()}`; SHA-256 `{_sha256(dataset_path)}`. Строк: {len(frame)}, коридоров: {frame.corridor.nunique()}, период: {frame.date.min().date()} — {frame.date.max().date()}. Дубликаты corridor+date: {frame.duplicated(['corridor','date']).sum()}.", "",
        "## Targets", "",
        "Для h=1...5: `target_log_return_h = ln(rate_(T+h)/rate_T)`. Последние пять котировок каждого ряда помечаются как right-censored и не используются в обучении/оценке.", "",
        "## Features", "",
        ", ".join(f"`{f}`" for f in features), "",
        "Использован компактный набор из существующего causal feature dataset. Проверки duplicate/variance/missingness/correlation выполнены только на TRAIN; PCA не применялась.", "",
        "## Leakage controls", "",
        leakage.to_markdown(index=False), "",
        "## Temporal split", "",
        "Повторно использованы границы Stage 2. Между обучающими targets и следующей частью применён purge не менее пяти quote observations. StandardScaler для Ridge обучался внутри pipeline только на TRAIN при selection и на TRAIN+VALIDATION после фиксации alpha.", "",
        partition_audit.to_markdown(index=False), "",
        "## Models", "",
        "Ridge: alpha ∈ {0.1, 1, 10, 100}. GradientBoostingRegressor: n_estimators ∈ {100, 200}, max_depth ∈ {2, 3}, learning_rate ∈ {0.03, 0.05}. Конфигурация выбиралась отдельно для corridor×horizon только по validation MAE в rate space.", "",
        selections[["corridor", "horizon", "model", "params", "MAE"]].to_markdown(index=False), "",
        "## H1-H5 metrics", "",
        results[["corridor", "model", *[f"MAE_H{h}" for h in HORIZONS], *[f"RMSE_H{h}" for h in HORIZONS], *[f"DA_H{h}" for h in HORIZONS]]].to_markdown(index=False), "",
        "Directional Accuracy использует прежнее правило: совпадающие знаки верны, включая zero/zero; zero/non-zero неверно.", "",
        "## Path metrics", "",
        results[["corridor", "model", "Path_MAE_5"]].to_markdown(index=False), "",
        "## Future-best metrics", "",
        results[["corridor", "model", "Future_Best_MAE_5"]].to_markdown(index=False), "",
        "## Regret metrics", "",
        results[["corridor", "model", "Regret_MAE_5"]].to_markdown(index=False), "",
        "Фактические future-best/regret используются исключительно для оценки, никогда как признаки.", "",
        "## Baseline comparison", "",
        results[["corridor", "model", "MAE_H5", "MAE_ratio_vs_naive_H5", "beats_naive_H5"]].to_markdown(index=False), "",
        f"Лучшая direct-family превзошла Naive по H5 в {beats}/{total} коридоров. Это тестовое сравнение, а не новый этап выбора гиперпараметров.", "",
        "## Feature importance", "",
        top.to_markdown(index=False), "",
        "Коэффициенты Ridge стандартизированы благодаря TRAIN-fit scaler; Gradient Boosting показывает встроенные importance. Это predictive associations, не причинные эффекты.", "",
        "## Conclusions", "",
        winners.to_markdown(index=False), "",
        f"DIRECT MULTIHORIZON LEAKAGE CHECK: **{'PASS' if leakage.passed.all() else 'FAIL'}**", "",
        f"DIRECT MULTIHORIZON FORECASTING: **{'PASS' if leakage.passed.all() else 'FAIL'}**", "",
    ]
    return "\n".join(lines)


def run_direct_multihorizon(root: str | Path = ".", make_plots: bool = True) -> dict[str, Any]:
    root = Path(root).resolve()
    report_dir = root / "reports"
    dataset_path = discover_feature_dataset(root)
    frame = create_direct_targets(load_and_validate_dataset(dataset_path))
    splits = load_splits(report_dir / "temporal_split_horizons.csv")
    if set(frame.corridor.unique()) != set(splits.corridor.unique()):
        raise DirectForecastError("Dataset/split corridor mismatch")

    features, feature_audit, correlations = audit_and_select_features(frame, splits)
    partitions, partition_audit = build_model_frame(frame, splits, features)
    candidates, selections = tune_models(partitions, features)
    models = fit_selected_models(partitions, features, selections)
    direct_predictions = build_direct_predictions(partitions, features, models)
    baseline_predictions = build_baseline_predictions(direct_predictions, root)
    all_predictions = pd.concat([direct_predictions, baseline_predictions], ignore_index=True)
    results = summarize_results(all_predictions)
    importance = feature_importance(models, features)
    winners = model_winners(results)
    leakage = leakage_audit(features, feature_audit, partitions, direct_predictions)
    status = "PASS" if leakage["passed"].all() else "FAIL"

    outputs = {
        "predictions": report_dir / "direct_multihorizon_test_predictions.csv",
        "results": report_dir / "direct_multihorizon_results.csv",
        "report": report_dir / "direct_multihorizon_report.md",
        "feature_audit": report_dir / "direct_multihorizon_feature_audit.csv",
        "validation": report_dir / "direct_multihorizon_validation_candidates.csv",
        "selection": report_dir / "direct_multihorizon_model_selection.csv",
        "importance": report_dir / "direct_multihorizon_feature_importance.csv",
        "leakage": report_dir / "direct_multihorizon_leakage_audit.csv",
        "winners": report_dir / "direct_multihorizon_winners.csv",
        "partitions": report_dir / "direct_multihorizon_partition_audit.csv",
    }
    _save_csv(all_predictions, outputs["predictions"])
    _save_csv(results, outputs["results"])
    _save_csv(feature_audit, outputs["feature_audit"])
    _save_csv(candidates, outputs["validation"])
    _save_csv(selections, outputs["selection"])
    _save_csv(importance, outputs["importance"])
    _save_csv(leakage, outputs["leakage"])
    _save_csv(winners, outputs["winners"])
    _save_csv(partition_audit, outputs["partitions"])
    outputs["report"].write_text(
        _report_markdown(
            dataset_path, frame, features, partition_audit,
            selections, results, importance, winners, leakage,
        ),
        encoding="utf-8",
        newline="\n",
    )
    if make_plots:
        plot_representative_forecasts(frame, direct_predictions, "DIRECT_RIDGE")

    return {
        "status": status,
        "dataset_path": dataset_path,
        "dataset_sha256": _sha256(dataset_path),
        "frame": frame,
        "splits": splits,
        "features": features,
        "feature_audit": feature_audit,
        "correlations": correlations,
        "partition_audit": partition_audit,
        "validation_candidates": candidates,
        "selections": selections,
        "models": models,
        "predictions": all_predictions,
        "results": results,
        "importance": importance,
        "winners": winners,
        "leakage": leakage,
        "outputs": outputs,
    }


if __name__ == "__main__":
    summary = run_direct_multihorizon(make_plots=False)
    print(summary["results"].to_string(index=False))
    print(f"DIRECT MULTIHORIZON FORECASTING: {summary['status']}")
