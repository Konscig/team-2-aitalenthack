import numpy as np
import pandas as pd

from src.catboost_multihorizon import (
    CONFIGS,
    _practical_status,
    predict_next_5_rates,
)


class _ConstantModel:
    def __init__(self, log_return: float) -> None:
        self.log_return = log_return

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        return np.full(len(frame), self.log_return)


def test_controlled_grid_has_exactly_four_configurations() -> None:
    assert len(CONFIGS) == 4
    assert all(config["iterations"] in {300, 500} for config in CONFIGS)


def test_practical_improvement_threshold() -> None:
    assert _practical_status(1.0) == "IMPROVED"
    assert _practical_status(0.5) == "PRACTICALLY_TIED"
    assert _practical_status(0.0) == "PRACTICALLY_TIED"
    assert _practical_status(-0.001) == "WORSE"


def test_five_horizon_models_receive_same_x_t() -> None:
    models = {
        "A_RUB": {
            horizon: _ConstantModel(np.log(1 + horizon / 100))
            for horizon in range(1, 6)
        }
    }
    row = pd.Series({"rate": 10.0, "ret_1": 0.01})
    predicted = predict_next_5_rates(row, "A_RUB", models, ["ret_1"])
    assert np.allclose(predicted, [10.1, 10.2, 10.3, 10.4, 10.5])
