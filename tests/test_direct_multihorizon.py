import numpy as np
import pandas as pd

from src.direct_multihorizon import (
    HORIZONS,
    add_path_evaluation,
    create_direct_targets,
    predict_next_5_rates,
)


class _ConstantLogReturnModel:
    def __init__(self, value: float) -> None:
        self.value = value

    def predict(self, values: np.ndarray) -> np.ndarray:
        return np.full(len(values), self.value)


def test_targets_do_not_cross_corridor_boundary() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-01-03"] * 2
            ),
            "corridor": ["A_RUB"] * 3 + ["B_RUB"] * 3,
            "rate": [1.0, 2.0, 4.0, 10.0, 20.0, 40.0],
        }
    )
    result = create_direct_targets(frame)
    assert result.loc[1, "actual_rate_h1"] == 4.0
    assert pd.isna(result.loc[2, "actual_rate_h1"])
    assert result.loc[4, "actual_rate_h1"] == 40.0


def test_predict_next_5_rates_returns_ordered_direct_vector() -> None:
    models = {
        "A_RUB": {
            "DIRECT_RIDGE": {
                horizon: _ConstantLogReturnModel(np.log(1 + horizon / 100))
                for horizon in HORIZONS
            }
        }
    }
    row = pd.Series({"rate": 10.0, "feature": 1.0})
    predicted = predict_next_5_rates(
        row, "A_RUB", "DIRECT_RIDGE", models, ["feature"]
    )
    assert np.allclose(predicted, [10.1, 10.2, 10.3, 10.4, 10.5])


def test_future_best_and_regret_are_evaluation_columns() -> None:
    row = {"corridor": "A_RUB", "date": pd.Timestamp("2024-01-01"), "rate_t": 10.0}
    row.update({f"actual_rate_h{h}": value for h, value in enumerate([9.8, 9.5, 9.7, 9.9, 10.1], 1)})
    row.update({f"predicted_rate_h{h}": value for h, value in enumerate([9.9, 9.8, 9.7, 9.6, 9.5], 1)})
    result = add_path_evaluation(pd.DataFrame([row])).iloc[0]
    assert result["actual_future_best_5"] == 9.5
    assert result["predicted_future_best_5"] == 9.5
    assert np.isclose(result["actual_regret_5"], 0.05)
    assert np.isclose(result["predicted_regret_5"], 0.05)
