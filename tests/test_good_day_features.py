import numpy as np
import pandas as pd

from src.good_day_features import PREDICTED, build_good_day_features


def _inputs():
    rows = []
    for corridor, offset in (("AAA_RUB", 0.0), ("BBB_RUB", 100.0)):
        for index, date in enumerate(pd.date_range("2024-01-01", periods=7, freq="D")):
            rows.append({
                "corridor": corridor,
                "date": date,
                "rate": offset + index + 1.0,
                "favourability_percentile_90": np.nan,
            })
    history = pd.DataFrame(rows)
    origin = history.groupby("corridor", as_index=False).nth(5)
    predictions = origin.rename(columns={"rate": "rate_t"})[["corridor", "date", "rate_t"]]
    for horizon in range(1, 6):
        predictions[f"predicted_rate_h{horizon}"] = predictions["rate_t"] - horizon * 0.1
        predictions[f"actual_rate_h{horizon}"] = predictions["rate_t"] + horizon
    return history, predictions


def test_past_best_excludes_current_and_stays_inside_corridor():
    history, predictions = _inputs()
    output = build_good_day_features(history, predictions)

    assert output.loc[output.corridor.eq("AAA_RUB"), "past_best_5"].iloc[0] == 1.0
    assert output.loc[output.corridor.eq("BBB_RUB"), "past_best_5"].iloc[0] == 101.0


def test_predicted_regret_uses_only_saved_prediction_path():
    history, predictions = _inputs()
    output = build_good_day_features(history, predictions)
    expected_best = output[PREDICTED].min(axis=1)
    expected_regret = (output.rate_t - expected_best) / output.rate_t

    assert np.allclose(output.predicted_future_best_5, expected_best)
    assert np.allclose(output.predicted_regret_5, expected_regret)
    assert not any(column.startswith("actual_rate_h") for column in output.columns)


def test_realized_columns_are_evaluation_only():
    history, predictions = _inputs()
    output = build_good_day_features(history, predictions)

    assert {"actual_future_best_5", "actual_regret_5"}.issubset(output.columns)
    changed = predictions.copy()
    changed[[f"actual_rate_h{h}" for h in range(1, 6)]] = 0.01
    changed_output = build_good_day_features(history, changed)
    assert np.allclose(output.predicted_regret_5, changed_output.predicted_regret_5)
