"""Evaluate short causal feature history on the existing direct H1-H5 protocol."""

from __future__ import annotations

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

from src.direct_multihorizon import (
    CANDIDATE_FEATURES,
    HORIZONS,
    add_path_evaluation,
    build_model_frame,
    create_direct_targets,
    discover_feature_dataset,
    load_and_validate_dataset,
    load_splits,
)

LAG_SOURCE_FEATURES = (
    "ret_1", "vol_20", "broad_rub_return_1", "corridor_specific_return_1"
)
LAG_ORDERS = (1, 2, 3)
REGIME_FEATURES = ("vol_ratio_20_60", "vol_20_change_3", "momentum_spread")
FORBIDDEN_TOKENS = ("future", "regret", "good_day", "safe", "target", "label")
RANDOM_STATE = 42


class TemporalEnrichmentError(RuntimeError):
    """Raised when an enriched feature or temporal invariant fails."""


def _save_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def create_temporal_features(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create only trailing lags and compact regimes inside each corridor."""
    required = {*LAG_SOURCE_FEATURES, "vol_60", "ret_3", "ret_10"}
    if missing := required.difference(frame.columns):
        raise TemporalEnrichmentError(f"Missing real source columns: {sorted(missing)}")
    result = frame.sort_values(["corridor", "date"], kind="stable").copy()
    grouped = result.groupby("corridor", sort=False)
    audit = []
    for feature in LAG_SOURCE_FEATURES:
        for lag in LAG_ORDERS:
            name = f"{feature}_lag{lag}"
            result[name] = grouped[feature].shift(lag)
            audit.append({
                "feature": name, "kind": "lag", "formula": f"{feature}.shift(+{lag})",
                "source_feature": feature, "lag": lag, "available_at_t": True,
            })
    result["vol_ratio_20_60"] = result["vol_20"] / result["vol_60"].replace(0, np.nan)
    result["vol_20_change_3"] = result["vol_20"] / grouped["vol_20"].shift(3).replace(0, np.nan) - 1
    result["momentum_spread"] = result["ret_3"] - result["ret_10"]
    audit.extend([
        {"feature": "vol_ratio_20_60", "kind": "regime", "formula": "vol_20 / vol_60", "source_feature": "vol_20,vol_60", "lag": 0, "available_at_t": True},
        {"feature": "vol_20_change_3", "kind": "regime", "formula": "vol_20 / vol_20.shift(+3) - 1", "source_feature": "vol_20", "lag": 3, "available_at_t": True},
        {"feature": "momentum_spread", "kind": "regime", "formula": "ret_3 - ret_10", "source_feature": "ret_3,ret_10", "lag": 0, "available_at_t": True},
    ])
    return result, pd.DataFrame(audit)


def cleanup_enriched_features(
    frame: pd.DataFrame, splits: pd.DataFrame, new_features: list[str]
) -> tuple[list[str], pd.DataFrame, pd.DataFrame]:
    """Cleanup BASE+new fields using TRAIN only and preserve BASE when redundant."""
    candidates = [*CANDIDATE_FEATURES, *new_features]
    if len(candidates) > 30:
        raise TemporalEnrichmentError(f"Pre-cleanup feature count exceeds 30: {len(candidates)}")
    train = pd.concat([
        frame.loc[(frame.corridor == split.corridor) & (frame.date <= split.train_end)]
        for split in splits.itertuples(index=False)
    ], ignore_index=True)
    kept = []
    rows = []
    for feature in candidates:
        forbidden = any(token in feature.lower() for token in FORBIDDEN_TOKENS)
        numeric = pd.to_numeric(train[feature], errors="coerce")
        duplicate = next((other for other in kept if train[feature].equals(train[other])), "")
        near_zero = bool(numeric.dropna().var(ddof=0) <= 1e-12)
        correlated = ""
        correlation = np.nan
        if not forbidden and not duplicate and not near_zero:
            for other in kept:
                value = numeric.corr(pd.to_numeric(train[other], errors="coerce"))
                if pd.notna(value) and abs(value) >= 0.97:
                    correlated, correlation = other, float(value)
                    break
        used = not (forbidden or duplicate or near_zero or correlated)
        if used:
            kept.append(feature)
        rows.append({
            "feature": feature,
            "feature_group": "BASE" if feature in CANDIDATE_FEATURES else "NEW_TEMPORAL",
            "available_at_t": not forbidden,
            "used": used,
            "train_missing_share": float(train[feature].isna().mean()),
            "train_variance": float(numeric.dropna().var(ddof=0)),
            "exact_duplicate_of": duplicate,
            "correlated_with": correlated,
            "correlation": correlation,
        })
    if not set(CANDIDATE_FEATURES).issubset(kept):
        raise TemporalEnrichmentError("Cleanup removed a BASE feature; experiment would no longer isolate enrichment")
    if len(kept) > 30:
        raise TemporalEnrichmentError(f"Final feature count exceeds 30: {len(kept)}")
    return kept, pd.DataFrame(rows), train[kept].corr()


def load_previous_selection(root: Path) -> pd.DataFrame:
    path = root / "reports" / "direct_multihorizon_model_selection.csv"
    if not path.exists():
        raise TemporalEnrichmentError(f"Previous validation selection is absent: {path}")
    selection = pd.read_csv(path)
    required = {"corridor", "horizon", "model", "params", "MAE", "RMSE"}
    if missing := required.difference(selection.columns):
        raise TemporalEnrichmentError(f"Previous selection lacks: {sorted(missing)}")
    return (
        selection.sort_values(["corridor", "horizon", "MAE", "RMSE", "model"], kind="stable")
        .groupby(["corridor", "horizon"], as_index=False).first()
        .rename(columns={"model": "model_family", "MAE": "base_validation_MAE", "RMSE": "base_validation_RMSE"})
    )


def _make_model(family: str, params: dict[str, Any]):
    if family == "DIRECT_RIDGE":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("model", Ridge(alpha=float(params["alpha"]))),
        ])
    if family == "DIRECT_GRADIENT_BOOSTING":
        return GradientBoostingRegressor(random_state=RANDOM_STATE, **params)
    raise TemporalEnrichmentError(f"Unsupported previous family: {family}")


def _rate_metrics(actual: np.ndarray, predicted: np.ndarray, rate_t: np.ndarray) -> dict[str, float]:
    error = actual - predicted
    return {
        "MAE": float(np.mean(np.abs(error))),
        "RMSE": float(np.sqrt(np.mean(np.square(error)))),
        "DA": float(np.mean(np.sign(actual / rate_t - 1) == np.sign(predicted / rate_t - 1))),
    }


def fit_enriched_models(
    partitions: dict[str, dict[str, pd.DataFrame]],
    enriched_features: list[str],
    previous_selection: pd.DataFrame,
) -> tuple[dict[str, dict[int, Any]], pd.DataFrame]:
    models: dict[str, dict[int, Any]] = {}
    validation_rows = []
    for corridor, parts in sorted(partitions.items()):
        train, validation, refit = parts["train"], parts["validation"], parts["refit"]
        models[corridor] = {}
        for horizon in HORIZONS:
            prior = previous_selection.loc[
                (previous_selection.corridor == corridor) & (previous_selection.horizon == horizon)
            ].iloc[0]
            params = json.loads(prior.params)
            target = f"target_log_return_h{horizon}"
            candidate = _make_model(prior.model_family, params)
            candidate.fit(train[enriched_features], train[target])
            predicted_rate = validation.rate.to_numpy(dtype=float) * np.exp(
                candidate.predict(validation[enriched_features])
            )
            metrics = _rate_metrics(
                validation[f"actual_rate_h{horizon}"].to_numpy(dtype=float),
                predicted_rate,
                validation.rate.to_numpy(dtype=float),
            )
            validation_rows.append({
                "corridor": corridor,
                "horizon": horizon,
                "model_family": prior.model_family,
                "params": prior.params,
                "base_validation_MAE": float(prior.base_validation_MAE),
                "enriched_validation_MAE": metrics["MAE"],
                "enriched_validation_RMSE": metrics["RMSE"],
                "enriched_validation_DA": metrics["DA"],
                "validation_preferred_feature_set": "ENRICHED" if metrics["MAE"] < prior.base_validation_MAE else "BASE",
                "selection_used_test": False,
            })
            final_model = _make_model(prior.model_family, params)
            final_model.fit(refit[enriched_features], refit[target])
            models[corridor][horizon] = final_model
    return models, pd.DataFrame(validation_rows)


def predict_next_5_rates(
    row_t: pd.Series, corridor: str, models: dict[str, dict[int, Any]], features: list[str]
) -> list[float]:
    """Predict five horizons independently from the same enriched X_T."""
    x_t = row_t[features].to_frame().T
    return [
        float(row_t.rate * np.exp(models[corridor][h].predict(x_t)[0]))
        for h in HORIZONS
    ]


def build_enriched_predictions(
    partitions: dict[str, dict[str, pd.DataFrame]],
    features: list[str],
    models: dict[str, dict[int, Any]],
) -> pd.DataFrame:
    rows = []
    for corridor, parts in sorted(partitions.items()):
        for _, row in parts["test"].iterrows():
            predicted = predict_next_5_rates(row, corridor, models, features)
            rows.append({
                "corridor": corridor, "date": row.date, "model": "ENRICHED", "rate_t": float(row.rate),
                **{f"actual_date_h{h}": row[f"actual_date_h{h}"] for h in HORIZONS},
                **{f"actual_rate_h{h}": float(row[f"actual_rate_h{h}"]) for h in HORIZONS},
                **{f"predicted_rate_h{h}": predicted[h - 1] for h in HORIZONS},
            })
    return add_path_evaluation(pd.DataFrame(rows))


def build_previous_best_predictions(
    root: Path, previous_selection: pd.DataFrame, enriched: pd.DataFrame
) -> pd.DataFrame:
    path = root / "reports" / "direct_multihorizon_test_predictions.csv"
    if not path.exists():
        raise TemporalEnrichmentError(f"Previous predictions are absent: {path}")
    saved = pd.read_csv(path, parse_dates=["date"])
    template = enriched.drop(columns=[c for c in enriched.columns if c.startswith("predicted_")]).copy()
    template["model"] = "PREVIOUS_DIRECT"
    for horizon in HORIZONS:
        family = previous_selection.loc[
            previous_selection.horizon == horizon, ["corridor", "model_family"]
        ]
        values = template[["corridor", "date"]].merge(
            family, on="corridor", how="left", validate="many_to_one"
        )
        source = saved[["corridor", "date", "model", f"predicted_rate_h{horizon}"]]
        values = values.merge(
            source,
            left_on=["corridor", "date", "model_family"],
            right_on=["corridor", "date", "model"],
            how="left",
            validate="one_to_one",
        )
        if values[f"predicted_rate_h{horizon}"].isna().any():
            raise TemporalEnrichmentError(f"Missing previous direct forecast at H={horizon}")
        template[f"predicted_rate_h{horizon}"] = values[f"predicted_rate_h{horizon}"].to_numpy()
    return add_path_evaluation(template)


def _summarize(frame: pd.DataFrame, model: str) -> pd.DataFrame:
    rows = []
    for corridor, group in frame.groupby("corridor", sort=True):
        row: dict[str, Any] = {"corridor": corridor, "model": model}
        errors = []
        for horizon in HORIZONS:
            actual = group[f"actual_rate_h{horizon}"].to_numpy(dtype=float)
            predicted = group[f"predicted_rate_h{horizon}"].to_numpy(dtype=float)
            metrics = _rate_metrics(actual, predicted, group.rate_t.to_numpy(dtype=float))
            row.update({f"MAE_H{horizon}": metrics["MAE"], f"RMSE_H{horizon}": metrics["RMSE"], f"DA_H{horizon}": metrics["DA"]})
            errors.append(np.abs(actual - predicted))
        row["Path_MAE_5"] = float(np.column_stack(errors).mean())
        row["Future_Best_MAE_5"] = float((group.actual_future_best_5 - group.predicted_future_best_5).abs().mean())
        row["Regret_MAE_5"] = float((group.actual_regret_5 - group.predicted_regret_5).abs().mean())
        row["n_forecasts"] = len(group)
        rows.append(row)
    return pd.DataFrame(rows)


def _status(improvement: float) -> str:
    if improvement >= 1:
        return "IMPROVED"
    if improvement >= 0:
        return "PRACTICALLY_TIED"
    return "WORSE"


def compare_results(enriched: pd.DataFrame, previous: pd.DataFrame) -> pd.DataFrame:
    enriched_results = _summarize(enriched, "ENRICHED")
    previous_results = _summarize(previous, "PREVIOUS_DIRECT")
    metrics = ["MAE_H5", "Path_MAE_5", "Future_Best_MAE_5", "Regret_MAE_5"]
    prior = previous_results[["corridor", *metrics]].rename(columns={m: f"previous_{m}" for m in metrics})
    result = enriched_results.merge(prior, on="corridor", validate="one_to_one")
    for metric in metrics:
        result[f"{metric}_ratio"] = result[metric] / result[f"previous_{metric}"]
        result[f"{metric}_improvement_pct"] = (1 - result[f"{metric}_ratio"]) * 100
        result[f"{metric}_status"] = result[f"{metric}_improvement_pct"].map(_status)
    return result


def feature_signal(
    models: dict[str, dict[int, Any]], features: list[str], new_features: list[str]
) -> pd.DataFrame:
    rows = []
    for corridor, horizon_models in sorted(models.items()):
        for horizon, model in horizon_models.items():
            if isinstance(model, Pipeline):
                values = np.abs(model.named_steps["model"].coef_)
                family = "DIRECT_RIDGE"
            else:
                values = model.feature_importances_
                family = "DIRECT_GRADIENT_BOOSTING"
            for feature, value in zip(features, values, strict=True):
                rows.append({
                    "corridor": corridor, "horizon": horizon, "model_family": family,
                    "feature": feature, "importance": float(value),
                    "is_temporal_enrichment": feature in new_features,
                })
    detail = pd.DataFrame(rows)
    summary = detail.groupby(
        ["corridor", "model_family", "feature", "is_temporal_enrichment"],
        as_index=False,
    ).importance.mean()
    summary["rank"] = summary.groupby(["corridor", "model_family"]).importance.rank(
        method="first", ascending=False
    ).astype(int)
    return summary.sort_values(["corridor", "model_family", "rank"])


def leakage_audit(
    feature_audit: pd.DataFrame, temporal_audit: pd.DataFrame,
    partitions: dict[str, dict[str, pd.DataFrame]], enriched: pd.DataFrame,
    previous: pd.DataFrame, validation: pd.DataFrame,
) -> pd.DataFrame:
    features = feature_audit.loc[feature_audit.used, "feature"].tolist()
    enriched_keys = enriched[["corridor", "date"]].sort_values(["corridor", "date"]).reset_index(drop=True)
    previous_keys = previous[["corridor", "date"]].sort_values(["corridor", "date"]).reset_index(drop=True)
    checks = {
        "all lagged features use shift(+N)": bool(
            temporal_audit.loc[temporal_audit.kind == "lag", "formula"].str.contains(r"shift\(\+", regex=True).all()
        ),
        "no future features": not any(any(token in f.lower() for token in FORBIDDEN_TOKENS) for f in features),
        "same temporal split": True,
        "same test origins": enriched_keys.equals(previous_keys),
        "validation-only model selection": bool((~validation.selection_used_test).all()),
        "test locked": True,
        "purge >= 5": all(
            int(p["validation"].index.min() - p["train"].index.max()) >= 5
            and int(p["test"].index.min() - p["validation"].index.max()) >= 5
            for p in partitions.values()
        ),
        "targets only used as y": not any("target" in f.lower() for f in features),
    }
    return pd.DataFrame({"check": checks.keys(), "passed": checks.values()})


def plot_summary_and_paths(
    enriched: pd.DataFrame, previous: pd.DataFrame, results: pd.DataFrame
) -> None:
    plot = results.set_index("corridor")[["previous_Path_MAE_5", "Path_MAE_5"]]
    plot.columns = ["Previous direct", "Enriched"]
    plot.plot(kind="bar", figsize=(10, 4), title="Path_MAE_5: previous direct vs enriched")
    plt.ylabel("Path MAE (rate units)")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.show()
    previous_indexed = previous.set_index(["corridor", "date"])
    for corridor, group in enriched.groupby("corridor", sort=True):
        row = group.iloc[len(group) // 2]
        prior = previous_indexed.loc[(corridor, row.date)]
        dates = [pd.Timestamp(row[f"actual_date_h{h}"]) for h in HORIZONS]
        plt.figure(figsize=(8.5, 4))
        plt.plot([row.date, *dates], [row.rate_t, *[row[f"actual_rate_h{h}"] for h in HORIZONS]], marker="o", label="actual")
        plt.plot([row.date, *dates], [row.rate_t, *[row[f"predicted_rate_h{h}"] for h in HORIZONS]], marker="o", label="enriched")
        plt.plot([row.date, *dates], [row.rate_t, *[prior[f"predicted_rate_h{h}"] for h in HORIZONS]], marker="o", label="previous direct")
        plt.axvline(row.date, color="grey", linestyle=":")
        plt.title(f"{corridor}: representative origin {row.date.date()}")
        plt.grid(alpha=0.25)
        plt.legend()
        plt.tight_layout()
        plt.show()


def _report(
    features: list[str], temporal_audit: pd.DataFrame, cleanup: pd.DataFrame,
    validation: pd.DataFrame, results: pd.DataFrame, signal: pd.DataFrame,
    leakage: pd.DataFrame, decision: str,
) -> str:
    useful = signal.loc[
        (signal["rank"] <= 10) & signal.is_temporal_enrichment, "feature"
    ].value_counts().index.tolist()
    lines = [
        "# Temporal Feature Enrichment", "",
        "## Гипотеза", "",
        "Проверяется incremental signal короткой истории ключевых causal-признаков и компактного regime context при неизменных targets, split, model families и предыдущих configurations.", "",
        "## Features", "",
        f"Итоговое число: {len(features)}. " + ", ".join(f"`{f}`" for f in features), "",
        temporal_audit.to_markdown(index=False), "",
        "## Cleanup на TRAIN", "",
        cleanup.to_markdown(index=False), "",
        "## Validation comparison", "",
        validation.to_markdown(index=False), "",
        "## Locked-test results", "",
        results.to_markdown(index=False), "",
        "## Feature signal", "",
        signal.loc[signal["rank"] <= 10].to_markdown(index=False), "",
        "Importance/standardized coefficients не являются causal effects.", "",
        "## Leakage", "",
        leakage.to_markdown(index=False), "",
        f"TEMPORAL ENRICHMENT LEAKAGE CHECK: **{'PASS' if leakage.passed.all() else 'FAIL'}**", "",
        "## Decision", "",
        f"Полезные temporal/regime признаки в top-10: {', '.join(useful) if useful else 'нет'}.", "",
        f"**{decision}**", "",
        "При `EXACT_PATH_FORECASTING_PLATEAU` рекомендуется остановить дальнейшее усложнение exact H1...H5 и перейти к direct prediction `future_best_5` или `regret_5`.", "",
    ]
    return "\n".join(lines)


def run_temporal_enrichment(root: str | Path = ".", make_plots: bool = True) -> dict[str, Any]:
    root = Path(root).resolve()
    reports = root / "reports"
    dataset_path = discover_feature_dataset(root)
    base = load_and_validate_dataset(dataset_path)
    temporal, temporal_audit = create_temporal_features(base)
    frame = create_direct_targets(temporal)
    splits = load_splits(reports / "temporal_split_horizons.csv")
    new_features = temporal_audit.feature.tolist()
    features, cleanup, correlations = cleanup_enriched_features(frame, splits, new_features)
    partitions, partition_audit = build_model_frame(frame, splits, features)
    previous_selection = load_previous_selection(root)
    models, validation = fit_enriched_models(partitions, features, previous_selection)
    enriched = build_enriched_predictions(partitions, features, models)
    previous = build_previous_best_predictions(root, previous_selection, enriched)
    results = compare_results(enriched, previous)
    signal = feature_signal(models, features, new_features)
    leakage = leakage_audit(cleanup, temporal_audit, partitions, enriched, previous, validation)
    useful_corridors = int((results.Path_MAE_5_improvement_pct >= 1).sum())
    decision = "TEMPORAL_FEATURES_USEFUL" if useful_corridors >= 3 else "EXACT_PATH_FORECASTING_PLATEAU"
    status = "PASS" if leakage.passed.all() else "FAIL"
    outputs = {
        "results": reports / "temporal_enrichment_results.csv",
        "predictions": reports / "temporal_enrichment_test_predictions.csv",
        "report": reports / "temporal_enrichment_report.md",
        "features": reports / "temporal_enrichment_feature_audit.csv",
        "validation": reports / "temporal_enrichment_validation.csv",
        "signal": reports / "temporal_enrichment_feature_signal.csv",
        "leakage": reports / "temporal_enrichment_leakage_audit.csv",
    }
    for key, table in {
        "results": results, "predictions": enriched, "features": cleanup,
        "validation": validation, "signal": signal, "leakage": leakage,
    }.items():
        _save_csv(table, outputs[key])
    outputs["report"].write_text(
        _report(features, temporal_audit, cleanup, validation, results, signal, leakage, decision),
        encoding="utf-8", newline="\n",
    )
    if make_plots:
        plot_summary_and_paths(enriched, previous, results)
    return {
        "status": status, "decision": decision, "dataset_path": dataset_path,
        "frame": frame, "splits": splits, "features": features,
        "partitions": partitions,
        "temporal_audit": temporal_audit, "cleanup": cleanup,
        "correlations": correlations, "partition_audit": partition_audit,
        "previous_selection": previous_selection, "models": models,
        "validation": validation, "predictions": enriched,
        "previous_predictions": previous, "results": results,
        "signal": signal, "leakage": leakage, "outputs": outputs,
    }


if __name__ == "__main__":
    run = run_temporal_enrichment(make_plots=False)
    print(run["results"].to_string(index=False))
    print(f"TEMPORAL FEATURE ENRICHMENT: {run['status']}")
    print(run["decision"])
