from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

DAY_PATTERN = re.compile(r"^(\d{2})")
REQUIRED_COLUMNS = ("#日", "総室数", "宿泊室数")


@dataclass(frozen=True)
class ParsedMonth:
    month: str
    days: dict[str, int]


def parse_day(raw: str) -> str:
    match = DAY_PATTERN.match((raw or "").strip())
    if not match:
        raise ValueError(f"cannot parse day from '#日': {raw!r}")
    return match.group(1)


def preview_csv(csv_path: Path, head_rows: int = 5) -> str:
    lines: list[str] = []
    with csv_path.open("r", encoding="cp932", errors="replace") as f:
        for i, line in enumerate(f):
            if i > head_rows:
                break
            lines.append(line.rstrip("\n"))
    return "\n".join(lines)


def parse_one_csv(csv_path: Path, target_month: str) -> ParsedMonth:
    try:
        with csv_path.open("r", encoding="cp932", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise RuntimeError(f"CSV has no header: {csv_path}")

            missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
            if missing:
                raise RuntimeError(f"CSV missing required columns {missing}: {csv_path}")

            days: dict[str, int] = {}
            for row in reader:
                day = parse_day(row["#日"])
                total = int(row["総室数"])
                stay = int(row["宿泊室数"])
                days[day] = total - stay
            return ParsedMonth(month=target_month, days=days)
    except Exception as exc:
        preview = preview_csv(csv_path)
        raise RuntimeError(f"CSV parse failed: {csv_path}\n{preview}") from exc


def merge_months(parsed: Iterable[ParsedMonth]) -> dict[str, dict[str, int]]:
    return {item.month: item.days for item in parsed}


def find_today_vacant(months: dict[str, dict[str, int]], today: date | None = None) -> dict[str, int | str]:
    today = today or date.today()
    month_key = today.strftime("%Y-%m")
    day_key = today.strftime("%d")
    month_map = months.get(month_key)
    if not month_map or day_key not in month_map:
        raise RuntimeError(f"today vacancy not found: {month_key} {day_key}")
    return {"date": today.isoformat(), "vacant": month_map[day_key]}
