import numpy as np
import pandas as pd
import pytest

from src.features.advanced_features import (
    build_advanced_features,
    build_cross_currency_features,
    build_reversal_features,
)
from src.features.base_features import build_base_market_features


ALL = ("TJS", "UZS", "KGS", "AMD", "KZT", "USD", "EUR", "CNY")


def _source(periods=100):
    dates = pd.date_range("2024-01-01", periods=periods, freq="D")
    frames = []
    for index, currency in enumerate(ALL, start=1):
        rates = index + np.arange(periods) * (index / 1000)
        frames.append(pd.DataFrame({"date": dates, "currency": currency, "unit_rate": rates,
                                    "source_quote_date": dates, "is_new_quote": True}))
    return pd.concat(frames, ignore_index=True)


def _reversal_base(rates):
    dates = pd.date_range("2024-01-01", periods=len(rates), freq="D")
    source = pd.concat([pd.DataFrame({"date": dates, "currency": c, "unit_rate": rates,
                                     "source_quote_date": dates, "is_new_quote": True})
                        for c in ("TJS", "UZS", "KGS", "AMD", "KZT")])
    return build_base_market_features(source)


def test_days_since_min():
    base = _reversal_base(list(range(1, 21)) + [21, 22])
    result = build_reversal_features(base).query("corridor == 'TJS_RUB'").reset_index(drop=True)
    assert result.loc[19, "days_since_min_20"] == 19
    assert result.loc[20, "days_since_min_20"] == 19


def test_return_sign_reversal():
    result = build_reversal_features(_reversal_base([10, 9, 10])).query("corridor == 'TJS_RUB'")
    assert result.iloc[-1].return_sign_reversal_up == 1


def test_reversal_strength():
    base = _reversal_base([10, 9, 10])
    result = build_reversal_features(base).query("corridor == 'TJS_RUB'").iloc[-1]
    expected = base.query("corridor == 'TJS_RUB'").ret_1.iloc[-1] - base.query("corridor == 'TJS_RUB'").ret_1.iloc[-2]
    assert result.reversal_strength == pytest.approx(expected)


def test_near_min_reversal():
    rates = list(range(30, 10, -1)) + [10.0, 10.1]
    result = build_reversal_features(_reversal_base(rates)).query("corridor == 'TJS_RUB'").iloc[-1]
    assert result.near_min_reversal_010 == 1


def test_reversal_2d():
    rates = list(range(30, 10, -1)) + [10.0, 10.1, 10.2]
    result = build_reversal_features(_reversal_base(rates)).query("corridor == 'TJS_RUB'").iloc[-1]
    assert result.reversal_2d_010 == 1


def test_implied_cross_identity():
    source = _source()
    result = build_advanced_features(source)
    row = result.query("corridor == 'TJS_RUB'").iloc[-1]
    usd = source.query("currency == 'USD'").iloc[-1].unit_rate
    assert row.recipient_usd_implied == pytest.approx(row.rate / usd)


def test_broad_rub_return():
    source = _source()
    result = build_advanced_features(source).query("corridor == 'TJS_RUB'").iloc[-1]
    expected = np.mean([(g.unit_rate.iloc[-1] / g.unit_rate.iloc[-2] - 1)
                        for _, g in source[source.currency.isin(["USD", "EUR", "CNY"])].groupby("currency")])
    assert result.broad_rub_return_1 == pytest.approx(expected)


def test_zscore_uses_trailing_history():
    source = _source()
    base = build_base_market_features(source)
    original = build_cross_currency_features(base, source)
    changed = source.copy()
    changed.loc[(changed.currency == "USD") & (changed.date > pd.Timestamp("2024-03-20")), "unit_rate"] *= 100
    altered = build_cross_currency_features(base, changed)
    before = original.date <= pd.Timestamp("2024-03-20")
    pd.testing.assert_series_equal(original.loc[before, "broad_rub_z_1"].reset_index(drop=True), altered.loc[before, "broad_rub_z_1"].reset_index(drop=True))


def test_cross_currency_alignment():
    source = _source()
    missing_date = pd.Timestamp("2024-02-20")
    source = source.loc[~((source.currency == "USD") & (source.date == missing_date))]
    result = build_advanced_features(source).query("corridor == 'TJS_RUB' and date == @missing_date").iloc[0]
    assert result.usd_rub_source_quote_date == missing_date - pd.Timedelta(days=1)
    assert result.usd_rub_freshness_days == 1


def test_cross_currency_no_future():
    source = _source()
    result = build_advanced_features(source)
    for currency in ("usd", "eur", "cny"):
        assert (result[f"{currency}_rub_source_quote_date"] <= result.date).all()
