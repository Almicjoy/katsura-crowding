"""Backfill per-day summaries into Redis. Safe to re-run: stored days are skipped.

Run from backend/:
  uv run --env-file .env --with requests --with tzdata python scripts/backfill.py --since 2021-10-01

Options:
  --since DATE      oldest date to fetch, YYYY-MM-DD (default: 730 days ago)
  --workers N       parallel downloads (default 4; keep it modest, JRISS looks like a dev server)
  --stop-after N    stop after N days in a row with no file; 0 = check every date (default 30)
"""

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # fine when the variables are already in the environment

import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from _common import JST, redis_pipeline, build_day, store_day, mark_missing  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--since")
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--stop-after", type=int, default=30)
args = ap.parse_args()

base_url = os.environ["JRISS_DAILY_URL"].rstrip("/")
auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])

today = datetime.now(JST).date()
since = date.fromisoformat(args.since) if args.since else today - timedelta(days=2000)
dates = [today - timedelta(days=i) for i in range(1, (today - since).days + 1)]  # newest first
print(f"{len(dates)} days to check, {dates[0]} back to {dates[-1]}")


def process(d, tries=3):
    err = ""
    for attempt in range(tries):
        try:
            summary = build_day(d, base_url, auth)
            if summary is None:
                mark_missing(d)
                return "none"
            store_day(d, summary)
            return f"stored ({len(summary)} sensors)"
        except requests.RequestException as e:
            err = str(e)
            time.sleep(attempt + 1)
    return f"error: {err}"


CHUNK = 60
missing_run, earliest, errors, stored, stop = 0, None, [], 0, False
with ThreadPoolExecutor(max_workers=args.workers) as pool:
    for i in range(0, len(dates), CHUNK):
        chunk = dates[i:i + CHUNK]
        # One round trip to find which days of this chunk are already stored
        have = [bool(r) for r in redis_pipeline([["HEXISTS", f"day:{d:%Y%m%d}", "_done"] for d in chunk])]
        todo = [d for d, h in zip(chunk, have) if not h]
        results = dict(zip(todo, pool.map(process, todo)))
        for d, h in zip(chunk, have):  # newest to oldest, so runs of missing days count correctly
            status = "already stored" if h else results[d]
            print(d, status)
            if status == "none":
                missing_run += 1
            elif status.startswith("error"):
                errors.append(d)
            else:
                earliest, missing_run = d, 0
                stored += status.startswith("stored")
            if args.stop_after and missing_run >= args.stop_after:
                print(f"Stopping: {args.stop_after} days in a row without a file.")
                stop = True
                break
        if stop:
            break

print(f"\nDone. Stored {stored} new days. Earliest day with data: {earliest}")
if errors:
    print(f"{len(errors)} days failed after retries (run the script again to retry them): "
          + ", ".join(str(d) for d in errors))