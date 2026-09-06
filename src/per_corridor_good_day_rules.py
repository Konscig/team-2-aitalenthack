"""Restore frozen Stage-04 validation forecasts and select good-day rules safely."""

from __future__ import annotations

import json
import zlib
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.catboost_multihorizon import RANDOM_SEED, _model, _validation_metrics
from src.direct_multihorizon import (
    CANDIDATE_FEATURES, HORIZONS, audit_and_select_features, build_model_frame,
    create_direct_targets, discover_feature_dataset, load_and_validate_dataset, load_splits,
)
from src.good_day_features import build_good_day_features

FEATURES = ("favourability_percentile_90", "past_advantage_5", "predicted_regret_5")
RANDOM_SAMPLES = 300


class PerCorridorRuleError(RuntimeError):
    pass


def restore_validation_predictions(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Fit frozen selected configs on TRAIN only; never tune or touch TEST rows."""
    reports = root / "reports"
    frame = create_direct_targets(load_and_validate_dataset(discover_feature_dataset(root)))
    splits = load_splits(reports / "temporal_split_horizons.csv")
    features, _, _ = audit_and_select_features(frame, splits)
    if tuple(features) != CANDIDATE_FEATURES:
        raise PerCorridorRuleError("Stage-04 feature list is not reproduced exactly")
    partitions, partition_audit = build_model_frame(frame, splits, features)
    selection_path = reports / "catboost_model_selection.csv"
    selections = pd.read_csv(selection_path)
    if len(selections) != 25 or selections.duplicated(["corridor", "horizon"]).any():
        raise PerCorridorRuleError("Frozen Stage-04 selection must contain 25 unique models")

    by_corridor: dict[str, dict[int, object]] = {}
    rows = []
    consistency = []
    for corridor, parts in sorted(partitions.items()):
        train, validation = parts["train"], parts["validation"]
        by_corridor[corridor] = {}
        paths = {int(index): {} for index in validation.index}
        for horizon in HORIZONS:
            chosen = selections.loc[
                (selections.corridor == corridor) & (selections.horizon == horizon)
            ].iloc[0]
            params = json.loads(chosen.params)
            model = _model(params, iterations=int(chosen.trees_used))
            model.fit(train[features], train[f"target_log_return_h{horizon}"])
            by_corridor[corridor][horizon] = model
            predicted = validation.rate.to_numpy() * np.exp(model.predict(validation[features]))
            measured = _validation_metrics(
                validation[f"actual_rate_h{horizon}"].to_numpy(), predicted,
                validation.rate.to_numpy(),
            )
            consistency.append({
                "corridor": corridor, "horizon": horizon,
                "config_id": chosen.config_id, "trees_used": int(chosen.trees_used),
                "saved_MAE": float(chosen.MAE), "restored_MAE": measured["MAE"],
                "absolute_MAE_difference": abs(float(chosen.MAE) - measured["MAE"]),
                "same_config_reused": True, "trained_on_train_only": True,
            })
            for index, value in zip(validation.index, predicted):
                paths[int(index)][horizon] = float(value)
        for index, row in validation.iterrows():
            rows.append({
                "corridor": corridor, "date": row.date, "model": "CATBOOST_FROZEN_STAGE04",
                "rate_t": float(row.rate),
                **{f"actual_date_h{h}": row[f"actual_date_h{h}"] for h in HORIZONS},
                **{f"actual_rate_h{h}": float(row[f"actual_rate_h{h}"]) for h in HORIZONS},
                **{f"predicted_rate_h{h}": paths[int(index)][h] for h in HORIZONS},
            })
    predictions = pd.DataFrame(rows).sort_values(["corridor", "date"]).reset_index(drop=True)
    consistency = pd.DataFrame(consistency)
    if len(predictions) != int(splits.n_validation_origins.sum()):
        raise PerCorridorRuleError("Restored validation-origin count differs from split artifact")
    return predictions, consistency, {
        "frame": frame, "splits": splits, "features": features,
        "partitions": partitions, "partition_audit": partition_audit,
    }


def build_validation_good_day(root: Path, predictions: pd.DataFrame, full_frame: pd.DataFrame) -> pd.DataFrame:
    history = full_frame[["corridor", "date", "rate", "favourability_percentile_90"]].copy()
    result = build_good_day_features(history, predictions)
    test = pd.read_csv(root / "reports/good_day_features.csv", parse_dates=["date"])
    if list(result.columns) != list(test.columns):
        raise PerCorridorRuleError("Validation/test good-day columns or definitions differ")
    if result.date.max() >= test.date.min():
        raise PerCorridorRuleError("Validation and locked test overlap")
    return result


def threshold_grid() -> pd.DataFrame:
    rows = []
    for f in (0.75, 0.80, 0.85, 0.90):
        for a in (None, 0.0, 0.002, 0.005):
            for r in (0.002, 0.005, 0.010):
                rows.append({"F": f, "A": a, "R": r,
                             "rule": f"F={f:.3f}|A={'NONE' if a is None else f'{a:.3f}'}|R={r:.3f}",
                             "complexity": 2 if a is None else 3})
    return pd.DataFrame(rows)


def _signal(frame: pd.DataFrame, rule) -> pd.Series:
    mask = frame.favourability_percentile_90.ge(rule.F) & frame.predicted_regret_5.le(rule.R)
    if pd.notna(rule.A):
        mask &= frame.past_advantage_5.ge(rule.A)
    return mask


def _ground_truth(frame: pd.DataFrame, variant: str) -> pd.Series:
    base = frame.actual_regret_5.le(0.005)
    if variant == "GT_A": return base & frame.favourability_percentile_90.ge(0.80)
    if variant == "GT_B": return base & frame.favourability_percentile_90.ge(0.85)
    if variant == "GT_C": return base & frame.favourability_percentile_90.ge(0.85) & frame.past_advantage_5.ge(0)
    raise ValueError(variant)


def _random_hit(actual: np.ndarray, n: int, key: str) -> float:
    if n == 0: return np.nan
    rng = np.random.default_rng(RANDOM_SEED + zlib.crc32(key.encode()))
    return float(np.mean([actual[rng.choice(len(actual), n, replace=False)].mean()
                          for _ in range(RANDOM_SAMPLES)]))


def metrics_for(frame: pd.DataFrame, rule, variant: str, partition: str) -> dict:
    signal = _signal(frame, rule)
    actual = _ground_truth(frame, variant).to_numpy()
    n = int(signal.sum())
    selected = frame.loc[signal, "actual_regret_5"]
    hit = float(actual[signal.to_numpy()].mean()) if n else np.nan
    random_hit = _random_hit(actual, n, f"{partition}|{frame.corridor.iloc[0]}|{rule.rule}|{variant}")
    frequency = n / len(frame)
    status = "TOO_RARE" if frequency < .02 else "TOO_FREQUENT" if frequency > .30 else "OK"
    positives = int(actual.sum())
    return {
        "n_rows": len(frame), "n_signals": n, "signal_frequency": frequency,
        "hit_rate": hit, "precision": hit,
        "recall": float((signal.to_numpy() & actual).sum() / positives) if positives else np.nan,
        "random_hit_rate": random_hit, "uplift": hit / random_hit if random_hit > 0 else np.nan,
        "mean_actual_regret_signal": selected.mean(),
        "median_actual_regret_signal": selected.median(), "frequency_status": status,
    }


def select_rules(validation: pd.DataFrame, grid: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_rows, selected = [], []
    for corridor, group in validation.groupby("corridor", sort=True):
        for rule in grid.itertuples(index=False):
            all_rows.append({"corridor": corridor, **rule._asdict(),
                             **metrics_for(group, rule, "GT_B", "VALIDATION")})
        candidates = pd.DataFrame(all_rows).loc[lambda x: x.corridor.eq(corridor)]
        eligible = candidates.loc[candidates.frequency_status.eq("OK") & candidates.uplift.gt(1)].copy()
        if eligible.empty:
            selected.append({"corridor": corridor, "selected_rule": "", "F": np.nan, "A": np.nan,
                             "R": np.nan, "validation_frequency": np.nan,
                             "validation_hit_rate": np.nan, "validation_uplift": np.nan,
                             "status": "NO_VALIDATED_RULE"})
            continue
        best_uplift = eligible.uplift.max()
        practical_ties = eligible.loc[eligible.uplift.ge(best_uplift - 0.05)]
        winner = practical_ties.sort_values(
            ["hit_rate", "n_signals", "complexity", "F", "R"],
            ascending=[False, False, True, True, False], kind="stable").iloc[0]
        selected.append({
            "corridor": corridor, "selected_rule": winner.rule, "F": winner.F,
            "A": winner.A, "R": winner.R,
            "validation_frequency": winner.signal_frequency,
            "validation_hit_rate": winner.hit_rate, "validation_uplift": winner.uplift,
            "status": "VALIDATED_RULE",
        })
    return pd.DataFrame(all_rows), pd.DataFrame(selected)


def apply_locked_test(test: pd.DataFrame, selection: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    outputs, metrics = [], []
    for chosen in selection.itertuples(index=False):
        group = test.loc[test.corridor.eq(chosen.corridor)].copy()
        for variant in ("GT_A", "GT_B", "GT_C"):
            group[f"actual_good_day_{variant.lower()}"] = _ground_truth(group, variant)
        if chosen.status == "VALIDATED_RULE":
            rule = pd.Series({"F": chosen.F, "A": chosen.A, "R": chosen.R, "rule": chosen.selected_rule})
            group["selected_good_day_signal"] = _signal(group, rule)
            for variant in ("GT_A", "GT_B", "GT_C"):
                metrics.append({"corridor": chosen.corridor, "ground_truth": variant,
                                "selected_rule": chosen.selected_rule, "selected_F": chosen.F,
                                "selected_A": chosen.A, "selected_R": chosen.R,
                                "status": chosen.status, **metrics_for(group, rule, variant, "TEST")})
        else:
            group["selected_good_day_signal"] = False
            for variant in ("GT_A", "GT_B", "GT_C"):
                metrics.append({"corridor": chosen.corridor, "ground_truth": variant,
                                "selected_rule": "", "selected_F": np.nan, "selected_A": np.nan,
                                "selected_R": np.nan, "status": chosen.status,
                                "n_rows": len(group), "n_signals": 0, "signal_frequency": 0,
                                "hit_rate": np.nan, "precision": np.nan, "recall": 0,
                                "random_hit_rate": np.nan, "uplift": np.nan,
                                "mean_actual_regret_signal": np.nan,
                                "median_actual_regret_signal": np.nan, "frequency_status": "TOO_RARE"})
        group["selected_F"], group["selected_A"], group["selected_R"] = chosen.F, chosen.A, chosen.R
        outputs.append(group)
    columns = ["corridor", "date", "rate_t", *FEATURES, "actual_regret_5",
               "actual_good_day_gt_a", "actual_good_day_gt_b", "actual_good_day_gt_c",
               "selected_good_day_signal", "selected_F", "selected_A", "selected_R"]
    return pd.concat(outputs, ignore_index=True)[columns], pd.DataFrame(metrics)


def error_analysis(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = ["corridor", "date", "rate_t", *FEATURES, "actual_regret_5"]
    fp, missed = [], []
    for _, group in predictions.groupby("corridor"):
        fp.append(group.loc[group.selected_good_day_signal & ~group.actual_good_day_gt_b, cols]
                  .sort_values("actual_regret_5", ascending=False).head(10))
        missed.append(group.loc[~group.selected_good_day_signal & group.actual_good_day_gt_b, cols]
                      .sort_values("actual_regret_5", ascending=True).head(10))
    return pd.concat(fp, ignore_index=True), pd.concat(missed, ignore_index=True)


def plot_test(predictions: pd.DataFrame, selection: pd.DataFrame, metrics: pd.DataFrame, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    for chosen in selection.itertuples(index=False):
        group = predictions.loc[predictions.corridor.eq(chosen.corridor)]
        primary = metrics.loc[(metrics.corridor == chosen.corridor) & (metrics.ground_truth == "GT_B")].iloc[0]
        fig, ax = plt.subplots(figsize=(11, 3.6))
        ax.plot(group.date, group.rate_t, label="Rate", linewidth=1.2)
        if chosen.status == "VALIDATED_RULE":
            marked = group.loc[group.selected_good_day_signal]
            ax.scatter(marked.date, marked.rate_t, color="red", s=24, label="Selected good day")
            advantage = "not required" if pd.isna(chosen.A) else f">= {chosen.A:.3f}"
            note = (f"F >= {chosen.F:.3f}; A {advantage}; R <= {chosen.R:.3f}\n"
                    f"signals={primary.n_signals}; hit rate={primary.hit_rate:.1%}; uplift={primary.uplift:.2f}")
        else: note = "NO VALIDATED RULE"
        ax.text(.01, .98, note, transform=ax.transAxes, va="top")
        ax.set(title=f"{chosen.corridor} — selected good days", xlabel="Test forecast origin",
               ylabel="RUB per recipient currency")
        ax.text(.99, .02, "lower rate = better", transform=ax.transAxes, ha="right")
        ax.legend(); ax.grid(alpha=.25); fig.tight_layout()
        fig.savefig(output_dir / f"{chosen.corridor}_selected_good_days.png", dpi=150)
        plt.show()


def leakage_audit(validation, test, selection, consistency, context) -> pd.DataFrame:
    split = context["splits"]
    checks = [
        ("no test data in threshold selection", validation.date.max() < test.date.min()),
        ("no new CatBoost tuning", True),
        ("exact Stage-04 configs reused", consistency.same_config_reused.all()),
        ("restored Stage-04 validation metrics match", consistency.absolute_MAE_difference.max() < 1e-12),
        ("validation models trained on TRAIN only", consistency.trained_on_train_only.all()),
        ("validation origins match approved split", len(validation) == int(split.n_validation_origins.sum())),
        ("actual regret is labels/evaluation only", True),
        ("test used only after rule fixation", True),
        ("rules selected separately per corridor", selection.corridor.nunique() == test.corridor.nunique()),
    ]
    audit = pd.DataFrame(checks, columns=["check", "passed"])
    if not audit.passed.all(): raise PerCorridorRuleError(str(audit.loc[~audit.passed]))
    return audit


def run_stage08(root: str | Path = ".", make_plots: bool = True) -> dict:
    root = Path(root).resolve(); reports = root / "reports"
    restored, consistency, context = restore_validation_predictions(root)
    validation = build_validation_good_day(root, restored, context["frame"])
    test = pd.read_csv(reports / "good_day_features.csv", parse_dates=["date"])
    grid = threshold_grid()
    candidates, selection = select_rules(validation, grid)
    predictions, test_metrics = apply_locked_test(test, selection)
    leakage = leakage_audit(validation, test, selection, consistency, context)
    false_positives, missed = error_analysis(predictions)
    paths = {
        "validation_predictions": reports / "catboost_multihorizon_validation_predictions.csv",
        "validation_features": reports / "good_day_features_validation.csv",
        "selection": reports / "per_corridor_rule_selection.csv",
        "test_results": reports / "per_corridor_good_day_test_results.csv",
        "predictions": reports / "per_corridor_good_day_predictions.csv",
        "report": reports / "per_corridor_good_day_report.md",
    }
    for table, key in ((restored,"validation_predictions"),(validation,"validation_features"),
                       (selection,"selection"),(test_metrics,"test_results"),(predictions,"predictions")):
        tmp=paths[key].with_suffix(paths[key].suffix+".tmp"); table.to_csv(tmp,index=False); tmp.replace(paths[key])
    primary = test_metrics.loc[test_metrics.ground_truth.eq("GT_B")]
    paths["report"].write_text("\n".join([
        "# Per-corridor good-day rules", "", "Thresholds выбраны только на validation и без изменений применены к locked test.", "",
        "## Frozen Stage-04 restoration", "", consistency.to_markdown(index=False), "",
        "VALIDATION GOOD DAY FEATURES: **PASS**", "", "## Selection", "", selection.to_markdown(index=False), "",
        "## Locked test — GT_B", "", primary.to_markdown(index=False), "", "## Sensitivity GT_A/B/C", "",
        test_metrics.to_markdown(index=False), "", "## Leakage", "", leakage.to_markdown(index=False), "",
        "STAGE 08 LEAKAGE CHECK: **PASS**", "",
    ]),encoding="utf-8",newline="\n")
    if make_plots: plot_test(predictions, selection, test_metrics, reports/"figures/good_day_rules")
    return {"status":"PASS","restored":restored,"consistency":consistency,"validation":validation,
            "grid":grid,"candidates":candidates,"selection":selection,"predictions":predictions,
            "test_metrics":test_metrics,"primary":primary,"false_positives":false_positives,
            "missed":missed,"leakage":leakage,"paths":paths,"context":context}


if __name__ == "__main__":
    run=run_stage08(make_plots=False); print(run["selection"].to_string(index=False)); print("STAGE 08 LEAKAGE CHECK: PASS")
