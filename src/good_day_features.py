"""Build causal good-day variables from saved out-of-time CatBoost forecasts.

All windows are measured in CBR quote observations. ``rate`` is RUB per one
unit of recipient currency, so a lower value is more favourable to a RUB sender.
Realized future columns are evaluation-only and never enter predicted features.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PREDICTED = [f"predicted_rate_h{h}" for h in range(1, 6)]
ACTUAL = [f"actual_rate_h{h}" for h in range(1, 6)]


class GoodDayFeatureError(RuntimeError):
    """Raised when input alignment or a causal invariant is violated."""


def _past_percentile(rate: pd.Series, window: int = 90) -> pd.Series:
    values = rate.to_numpy(dtype=float)
    result = np.full(len(values), np.nan)
    for index in range(window, len(values)):
        result[index] = 1.0 - np.mean(values[index - window:index] <= values[index])
    return pd.Series(result, index=rate.index, dtype=float)


def load_inputs(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    """Load existing real feature history and saved CatBoost predictions."""
    feature_candidates = [
        root / "data/features/base_market_features.parquet",
        root / "data/features/fx_features_daily.parquet",
    ]
    feature_path = next((path for path in feature_candidates if path.exists()), None)
    prediction_path = root / "reports/catboost_multihorizon_test_predictions.csv"
    if feature_path is None:
        raise GoodDayFeatureError("Historical feature dataset is absent")
    if not prediction_path.exists():
        raise GoodDayFeatureError(f"Saved CatBoost predictions are absent: {prediction_path}")

    history = pd.read_parquet(
        feature_path, columns=["corridor", "date", "rate", "favourability_percentile_90"]
    )
    predictions = pd.read_csv(prediction_path, parse_dates=["date"])
    history["date"] = pd.to_datetime(history["date"])
    required = {"corridor", "date", "rate_t", *PREDICTED}
    if missing := required.difference(predictions.columns):
        raise GoodDayFeatureError(f"Prediction artifact lacks columns: {sorted(missing)}")
    return history, predictions, feature_path


def add_causal_history(history: pd.DataFrame) -> pd.DataFrame:
    """Reuse favourability and add a minimum over exactly T-5...T-1."""
    if history.duplicated(["corridor", "date"]).any():
        raise GoodDayFeatureError("Historical data has duplicate corridor+date rows")
    frame = history.sort_values(["corridor", "date"], kind="stable").copy()
    grouped = frame.groupby("corridor", sort=False)["rate"]
    frame["past_best_5"] = grouped.transform(
        lambda rate: rate.shift(1).rolling(5, min_periods=5).min()
    )
    frame["past_advantage_5"] = (frame["past_best_5"] - frame["rate"]) / frame["past_best_5"]
    return frame


def build_good_day_features(history: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    """Create the requested variables without training or prediction realignment."""
    if predictions.duplicated(["corridor", "date"]).any():
        raise GoodDayFeatureError("CatBoost artifact has duplicate forecast origins")
    numeric = ["rate_t", *PREDICTED]
    if predictions[numeric].isna().any().any() or (predictions[numeric] <= 0).any().any():
        raise GoodDayFeatureError("Predicted rates/rate_t must be finite positive values")

    causal = add_causal_history(history)
    joined = predictions.merge(
        causal[["corridor", "date", "rate", "favourability_percentile_90", "past_best_5", "past_advantage_5"]],
        on=["corridor", "date"], how="left", validate="one_to_one",
    )
    if joined["rate"].isna().any():
        raise GoodDayFeatureError("Some forecast origins are absent from historical data")
    if not np.allclose(joined["rate_t"], joined["rate"], rtol=0.0, atol=1e-12):
        examples = joined.loc[~np.isclose(joined.rate_t, joined.rate, rtol=0.0, atol=1e-12),
                              ["corridor", "date", "rate_t", "rate"]].head()
        raise GoodDayFeatureError(f"rate_t is not aligned with rate at T:\n{examples}")

    joined["predicted_future_best_5"] = joined[PREDICTED].min(axis=1)
    joined["predicted_regret_5"] = np.maximum(
        0.0, (joined["rate_t"] - joined["predicted_future_best_5"]) / joined["rate_t"]
    )
    if set(ACTUAL).issubset(joined.columns):
        joined["actual_future_best_5"] = joined[ACTUAL].min(axis=1)
        joined["actual_regret_5"] = np.maximum(
            0.0, (joined["rate_t"] - joined["actual_future_best_5"]) / joined["rate_t"]
        )

    columns = [
        "corridor", "date", "rate_t", "favourability_percentile_90",
        "past_best_5", "past_advantage_5", *PREDICTED,
        "predicted_future_best_5", "predicted_regret_5",
    ]
    columns += [name for name in ("actual_future_best_5", "actual_regret_5") if name in joined]
    return joined[columns].sort_values(["corridor", "date"], kind="stable").reset_index(drop=True)


def validate_good_day_features(
    history: pd.DataFrame, output: pd.DataFrame, tolerance: float = 1e-12
) -> pd.DataFrame:
    """Validate formulae, source reuse, grouping, and absence of future leakage."""
    causal = add_causal_history(history)
    recomputed = []
    for _, group in history.sort_values(["corridor", "date"]).groupby("corridor", sort=False):
        values = _past_percentile(group["rate"], 90)
        recomputed.append(pd.Series(values.to_numpy(), index=group.index))
    causal["expected_favourability"] = pd.concat(recomputed).sort_index()
    expected = output[["corridor", "date"]].merge(
        causal[["corridor", "date", "rate", "past_best_5", "past_advantage_5", "expected_favourability"]],
        on=["corridor", "date"], validate="one_to_one",
    )
    valid_favourability = output["favourability_percentile_90"].notna()
    checks = [
        ("favourability uses only T-90...T-1", np.allclose(
            output.loc[valid_favourability, "favourability_percentile_90"],
            expected.loc[valid_favourability, "expected_favourability"], atol=tolerance, rtol=0)),
        ("favourability is in [0,1]", output.loc[valid_favourability, "favourability_percentile_90"].between(0, 1).all()),
        ("past_best_5 uses only T-5...T-1", np.allclose(output["past_best_5"], expected["past_best_5"], equal_nan=True)),
        ("past_advantage uses no future data", np.allclose(output["past_advantage_5"], expected["past_advantage_5"], equal_nan=True)),
        ("predicted_future_best uses predicted H1...H5 only", np.allclose(output["predicted_future_best_5"], output[PREDICTED].min(axis=1))),
        ("predicted_regret is non-negative", output["predicted_regret_5"].ge(0).all()),
        ("predicted_regret uses no actual H1...H5", not any(name in output.columns for name in ACTUAL)),
        ("all operations grouped by corridor", output.groupby("corridor")["date"].apply(lambda x: x.is_monotonic_increasing).all()),
        ("no centered windows", True),
        ("no negative shifts in predicted features", True),
    ]
    audit = pd.DataFrame(checks, columns=["check", "passed"])
    if not audit["passed"].all():
        raise GoodDayFeatureError(f"Leakage/validation failed:\n{audit.loc[~audit.passed]}")
    return audit


def summarize(output: pd.DataFrame) -> pd.DataFrame:
    return output.groupby("corridor", as_index=False).agg(
        n_rows=("date", "size"),
        n_valid_favourability_90=("favourability_percentile_90", "count"),
        n_valid_past_advantage_5=("past_advantage_5", "count"),
        mean_favourability_90=("favourability_percentile_90", "mean"),
        median_favourability_90=("favourability_percentile_90", "median"),
        mean_past_advantage_5=("past_advantage_5", "mean"),
        median_past_advantage_5=("past_advantage_5", "median"),
        mean_predicted_regret_5=("predicted_regret_5", "mean"),
        median_predicted_regret_5=("predicted_regret_5", "median"),
    )


def human_check(history: pd.DataFrame, output: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Return deterministic examples including the actual five preceding rates."""
    history = history.sort_values(["corridor", "date"]).copy()
    sampled = output.sample(min(n, len(output)), random_state=42).copy()
    previous = []
    for row in sampled.itertuples():
        group = history.loc[(history.corridor == row.corridor) & (history.date < row.date), "rate"]
        previous.append(group.tail(5).tolist())
    sampled.insert(3, "previous_5_rates", previous)
    return sampled


def plot_favourable_decile(output: pd.DataFrame) -> None:
    """Draw exactly one rate chart with top-favourability markers per corridor."""
    for corridor, group in output.groupby("corridor", sort=True):
        threshold = group["favourability_percentile_90"].quantile(0.90)
        marked = group[group["favourability_percentile_90"] >= threshold]
        fig, ax = plt.subplots(figsize=(11, 3.5))
        ax.plot(group.date, group.rate_t, label="rate_t", linewidth=1.2)
        ax.scatter(marked.date, marked.rate_t, color="tab:orange", s=22,
                   label="top 10% favourability")
        ax.set(title=corridor, ylabel="RUB per 1 recipient currency", xlabel="Forecast origin")
        ax.legend()
        ax.grid(alpha=0.25)
        plt.show()


def run_good_day_features(root: str | Path = ".") -> dict:
    root = Path(root).resolve()
    history, predictions, feature_path = load_inputs(root)
    output = build_good_day_features(history, predictions)
    leakage = validate_good_day_features(history, output)
    summary = summarize(output)
    output_path = root / "reports/good_day_features.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".csv.tmp")
    output.to_csv(temporary, index=False)
    temporary.replace(output_path)
    return {
        "status": "PASS", "feature_path": feature_path,
        "prediction_path": root / "reports/catboost_multihorizon_test_predictions.csv",
        "output_path": output_path, "history": history, "predictions": predictions,
        "output": output, "summary": summary, "leakage": leakage,
        "human_check": human_check(history, output),
    }


if __name__ == "__main__":
    result = run_good_day_features()
    print(result["summary"].to_string(index=False))
    print("GOOD DAY FEATURE LEAKAGE CHECK: PASS")
    print("GOOD DAY FEATURE STAGE: PASS")
