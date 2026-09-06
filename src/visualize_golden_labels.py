"""Create zoomable SVG charts with golden labels and a prioritized push stream."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from src.build_golden_labels import (
    CLOSING_HORIZON_DAYS,
    CLOSING_MAX_REBOUND_BPS,
    CLOSING_MIN_FUTURE_MEDIAN_RISE_BPS,
    CLOSING_MIN_REBOUND_BPS,
    HORIZONS,
    RULES,
)

WIDTH = 1500
PANEL_HEIGHT = 260
LEFT = 92
RIGHT = 35
TOP = 100
BOTTOM = 36

RULE_TITLES = {
    "regret_max": "Будущий regret не превышает порог",
    "near_local_min": "Курс близок к локальному минимуму",
    "centered_mean_benefit": "Курс лучше локального среднего",
    "future_median_benefit": "Курс лучше будущей медианы",
    "stable_80pct": "Курс выдерживает сравнение с 80% будущих дней",
    "no_early_better": "В ближайшей половине горизонта нет заметно лучшего дня",
    "low_p10_30_and_regret": "Редко низкий курс за 30 котировок + малый regret",
    "low_p20_60_and_regret": "Низкий курс за 60 котировок + малый regret",
}

RULE_EXPLANATIONS = {
    "near_local_min": ("good, если курс T не более чем на X хуже минимального курса в календарном окне [T−h; T+h]"),
    "regret_max": "good, если в следующие h дней курс не станет лучше более чем на X",
    "centered_mean_benefit": "good, если курс T лучше среднего в окне [T−h; T+h] минимум на X",
    "future_median_benefit": "good, если курс T лучше медианы следующих h дней минимум на X",
    "stable_80pct": "good, если хотя бы 80% следующих h дней не лучше T более чем на X",
    "no_early_better": "good, если в первой половине следующих h дней нет курса лучше T более чем на X",
    "low_p10_30_and_regret": "good, если курс в нижних 10% прошлых 30 котировок и future regret ≤ X",
    "low_p20_60_and_regret": "good, если курс в нижних 20% прошлых 60 котировок и future regret ≤ X",
}


def select_pushes(frame: pd.DataFrame, *, cooldown_days: int = 4, weekly_cap: int = 2) -> pd.Series:
    """Thin retrospective good days into an illustrative communication stream.

    The first available good date is selected. Further dates require a rolling
    calendar-day cooldown and are capped per ISO calendar week.
    """
    selected = pd.Series(False, index=frame.index, dtype=bool)
    last_push: pd.Timestamp | None = None
    weekly_counts: dict[tuple[int, int], int] = {}
    for index, row in frame.sort_values("date").iterrows():
        if not bool(row.good):
            continue
        date = pd.Timestamp(row.date)
        iso = date.isocalendar()
        week = (int(iso.year), int(iso.week))
        cooldown_passed = last_push is None or (date - last_push).days >= cooldown_days
        if cooldown_passed and weekly_counts.get(week, 0) < weekly_cap:
            selected.loc[index] = True
            last_push = date
            weekly_counts[week] = weekly_counts.get(week, 0) + 1
    return selected


def select_scenario_pushes(
    frame: pd.DataFrame, *, cooldown_days: int = 4, weekly_cap: int = 2
) -> tuple[pd.Series, pd.Series]:
    """Select a causal stream with good, closing, then market-fact priority."""
    selected = pd.Series(False, index=frame.index, dtype=bool)
    scenario = pd.Series(pd.NA, index=frame.index, dtype="string")
    last_push: pd.Timestamp | None = None
    weekly_counts: dict[tuple[int, int], int] = {}
    for index, row in frame.sort_values("date").iterrows():
        candidate = (
            "good_now"
            if bool(row.good)
            else "window_closing"
            if bool(row.closing)
            else "positive_market_fact"
            if bool(getattr(row, "positive_market_fact", False))
            else None
        )
        if candidate is None:
            continue
        date = pd.Timestamp(row.date)
        iso = date.isocalendar()
        week = (int(iso.year), int(iso.week))
        cooldown_passed = last_push is None or (date - last_push).days >= cooldown_days
        if cooldown_passed and weekly_counts.get(week, 0) < weekly_cap:
            selected.loc[index] = True
            scenario.loc[index] = candidate
            last_push = date
            weekly_counts[week] = weekly_counts.get(week, 0) + 1
    return selected, scenario


def _path(
    frame: pd.DataFrame, x0: float, x1: float, y0: float, y1: float
) -> tuple[
    str,
    Callable[[pd.Timestamp], float],
    Callable[[float], float],
    float,
    float,
]:
    dates = pd.to_datetime(frame.date)
    start, stop = dates.min().value, dates.max().value
    rates = frame.rate.astype(float)
    low, high = rates.min(), rates.max()
    padding = max((high - low) * 0.08, high * 0.002)
    low, high = low - padding, high + padding

    def x_scale(value: pd.Timestamp) -> float:
        return x0 + (value.value - start) / (stop - start) * (x1 - x0)

    def y_scale(value: float) -> float:
        return y1 - (value - low) / (high - low) * (y1 - y0)

    points = " ".join(f"{x_scale(date):.1f},{y_scale(rate):.1f}" for date, rate in zip(dates, rates, strict=True))
    return points, x_scale, y_scale, low, high


def plot_rule(
    labels_dir: Path,
    output_dir: Path,
    *,
    rule: str,
    corridor: str,
    x_bps: int,
    cooldown_days: int,
    weekly_cap: int,
) -> Path:
    """Save rate and good points for one rule across all horizons as a vector SVG."""
    height = TOP + len(HORIZONS) * PANEL_HEIGHT + BOTTOM
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        "<style>text{font-family:-apple-system,BlinkMacSystemFont,sans-serif;fill:#17202a}"
        ".axis{stroke:#bfc9ca;stroke-width:1}.line{fill:none;stroke:#34495e;stroke-width:1.4}"
        ".good{fill:#e74c3c;fill-opacity:.62;stroke:white;stroke-width:.7}"
        ".push{fill:#1565c0;stroke:white;stroke-width:1.2}</style>",
        f'<text x="{LEFT}" y="28" font-size="20" font-weight="600">'
        f"{escape(corridor)} · {escape(RULE_TITLES[rule])}</text>",
        f'<text x="{LEFT}" y="50" font-size="12">{escape(RULE_EXPLANATIONS[rule])}; '
        f"X = {x_bps} bps ({x_bps / 100:.2g}%). Чем ниже курс, тем выгоднее перевод.</text>",
        f'<text x="{LEFT}" y="70" font-size="12">'
        "Красная точка — исторически good; синий ромб — push после коммуникационного фильтра: "
        f"cooldown {cooldown_days} дня, максимум {weekly_cap} в неделю.</text>",
        f'<text x="{LEFT}" y="89" font-size="11" fill="#5d6d7e">'
        "h измеряется в календарных днях; выходные заполнены последним опубликованным курсом ЦБ. "
        "SVG можно масштабировать в браузере.</text>",
    ]
    for index, horizon in enumerate(HORIZONS):
        name = f"{rule}__h-{horizon:02d}__x-{x_bps:03d}bps.parquet"
        frame = pd.read_parquet(labels_dir / name)
        frame = frame.loc[frame.corridor.eq(corridor)].sort_values("date")
        frame["push"] = select_pushes(frame, cooldown_days=cooldown_days, weekly_cap=weekly_cap)
        y0 = TOP + index * PANEL_HEIGHT + 28
        y1 = TOP + (index + 1) * PANEL_HEIGHT - 42
        x0, x1 = LEFT, WIDTH - RIGHT
        points, x_scale, y_scale, low, high = _path(frame, x0, x1, y0, y1)
        good = frame.loc[frame.good]
        pushes = frame.loc[frame.push]
        parts.extend(
            [
                f'<line class="axis" x1="{x0}" x2="{x0}" y1="{y0}" y2="{y1}"/>',
                f'<line class="axis" x1="{x0}" x2="{x1}" y1="{y1}" y2="{y1}"/>',
                f'<text x="{x0}" y="{y0 - 9}" font-size="14" font-weight="600">'
                f"h = {horizon} календарных дней · good-дней: {len(good)} · push: {len(pushes)}</text>",
                f'<text x="8" y="{y0 + 4}" font-size="11">{high:.5g}</text>',
                f'<text x="8" y="{y1}" font-size="11">{low:.5g}</text>',
                f'<polyline class="line" points="{points}"/>',
            ]
        )
        for row in good.itertuples(index=False):
            x, y = x_scale(pd.Timestamp(row.date)), y_scale(float(row.rate))
            tooltip = f"{row.date:%Y-%m-%d}; rate={row.rate:.6g}; regret={row.future_regret_bps:.1f} bps"
            parts.append(
                f'<circle class="good" cx="{x:.1f}" cy="{y:.1f}" r="4"><title>{escape(tooltip)}</title></circle>'
            )
        for row in pushes.itertuples(index=False):
            x, y = x_scale(pd.Timestamp(row.date)), y_scale(float(row.rate))
            tooltip = f"PUSH {row.date:%Y-%m-%d}; rate={row.rate:.6g}"
            size = 7
            points = f"{x:.1f},{y - size:.1f} {x + size:.1f},{y:.1f} {x:.1f},{y + size:.1f} {x - size:.1f},{y:.1f}"
            parts.append(f'<polygon class="push" points="{points}"><title>{escape(tooltip)}</title></polygon>')
        labels = (
            (0, frame.date.min().strftime("%Y-%m")),
            (0.5, frame.date.iloc[len(frame) // 2].strftime("%Y-%m")),
            (1, frame.date.max().strftime("%Y-%m")),
        )
        for fraction, label in labels:
            x = x0 + fraction * (x1 - x0)
            parts.append(f'<text x="{x:.1f}" y="{y1 + 20}" font-size="11" text-anchor="middle">{label}</text>')
    parts.append("</svg>")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{corridor}__{rule}__x-{x_bps:03d}bps.svg"
    output.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return output


def write_communication_review(
    labels_dir: Path,
    output_dir: Path,
    *,
    corridor: str,
    x_bps: int,
    cooldown_days: int,
    weekly_cap: int,
) -> tuple[Path, Path]:
    """Write aggregate counts and selected push dates for reproducible review."""
    summary_rows = []
    schedule_parts = []
    for item in RULES:
        for horizon in HORIZONS:
            name = f"{item.identifier}__h-{horizon:02d}__x-{x_bps:03d}bps.parquet"
            frame = pd.read_parquet(labels_dir / name)
            frame = frame.loc[frame.corridor.eq(corridor)].sort_values("date").copy()
            frame["date"] = pd.to_datetime(frame.date)
            frame["push"] = select_pushes(frame, cooldown_days=cooldown_days, weekly_cap=weekly_cap)
            pushes = frame.loc[frame.push].copy()
            week_counts = pushes.date.dt.to_period("W-SUN").value_counts()
            gaps = pushes.date.diff().dt.days.dropna()
            observed_weeks = frame.date.dt.to_period("W-SUN").nunique()
            summary_rows.append(
                {
                    "rule": item.identifier,
                    "horizon_calendar_days": horizon,
                    "x_bps": x_bps,
                    "corridor": corridor,
                    "good_days": int(frame.good.sum()),
                    "pushes": len(pushes),
                    "observed_weeks": observed_weeks,
                    "pushes_per_week": len(pushes) / observed_weeks,
                    "weeks_with_push": len(week_counts),
                    "weeks_with_two_pushes": int(week_counts.eq(2).sum()),
                    "median_gap_days": float(gaps.median()) if len(gaps) else np.nan,
                    "cooldown_calendar_days": cooldown_days,
                    "weekly_cap": weekly_cap,
                }
            )
            if not pushes.empty:
                schedule = pushes[["date", "rate", "future_regret_bps"]].copy()
                schedule.insert(0, "horizon_calendar_days", horizon)
                schedule.insert(0, "rule", item.identifier)
                schedule_parts.append(schedule)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / f"{corridor}__communication_summary__x-{x_bps:03d}bps.csv"
    schedule_path = output_dir / f"{corridor}__push_schedule__x-{x_bps:03d}bps.csv"
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)
    pd.concat(schedule_parts, ignore_index=True).to_csv(schedule_path, index=False)
    return summary_path, schedule_path


def plot_weekend_review(
    labels_dir: Path,
    output_dir: Path,
    *,
    corridor: str,
    horizon: int,
    x_bps: int,
    cooldown_days: int,
    weekly_cap: int,
) -> tuple[Path, Path]:
    """Compare the original label with a Saturday/Sunday eligibility filter."""
    name = f"near_local_min__h-{horizon:02d}__x-{x_bps:03d}bps.parquet"
    source = pd.read_parquet(labels_dir / name)
    source = source.loc[source.corridor.eq(corridor)].sort_values("date").copy()
    source["date"] = pd.to_datetime(source.date)
    source["is_weekend"] = source.date.dt.dayofweek.ge(5)
    source["original_good"] = source.good
    source["original_push"] = select_pushes(source, cooldown_days=cooldown_days, weekly_cap=weekly_cap)
    source["good"] = source.original_good & ~source.is_weekend
    source["weekday_push"] = select_pushes(source, cooldown_days=cooldown_days, weekly_cap=weekly_cap)

    height = TOP + 2 * PANEL_HEIGHT + BOTTOM
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        "<style>text{font-family:-apple-system,BlinkMacSystemFont,sans-serif;fill:#17202a}"
        ".axis{stroke:#bfc9ca;stroke-width:1}.line{fill:none;stroke:#34495e;stroke-width:1.4}"
        ".good{fill:#e74c3c;fill-opacity:.62;stroke:white;stroke-width:.7}"
        ".push{fill:#1565c0;stroke:white;stroke-width:1.2}"
        ".weekend{stroke:#f39c12;stroke-width:2.5}</style>",
        f'<text x="{LEFT}" y="28" font-size="20" font-weight="600">'
        f"{escape(corridor)} · влияние выходных на near_local_min</text>",
        f'<text x="{LEFT}" y="50" font-size="12">h = {horizon} календарных дней; '
        f"X = {x_bps} bps. Оранжевый крест — good-день, попавший на субботу или воскресенье.</text>",
        f'<text x="{LEFT}" y="70" font-size="12">Красная точка — доступный good; '
        f"синий ромб — push после cooldown {cooldown_days} дня и лимита {weekly_cap} в неделю.</text>",
    ]
    panels = (
        ("Без календарного запрета", "original_good", "original_push"),
        ("Суббота и воскресенье исключены", "good", "weekday_push"),
    )
    for index, (title, good_column, push_column) in enumerate(panels):
        y0 = TOP + index * PANEL_HEIGHT + 28
        y1 = TOP + (index + 1) * PANEL_HEIGHT - 42
        x0, x1 = LEFT, WIDTH - RIGHT
        points, x_scale, y_scale, low, high = _path(source, x0, x1, y0, y1)
        good = source.loc[source[good_column]]
        pushes = source.loc[source[push_column]]
        parts.extend(
            [
                f'<line class="axis" x1="{x0}" x2="{x0}" y1="{y0}" y2="{y1}"/>',
                f'<line class="axis" x1="{x0}" x2="{x1}" y1="{y1}" y2="{y1}"/>',
                f'<text x="{x0}" y="{y0 - 9}" font-size="14" font-weight="600">'
                f"{escape(title)} · good-дней: {len(good)} · push: {len(pushes)}</text>",
                f'<text x="8" y="{y0 + 4}" font-size="11">{high:.5g}</text>',
                f'<text x="8" y="{y1}" font-size="11">{low:.5g}</text>',
                f'<polyline class="line" points="{points}"/>',
            ]
        )
        for row in good.itertuples(index=False):
            x, y = x_scale(pd.Timestamp(row.date)), y_scale(float(row.rate))
            parts.append(f'<circle class="good" cx="{x:.1f}" cy="{y:.1f}" r="4"/>')
        for row in source.loc[source.original_good & source.is_weekend].itertuples(index=False):
            x, y = x_scale(pd.Timestamp(row.date)), y_scale(float(row.rate))
            size = 6
            parts.extend(
                [
                    f'<line class="weekend" x1="{x - size:.1f}" y1="{y - size:.1f}" '
                    f'x2="{x + size:.1f}" y2="{y + size:.1f}"/>',
                    f'<line class="weekend" x1="{x - size:.1f}" y1="{y + size:.1f}" '
                    f'x2="{x + size:.1f}" y2="{y - size:.1f}"><title>'
                    f"{row.date:%Y-%m-%d}; {row.date.day_name()}; rate={row.rate:.6g}"
                    "</title></line>",
                ]
            )
        for row in pushes.itertuples(index=False):
            x, y = x_scale(pd.Timestamp(row.date)), y_scale(float(row.rate))
            size = 7
            diamond = f"{x:.1f},{y - size:.1f} {x + size:.1f},{y:.1f} {x:.1f},{y + size:.1f} {x - size:.1f},{y:.1f}"
            parts.append(f'<polygon class="push" points="{diamond}"/>')
        for fraction, label in (
            (0, source.date.min().strftime("%Y-%m")),
            (0.5, source.date.iloc[len(source) // 2].strftime("%Y-%m")),
            (1, source.date.max().strftime("%Y-%m")),
        ):
            x = x0 + fraction * (x1 - x0)
            parts.append(f'<text x="{x:.1f}" y="{y1 + 20}" font-size="11" text-anchor="middle">{label}</text>')
    parts.append("</svg>")

    output_dir.mkdir(parents=True, exist_ok=True)
    chart_path = output_dir / f"{corridor}__near_local_min__h-{horizon:02d}__weekend-review.svg"
    data_path = output_dir / f"{corridor}__near_local_min__h-{horizon:02d}__weekend-review.csv"
    chart_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    source.loc[
        source.original_good,
        [
            "date",
            "rate",
            "is_weekend",
            "original_good",
            "original_push",
            "good",
            "weekday_push",
        ],
    ].to_csv(data_path, index=False)
    return chart_path, data_path


def plot_scenario_review(
    labels_path: Path,
    output_dir: Path,
    *,
    corridor: str,
    start: str,
    end: str,
    cooldown_days: int,
    weekly_cap: int,
) -> tuple[Path, Path, Path]:
    """Plot three scenario types and their prioritized push stream."""
    frame = pd.read_parquet(labels_path)
    frame["date"] = pd.to_datetime(frame.date)
    frame = (
        frame.loc[frame.corridor.eq(corridor) & frame.date.between(pd.Timestamp(start), pd.Timestamp(end))]
        .sort_values("date")
        .copy()
    )
    if frame.empty:
        raise ValueError(f"No rows for {corridor} in {start}..{end}")
    fact_columns = [
        "fact_decline_3_quotes",
        "fact_weekly_gain_1pct",
        "fact_low_percentile_30d",
        "positive_market_fact",
    ]
    missing = {"good", "closing", *fact_columns} - set(frame.columns)
    if missing:
        raise ValueError(f"Canonical labels are missing columns: {sorted(missing)}")
    frame["push"], frame["push_scenario"] = select_scenario_pushes(
        frame,
        cooldown_days=cooldown_days,
        weekly_cap=weekly_cap,
    )

    good = frame.good.astype(bool)
    closing = frame.closing.astype(bool)
    facts = frame.positive_market_fact.astype(bool)
    overlap = good & closing
    pushes = frame.loc[frame.push]
    good_pushes = pushes.loc[pushes.push_scenario.eq("good_now")]
    closing_pushes = pushes.loc[pushes.push_scenario.eq("window_closing")]
    fact_pushes = pushes.loc[pushes.push_scenario.eq("positive_market_fact")]
    observed_weeks = frame.date.dt.to_period("W-SUN").nunique()

    scenario_top = 174
    height = scenario_top + 2 * PANEL_HEIGHT + BOTTOM
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        "<style>text{font-family:-apple-system,BlinkMacSystemFont,sans-serif;fill:#17202a}"
        ".axis{stroke:#bfc9ca;stroke-width:1}.line{fill:none;stroke:#34495e;stroke-width:1.4}"
        ".good{fill:#e74c3c;fill-opacity:.72;stroke:white;stroke-width:.7}"
        ".closing{fill:#f39c12;fill-opacity:.72;stroke:white;stroke-width:.7}"
        ".fact{stroke:#8e44ad;stroke-width:2.2}"
        ".push-good{fill:#1565c0;stroke:white;stroke-width:1.2}"
        ".push-closing{fill:#00897b;stroke:white;stroke-width:1.2}"
        ".push-fact{fill:#8e44ad;stroke:white;stroke-width:1.2}</style>",
        f'<text x="{LEFT}" y="28" font-size="20" font-weight="600">'
        f"{escape(corridor)} · good + closing + positive market facts</text>",
        f'<text x="{LEFT}" y="48" font-size="12">good=1: курс не более чем на 1% выше минимума в [T−10; T+10].</text>',
        f'<text x="{LEFT}" y="66" font-size="12">'
        f"closing=1: good=0; курс >{CLOSING_MIN_REBOUND_BPS / 100:.0f}%, но ≤"
        f"{CLOSING_MAX_REBOUND_BPS / 100:.0f}% выше минимума предыдущих {CLOSING_HORIZON_DAYS} дней.</text>",
        f'<text x="{LEFT}" y="84" font-size="12">'
        f"Hindsight для closing: медиана следующих {CLOSING_HORIZON_DAYS} календарных дней "
        f"минимум на {CLOSING_MIN_FUTURE_MEDIAN_RISE_BPS / 100:.0f}% выше курса T.</text>",
        f'<text x="{LEFT}" y="102" font-size="12">'
        "fact: снижение 3 обновления подряд ИЛИ улучшение ≥1% за 7 дней ИЛИ "
        "курс выгоднее 90% предыдущих 30 дней.</text>",
        f'<text x="{LEFT}" y="120" font-size="12">'
        f"Политика: good → closing → fact; cooldown {cooldown_days} дня; "
        f"не более {weekly_cap} push в неделю.</text>",
        f'<text x="{LEFT}" y="138" font-size="11">'
        "Красный круг — good; оранжевый треугольник — closing; "
        "фиолетовый крест — fact. Ромбы: синий good, зелёный closing, фиолетовый fact.</text>",
    ]

    panels = (
        (
            f"Все размеченные дни · good: {int(good.sum())} · closing: {int(closing.sum())} · "
            f"fact: {int(facts.sum())} · пересечение good/closing: {int(overlap.sum())}",
            False,
        ),
        (
            f"После коммуникационной политики · push: {len(pushes)} ({len(good_pushes)} good + "
            f"{len(closing_pushes)} closing + {len(fact_pushes)} fact) · "
            f"{len(pushes) / observed_weeks:.2f} в неделю",
            True,
        ),
    )
    for panel_index, (title, push_panel) in enumerate(panels):
        y0 = scenario_top + panel_index * PANEL_HEIGHT + 28
        y1 = scenario_top + (panel_index + 1) * PANEL_HEIGHT - 42
        x0, x1 = LEFT, WIDTH - 70
        points, x_scale, y_scale, low, high = _path(frame, x0, x1, y0, y1)
        parts.extend(
            [
                f'<line class="axis" x1="{x0}" x2="{x0}" y1="{y0}" y2="{y1}"/>',
                f'<line class="axis" x1="{x0}" x2="{x1}" y1="{y1}" y2="{y1}"/>',
                f'<text x="{x0}" y="{y0 - 9}" font-size="14" font-weight="600">{escape(title)}</text>',
                f'<text x="8" y="{y0 + 4}" font-size="11">{high:.5g}</text>',
                f'<text x="8" y="{y1}" font-size="11">{low:.5g}</text>',
                f'<polyline class="line" points="{points}"/>',
            ]
        )
        if not push_panel:
            for row in frame.loc[facts].itertuples(index=False):
                x, y = x_scale(pd.Timestamp(row.date)), y_scale(float(row.rate))
                size = 5
                active = []
                if row.fact_decline_3_quotes:
                    active.append("decline_3_quotes")
                if row.fact_weekly_gain_1pct:
                    active.append("weekly_gain_1pct")
                if row.fact_low_percentile_30d:
                    active.append("low_percentile_30d")
                tooltip = f"FACT {row.date:%Y-%m-%d}; {', '.join(active)}; rate={row.rate:.6g}"
                parts.append(
                    f'<g class="fact"><title>{escape(tooltip)}</title>'
                    f'<line x1="{x - size:.1f}" y1="{y - size:.1f}" '
                    f'x2="{x + size:.1f}" y2="{y + size:.1f}"/>'
                    f'<line x1="{x - size:.1f}" y1="{y + size:.1f}" '
                    f'x2="{x + size:.1f}" y2="{y - size:.1f}"/>'
                    "</g>"
                )
            for row in frame.loc[closing].itertuples(index=False):
                x, y = x_scale(pd.Timestamp(row.date)), y_scale(float(row.rate))
                size = 6
                triangle = f"{x:.1f},{y - size:.1f} {x + size:.1f},{y + size:.1f} {x - size:.1f},{y + size:.1f}"
                tooltip = (
                    f"WINDOW CLOSING {row.date:%Y-%m-%d}; rate={row.rate:.6g}; "
                    f"rebound={row.rebound_from_past_min_bps:.1f} bps; "
                    f"future median change={row.future_median_change_bps:.1f} bps"
                )
                parts.append(f'<polygon class="closing" points="{triangle}"><title>{escape(tooltip)}</title></polygon>')
            for row in frame.loc[good].itertuples(index=False):
                x, y = x_scale(pd.Timestamp(row.date)), y_scale(float(row.rate))
                tooltip = f"GOOD {row.date:%Y-%m-%d}; rate={row.rate:.6g}; regret={row.future_regret_bps:.1f} bps"
                parts.append(
                    f'<circle class="good" cx="{x:.1f}" cy="{y:.1f}" r="4"><title>{escape(tooltip)}</title></circle>'
                )
        else:
            for row in pushes.itertuples(index=False):
                x, y = x_scale(pd.Timestamp(row.date)), y_scale(float(row.rate))
                size = 7
                diamond = f"{x:.1f},{y - size:.1f} {x + size:.1f},{y:.1f} {x:.1f},{y + size:.1f} {x - size:.1f},{y:.1f}"
                css = {
                    "good_now": "push-good",
                    "window_closing": "push-closing",
                    "positive_market_fact": "push-fact",
                }[row.push_scenario]
                tooltip = f"PUSH {row.push_scenario} {row.date:%Y-%m-%d}; rate={row.rate:.6g}"
                parts.append(f'<polygon class="{css}" points="{diamond}"><title>{escape(tooltip)}</title></polygon>')
        for fraction, label in (
            (0, frame.date.min().strftime("%Y-%m")),
            (0.5, frame.date.iloc[len(frame) // 2].strftime("%Y-%m")),
            (1, frame.date.max().strftime("%Y-%m")),
        ):
            x = x0 + fraction * (x1 - x0)
            parts.append(f'<text x="{x:.1f}" y="{y1 + 20}" font-size="11" text-anchor="middle">{label}</text>')
    parts.append("</svg>")

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{corridor}__good-closing-facts__h-10"
    chart_path = output_dir / f"{stem}.svg"
    schedule_path = output_dir / f"{stem}__schedule.csv"
    summary_path = output_dir / f"{stem}__summary.csv"
    chart_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    export_columns = [
        "date",
        "corridor",
        "rate",
        "good",
        "closing",
        *fact_columns,
        "rebound_from_past_min_bps",
        "future_median_change_bps",
        "future_regret_bps",
        "push",
        "push_scenario",
    ]
    frame.loc[good | closing | facts | frame.push, export_columns].to_csv(schedule_path, index=False)
    week_counts = pushes.date.dt.to_period("W-SUN").value_counts()
    pd.DataFrame(
        [
            {
                "corridor": corridor,
                "start": frame.date.min().date(),
                "end": frame.date.max().date(),
                "observed_weeks": observed_weeks,
                "good_days": int(good.sum()),
                "closing_days": int(closing.sum()),
                "positive_market_fact_days": int(facts.sum()),
                "fact_decline_3_quotes_days": int(frame.fact_decline_3_quotes.sum()),
                "fact_weekly_gain_1pct_days": int(frame.fact_weekly_gain_1pct.sum()),
                "fact_low_percentile_30d_days": int(frame.fact_low_percentile_30d.sum()),
                "overlap_days": int(overlap.sum()),
                "pushes_total": len(pushes),
                "pushes_good_now": len(good_pushes),
                "pushes_closing": len(closing_pushes),
                "pushes_positive_market_fact": len(fact_pushes),
                "pushes_per_week": len(pushes) / observed_weeks,
                "weeks_with_push": len(week_counts),
                "weeks_with_two_pushes": int(week_counts.eq(2).sum()),
                "cooldown_calendar_days": cooldown_days,
                "weekly_cap": weekly_cap,
            }
        ]
    ).to_csv(summary_path, index=False)
    return chart_path, schedule_path, summary_path


def write_scenario_portfolio_summary(
    labels_path: Path,
    output_dir: Path,
    *,
    start: str,
    end: str,
    cooldown_days: int,
    weekly_cap: int,
) -> Path:
    """Summarize the same prioritized policy for every corridor."""
    source = pd.read_parquet(labels_path)
    source["date"] = pd.to_datetime(source.date)
    source = source.loc[source.date.between(pd.Timestamp(start), pd.Timestamp(end))].copy()
    rows = []
    for corridor, frame in source.groupby("corridor", sort=True):
        frame = frame.sort_values("date").copy()
        frame["push"], frame["push_scenario"] = select_scenario_pushes(
            frame,
            cooldown_days=cooldown_days,
            weekly_cap=weekly_cap,
        )
        pushes = frame.loc[frame.push]
        week_counts = pushes.date.dt.to_period("W-SUN").value_counts()
        observed_weeks = frame.date.dt.to_period("W-SUN").nunique()
        rows.append(
            {
                "corridor": corridor,
                "good_days": int(frame.good.sum()),
                "closing_days": int(frame.closing.sum()),
                "positive_market_fact_days": int(frame.positive_market_fact.sum()),
                "overlap_days": int((frame.good & frame.closing.astype(bool)).sum()),
                "pushes_total": len(pushes),
                "pushes_good_now": int(pushes.push_scenario.eq("good_now").sum()),
                "pushes_closing": int(pushes.push_scenario.eq("window_closing").sum()),
                "pushes_positive_market_fact": int(pushes.push_scenario.eq("positive_market_fact").sum()),
                "pushes_per_week": len(pushes) / observed_weeks,
                "weeks_with_push": len(week_counts),
                "weeks_with_two_pushes": int(week_counts.eq(2).sum()),
                "observed_weeks": observed_weeks,
            }
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "all_corridors__good-closing-facts__h-10__summary.csv"
    pd.DataFrame(rows).to_csv(output, index=False)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels-dir", default="data/labels/golden_review/2025-07-01_2026-07-31")
    parser.add_argument("--output-dir", default="reports/golden_labels")
    parser.add_argument("--corridor", default="TJS_RUB")
    parser.add_argument("--x-bps", type=int, choices=[25, 50, 100], default=100)
    parser.add_argument("--cooldown-days", type=int, default=4)
    parser.add_argument("--weekly-cap", type=int, default=2)
    parser.add_argument("--canonical-labels", default="data/labels/golden_labels.parquet")
    parser.add_argument("--start", default="2025-07-01")
    parser.add_argument("--end", default="2026-07-31")
    parser.add_argument(
        "--review-grid",
        action="store_true",
        help="Also regenerate the exploratory good-rule grid and weekend review.",
    )
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir)
    review_outputs: list[Path] = []
    if args.review_grid:
        labels_dir = Path(args.labels_dir)
        review_outputs.extend(
            plot_rule(
                labels_dir,
                output_dir,
                rule=item.identifier,
                corridor=args.corridor,
                x_bps=args.x_bps,
                cooldown_days=args.cooldown_days,
                weekly_cap=args.weekly_cap,
            )
            for item in RULES
        )
        review_outputs.extend(
            write_communication_review(
                labels_dir,
                output_dir,
                corridor=args.corridor,
                x_bps=args.x_bps,
                cooldown_days=args.cooldown_days,
                weekly_cap=args.weekly_cap,
            )
        )
        review_outputs.extend(
            plot_weekend_review(
                labels_dir,
                output_dir,
                corridor=args.corridor,
                horizon=10,
                x_bps=args.x_bps,
                cooldown_days=args.cooldown_days,
                weekly_cap=args.weekly_cap,
            )
        )
    scenario_review = plot_scenario_review(
        Path(args.canonical_labels),
        output_dir,
        corridor=args.corridor,
        start=args.start,
        end=args.end,
        cooldown_days=args.cooldown_days,
        weekly_cap=args.weekly_cap,
    )
    portfolio_summary = write_scenario_portfolio_summary(
        Path(args.canonical_labels),
        output_dir,
        start=args.start,
        end=args.end,
        cooldown_days=args.cooldown_days,
        weekly_cap=args.weekly_cap,
    )
    print(f"PASS: final chart and summaries -> {output_dir}")
    print(*(str(path) for path in (*scenario_review, portfolio_summary, *review_outputs)), sep="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
