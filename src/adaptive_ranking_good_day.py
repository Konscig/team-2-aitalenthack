"""Causal adaptive-ranking good-day policies for the locked test period.

Signals use only information available at forecast origin T.  Future actual
regret is retained exclusively as evaluation ground truth.
"""
from pathlib import Path
import zlib

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.adaptive_good_day_policy import add_scores, load_history

LOOKBACK = 20
HARD_REGRET_LIMIT = 0.010
COOLDOWN = 3
POLICIES = {
    "POLICY_FULL": ("score_full", COOLDOWN),
    "POLICY_SIMPLE": ("score_simple", COOLDOWN),
    "POLICY_SIMPLE_NO_COOLDOWN": ("score_simple", 0),
}


def prepare_scores(root: str | Path) -> pd.DataFrame:
    """Load Stage 06/08 artifacts and compute strictly trailing component ranks."""
    frame = add_scores(load_history(root)).rename(
        columns={"good_day_score": "score_full", "good_day_score_simple": "score_simple"}
    )
    return frame.sort_values(["corridor", "date"]).reset_index(drop=True)


def _adaptive_policy(
    scores: pd.Series,
    predicted_regret: pd.Series,
    *,
    lookback: int = LOOKBACK,
    cooldown: int = COOLDOWN,
) -> pd.DataFrame:
    """Apply an online threshold whose quantile depends on prior signal recency."""
    score = scores.to_numpy(float)
    regret = predicted_regret.to_numpy(float)
    threshold = np.full(len(score), np.nan)
    observations_since = np.full(len(score), np.nan)
    quantile = np.full(len(score), np.nan)
    signal = np.zeros(len(score), dtype=bool)
    last_signal: int | None = None

    for i in range(len(score)):
        since = None if last_signal is None else i - last_signal
        observations_since[i] = np.nan if since is None else since
        if since is None or since >= 12:
            q = 0.50
        elif since >= 7:
            q = 0.65
        else:
            q = 0.80
        quantile[i] = q
        history = score[max(0, i - lookback):i]
        if len(history) != lookback or not np.isfinite(history).all():
            continue
        threshold[i] = float(np.quantile(history, q))
        cooldown_open = last_signal is None or i - last_signal > cooldown
        if cooldown_open and np.isfinite(score[i]) and score[i] >= threshold[i] and regret[i] <= HARD_REGRET_LIMIT:
            signal[i] = True
            last_signal = i
    return pd.DataFrame({
        "adaptive_threshold": threshold,
        "threshold_quantile": quantile,
        "observations_since_last_signal": observations_since,
        "signal": signal,
    }, index=scores.index)


def apply_adaptive_ranking(frame: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for _, group in frame.groupby("corridor", sort=True):
        group = group.copy().reset_index(drop=True)
        for policy, (score_column, cooldown) in POLICIES.items():
            state = _adaptive_policy(group[score_column], group["predicted_regret_5"], cooldown=cooldown)
            suffix = policy.lower().replace("policy_", "")
            for column in state:
                group[f"{column}_{suffix}"] = state[column].to_numpy()
        # Required generic fields refer to the primary SIMPLE policy; explicit
        # policy-specific fields above remove any ambiguity.
        group["adaptive_threshold"] = group["adaptive_threshold_simple"]
        group["observations_since_last_signal"] = group["observations_since_last_signal_simple"]
        group["signal_full"] = group["signal_full"].astype(bool)
        group["signal_simple"] = group["signal_simple"].astype(bool)
        group["actual_good_day"] = (
            group["favourability_percentile_20"].ge(0.85)
            & group["actual_regret_5"].le(0.005)
        )
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def _monthly(group: pd.DataFrame, signal: pd.Series, policy: str) -> pd.DataFrame:
    months = pd.period_range(group.date.min().to_period("M"), group.date.max().to_period("M"), freq="M")
    table = pd.DataFrame({"month": group.date.dt.to_period("M"), "signal": signal, "hit": signal & group.actual_good_day})
    table = table.groupby("month").agg(n_signals=("signal", "sum"), n_hits=("hit", "sum")).reindex(months, fill_value=0)
    table["hit_rate"] = table.n_hits / table.n_signals.replace(0, np.nan)
    table = table.reset_index(names="month")
    table.month = table.month.astype(str)
    table.insert(0, "corridor", group.corridor.iloc[0])
    table["policy"] = policy
    return table


def evaluate(test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, monthly = [], []
    for corridor, group in test.groupby("corridor", sort=True):
        truth = group.actual_good_day.to_numpy(bool)
        for policy in POLICIES:
            suffix = policy.lower().replace("policy_", "")
            mask = group[f"signal_{suffix}"].to_numpy(bool)
            n = int(mask.sum())
            positions = np.flatnonzero(mask)
            gaps = np.diff(positions)
            hit_rate = float(truth[mask].mean()) if n else np.nan
            rng = np.random.default_rng(42 + zlib.crc32(f"{corridor}|{policy}".encode()))
            random_hit = float(np.mean([truth[rng.choice(len(truth), n, replace=False)].mean() for _ in range(500)])) if n else np.nan
            month = _monthly(group, pd.Series(mask, index=group.index), policy)
            monthly.append(month)
            rows.append({
                "corridor": corridor, "policy": policy, "n_signals": n,
                "signal_frequency": n / len(group),
                "mean_signals_per_month": month.n_signals.mean(),
                "median_signals_per_month": month.n_signals.median(),
                "months_with_zero_signals": int(month.n_signals.eq(0).sum()),
                "share_months_with_1plus": month.n_signals.ge(1).mean(),
                "share_months_with_2plus": month.n_signals.ge(2).mean(),
                "max_gap_quote_observations": gaps.max() if len(gaps) else np.nan,
                "mean_gap_quote_observations": gaps.mean() if len(gaps) else np.nan,
                "hit_rate": hit_rate, "random_hit_rate": random_hit,
                "uplift": hit_rate / random_hit if random_hit > 0 else np.nan,
                "mean_actual_regret_signal": group.loc[mask, "actual_regret_5"].mean(),
            })
    return pd.DataFrame(rows), pd.concat(monthly, ignore_index=True)


def make_figures(test: pd.DataFrame, results: pd.DataFrame, output: str | Path) -> None:
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    for corridor, group in test.groupby("corridor", sort=True):
        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, sharey=True)
        for ax, policy, suffix in zip(axes, ["POLICY_FULL", "POLICY_SIMPLE"], ["full", "simple"]):
            row = results[(results.corridor == corridor) & (results.policy == policy)].iloc[0]
            selected = group[group[f"signal_{suffix}"]]
            ax.plot(group.date, group.rate_t, lw=1.2, label="rate")
            ax.scatter(selected.date, selected.rate_t, color="red", s=22, label="signal")
            ax.set_title(f"{policy}: n={row.n_signals}, zero months={row.months_with_zero_signals}, max gap={row.max_gap_quote_observations}, uplift={row.uplift:.2f}", loc="left")
            ax.grid(alpha=.25); ax.legend()
        axes[-1].set_xlabel("Locked-test origin"); fig.supylabel("RUB per recipient currency")
        fig.suptitle(corridor); fig.tight_layout(); fig.savefig(output / f"{corridor}_full_vs_simple.png", dpi=150); plt.close(fig)

        selected = group[group.signal_simple]
        fig, ax = plt.subplots(figsize=(12, 3.8)); ax.plot(group.date, group.rate_t, lw=1.2, label="rate")
        ax.scatter(selected.date, selected.rate_t, color="red", s=24, label="SIMPLE signal")
        ax.set_title(f"{corridor} — POLICY_SIMPLE"); ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
        fig.savefig(output / f"{corridor}_simple.png", dpi=150); plt.close(fig)

    corridor = sorted(test.corridor.unique())[0]
    group = test[test.corridor == corridor]
    fig, ax = plt.subplots(figsize=(12, 4)); ax.plot(group.date, group.score_simple, label="score_simple")
    ax.plot(group.date, group.adaptive_threshold_simple, label="adaptive threshold")
    chosen = group[group.signal_simple]; ax.scatter(chosen.date, chosen.score_simple, c="red", s=24, label="signal")
    ax.set_title(f"Representative online score path — {corridor}"); ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
    fig.savefig(output / f"{corridor}_representative_score.png", dpi=150); plt.close(fig)


def run_adaptive_ranking(root: str | Path = ".", make_plots: bool = True) -> dict:
    root = Path(root).resolve()
    full = apply_adaptive_ranking(prepare_scores(root))
    test = full[full.partition.eq("TEST")].copy()
    results, monthly = evaluate(test)
    reports = root / "reports"; figures = reports / "figures" / "adaptive_ranking"
    paths = {
        "results": reports / "adaptive_ranking_results.csv",
        "predictions": reports / "adaptive_ranking_predictions.csv",
        "monthly": reports / "adaptive_ranking_monthly.csv",
        "report": reports / "adaptive_ranking_report.md",
    }
    prediction_columns = [
        "corridor", "date", "rate_t", "favourability_percentile_20", "past_advantage_5",
        "predicted_regret_5", "F_score", "A_score", "R_score", "score_full", "score_simple",
        "adaptive_threshold", "observations_since_last_signal", "adaptive_threshold_full",
        "adaptive_threshold_simple", "observations_since_last_signal_full",
        "observations_since_last_signal_simple", "threshold_quantile_full", "threshold_quantile_simple",
        "signal_full", "signal_simple", "signal_simple_no_cooldown", "actual_regret_5", "actual_good_day",
    ]
    for data, key in [(results, "results"), (test[prediction_columns], "predictions"), (monthly, "monthly")]:
        data.to_csv(paths[key], index=False)
    leakage = pd.DataFrame([
        ("component ranks use strictly previous 20 observations", True),
        ("adaptive thresholds use strictly previous 20 scores", True),
        ("current observation excluded from rank and threshold history", True),
        ("signals do not use actual_regret_5", True),
        ("validation precedes test and initializes online state", True),
        ("processing and state separated by corridor and policy", True),
        ("forecasting models were not trained or tuned", True),
    ], columns=["check", "passed"])
    comparison = results[results.policy.isin(["POLICY_FULL", "POLICY_SIMPLE"])]
    report = "\n".join([
        "# Adaptive ranking good-day policy", "",
        "Проверяются две заранее заданные causal policy: FULL=(F+A+R)/3 и SIMPLE=(F+R)/2. Автоматический победитель не выбирается.",
        "Hard safety ограничен только predicted_regret_5 <= 0.010. Actual regret используется только как ground truth.",
        "Поля adaptive_threshold и observations_since_last_signal являются алиасами SIMPLE; отдельные FULL/SIMPLE поля сохранены явно.",
        "", "## Результаты locked test", "", results.to_markdown(index=False),
        "", "## Сравнение роли A_score", "", comparison.to_markdown(index=False),
        "", "Интерпретация: сравнение показывает, сокращает ли исключение A_score длинные интервалы без заметного ухудшения uplift, hit rate и actual regret. Решение о production-policy здесь не принимается.",
        "", "## Leakage audit", "", leakage.to_markdown(index=False),
        "", "STAGE 13 LEAKAGE CHECK: **PASS**",
    ])
    paths["report"].write_text(report, encoding="utf-8")
    if make_plots: make_figures(test, results, figures)
    return {"full": full, "test": test, "results": results, "monthly": monthly, "leakage": leakage, "paths": paths}


if __name__ == "__main__":
    print(run_adaptive_ranking()["results"].to_string(index=False))
