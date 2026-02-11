from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from innto_fetcher import fetch_monthly_csv
from parse_ope_status_csv import find_today_vacant, merge_months, parse_one_csv
from post_to_worker import post_ingest

JST = timezone(timedelta(hours=9))


def main() -> int:
    downloaded = fetch_monthly_csv()
    parsed = [parse_one_csv(path, month.key) for month, path in downloaded]
    months = merge_months(parsed)
    today = find_today_vacant(months)

    payload = {
        "ts": datetime.now(JST).isoformat(),
        "months": months,
        "today": today,
        "meta": {"source": "innto_ope_status"},
    }

    result = post_ingest(payload)
    print(json.dumps({"payload": payload, "result": result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
