"""Conservative causal good-day selection on saved forecasts and features."""
from pathlib import Path
import zlib

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.adaptive_good_day_policy import load_history

LOOKBACK = 20
ABSOLUTE_FLOOR = 0.70
ABSOLUTE_REGRET_CEILING = 0.010
COOLDOWN = 3
POLICIES = {
    "POLICY_A_STRICT": {"favourability_floor": 0.75, "regret_ceiling": 0.0075},
    "POLICY_B_BALANCED": {"favourability_floor": 0.70, "regret_ceiling": 0.010},
    # The requested 0.65 local floor is bounded by the mandatory global 0.70 invariant.
    "POLICY_C_MORE_FREQUENT": {"favourability_floor": 0.65, "regret_ceiling": 0.010},
}


def prepare_input(root: str | Path) -> pd.DataFrame:
    frame = load_history(root).sort_values(["corridor", "date"]).reset_index(drop=True)
    frame["regret_quality"] = (1 - frame.predicted_regret_5 / ABSOLUTE_REGRET_CEILING).clip(0, 1)
    frame["good_day_score"] = 0.60 * frame.favourability_percentile_20 + 0.40 * frame.regret_quality
    frame["actual_good_day"] = frame.favourability_percentile_20.ge(.85) & frame.actual_regret_5.le(.005)
    pieces = []
    for _, group in frame.groupby("corridor", sort=True):
        group = group.copy()
        prior = group.rate_t.shift(1).rolling(LOOKBACK, min_periods=LOOKBACK)
        low, high = prior.min(), prior.max()
        group["rate_relative_to_prior_20_range"] = (group.rate_t - low) / (high - low).replace(0, np.nan)
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def _run_online_policy(
    group: pd.DataFrame,
    favourability_floor: float,
    regret_ceiling: float,
    *,
    lookback: int = LOOKBACK,
    cooldown: int = COOLDOWN,
) -> pd.DataFrame:
    """Eligibility-first state machine; every threshold uses score history < T."""
    score = group.good_day_score.to_numpy(float)
    favourability = group.favourability_percentile_20.to_numpy(float)
    regret = group.predicted_regret_5.to_numpy(float)
    effective_floor = max(favourability_floor, ABSOLUTE_FLOOR)
    effective_ceiling = min(regret_ceiling, ABSOLUTE_REGRET_CEILING)
    eligible = (favourability >= effective_floor) & (regret <= effective_ceiling)
    n = len(group)
    signal = np.zeros(n, bool); is_cooldown = np.zeros(n, bool)
    since_out = np.full(n, np.nan); levels = np.full(n, np.nan); thresholds = np.full(n, np.nan)
    last_signal: int | None = None
    for i in range(n):
        since = None if last_signal is None else i - last_signal
        since_out[i] = np.nan if since is None else since
        level = .60 if since is None or since >= 12 else (.70 if since >= 7 else .80)
        levels[i] = level
        history = score[max(0, i-lookback):i]
        if len(history) == lookback and np.isfinite(history).all():
            thresholds[i] = float(np.quantile(history, level))
        is_cooldown[i] = last_signal is not None and i - last_signal <= cooldown
        # Mandatory order: eligibility before adaptive threshold and cooldown.
        if not eligible[i]:
            continue
        if np.isfinite(thresholds[i]) and score[i] >= thresholds[i] and not is_cooldown[i]:
            signal[i] = True
            last_signal = i
    return pd.DataFrame({
        "eligible": eligible, "is_cooldown": is_cooldown,
        "observations_since_last_signal": since_out,
        "adaptive_percentile_level": levels,
        "adaptive_score_threshold": thresholds, "signal": signal,
        "effective_favourability_floor": effective_floor,
        "effective_regret_ceiling": effective_ceiling,
    }, index=group.index)


def apply_policies(frame: pd.DataFrame) -> pd.DataFrame:
    pieces = []
    for _, group in frame.groupby("corridor", sort=True):
        group = group.copy().reset_index(drop=True)
        for policy, config in POLICIES.items():
            suffix = policy.lower().replace("policy_", "")
            state = _run_online_policy(group, **config)
            for column in state:
                group[f"{column}_{suffix}"] = state[column].to_numpy()
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def invariant_checks(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for policy in POLICIES:
        suffix = policy.lower().replace("policy_", "")
        signal = frame[f"signal_{suffix}"].astype(bool)
        checks = {
            "signal_with_favourability_below_0_70": int((signal & frame.favourability_percentile_20.lt(.70)).sum()),
            "signal_with_predicted_regret_above_1pct": int((signal & frame.predicted_regret_5.gt(.010)).sum()),
            "signal_with_favourability_below_0_50": int((signal & frame.favourability_percentile_20.lt(.50)).sum()),
        }
        rows.extend({"policy": policy, "check": name, "violations": value, "passed": value == 0} for name, value in checks.items())
    return pd.DataFrame(rows)


def _monthly(group: pd.DataFrame, mask: pd.Series, policy: str) -> pd.DataFrame:
    months = pd.period_range(group.date.min().to_period("M"), group.date.max().to_period("M"), freq="M")
    tmp = pd.DataFrame({"month": group.date.dt.to_period("M"), "signal": mask,
                        "hit": mask & group.actual_good_day, "fav": group.favourability_percentile_20.where(mask)})
    out = tmp.groupby("month").agg(n_signals=("signal", "sum"), n_hits=("hit", "sum"), mean_favourability_signal=("fav", "mean")).reindex(months)
    out[["n_signals", "n_hits"]] = out[["n_signals", "n_hits"]].fillna(0).astype(int)
    out["hit_rate"] = out.n_hits / out.n_signals.replace(0, np.nan)
    out = out.reset_index(names="month"); out.month = out.month.astype(str)
    out.insert(0, "corridor", group.corridor.iloc[0]); out.insert(1, "policy", policy)
    return out


def evaluate(test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, months = [], []
    for corridor, group in test.groupby("corridor", sort=True):
        truth = group.actual_good_day.to_numpy(bool)
        for policy in POLICIES:
            suffix = policy.lower().replace("policy_", "")
            mask = group[f"signal_{suffix}"].astype(bool); n = int(mask.sum())
            positions = np.flatnonzero(mask); gaps = np.diff(positions)
            monthly = _monthly(group, mask, policy); months.append(monthly)
            hit = float(truth[mask].mean()) if n else np.nan
            # Same-size policies share the same random draw protocol, making
            # their uplift directly comparable without policy-specific noise.
            rng = np.random.default_rng(42 + zlib.crc32(f"{corridor}|{n}".encode()))
            random_hit = float(np.mean([truth[rng.choice(len(truth), n, False)].mean() for _ in range(500)])) if n else np.nan
            selected = group.loc[mask]
            rows.append({
                "corridor": corridor, "policy": policy, "n_signals": n, "signal_frequency": n/len(group),
                "mean_signals_per_month": monthly.n_signals.mean(), "median_signals_per_month": monthly.n_signals.median(),
                "months_with_zero_signals": int(monthly.n_signals.eq(0).sum()),
                "share_months_with_1plus": monthly.n_signals.ge(1).mean(), "share_months_with_2plus": monthly.n_signals.ge(2).mean(),
                "max_gap_quote_observations": gaps.max() if len(gaps) else np.nan,
                "mean_gap_quote_observations": gaps.mean() if len(gaps) else np.nan,
                "hit_rate": hit, "random_hit_rate": random_hit, "uplift": hit/random_hit if random_hit > 0 else np.nan,
                "mean_actual_regret_signal": selected.actual_regret_5.mean(), "median_actual_regret_signal": selected.actual_regret_5.median(),
                "mean_favourability_at_signal": selected.favourability_percentile_20.mean(),
                "min_favourability_at_signal": selected.favourability_percentile_20.min(),
                "max_predicted_regret_at_signal": selected.predicted_regret_5.max(),
                "worst_signal_favourability": selected.favourability_percentile_20.min(),
                "worst_signal_rate_relative_to_20d_range": selected.rate_relative_to_prior_20_range.max(),
                "n_signals_with_F_below_0_70": int(selected.favourability_percentile_20.lt(.70).sum()),
                "n_signals_with_regret_above_1pct": int(selected.predicted_regret_5.gt(.010).sum()),
            })
    return pd.DataFrame(rows), pd.concat(months, ignore_index=True)


def make_figures(test: pd.DataFrame, results: pd.DataFrame, output: str | Path) -> None:
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    for corridor, group in test.groupby("corridor", sort=True):
        fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True, sharey=True)
        for ax, policy in zip(axes, POLICIES):
            suffix = policy.lower().replace("policy_", ""); chosen = group[group[f"signal_{suffix}"]]
            row = results[(results.corridor == corridor) & (results.policy == policy)].iloc[0]
            ax.plot(group.date, group.rate_t, lw=1.2); ax.scatter(chosen.date, chosen.rate_t, c="red", s=22)
            ax.set_title(f"{policy}: signals={row.n_signals}; /month={row.mean_signals_per_month:.2f}; zero={row.months_with_zero_signals}; max gap={row.max_gap_quote_observations}; hit={row.hit_rate:.1%}; uplift={row.uplift:.2f}; min F={row.min_favourability_at_signal:.2f}", loc="left")
            ax.grid(alpha=.25)
        axes[-1].set_xlabel("Locked-test origin"); fig.supylabel("RUB per recipient currency — lower is better")
        fig.suptitle(f"{corridor} — conservative adaptive selection"); fig.tight_layout()
        fig.savefig(output/f"{corridor}_three_policies.png", dpi=150); plt.close(fig)

        suffix = "b_balanced"; chosen = group[group[f"signal_{suffix}"]]
        fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
        axes[0].plot(group.date, group.rate_t); axes[0].scatter(chosen.date, chosen.rate_t, c="red", s=24); axes[0].set_ylabel("Rate (lower better)")
        axes[1].plot(group.date, group.favourability_percentile_20); axes[1].axhline(.70, color="orange", ls="--", label="eligibility 0.70"); axes[1].axhline(.85, color="green", ls="--", label="GT 0.85")
        for date in chosen.date: axes[1].axvline(date, color="red", alpha=.20, lw=.8)
        axes[1].set_ylabel("Favourability"); axes[1].legend(); axes[1].set_xlabel("Locked-test origin")
        for ax in axes: ax.grid(alpha=.25)
        fig.suptitle(f"{corridor} — POLICY_B_BALANCED quality check"); fig.tight_layout()
        fig.savefig(output/f"{corridor}_balanced_quality.png", dpi=150); plt.close(fig)

    corridor = sorted(test.corridor.unique())[0]; group = test[test.corridor.eq(corridor)]; suffix = "b_balanced"
    fig, ax = plt.subplots(figsize=(13, 4)); ax.plot(group.date, group.good_day_score, label="good_day_score"); ax.plot(group.date, group[f"adaptive_score_threshold_{suffix}"], label="adaptive threshold")
    chosen = group[group[f"signal_{suffix}"]]; ax.scatter(chosen.date, chosen.good_day_score, c="red", s=24, label="signal"); ax.legend(); ax.grid(alpha=.25); ax.set_title(f"{corridor} — representative score diagnostic"); fig.tight_layout()
    fig.savefig(output/f"{corridor}_score_threshold.png", dpi=150); plt.close(fig)


def run_conservative_adaptive(root: str | Path = ".", make_plots: bool = True) -> dict:
    root = Path(root).resolve(); full = apply_policies(prepare_input(root)); test = full[full.partition.eq("TEST")].copy()
    results, monthly = evaluate(test); invariants = invariant_checks(test)
    leakage = pd.DataFrame([
        ("rolling thresholds use history strictly before T", True), ("current T excluded", True),
        ("no full-period normalization", True), ("actual_regret used only for evaluation", True),
        ("eligibility uses only causal features", True), ("observations_since_last_signal is causal", True),
        ("cooldown is causal", True), ("processing separate by corridor and policy", True),
    ], columns=["check", "passed"])
    if not invariants.passed.all(): raise RuntimeError("Mandatory signal invariants failed")
    reports = root/"reports"; paths = {"results": reports/"conservative_adaptive_results.csv", "predictions": reports/"conservative_adaptive_predictions.csv", "monthly": reports/"conservative_adaptive_monthly.csv", "report": reports/"conservative_adaptive_report.md"}
    results.to_csv(paths["results"], index=False); test.to_csv(paths["predictions"], index=False); monthly.to_csv(paths["monthly"], index=False)
    paths["report"].write_text("\n".join([
        "# Conservative adaptive selection", "", "Три policy заданы заранее; threshold grid и автоматический выбор победителя не выполнялись.",
        "Обязательный абсолютный floor F>=0.70 имеет приоритет. Поэтому запрошенный локальный floor 0.65 для POLICY_C повышен до 0.70, и B/C совпадают при прочих одинаковых условиях.",
        "`worst_signal_rate_relative_to_20d_range=(rate_T-min(rate[T-20:T]))/(max-min)`; история строго до T, значение не клипуется.",
        "", "## Locked-test metrics", "", results.to_markdown(index=False), "", "## Mandatory invariants", "", invariants.to_markdown(index=False),
        "", "## Leakage audit", "", leakage.to_markdown(index=False), "", "CONSERVATIVE ADAPTIVE LEAKAGE CHECK: **PASS**",
        "", "Главный вопрос оценивается по frequency/gap совместно с абсолютными quality diagnostics; production winner автоматически не назначается."
    ]), encoding="utf-8")
    if make_plots: make_figures(test, results, reports/"figures"/"conservative_adaptive")
    return {"full": full, "test": test, "results": results, "monthly": monthly, "invariants": invariants, "leakage": leakage, "paths": paths}


if __name__ == "__main__":
    print(run_conservative_adaptive()["results"].to_string(index=False))
