"""Stage 2 diagnostics for real CBR quote-time FX series.

This module performs no forecasting and trains no tournament model. It is called
from ``notebooks/02_model_tournament.ipynb`` and writes only the requested summary.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from IPython.display import Markdown, display
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.stattools import acf as sm_acf
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.stattools import pacf as sm_pacf

ALPHA = 0.05
MAX_LAG = 40
MAX_GRID_ORDER = 5
FORECAST_HORIZONS = (1, 3, 5, 10)
PRIMARY_PRODUCT_HORIZON = 5
MAX_FORECAST_HORIZON = max(FORECAST_HORIZONS)
MODEL_SELECTION_POLICY = [
    {
        "priority": 1,
        "rule": "eligibility",
        "criterion": "finite validation metrics on common origins for H=1,3,5,10",
    },
    {
        "priority": 2,
        "rule": "primary_ranking",
        "criterion": "minimum validation RATE MAE at primary H=5",
    },
    {
        "priority": 3,
        "rule": "long_horizon_tiebreak",
        "criterion": "minimum validation RATE MAE at H=10",
    },
    {
        "priority": 4,
        "rule": "secondary_tiebreak",
        "criterion": "minimum validation RATE RMSE at H=5, then lower p+q",
    },
    {
        "priority": 5,
        "rule": "promotion_guardrail",
        "criterion": "compare selected model with NAIVE at both H=5 and H=10",
    },
    {
        "priority": 6,
        "rule": "diagnostic_only",
        "criterion": "H=1 and H=3 cannot select the winner on their own",
    },
    {
        "priority": 7,
        "rule": "test_lock",
        "criterion": "test metrics never select p,d,q or preprocessing",
    },
]
SUMMARY_COLUMNS = [
    "corridor",
    "rate_adf_p",
    "rate_kpss_p",
    "diff_rate_adf_p",
    "diff_rate_kpss_p",
    "log_return_adf_p",
    "log_return_kpss_p",
    "recommended_rate_d",
    "recommended_logret_d",
]


def _stationarity_tests(series: pd.Series) -> dict[str, object]:
    clean = pd.to_numeric(series, errors="raise").dropna()
    if len(clean) < 50:
        raise ValueError(f"Not enough observations for tests: {len(clean)}")
    adf = adfuller(
        clean.to_numpy(),
        regression="c",
        autolag="AIC",
        result_object=False,
    )
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        kpss_result = kpss(clean.to_numpy(), regression="c", nlags="auto")
    return {
        "adf_statistic": float(adf[0]),
        "adf_p": float(adf[1]),
        "adf_used_lags": int(adf[2]),
        "adf_n_obs": int(adf[3]),
        "kpss_statistic": float(kpss_result[0]),
        "kpss_p": float(kpss_result[1]),
        "kpss_used_lags": int(kpss_result[2]),
        "kpss_warning": " | ".join(str(item.message) for item in captured),
    }


def _conclusion(adf_p: float, kpss_p: float) -> str:
    adf_rejects = adf_p < ALPHA
    kpss_rejects = kpss_p < ALPHA
    if adf_rejects and not kpss_rejects:
        return "evidence consistent with stationarity"
    if not adf_rejects and kpss_rejects:
        return "evidence consistent with non-stationarity"
    if adf_rejects and kpss_rejects:
        return "mixed evidence: possible regime/variance change"
    return "inconclusive: neither null rejected"


def _prepare_series(dataset_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    frame = pd.read_parquet(dataset_path).copy()
    required = {"date", "corridor", "rate", "log_ret_1"}
    if missing := required.difference(frame.columns):
        raise ValueError(f"Missing Stage 2 columns: {sorted(missing)}")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame = frame.sort_values(["corridor", "date"]).reset_index(drop=True)
    if frame.duplicated(["corridor", "date"]).any():
        examples = frame.loc[
            frame.duplicated(["corridor", "date"], keep=False),
            ["corridor", "date"],
        ].head(10)
        raise ValueError(f"Duplicate corridor/date rows:\n{examples}")

    frame["diff_rate"] = frame.groupby("corridor", sort=False)["rate"].diff()
    frame["manual_log_ret_1"] = np.log(
        frame["rate"] / frame.groupby("corridor", sort=False)["rate"].shift(1)
    )
    frame["log_ret_abs_error"] = (
        frame["log_ret_1"] - frame["manual_log_ret_1"]
    ).abs()
    comparable = frame.dropna(subset=["log_ret_1", "manual_log_ret_1"])
    max_error = float(comparable["log_ret_abs_error"].max())
    if max_error > 1e-12:
        raise AssertionError(f"log_ret_1 mismatch; max abs error={max_error:.3e}")
    checks = (
        comparable.groupby("corridor", group_keys=False)
        .sample(n=3, random_state=42)
        .sort_values(["corridor", "date"])
        .loc[
            :,
            [
                "date",
                "corridor",
                "rate",
                "manual_log_ret_1",
                "log_ret_1",
                "log_ret_abs_error",
            ],
        ]
        .rename(columns={"manual_log_ret_1": "expected_log_ret_1"})
    )
    return frame, checks, max_error


def _plot_series(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    display(Markdown("## 2. Visual diagnostics"))
    for corridor, group in frame.groupby("corridor", sort=True):
        series = group.set_index("date").sort_index()
        fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)
        axes[0].plot(series.index, series["rate"], linewidth=1)
        axes[0].set_title(f"{corridor}: normalized rate")
        axes[0].set_ylabel("RUB / currency unit")
        axes[1].plot(series.index, series["diff_rate"], linewidth=0.8)
        axes[1].set_title(f"{corridor}: first difference of rate")
        axes[2].plot(series.index, series["log_ret_1"], linewidth=0.8)
        axes[2].set_title(f"{corridor}: log_ret_1")
        axes[2].set_xlabel("Quote date")
        for axis in axes:
            axis.axhline(0, color="black", linewidth=0.5)
            axis.grid(alpha=0.25)
        plt.tight_layout()
        plt.show()
        change = (series["rate"].iloc[-1] / series["rate"].iloc[0] - 1) * 100
        diff_std = series["diff_rate"].std()
        log_std = series["log_ret_1"].std()
        display(
            Markdown(
                f"**{corridor}.** `rate` изменился между краями выборки на "
                f"`{change:.1f}%`; это описание истории, не прогноз. `diff_rate` "
                f"колеблется около нуля (std `{diff_std:.6g}`), но имеет всплески. "
                f"`log_ret_1` нормирует масштаб (std `{log_std:.6g}`). Вывод о "
                "стационарности делается ниже по ADF/KPSS, а не только по графику."
            )
        )
        rows.append(
            {
                "corridor": corridor,
                "rate_change_pct": change,
                "diff_rate_std": diff_std,
                "log_return_std": log_std,
            }
        )
    return pd.DataFrame(rows)


def _plot_rolling(frame: pd.DataFrame) -> None:
    display(Markdown("## 3. Rolling statistics: 20 и 60 quote observations"))
    for corridor, group in frame.groupby("corridor", sort=True):
        series = group.set_index("date").sort_index()
        fig, axes = plt.subplots(2, 2, figsize=(15, 8), sharex=True)
        for window in (20, 60):
            rate_roll = series["rate"].rolling(window)
            log_roll = series["log_ret_1"].rolling(window)
            axes[0, 0].plot(series.index, rate_roll.mean(), label=f"mean {window}")
            axes[0, 1].plot(series.index, rate_roll.std(), label=f"std {window}")
            axes[1, 0].plot(series.index, log_roll.mean(), label=f"mean {window}")
            axes[1, 1].plot(series.index, log_roll.std(), label=f"std {window}")
        titles = ["rate mean", "rate std", "log return mean", "log return std"]
        for axis, title in zip(axes.flat, titles, strict=True):
            axis.set_title(f"{corridor}: rolling {title}")
            axis.legend()
            axis.grid(alpha=0.25)
        plt.tight_layout()
        plt.show()
        rate_std = series["rate"].rolling(20).std().dropna()
        log_std = series["log_ret_1"].rolling(20).std().dropna()
        display(
            Markdown(
                f"**{corridor}.** Rolling mean уровня и rolling variance меняются "
                f"во времени. Для окна 20 отношение max/min rolling std равно "
                f"`{rate_std.max() / rate_std.min():.2f}` для rate и "
                f"`{log_std.max() / log_std.min():.2f}` для log returns. Это "
                "диагностика меняющейся волатильности, не forecast conclusion."
            )
        )


def _run_all_tests(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    columns = {"rate": "rate", "diff_rate": "diff_rate", "log_return": "log_ret_1"}
    for corridor, group in frame.groupby("corridor", sort=True):
        for series_name, column in columns.items():
            result = _stationarity_tests(group[column])
            rows.append(
                {
                    "corridor": corridor,
                    "series": series_name,
                    **result,
                    "diagnostic_conclusion": _conclusion(
                        result["adf_p"], result["kpss_p"]
                    ),
                }
            )
    return pd.DataFrame(rows)


def _make_summary(tests: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    wide = tests.pivot(index="corridor", columns="series", values=["adf_p", "kpss_p"])
    rows = []
    for corridor in wide.index:
        values = {
            "rate_adf_p": float(wide.loc[corridor, ("adf_p", "rate")]),
            "rate_kpss_p": float(wide.loc[corridor, ("kpss_p", "rate")]),
            "diff_rate_adf_p": float(wide.loc[corridor, ("adf_p", "diff_rate")]),
            "diff_rate_kpss_p": float(wide.loc[corridor, ("kpss_p", "diff_rate")]),
            "log_return_adf_p": float(wide.loc[corridor, ("adf_p", "log_return")]),
            "log_return_kpss_p": float(wide.loc[corridor, ("kpss_p", "log_return")]),
        }
        rate_d = int(
            not (
                values["rate_adf_p"] < ALPHA
                and values["rate_kpss_p"] >= ALPHA
            )
            and values["diff_rate_adf_p"] < ALPHA
        )
        rows.append(
            {
                "corridor": corridor,
                **values,
                "recommended_rate_d": rate_d,
                "recommended_logret_d": 0,
                "rate_conclusion": _conclusion(
                    values["rate_adf_p"], values["rate_kpss_p"]
                ),
                "diff_rate_conclusion": _conclusion(
                    values["diff_rate_adf_p"], values["diff_rate_kpss_p"]
                ),
                "log_return_conclusion": _conclusion(
                    values["log_return_adf_p"], values["log_return_kpss_p"]
                ),
            }
        )
    full = pd.DataFrame(rows)
    return full[SUMMARY_COLUMNS], full


def _plot_acf_pacf(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    display(Markdown("## 7. ACF/PACF и границы будущего grid search"))
    for corridor, group in frame.groupby("corridor", sort=True):
        inputs = {
            "log_return": group["log_ret_1"].dropna(),
            "diff_rate": group["diff_rate"].dropna(),
        }
        fig, axes = plt.subplots(2, 2, figsize=(15, 9))
        for row_index, (name, series) in enumerate(inputs.items()):
            lag = min(MAX_LAG, len(series) // 4 - 1)
            plot_acf(series, lags=lag, zero=False, ax=axes[row_index, 0])
            plot_pacf(series, lags=lag, zero=False, method="ywm", ax=axes[row_index, 1])
            axes[row_index, 0].set_title(f"{corridor}: ACF {name}")
            axes[row_index, 1].set_title(f"{corridor}: PACF {name}")
            bound = 1.96 / np.sqrt(len(series))
            acf_values = sm_acf(series, nlags=lag, fft=True)
            pacf_values = sm_pacf(series, nlags=lag, method="ywm")
            acf_lags = [i for i in range(1, 11) if abs(acf_values[i]) > bound]
            pacf_lags = [i for i in range(1, 11) if abs(pacf_values[i]) > bound]
            rows.append(
                {
                    "corridor": corridor,
                    "series": name,
                    "max_lag_plotted": lag,
                    "significant_acf_lags_first_10": acf_lags,
                    "significant_pacf_lags_first_10": pacf_lags,
                    "candidate_p_range": f"0..{min(MAX_GRID_ORDER, max(pacf_lags, default=1))}",
                    "candidate_q_range": f"0..{min(MAX_GRID_ORDER, max(acf_lags, default=1))}",
                }
            )
        plt.tight_layout()
        plt.show()
        display(
            Markdown(
                f"**{corridor}.** ACF/PACF ограничивают будущую сетку порядками "
                f"не выше `{MAX_GRID_ORDER}`, но не выбирают `p/q`. Выбор будет "
                "сделан только по validation metrics."
            )
        )
        display(pd.DataFrame([row for row in rows if row["corridor"] == corridor]))
    return pd.DataFrame(rows)


def _temporal_split(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for corridor, group in frame.groupby("corridor", sort=True):
        ordered = group.sort_values("date").reset_index(drop=True)
        train_stop = int(np.floor(len(ordered) * 0.70))
        validation_stop = int(np.floor(len(ordered) * 0.85))
        train = ordered.iloc[:train_stop]
        validation = ordered.iloc[train_stop:validation_stop]
        test = ordered.iloc[validation_stop:]
        validation_origins = ordered.iloc[
            train_stop - 1 : validation_stop - MAX_FORECAST_HORIZON
        ]
        test_origins = ordered.iloc[
            validation_stop - 1 : len(ordered) - MAX_FORECAST_HORIZON
        ]
        right_censored = ordered.iloc[-MAX_FORECAST_HORIZON:]
        if not (
            train["date"].max() < validation["date"].min()
            and validation["date"].max() < test["date"].min()
        ):
            raise AssertionError(f"Temporal split overlap for {corridor}")
        rows.append(
            {
                "corridor": corridor,
                "train_start": train["date"].min(),
                "train_end": train["date"].max(),
                "validation_start": validation["date"].min(),
                "validation_end": validation["date"].max(),
                "test_start": test["date"].min(),
                "test_end": test["date"].max(),
                "n_train": len(train),
                "n_validation": len(validation),
                "n_test": len(test),
                "validation_origin_start": validation_origins["date"].min(),
                "validation_origin_end": validation_origins["date"].max(),
                "test_origin_start": test_origins["date"].min(),
                "test_origin_end": test_origins["date"].max(),
                "n_validation_origins": len(validation_origins),
                "n_test_origins": len(test_origins),
                "n_right_censored_origins": len(right_censored),
                "forecast_horizons": ",".join(map(str, FORECAST_HORIZONS)),
                "primary_horizon": PRIMARY_PRODUCT_HORIZON,
                "max_horizon": MAX_FORECAST_HORIZON,
            }
        )
    return pd.DataFrame(rows)


def run_stage2(root: str | Path = ".") -> dict[str, object]:
    """Execute Stage 2 and return notebook-visible diagnostic artifacts."""
    root = Path(root).resolve()
    dataset_path = root / "data" / "features" / "fx_features_daily.parquet"
    report_path = root / "reports" / "time_series_diagnostics.csv"
    split_path = root / "reports" / "temporal_split_horizons.csv"
    policy_path = root / "reports" / "model_selection_policy.csv"

    display(Markdown("# STAGE 2 — TIME SERIES DIAGNOSTICS"))
    display(Markdown("Model tournament на этом этапе не выполняется."))
    frame, formula_checks, max_error = _prepare_series(dataset_path)
    splits = _temporal_split(frame)
    training_parts = []
    for split in splits.itertuples(index=False):
        training_parts.append(
            frame.loc[
                (frame["corridor"] == split.corridor)
                & (frame["date"] <= pd.Timestamp(split.train_end))
            ]
        )
    diagnostic_frame = pd.concat(training_parts, ignore_index=True)
    display(Markdown("## 1. Series и проверка формулы log return"))
    display(Markdown(f"Максимальная абсолютная ошибка: `{max_error:.3e}`."))
    display(formula_checks)
    display(
        Markdown(
            "Все diagnostics, влияющие на выбор `d` и будущих границ `p/q`, "
            "рассчитываются только на TRAIN. Validation и TEST для этого не читаются."
        )
    )
    visual_summary = _plot_series(diagnostic_frame)
    _plot_rolling(diagnostic_frame)

    display(Markdown("## 4–6. ADF, KPSS и differencing d"))
    display(
        Markdown(
            "ADF: H0 = unit root. KPSS: H0 = stationarity. При `p < 0.05` "
            "соответствующая H0 отвергается. Тесты — complementary evidence; "
            "они не доказывают стационарность."
        )
    )
    tests = _run_all_tests(diagnostic_frame)
    display(tests)
    summary, full_summary = _make_summary(tests)
    display(
        Markdown(
            "Для raw rate рассматриваются только `d=0/1`; основной кандидат при "
            "нестационарном уровне и более стационарной первой разности — "
            "`ARIMA(p,1,q)`. Для log return основной кандидат — `ARIMA(p,0,q)`. "
            "`d>1` без сильного основания не используется."
        )
    )
    display(full_summary)
    lag_diagnostics = _plot_acf_pacf(diagnostic_frame)

    display(Markdown("## 8. Forecast horizons и chronological split"))
    display(
        Markdown(
            "Зафиксированы quote-observation horizons `H=[1,3,5,10]`; это не "
            "календарные дни. `H=5` — PRIMARY PRODUCT HORIZON, остальные горизонты "
            "проверяют более короткое и длинное поведение. Forecast origin допустим "
            "только при наличии всех actual observations до `T+10`. Последние 10 "
            "строк каждого ряда исключаются только как origins: это right-censoring, "
            "а не missing data. Validation targets не пересекаются с test targets."
        )
    )
    display(Markdown("### Обязательная policy выбора p,d,q"))
    display(
        Markdown(
            "`p,d,q` нельзя выбирать по one-step MAE. После train-only ограничения "
            "кандидатов итоговая спецификация ранжируется на VALIDATION прежде всего "
            "по RATE MAE на primary `H=5`. `H=10` — обязательный long-horizon "
            "tie-breaker и guardrail при сравнении с Naive. `H=1` и `H=3` "
            "показываются как diagnostics и не выбирают победителя самостоятельно."
        )
    )
    selection_policy = pd.DataFrame(MODEL_SELECTION_POLICY)
    display(selection_policy)
    display(splits)
    display(
        Markdown(
            "## TEST SET IS LOCKED.\n\n"
            "`p,d,q`, preprocessing choices и model selection не выбираются по "
            "test metrics. Validation используется для выбора; test — только для "
            "финальной проверки. Split одинаков для Naive, ARIMA rate и ARIMA log-return."
        )
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(".csv.tmp")
    summary.to_csv(temporary, index=False)
    temporary.replace(report_path)
    split_temporary = split_path.with_suffix(".csv.tmp")
    splits.to_csv(split_temporary, index=False)
    split_temporary.replace(split_path)
    policy_temporary = policy_path.with_suffix(".csv.tmp")
    selection_policy.to_csv(policy_temporary, index=False)
    policy_temporary.replace(policy_path)
    checks = {
        "all_corridors_present": len(summary) == frame["corridor"].nunique() == 5,
        "schema_exact": list(summary.columns) == SUMMARY_COLUMNS,
        "no_missing_summary": not summary.isna().any().any(),
        "formula_valid": max_error <= 1e-12,
        "all_tests_executed": len(tests) == 15,
        "diagnostics_train_only": len(diagnostic_frame)
        == int(splits["n_train"].sum()),
        "split_sizes_valid": (splits[["n_train", "n_validation", "n_test"]] > 0).all().all(),
        "horizons_fixed": FORECAST_HORIZONS == (1, 3, 5, 10),
        "primary_horizon_fixed": PRIMARY_PRODUCT_HORIZON == 5,
        "selection_primary_is_h5": "H=5"
        in MODEL_SELECTION_POLICY[1]["criterion"],
        "h1_not_selection_objective": "cannot select"
        in MODEL_SELECTION_POLICY[5]["criterion"],
        "right_censoring_valid": (
            splits["n_right_censored_origins"] == MAX_FORECAST_HORIZON
        ).all(),
        "report_saved": report_path.exists()
        and split_path.exists()
        and policy_path.exists(),
        "models_trained": 0,
    }
    passed = all(bool(value) for key, value in checks.items() if key != "models_trained")
    passed = passed and checks["models_trained"] == 0
    display(Markdown(f"# STAGE 2 — TIME SERIES DIAGNOSTICS: {'PASS' if passed else 'FAIL'}"))
    for row in full_summary.itertuples(index=False):
        display(
            Markdown(
                f"**{row.corridor}:** raw rate — {row.rate_conclusion}; "
                f"differenced rate — {row.diff_rate_conclusion}; log return — "
                f"{row.log_return_conclusion}; recommended rate ARIMA `d="
                f"{row.recommended_rate_d}`; recommended log-return ARIMA "
                f"`d={row.recommended_logret_d}`."
            )
        )
    print(f"Report: {report_path.relative_to(root).as_posix()}")
    print(f"Split report: {split_path.relative_to(root).as_posix()}")
    print(f"Selection policy: {policy_path.relative_to(root).as_posix()}")
    print("Models trained: 0")
    print("TEST SET IS LOCKED.")
    if not passed:
        raise AssertionError(f"Stage 2 checks failed: {checks}")
    return {
        "summary": summary,
        "tests": tests,
        "splits": splits,
        "selection_policy": selection_policy,
        "lag_diagnostics": lag_diagnostics,
        "visual_summary": visual_summary,
        "checks": checks,
    }
