"""Evaluate the retrospective oracle policy through the public metrics API."""

from __future__ import annotations

import argparse

import pandas as pd

from src.backtest.metrics import HORIZONS, evaluate_predictions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="data/labels/golden_labels.parquet")
    parser.add_argument("--calendar", default="data/interim/fx_calendar_time.parquet")
    parser.add_argument("--corridor", action="append", help="Repeat for several corridors; default: TJS_RUB")
    parser.add_argument("--start", default="2025-07-01")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--output-dir", default="reports/evaluation/oracle_policy_tjs")
    parser.add_argument("--replicates", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cooldown-days", type=int, default=4)
    parser.add_argument("--weekly-cap", type=int, default=2)
    parser.add_argument("--average-transfer-rub", type=float, default=22_000)
    args = parser.parse_args(argv)

    labels = pd.read_parquet(args.labels)
    labels["date"] = pd.to_datetime(labels.date, errors="raise")
    corridors = args.corridor or ["TJS_RUB"]
    selected = labels.loc[
        labels.corridor.isin(corridors) & labels.date.between(pd.Timestamp(args.start), pd.Timestamp(args.end))
    ].copy()
    if selected.empty:
        raise ValueError("No label rows for requested corridors and period")
    missing_corridors = set(corridors) - set(selected.corridor)
    if missing_corridors:
        raise ValueError(f"No rows for corridors: {sorted(missing_corridors)}")

    prediction_columns = ["date", "corridor"]
    fact_columns = [column for column in selected if column.startswith("fact_")]
    predictions = selected[prediction_columns + fact_columns].copy()
    predictions["good_pred"] = selected.good
    predictions["closing_pred"] = selected.closing
    predictions["positive_market_fact"] = selected.get("positive_market_fact", False)
    result = evaluate_predictions(
        predictions,
        selected,
        pd.read_parquet(args.calendar),
        horizons=HORIZONS,
        replicates=args.replicates,
        cooldown_days=args.cooldown_days,
        weekly_cap=args.weekly_cap,
        seed=args.seed,
        average_transfer_rub=args.average_transfer_rub,
    )
    report = result.save(
        args.output_dir,
        description=(
            "Oracle sanity-check: golden `good` и `closing` намеренно подставлены как идеальные predictions. "
            "Это проверка формул и верхней границы, а не качество production-алгоритма."
        ),
    )
    print(f"PASS: {len(result.pushes)} oracle pushes; report -> {report}")
    print(result.scenario_metrics.loc[result.scenario_metrics.h_days.eq(10)].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
