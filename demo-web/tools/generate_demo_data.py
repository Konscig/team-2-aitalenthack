"""Build the browser fixture from the canonical golden-label dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.visualize_golden_labels import select_scenario_pushes  # noqa: E402

SOURCE = ROOT / "data/labels/golden_labels.parquet"
OUTPUT = ROOT / "demo-web/data.js"
PERIOD_START = pd.Timestamp("2025-07-01")
PERIOD_END = pd.Timestamp("2026-07-31")
AMOUNT_RUB = 22_000


def clean_number(value: object, digits: int = 6) -> float | None:
    if pd.isna(value):
        return None
    return round(float(value), digits)


def main() -> None:
    source = pd.read_parquet(SOURCE)
    source["date"] = pd.to_datetime(source.date)
    payload: dict[str, object] = {
        "meta": {
            "periodStart": PERIOD_START.strftime("%Y-%m-%d"),
            "periodEnd": PERIOD_END.strftime("%Y-%m-%d"),
            "amountRub": AMOUNT_RUB,
            "cooldownDays": 4,
            "weeklyCap": 2,
        },
        "corridors": {},
    }
    for corridor, frame in source.groupby("corridor", sort=True):
        frame = frame.loc[frame.date.between(PERIOD_START, PERIOD_END)].sort_values("date").copy()
        frame["push"], frame["push_scenario"] = select_scenario_pushes(
            frame, cooldown_days=4, weekly_cap=2
        )
        points = [
            [row.date.strftime("%Y-%m-%d"), clean_number(row.rate)]
            for row in frame.itertuples(index=False)
        ]
        signals = []
        for row in frame.loc[frame.push].itertuples(index=False):
            rate = float(row.rate)
            future_median = clean_number(row.future_median_rate)
            recipient_amount = AMOUNT_RUB / rate
            recipient_at_median = AMOUNT_RUB / float(row.future_median_rate) if future_median else None
            effect = recipient_amount - recipient_at_median if recipient_at_median is not None else 0
            active_facts = []
            if row.fact_decline_3_quotes:
                active_facts.append("decline_3")
            if row.fact_weekly_gain_1pct:
                active_facts.append("weekly_gain")
            if row.fact_low_percentile_30d:
                active_facts.append("low_percentile")
            signals.append(
                {
                    "date": row.date.strftime("%Y-%m-%d"),
                    "rate": clean_number(rate),
                    "type": str(row.push_scenario),
                    "recipientAmount": round(recipient_amount, 2),
                    "effectUnits": round(effect, 2),
                    "reboundBps": clean_number(row.rebound_from_past_min_bps, 1),
                    "futureMedianChangeBps": clean_number(row.future_median_change_bps, 1),
                    "futureRegretBps": clean_number(row.future_regret_bps, 1),
                    "ret5Pct": clean_number(float(row.ret_5) * 100, 2),
                    "facts": active_facts,
                }
            )
        counts = pd.Series([item["type"] for item in signals]).value_counts()
        payload["corridors"][corridor.replace("_RUB", "")] = {
            "points": points,
            "signals": signals,
            "summary": {
                "good": int(counts.get("good_now", 0)),
                "closing": int(counts.get("window_closing", 0)),
                "fact": int(counts.get("positive_market_fact", 0)),
                "total": len(signals),
                "weeks": int(frame.date.dt.to_period("W-SUN").nunique()),
            },
        }
    OUTPUT.write_text(
        "window.DEMO_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
