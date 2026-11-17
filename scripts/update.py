#!/usr/bin/env python3
"""Mirror the relics.run price data that HexDesk reads.

Downloads the newest daily price file and the item list, checks that both look
sane, and only then replaces the copies in this repository. When a download
fails or the data looks wrong, the last good copy stays in place and the script
exits non-zero so the workflow run is marked as failed.

Usage: python3 scripts/update.py [output-dir]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SOURCE = "https://relics.run/history"
USER_AGENT = "HexDeskPricing/1.0 (+https://github.com/OostHash/HexDeskPricing)"

# relics.run publishes the previous day's data shortly after midnight UTC, so
# today's file usually does not exist yet. Older than this means the source is
# stuck and someone should look at it.
MAX_AGE_DAYS = 3

MIN_PRICED_ITEMS = 1000
MIN_CATALOGUE_ITEMS = 1000


def download(url: str, attempts: int = 3) -> bytes | None:
    """Return the body, or None for a 404. Retries other failures."""
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            reason = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError) as error:
            reason = str(error)
        print(f"  attempt {attempt}/{attempts} failed: {reason}")
        if attempt < attempts:
            time.sleep(30 * attempt)
    raise RuntimeError(f"could not download {url}")


def check_prices(body: bytes) -> str | None:
    """Return a problem description, or None when the price file is usable."""
    try:
        data = json.loads(body)
    except ValueError as error:
        return f"not valid JSON ({error})"
    if not isinstance(data, dict):
        return "expected a JSON object keyed by item name"
    priced = sum(
        1
        for records in data.values()
        if isinstance(records, list)
        and any(
            isinstance(r, dict) and r.get("order_type") == "closed" and r.get("median") is not None
            for r in records
        )
    )
    if priced < MIN_PRICED_ITEMS:
        return f"only {priced} items have a closed median (expected at least {MIN_PRICED_ITEMS})"
    return None


def check_items(body: bytes) -> str | None:
    try:
        data = json.loads(body)
    except ValueError as error:
        return f"not valid JSON ({error})"
    if not isinstance(data, list):
        return "expected a JSON array of items"
    usable = sum(
        1
        for item in data
        if isinstance(item, dict)
        and item.get("slug")
        and (item.get("i18n") or {}).get("en", {}).get("name")
    )
    if usable < MIN_CATALOGUE_ITEMS:
        return f"only {usable} items have a slug and English name (expected at least {MIN_CATALOGUE_ITEMS})"
    return None


def write_if_changed(path: Path, body: bytes) -> bool:
    if path.exists() and path.read_bytes() == body:
        return False
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(body)
    tmp.replace(path)
    return True


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    out.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date()
    failures: list[str] = []
    changed = False
    price_date = None

    # Prices: newest available day, newest first.
    for age in range(MAX_AGE_DAYS + 1):
        day = (today - timedelta(days=age)).isoformat()
        url = f"{SOURCE}/price_history_{day}.json"
        print(f"Prices: trying {day}")
        try:
            body = download(url)
        except RuntimeError as error:
            failures.append(str(error))
            break
        if body is None:
            continue
        problem = check_prices(body)
        if problem:
            failures.append(f"price file for {day} rejected: {problem}")
            break
        changed |= write_if_changed(out / "price_history_latest.json", body)
        price_date = day
        print(f"Prices: using {day}")
        break
    else:
        failures.append(f"no price file found for the last {MAX_AGE_DAYS + 1} days")

    print("Items: downloading")
    try:
        body = download(f"{SOURCE}/item_data/items.json")
        problem = "not found (404)" if body is None else check_items(body)
        if problem:
            failures.append(f"items.json rejected: {problem}")
        else:
            changed |= write_if_changed(out / "items.json", body)
    except RuntimeError as error:
        failures.append(str(error))

    if changed:
        meta_path = out / "meta.json"
        meta = json.loads(meta_path.read_text("utf-8")) if meta_path.exists() else {}
        meta["source"] = SOURCE
        if price_date:
            meta["price_date"] = price_date
        meta["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", "utf-8")

    print("Changed." if changed else "No changes.")
    for failure in failures:
        print(f"::error::{failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
