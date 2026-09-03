import math

import pandas as pd
import pytest

from src.features.base_features import FeatureError, build_base_market_features, run_causality_check


def _quotes(rates: list[float], currency: str = "TJS") -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(rates), freq="D")
    return pd.DataFrame({"date": dates, "currency": currency, "unit_rate": rates,
                         "source_quote_date": dates, "is_new_quote": True})


def _all_corridors(rates: list[float]) -> pd.DataFrame:
    return pd.concat([_quotes(rates, c) for c in ("TJS", "UZS", "KGS", "AMD", "KZT")])


@pytest.fixture
def increasing() -> pd.DataFrame:
    return build_base_market_features(_all_corridors([float(v) for v in range(1, 401)]))


def _tjs(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[frame["corridor"] == "TJS_RUB"].reset_index(drop=True)


def test_return_formula(increasing):
    assert _tjs(increasing).loc[20, "ret_20"] == pytest.approx(21 / 1 - 1)


def test_log_return_formula(increasing):
    assert _tjs(increasing).loc[10, "log_ret_1"] == pytest.approx(math.log(11 / 10))


def test_sma_formula(increasing):
    assert _tjs(increasing).loc[4, "sma_5"] == pytest.approx(3.0)


def test_dist_sma_formula(increasing):
    assert _tjs(increasing).loc[4, "dist_sma_5"] == pytest.approx(5 / 3 - 1)


def test_rolling_min_max(increasing):
    row = _tjs(increasing).loc[9]
    assert (row["rolling_min_10"], row["rolling_max_10"]) == (1, 10)
    assert row["dist_min_10"] == pytest.approx(9)
    assert row["dist_max_10"] == pytest.approx(0)


def test_percentile_uses_only_past():
    row = _tjs(build_base_market_features(_all_corridors([1.0] * 20 + [2.0]))).iloc[-1]
    assert row["percentile_20"] == 1.0
    assert row["favourability_percentile_20"] == 0.0


def test_momentum(increasing):
    assert _tjs(increasing).loc[20, "mom_20"] == pytest.approx(20)


def test_streak():
    data = _tjs(build_base_market_features(_all_corridors([3, 2, 1, 1, 2, 3, 2])))
    assert data["down_streak"].tolist() == [0, 1, 2, 0, 0, 0, 1]
    assert data["up_streak"].tolist() == [0, 0, 0, 0, 1, 2, 0]


def test_volatility():
    row = _tjs(build_base_market_features(_all_corridors([1, 2, 4, 8, 16, 32]))).iloc[-1]
    assert row["vol_5"] == pytest.approx(0.0, abs=1e-15)


def test_rolling_range(increasing):
    assert _tjs(increasing).loc[9, "rolling_range_10"] == pytest.approx((10 - 1) / 5.5)


def test_calendar_rows_are_rejected():
    source = _all_corridors([1.0, 2.0])
    source.iloc[0, source.columns.get_loc("is_new_quote")] = False
    with pytest.raises(FeatureError, match="Forward-filled"):
        build_base_market_features(source)


def test_causality_on_real_cbr_quotes():
    source = pd.read_parquet("data/interim/fx_quote_time.parquet")
    full = build_base_market_features(source)
    result = run_causality_check(source, full, samples=20, seed=73)
    assert result["status"] == "PASS"
    assert result["samples"] == 20
