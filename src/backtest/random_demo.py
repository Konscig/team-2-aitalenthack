"""Run a reproducible random-prediction baseline through the public metrics API."""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src.backtest.metrics import HORIZONS, evaluate_predictions


def _same_prevalence_random_predictions(labels: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Random scores with exactly the golden positive count per target/corridor."""
    rng = np.random.default_rng(seed)
    parts = []
    for _, group in labels.groupby("corridor", sort=True):
        group = group.sort_values("date")
        prediction = group[["date", "corridor"]].copy()
        for target in ("good", "closing"):
            score = rng.random(len(group))
            count = int(group[target].astype(bool).sum())
            selected = np.zeros(len(group), dtype=bool)
            if count:
                selected[np.argsort(score)[-count:]] = True
            prediction[f"{target}_score"] = score
            prediction[f"{target}_pred"] = selected
        prediction["positive_market_fact"] = False
        parts.append(prediction)
    return pd.concat(parts, ignore_index=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="data/labels/golden_labels.parquet")
    parser.add_argument("--calendar", default="data/interim/fx_calendar_time.parquet")
    parser.add_argument("--corridor", action="append", help="Repeat for several corridors; default: TJS_RUB")
    parser.add_argument("--start", default="2025-07-01")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument("--output-dir", default="reports/evaluation/random_signal_demo")
    parser.add_argument("--replicates", type=int, default=1_000)
    parser.add_argument("--seed", type=int, default=20260906)
    args = parser.parse_args(argv)

    labels = pd.read_parquet(args.labels)
    labels["date"] = pd.to_datetime(labels.date, errors="raise")
    corridors = args.corridor or ["TJS_RUB"]
    selected = labels.loc[
        labels.corridor.isin(corridors) & labels.date.between(pd.Timestamp(args.start), pd.Timestamp(args.end))
    ].copy()
    if selected.empty:
        raise ValueError("No labels for requested corridors and period")
    predictions = _same_prevalence_random_predictions(selected, args.seed)
    result = evaluate_predictions(
        predictions,
        selected,
        pd.read_parquet(args.calendar),
        horizons=HORIZONS,
        replicates=args.replicates,
        seed=args.seed,
    )
    report = result.save(
        args.output_dir,
        description=(
            "Random sanity-check: независимые uniform scores с фиксированным "
            f"seed={args.seed}; число положительных predictions по каждому target равно golden prevalence. "
            "Ожидаемый classification и safety lift находится около 1."
        ),
    )
    predictions.to_csv(f"{args.output_dir}/predictions.csv", index=False)
    print(f"PASS: {len(result.pushes)} random-model pushes; report -> {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
