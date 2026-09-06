import numpy as np
import pandas as pd

from src.arimax_multistep import _add_path_fields, _candidate_orders, _metrics


def test_candidate_orders_keep_previous_and_fixed_d() -> None:
    orders = _candidate_orders((0, 1, 2))
    assert orders[0] == (0, 1, 2)
    assert len(orders) <= 4
    assert all(order[1] == 1 for order in orders)


def test_path_future_best_and_regret_metrics() -> None:
    row = {"corridor": "A_RUB", "date": pd.Timestamp("2024-01-01"), "rate_t": 10.0}
    actual = [9.8, 9.5, 9.7, 9.9, 10.1]
    predicted = [9.9, 9.8, 9.7, 9.6, 9.5]
    for horizon, (actual_rate, predicted_rate) in enumerate(zip(actual, predicted), 1):
        row[f"actual_rate_h{horizon}"] = actual_rate
        row[f"predicted_rate_h{horizon}"] = predicted_rate
        row[f"lower_95_h{horizon}"] = predicted_rate - 1
        row[f"upper_95_h{horizon}"] = predicted_rate + 1
    frame = _add_path_fields(pd.DataFrame([row]))
    metrics = _metrics(frame)
    assert frame.loc[0, "actual_future_best_5"] == 9.5
    assert frame.loc[0, "predicted_future_best_5"] == 9.5
    assert np.isclose(metrics["Path_MAE_5"], np.mean(np.abs(np.array(actual) - predicted)))
    assert np.isclose(metrics["Regret_MAE_5"], 0.0)


def test_direction_treats_machine_precision_change_as_zero() -> None:
    row = {"corridor": "A_RUB", "date": pd.Timestamp("2024-01-01"), "rate_t": 10.0}
    for horizon in range(1, 6):
        row[f"actual_rate_h{horizon}"] = 10.0
        row[f"predicted_rate_h{horizon}"] = 10.0 + 1e-14
        row[f"lower_95_h{horizon}"] = 9.0
        row[f"upper_95_h{horizon}"] = 11.0
    metrics = _metrics(_add_path_fields(pd.DataFrame([row])))
    assert metrics["DirectionalAccuracy_H5"] == 1.0
