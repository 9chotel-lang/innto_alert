from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PWTimeoutError, sync_playwright

LOGIN_URL = "https://pms.innto.jp/login.html"
REPORT_URL = os.getenv("REPORT_URL", "https://pms.innto.jp/#report/ope-status")
INNTO_REQUIRED_ENVS = ("INNTO_HOTEL_ID", "INNTO_ACCOUNT", "INNTO_PASSWORD")
ENV_SETUP_HINT = (
    "Please set repository secrets in GitHub:\n"
    "  Settings -> Secrets and variables -> Actions -> New repository secret"
)


@dataclass(frozen=True)
class TargetMonth:
    year: int
    month: int

    @property
    def key(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def find_missing_env(names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not os.getenv(name)]


def validate_required_envs(names: tuple[str, ...] = INNTO_REQUIRED_ENVS) -> None:
    missing = find_missing_env(names)
    if missing:
        missing_text = ", ".join(missing)
        raise RuntimeError(f"Missing required env: {missing_text}\n{ENV_SETUP_HINT}")


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        validate_required_envs((name,))
    return value or ""


def target_months(base: date | None = None) -> list[TargetMonth]:
    base = base or date.today()
    this = TargetMonth(base.year, base.month)
    if base.month == 12:
        nxt = TargetMonth(base.year + 1, 1)
    else:
        nxt = TargetMonth(base.year, base.month + 1)
    return [this, nxt]


def resolve_download_dir() -> Path:
    configured = os.getenv("DOWNLOAD_DIR")
    if configured:
        path = Path(configured).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    return Path(tempfile.mkdtemp(prefix="innto_csv_"))


def login(page: Page) -> None:
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.locator("#hotelId").fill(required_env("INNTO_HOTEL_ID"))
    page.locator("#accountName").fill(required_env("INNTO_ACCOUNT"))
    page.locator("#password").fill(required_env("INNTO_PASSWORD"))
    page.get_by_role("button", name="サインイン").click()
    page.wait_for_load_state("networkidle")


def open_report_direct(page: Page) -> None:
    page.goto(REPORT_URL, wait_until="networkidle")


def select_month(page: Page, target_year: int, target_month: int) -> None:
    page.get_by_role("button", name=re.compile(r".*年\d+月")).click()
    page.locator("button.month").first.wait_for(timeout=10_000)
    page.locator("button.month", has_text=re.compile(rf"^{target_month}月$")).first.click()
    page.wait_for_load_state("networkidle")


def click_display(page: Page) -> None:
    page.get_by_role("button", name="表示").click()
    page.wait_for_load_state("networkidle")


def click_csv_download(page: Page) -> None:
    page.locator("button:has(span.iconfont-icon_download)").first.click()


def download_csv(page: Page, month: TargetMonth, download_dir: Path, run_tag: str) -> Path:
    select_month(page, month.year, month.month)
    click_display(page)

    save_path = download_dir / f"report_ope_status_{month.key}_run_{run_tag}.csv"
    with page.expect_download(timeout=120_000) as d:
        click_csv_download(page)
    d.value.save_as(str(save_path))
    return save_path


def fetch_monthly_csv() -> list[tuple[TargetMonth, Path]]:
    validate_required_envs()
    out_dir = resolve_download_dir()
    run_tag = date.today().isoformat()
    months = target_months()
    downloaded: list[tuple[TargetMonth, Path]] = []

    with sync_playwright() as p:
        headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        login(page)
        open_report_direct(page)

        for month in months:
            try:
                path = download_csv(page, month, out_dir, run_tag)
            except PWTimeoutError as exc:
                raise RuntimeError(f"download failed for {month.key}: {exc}") from exc
            downloaded.append((month, path))

        context.close()
        browser.close()

    return downloaded


if __name__ == "__main__":
    try:
        for m, path in fetch_monthly_csv():
            print(m.key, path)
    except RuntimeError as exc:
        print(str(exc))
        raise SystemExit(2)
