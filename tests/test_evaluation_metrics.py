import numpy as np
import pandas as pd
import pytest

from src.backtest.metrics import (
    build_outcomes,
    classification_metrics,
    evaluate_predictions,
    random_legal_schedules,
    threshold_sweep,
)
from src.backtest.metrics.evaluation import (
    evaluate_schedule,
    factual_push_breakdown,
    frequency_tables,
    random_classification_sanity,
)


def test_classification_metrics_precision_weighted_interface():
    result = classification_metrics(
        [True, True, False, False],
        [True, False, True, False],
        y_score=[0.9, 0.8, 0.7, 0.1],
    )

    assert result["true_positive"] == 1
    assert result["false_positive"] == 1
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5
    assert result["f_beta"] == 0.5
    assert result["classification_lift"] == 1.0
    assert result["average_precision"] == pytest.approx(1.0)


def test_classification_metrics_no_predictions_is_explicitly_undefined():
    result = classification_metrics([True, False], [False, False])

    assert np.isnan(result["precision"])
    assert np.isnan(result["f_beta"])
    assert result["recall"] == 0.0


def test_average_precision_does_not_depend_on_order_inside_score_tie():
    first = classification_metrics([1, 0, 1], [1, 1, 0], y_score=[0.9, 0.9, 0.1])
    second = classification_metrics([0, 1, 1], [1, 1, 0], y_score=[0.9, 0.9, 0.1])

    assert first["average_precision"] == second["average_precision"]


def test_threshold_sweep_exposes_precision_recall_tradeoff():
    result = threshold_sweep([1, 1, 0, 0], [0.9, 0.6, 0.7, 0.1], thresholds=[0.8, 0.5])

    assert result.predicted_positive.tolist() == [1, 3]
    assert result.precision.tolist() == [1.0, pytest.approx(2 / 3)]
    assert result.recall.tolist() == [0.5, 1.0]


def test_build_outcomes_uses_future_for_truth_and_centered_window_for_benefit():
    dates = pd.date_range("2026-01-01", periods=7, freq="D")
    calendar = pd.DataFrame(
        {
            "date": dates,
            "currency": "TJS",
            "unit_rate": [10.0, 9.0, 8.0, 7.0, 8.0, 9.0, 10.0],
        }
    )
    candidate = pd.DataFrame({"date": [dates[3]], "corridor": ["TJS_RUB"], "rate": [7.0]})

    result = build_outcomes(candidate, calendar, horizons=[2]).iloc[0]

    assert result.future_regret_bps == 0
    assert bool(result.safety_hit)
    assert bool(result.closing_confirmation_hit)
    assert result.future_median_change_bps == pytest.approx(10_000 * 1.5 / 7)
    assert result.benefit_bps == pytest.approx(10_000 * (8.2 - 7.0) / 8.2)
    assert bool(result.economic_positive)


def test_incomplete_outcome_window_is_na():
    dates = pd.date_range("2026-01-01", periods=4, freq="D")
    calendar = pd.DataFrame({"date": dates, "currency": "TJS", "unit_rate": [10.0, 9.0, 8.0, 7.0]})
    candidate = pd.DataFrame({"date": [dates[-1]], "corridor": ["TJS_RUB"], "rate": [7.0]})

    result = build_outcomes(candidate, calendar, horizons=[1]).iloc[0]

    assert pd.isna(result.safety_hit)
    assert np.isnan(result.benefit_bps)


def test_random_schedules_are_exact_legal_and_reproducible():
    dates = pd.bdate_range("2026-01-01", periods=60)
    first = random_legal_schedules(dates, n_pushes=15, replicates=10, seed=7)
    second = random_legal_schedules(dates, n_pushes=15, replicates=10, seed=7)

    pd.testing.assert_frame_equal(first, second)
    assert first.groupby("replicate").size().eq(15).all()
    for _, group in first.groupby("replicate"):
        selected = group.date.sort_values()
        assert selected.diff().dt.days.dropna().ge(4).all()
        assert selected.dt.to_period("W-SUN").value_counts().le(2).all()


def test_evaluation_and_frequency_return_scenario_and_portfolio_rows():
    dates = pd.bdate_range("2026-01-01", periods=30)
    outcome_rows = []
    for date in dates:
        for horizon in [5, 10]:
            outcome_rows.append(
                {
                    "date": date,
                    "corridor": "TJS_RUB",
                    "h_days": horizon,
                    "safety_hit": date.day % 2 == 0,
                    "closing_confirmation_hit": date.day % 3 == 0,
                    "benefit_bps": float(date.day - 15),
                }
            )
    outcomes = pd.DataFrame(outcome_rows)
    pushes = pd.DataFrame(
        {
            "date": dates[[0, 5, 10]],
            "push_scenario": ["good_now", "window_closing", "positive_market_fact"],
        }
    )

    metrics, random = evaluate_schedule(
        pushes,
        outcomes,
        dates,
        replicates=20,
        seed=3,
    )
    weekly, frequency = frequency_tables(pushes, start=dates.min(), end=dates.max())
    sanity = random_classification_sanity(
        pd.DataFrame({"good": [1, 0, 1, 0], "closing": [0, 1, 0, 0]}),
        replicates=100,
    )

    assert set(metrics.scenario) == {
        "good_now",
        "window_closing",
        "positive_market_fact",
        "portfolio",
    }
    assert len(random) == 20 * 2 * 4
    assert frequency.pushes.iloc[0] == 3
    assert weekly.push_count.sum() == 3
    assert set(sanity.target) == {"good", "closing"}

    pushes["fact_decline_3_quotes"] = [0, 0, 1]
    pushes["fact_weekly_gain_1pct"] = [0, 0, 1]
    pushes["fact_low_percentile_30d"] = [0, 0, 0]
    breakdown = factual_push_breakdown(pushes, outcomes)
    assert set(breakdown.group_type) == {"individual_overlapping", "exclusive_combination"}
    assert breakdown.signal_count.eq(1).all()


def test_evaluate_predictions_is_one_call_and_supports_multiple_corridors(tmp_path):
    dates = pd.bdate_range("2026-01-05", periods=15)
    corridors = ["TJS_RUB", "UZS_RUB"]
    predictions = pd.MultiIndex.from_product([dates, corridors], names=["date", "corridor"]).to_frame(index=False)
    predictions["good_pred"] = predictions.groupby("corridor").cumcount().isin([2, 8])
    predictions["closing_pred"] = predictions.groupby("corridor").cumcount().eq(12)
    predictions["good_score"] = np.where(predictions.good_pred, 0.9, 0.1)
    predictions["closing_score"] = np.where(predictions.closing_pred, 0.8, 0.2)

    labels = predictions[["date", "corridor"]].copy()
    labels["rate"] = labels.groupby("corridor").cumcount().map(lambda value: 10 - abs(value - 7) / 10)
    labels["good"] = predictions.good_pred
    labels["closing"] = predictions.closing_pred

    calendar_dates = pd.date_range(dates.min() - pd.Timedelta(days=2), dates.max() + pd.Timedelta(days=2))
    calendar = pd.MultiIndex.from_product([calendar_dates, ["TJS", "UZS"]], names=["date", "currency"]).to_frame(
        index=False
    )
    calendar["unit_rate"] = calendar.groupby("currency").cumcount().map(lambda value: 10 - abs(value - 11) / 10)
    calendar_rate = calendar.loc[calendar.currency.eq("TJS")].set_index("date").unit_rate
    labels["rate"] = labels.date.map(calendar_rate)

    result = evaluate_predictions(
        predictions,
        labels,
        calendar,
        horizons=(1, 2),
        replicates=10,
        seed=7,
    )

    expected_corridors = set(corridors)
    assert set(result.classification.corridor) == expected_corridors
    assert set(result.classification.target) == {"good", "closing"}
    assert set(result.scenario_metrics.corridor) == expected_corridors
    assert set(result.scenario_metrics.h_days) == {1, 2}
    assert set(result.frequency_summary.corridor) == expected_corridors
    assert result.pushes.groupby("corridor").size().eq(3).all()
    assert result.scenario_metrics.query("scenario == 'portfolio'").safety_hit_rate.notna().all()
    assert result.scenario_metrics.query("scenario == 'window_closing'").closing_confirmation_hit_rate.notna().all()
    assert result.scenario_metrics.query("scenario != 'window_closing'").closing_confirmation_hit_rate.isna().all()

    report = result.save(tmp_path / "report")
    assert report.exists()
    assert (report.parent / "classification_metrics.csv").exists()
    assert not (report.parent / "random_runs.csv").exists()
