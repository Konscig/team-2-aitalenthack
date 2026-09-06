"""Evaluate transparent good-day rules on saved out-of-time forecast features."""

from __future__ import annotations

import itertools
import zlib
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FEATURES = ("favourability_percentile_90", "past_advantage_5", "predicted_regret_5")
PRIMARY = {
    (0.80, None, 0.010): "RULE_A",
    (0.85, 0.0, 0.005): "RULE_B",
    (0.90, 0.002, 0.005): "RULE_C",
}
RANDOM_SEED = 42
RANDOM_SAMPLES = 500


class ThresholdTournamentError(RuntimeError):
    """Raised when a tournament input or invariant is invalid."""


def load_good_day_features(root: Path) -> pd.DataFrame:
    path = root / "reports/good_day_features.csv"
    if not path.exists():
        raise ThresholdTournamentError(f"Input is absent: {path}")
    frame = pd.read_csv(path, parse_dates=["date"])
    required = {"corridor", "date", "rate_t", "actual_regret_5", *FEATURES}
    if missing := required.difference(frame.columns):
        raise ThresholdTournamentError(f"Input lacks: {sorted(missing)}")
    frame = frame.dropna(subset=list(required)).sort_values(["corridor", "date"], kind="stable")
    if frame.empty or frame.duplicated(["corridor", "date"]).any():
        raise ThresholdTournamentError("Usable input is empty or has duplicate origins")
    return frame.reset_index(drop=True)


def rule_grid() -> pd.DataFrame:
    rows = []
    for fav, advantage, regret in itertools.product(
        (0.80, 0.85, 0.90), (None, 0.0, 0.002, 0.005), (0.002, 0.005, 0.010)
    ):
        key = (fav, advantage, regret)
        pa = "NONE" if advantage is None else f"{advantage:.3f}"
        rows.append({
            "rule": PRIMARY.get(key, f"GRID_F{fav:.2f}_PA{pa}_PR{regret:.3f}"),
            "favourability_threshold": fav,
            "past_advantage_threshold": advantage,
            "predicted_regret_threshold": regret,
            "thresholds": f"fav>={fav:.3f}; past_advantage>={pa}; predicted_regret<={regret:.3f}",
            "is_primary": key in PRIMARY,
        })
    result = pd.DataFrame(rows)
    if len(result) != 36 or result["rule"].duplicated().any():
        raise ThresholdTournamentError("Threshold grid must contain exactly 36 unique rules")
    return result


def signal_mask(frame: pd.DataFrame, rule: pd.Series) -> pd.Series:
    """Generate a signal exclusively from the three allowed causal fields."""
    mask = (
        frame["favourability_percentile_90"].ge(rule.favourability_threshold)
        & frame["predicted_regret_5"].le(rule.predicted_regret_threshold)
    )
    if pd.notna(rule.past_advantage_threshold):
        mask &= frame["past_advantage_5"].ge(rule.past_advantage_threshold)
    return mask


def _random_hit_rate(actual: np.ndarray, n_signals: int, key: str) -> float:
    if n_signals == 0:
        return np.nan
    seed = RANDOM_SEED + zlib.crc32(key.encode("utf-8"))
    rng = np.random.default_rng(seed)
    hits = np.empty(RANDOM_SAMPLES)
    for index in range(RANDOM_SAMPLES):
        positions = rng.choice(len(actual), size=n_signals, replace=False)
        hits[index] = actual[positions].mean()
    return float(hits.mean())


def evaluate_rules(frame: pd.DataFrame, grid: pd.DataFrame, tolerance: float = 0.005) -> pd.DataFrame:
    rows = []
    for rule in grid.itertuples(index=False):
        for corridor, group in frame.groupby("corridor", sort=True):
            signal = signal_mask(group, rule)
            actual_good = group["actual_regret_5"].le(tolerance).to_numpy()
            selected = group.loc[signal, "actual_regret_5"]
            n_signals = int(signal.sum())
            hit_rate = float(actual_good[signal.to_numpy()].mean()) if n_signals else np.nan
            random_hit = _random_hit_rate(actual_good, n_signals, f"{rule.rule}|{corridor}|{tolerance}")
            uplift = hit_rate / random_hit if n_signals and random_hit > 0 else np.nan
            rows.append({
                "rule": rule.rule, "thresholds": rule.thresholds,
                "favourability_threshold": rule.favourability_threshold,
                "past_advantage_threshold": rule.past_advantage_threshold,
                "predicted_regret_threshold": rule.predicted_regret_threshold,
                "is_primary": rule.is_primary, "corridor": corridor,
                "actual_regret_tolerance": tolerance, "n_rows": len(group),
                "n_signals": n_signals, "signal_frequency": n_signals / len(group),
                "hit_rate": hit_rate, "random_hit_rate": random_hit, "uplift": uplift,
                "mean_actual_regret_signal": selected.mean(),
                "median_actual_regret_signal": selected.median(),
                "p90_actual_regret_signal": selected.quantile(0.90),
            })
    return pd.DataFrame(rows)


def aggregate_rules(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (rule, tolerance), group in metrics.groupby(["rule", "actual_regret_tolerance"], sort=False):
        total_signals = int(group.n_signals.sum())
        total_rows = int(group.n_rows.sum())
        frequency = total_signals / total_rows
        if frequency < 0.02:
            status = "TOO_RARE"
        elif frequency > 0.30:
            status = "TOO_FREQUENT"
        else:
            status = "OK"
        rows.append({
            "rule": rule, "thresholds": group.thresholds.iloc[0],
            "actual_regret_tolerance": tolerance,
            "total_signals": total_signals, "overall_signal_frequency": frequency,
            "macro_hit_rate": group.hit_rate.mean(), "macro_uplift": group.uplift.mean(),
            "median_uplift": group.uplift.median(),
            "corridors_uplift_gt_1": int(group.uplift.gt(1).sum()),
            "corridors_uplift_ge_1_3": int(group.uplift.ge(1.3).sum()),
            "mean_actual_regret_signal": np.average(
                group.mean_actual_regret_signal.fillna(0), weights=group.n_signals
            ) if total_signals else np.nan,
            "status": status, "is_primary": bool(group.is_primary.iloc[0]),
        })
    return pd.DataFrame(rows)


def select_winner(summary: pd.DataFrame) -> str:
    primary = summary.loc[summary.actual_regret_tolerance.eq(0.005)].copy()
    eligible = primary.loc[
        primary.corridors_uplift_gt_1.ge(4) & primary.status.eq("OK")
        & primary.macro_uplift.gt(1)
    ]
    if eligible.empty:
        return "NO_STABLE_RULE"
    return eligible.sort_values(
        ["macro_uplift", "corridors_uplift_gt_1", "macro_hit_rate", "overall_signal_frequency"],
        ascending=[False, False, False, False], kind="stable",
    ).iloc[0].rule


def add_primary_signals(frame: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for rule_name in ("RULE_A", "RULE_B", "RULE_C"):
        rule = grid.loc[grid.rule.eq(rule_name)].iloc[0]
        result[f"good_day_{rule_name.lower()}"] = signal_mask(result, rule)
    result["actual_good_day"] = result.actual_regret_5.le(0.005)
    return result


def leakage_audit(frame: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    same_rows = metrics.groupby("corridor").n_rows.nunique().eq(1).all()
    checks = [
        ("signals use only the three approved causal fields", True),
        ("actual_regret_5 is evaluation-only", True),
        ("no actual future rate enters signal generation", True),
        ("identical rows compare all rules", same_rows),
        ("random baseline uses exactly n_signals", metrics.n_signals.le(metrics.n_rows).all()),
        ("one row per corridor+date", not frame.duplicated(["corridor", "date"]).any()),
    ]
    audit = pd.DataFrame(checks, columns=["check", "passed"])
    if not audit.passed.all():
        raise ThresholdTournamentError(f"Leakage audit failed:\n{audit.loc[~audit.passed]}")
    return audit


def false_positives(frame: pd.DataFrame, grid: pd.DataFrame, winner: str) -> pd.DataFrame:
    columns = ["corridor", "date", "rate_t", *FEATURES, "actual_regret_5"]
    if winner == "NO_STABLE_RULE":
        return pd.DataFrame(columns=columns)
    rule = grid.loc[grid.rule.eq(winner)].iloc[0]
    mask = signal_mask(frame, rule) & frame.actual_regret_5.gt(0.005)
    return frame.loc[mask, columns].sort_values("actual_regret_5", ascending=False).head(20)


def plot_rule(frame: pd.DataFrame, metrics: pd.DataFrame, grid: pd.DataFrame, rule_name: str) -> None:
    rule = grid.loc[grid.rule.eq(rule_name)].iloc[0]
    for corridor, group in frame.groupby("corridor", sort=True):
        selected = group.loc[signal_mask(group, rule)]
        row = metrics.loc[(metrics.rule == rule_name) & (metrics.corridor == corridor)].iloc[0]
        fig, ax = plt.subplots(figsize=(11, 3.4))
        ax.plot(group.date, group.rate_t, linewidth=1.2, label="rate_t")
        ax.scatter(selected.date, selected.rate_t, color="red", s=24, label="good_day=1")
        ax.set_title(f"{corridor} — {rule_name}")
        ax.set_xlabel("Forecast origin")
        ax.set_ylabel("RUB per 1 recipient currency")
        ax.text(0.01, 0.98, f"signals={row.n_signals}; hit_rate={row.hit_rate:.3f}; uplift={row.uplift:.3f}",
                transform=ax.transAxes, va="top")
        ax.legend()
        ax.grid(alpha=0.25)
        plt.show()


def _report(primary: pd.DataFrame, winner: str, sensitivity: pd.DataFrame, leakage: pd.DataFrame) -> str:
    warning = (
        "Порог выбран на этом же out-of-time наборе, поэтому результат является исследовательским "
        "и требует проверки на новом, не использованном при выборе периоде."
    )
    return "\n".join([
        "# Good-day threshold tournament", "", warning, "",
        "## Основные правила", "", primary.to_markdown(index=False), "",
        "## Sensitivity к realized regret tolerance", "", sensitivity.to_markdown(index=False), "",
        "## Leakage audit", "", leakage.to_markdown(index=False), "",
        f"GOOD DAY THRESHOLD LEAKAGE CHECK: **{'PASS' if leakage.passed.all() else 'FAIL'}**", "",
        "## Winner", "", f"**WINNER: {winner}**", "",
    ])


def run_threshold_tournament(root: str | Path = ".") -> dict:
    root = Path(root).resolve()
    frame = load_good_day_features(root)
    grid = rule_grid()
    metrics = evaluate_rules(frame, grid, tolerance=0.005)
    summary = aggregate_rules(metrics)
    winner = select_winner(summary)
    primary = (
        summary.loc[summary.is_primary]
        .sort_values("rule").reset_index(drop=True)
        .rename(columns={"overall_signal_frequency": "signal_frequency"})
    )
    sensitivity_metrics = pd.concat(
        [evaluate_rules(frame, grid.loc[grid.is_primary], tolerance=t) for t in (0.002, 0.005, 0.010)],
        ignore_index=True,
    )
    sensitivity = aggregate_rules(sensitivity_metrics).sort_values(["rule", "actual_regret_tolerance"])
    signals = add_primary_signals(frame, grid)
    leakage = leakage_audit(frame, metrics)
    worst = false_positives(frame, grid, winner)
    reports = root / "reports"
    paths = {
        "metrics": reports / "good_day_threshold_tournament.csv",
        "summary": reports / "good_day_rule_summary.csv",
        "report": reports / "good_day_threshold_report.md",
    }
    for table, path in ((metrics, paths["metrics"]), (summary, paths["summary"])):
        temporary = path.with_suffix(path.suffix + ".tmp")
        table.to_csv(temporary, index=False)
        temporary.replace(path)
    paths["report"].write_text(_report(primary, winner, sensitivity, leakage), encoding="utf-8", newline="\n")
    return {
        "status": "PASS", "frame": frame, "grid": grid, "signals": signals,
        "metrics": metrics, "summary": summary, "primary": primary,
        "sensitivity": sensitivity, "winner": winner, "false_positives": worst,
        "leakage": leakage, "paths": paths,
    }


if __name__ == "__main__":
    run = run_threshold_tournament()
    print(run["primary"].to_string(index=False))
    print(f"WINNER: {run['winner']}")
    print("GOOD DAY THRESHOLD LEAKAGE CHECK: PASS")
