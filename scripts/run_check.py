from __future__ import annotations

import argparse
import calendar
import csv
import json
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, sync_playwright

from innto_fetcher import ENV_SETUP_HINT, INNTO_REQUIRED_ENVS, fetch_monthly_csv, find_missing_env
from parse_ope_status_csv import find_today_vacant, merge_months, parse_one_csv
from post_to_worker import post_ingest

JST = timezone(timedelta(hours=9))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true", help="Run CI-safe checks only")
    return parser.parse_args()


def print_missing_env_and_exit(missing: list[str]) -> int:
    print(f"Missing required env: {', '.join(missing)}")
    print(ENV_SETUP_HINT)
    return 2


def should_post_to_worker() -> bool:
    return bool(os.getenv("WORKER_INGEST_URL") and os.getenv("WORKER_TOKEN"))


def build_payload(months: dict[str, dict[str, int]]) -> dict:
    return {
        "ts": datetime.now(JST).isoformat(),
        "months": months,
        "today": find_today_vacant(months),
        "meta": {"source": "innto_ope_status"},
    }


def post_or_stdout(payload: dict) -> dict:
    if should_post_to_worker():
        result = post_ingest(payload)
        print(json.dumps({"mode": "posted", "result": result}, ensure_ascii=False, indent=2))
        return result

    missing = [v for v in ("WORKER_INGEST_URL", "WORKER_TOKEN") if not os.getenv(v)]
    if missing:
        print(f"Worker credentials not set, stdout fallback mode. Missing: {', '.join(missing)}")
    print(json.dumps({"mode": "stdout", "payload": payload}, ensure_ascii=False, indent=2))
    return {"ok": True, "mode": "stdout"}


def playwright_smoke_check() -> None:
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except PlaywrightError as exc:
        raise RuntimeError(
            "Playwright startup failed. Install browser binaries with: python -m playwright install --with-deps chromium"
        ) from exc


def _month_key_pair(base: date) -> tuple[str, str]:
    this = base.strftime("%Y-%m")
    if base.month == 12:
        nxt = f"{base.year + 1:04d}-01"
    else:
        nxt = f"{base.year:04d}-{base.month + 1:02d}"
    return this, nxt


def _write_sample_csv(path: Path, month_key: str) -> None:
    year, month = map(int, month_key.split("-"))
    last_day = calendar.monthrange(year, month)[1]
    with path.open("w", encoding="cp932", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["#日", "総室数", "宿泊室数"])
        for day in range(1, last_day + 1):
            writer.writerow([f"{day:02d}(日)", "100", str((day * 3) % 90)])


def run_preflight() -> int:
    missing = find_missing_env(INNTO_REQUIRED_ENVS)
    if missing:
        return print_missing_env_and_exit(missing)

    try:
        playwright_smoke_check()
    except RuntimeError as exc:
        print(str(exc))
        return 2

    today = date.today()
    this_key, next_key = _month_key_pair(today)
    with tempfile.TemporaryDirectory(prefix="innto_preflight_") as d:
        p1 = Path(d) / f"report_ope_status_{this_key}.csv"
        p2 = Path(d) / f"report_ope_status_{next_key}.csv"
        _write_sample_csv(p1, this_key)
        _write_sample_csv(p2, next_key)
        parsed = [parse_one_csv(p1, this_key), parse_one_csv(p2, next_key)]
        months = merge_months(parsed)

    payload = build_payload(months)
    post_or_stdout(payload)
    return 0


def run_full() -> int:
    missing = find_missing_env(INNTO_REQUIRED_ENVS)
    if missing:
        return print_missing_env_and_exit(missing)

    downloaded = fetch_monthly_csv()
    parsed = [parse_one_csv(path, month.key) for month, path in downloaded]
    months = merge_months(parsed)
    payload = build_payload(months)
    post_or_stdout(payload)
    return 0


def main() -> int:
    args = parse_args()
    if args.preflight:
        return run_preflight()
    return run_full()


if __name__ == "__main__":
    raise SystemExit(main())
