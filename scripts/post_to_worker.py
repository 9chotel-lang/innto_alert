from __future__ import annotations

import json
import os
import urllib.request


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"environment variable is required: {name}")
    return value


def post_ingest(payload: dict) -> dict:
    url = required_env("WORKER_INGEST_URL")
    token = required_env("WORKER_TOKEN")

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as res:
        data = res.read().decode("utf-8")
        return json.loads(data)
