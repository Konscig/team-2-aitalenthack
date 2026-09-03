import pandas as pd

from src.features.calendar_features import build_calendar_feature_dataset


def test_missing_dates_are_forward_filled_and_marked():
    source = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-17", "2024-01-18", "2024-01-19", "2024-01-22"]),
        "corridor": "TJS_RUB",
        "rate": [10.0, 10.1, 10.2, 10.5],
        "ret_1": [0.0, 0.01, 0.0099, 0.0294],
    })
    result = build_calendar_feature_dataset(source)
    weekend = result.loc[result.date.isin(pd.to_datetime(["2024-01-20", "2024-01-21"]))]
    assert weekend.rate.tolist() == [10.2, 10.2]
    assert weekend.ret_1.tolist() == [0.0099, 0.0099]
    assert weekend.is_new_quote.tolist() == [False, False]
    assert weekend.source_quote_date.tolist() == [pd.Timestamp("2024-01-19")] * 2
    assert weekend.days_since_new_quote.tolist() == [1, 2]


def test_real_rows_are_unchanged():
    source = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-19", "2024-01-22"]),
        "corridor": "KZT_RUB",
        "rate": [0.2, 0.21],
    })
    result = build_calendar_feature_dataset(source)
    real = result.loc[result.is_new_quote, source.columns]
    pd.testing.assert_frame_equal(real.reset_index(drop=True), source)
