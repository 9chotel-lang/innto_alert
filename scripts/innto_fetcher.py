from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, List

from playwright.sync_api import Page, sync_playwright

LOGIN_URL = "https://innto.jp/login"
REPORT_URL = os.getenv("REPORT_URL", "https://innto.jp/report/ope-status")


@dataclass(frozen=True)
class TargetMonth:
    year: int
    month: int

    @property
    def key(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"environment variable is required: {name}")
    return value


def target_months(base: date | None = None) -> list[TargetMonth]:
    base = base or date.today()
    year = base.year
    month = base.month
    this = TargetMonth(year, month)
    if month == 12:
        nxt = TargetMonth(year + 1, 1)
    else:
        nxt = TargetMonth(year, month + 1)
    return [this, nxt]


def resolve_download_dir() -> Path:
    configured = os.getenv("DOWNLOAD_DIR")
    if configured:
        path = Path(configured).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    return Path(tempfile.mkdtemp(prefix="innto_csv_"))


def login(page: Page) -> None:
    hotel_id = required_env("INNTO_HOTEL_ID")
    account = required_env("INNTO_ACCOUNT")
    password = required_env("INNTO_PASSWORD")

    page.goto(LOGIN_URL, wait_until="networkidle")
    page.get_by_label("施設ID").fill(hotel_id)
    page.get_by_label("アカウント").fill(account)
    page.get_by_label("パスワード").fill(password)
    page.get_by_role("button", name="ログイン").click()
    page.wait_for_load_state("networkidle")


def open_report(page: Page) -> None:
    page.goto(REPORT_URL, wait_until="networkidle")


def select_month(page: Page, month: TargetMonth) -> None:
    # innto画面の月セレクタを想定。実際のDOMに合わせて調整しやすいよう
    # data-testid優先で探し、見つからない場合はラベル検索でフォールバック。
    key = month.key
    if page.locator("[data-testid='month-selector']").count() > 0:
        page.locator("[data-testid='month-selector']").select_option(key)
        return
    selector = page.get_by_label("対象年月")
    selector.select_option(key)


def download_csv(page: Page, month: TargetMonth, download_dir: Path) -> Path:
    select_month(page, month)
    page.wait_for_timeout(500)

    with page.expect_download() as download_info:
        if page.locator("[data-testid='download-csv']").count() > 0:
            page.locator("[data-testid='download-csv']").click()
        else:
            page.get_by_role("button", name="CSV").click()

    download = download_info.value
    suggested = download.suggested_filename or f"report_ope_status_{month.key}.csv"
    output = download_dir / suggested
    download.save_as(output)
    return output


def fetch_monthly_csv() -> list[tuple[TargetMonth, Path]]:
    out_dir = resolve_download_dir()
    months = target_months()
    downloaded: list[tuple[TargetMonth, Path]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        login(page)
        open_report(page)
        for month in months:
            path = download_csv(page, month, out_dir)
            downloaded.append((month, path))

        context.close()
        browser.close()

    return downloaded


if __name__ == "__main__":
    files = fetch_monthly_csv()
    for m, path in files:
        print(m.key, path)
