import numpy as np
import pandas as pd

from src.temporal_feature_enrichment import _status, create_temporal_features


def _frame() -> pd.DataFrame:
    rows = []
    for corridor, offset in (("AAA_RUB", 0.0), ("BBB_RUB", 100.0)):
        for index, date in enumerate(pd.date_range("2024-01-01", periods=5, freq="D")):
            value = offset + index + 1.0
            rows.append({
                "corridor": corridor,
                "date": date,
                "ret_1": value,
                "ret_3": value * 3,
                "ret_10": value * 10,
                "vol_20": value + 10,
                "vol_60": value + 20,
                "broad_rub_return_1": value + 30,
                "corridor_specific_return_1": value + 40,
            })
    return pd.DataFrame(rows)


def test_temporal_lags_are_strictly_trailing_and_corridor_local():
    enriched, _ = create_temporal_features(_frame())

    for _, group in enriched.groupby("corridor"):
        assert np.isnan(group.iloc[0]["ret_1_lag1"])
        assert group.iloc[1]["ret_1_lag1"] == group.iloc[0]["ret_1"]
        assert group.iloc[3]["ret_1_lag3"] == group.iloc[0]["ret_1"]


def test_regime_feature_formulas_use_only_current_or_past_values():
    enriched, audit = create_temporal_features(_frame())
    row = enriched.loc[enriched.corridor.eq("AAA_RUB")].iloc[3]

    assert np.isclose(row["vol_ratio_20_60"], row["vol_20"] / row["vol_60"])
    assert np.isclose(row["vol_20_change_3"], row["vol_20"] / 11.0 - 1.0)
    assert np.isclose(row["momentum_spread"], row["ret_3"] - row["ret_10"])
    assert audit["available_at_t"].all()
    assert not audit["formula"].str.contains(r"shift\(-", regex=True).any()


def test_practical_status_uses_one_percent_threshold():
    assert _status(1.0) == "IMPROVED"
    assert _status(0.999) == "PRACTICALLY_TIED"
    assert _status(-0.999) == "WORSE"
    assert _status(-1.0) == "WORSE"
