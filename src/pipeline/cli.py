from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from .download import DownloadConfig, IngestionError, run_download


def iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected ISO date YYYY-MM-DD") from exc


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Official CBR FX pipeline")
    subcommands = root.add_subparsers(dest="command", required=True)
    download = subcommands.add_parser("download", help="download immutable raw CBR history")
    download.add_argument("--start-date", type=iso_date, default=date(2019, 1, 1))
    download.add_argument(
        "--end-date",
        type=iso_date,
        help="inclusive end date; default: latest date reported by CBR",
    )
    download.add_argument("--raw-root", type=Path, default=Path("data/raw/cbr"))
    download.add_argument(
        "--reference-file",
        type=Path,
        default=Path("data/reference/cbr_currency_codes.csv"),
    )
    download.add_argument("--report-file", type=Path, default=Path("reports/raw_data_report.md"))
    download.add_argument("--timeout-seconds", type=float, default=30.0)
    download.add_argument("--max-attempts", type=int, default=4)
    download.add_argument("--backoff-seconds", type=float, default=1.0)
    download.add_argument("--force-download", action="store_true")
    return root


def configure_logging() -> None:
    Path("reports").mkdir(parents=True, exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("reports/raw_ingestion.log", encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)sZ %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        handlers=handlers,
        force=True,
    )
    logging.Formatter.converter = __import__("time").gmtime


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    configure_logging()
    if args.command != "download":
        raise AssertionError(args.command)
    config = DownloadConfig(
        start_date=args.start_date,
        end_date=args.end_date,
        raw_root=args.raw_root,
        reference_file=args.reference_file,
        report_file=args.report_file,
        timeout_seconds=args.timeout_seconds,
        max_attempts=args.max_attempts,
        backoff_seconds=args.backoff_seconds,
        force_download=args.force_download,
    )
    try:
        manifest = run_download(config)
    except (IngestionError, OSError, ValueError) as exc:
        logging.getLogger(__name__).error("RAW INGESTION FAILED: %s", exc)
        return 1
    logging.getLogger(__name__).info("RAW INGESTION PASS: %s", manifest)
    return 0
