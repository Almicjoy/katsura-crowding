"""One-time (re-runnable) backfill of per-day summaries into Redis.

Run from backend/:  python scripts/backfill.py [days] [stop_after_missing]
Needs:  pip install python-dotenv requests tzdata
"""

import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
from _common import JST, redis_cmd, build_day, store_day, mark_missing  # noqa: E402

days = int(sys.argv[1]) if len(sys.argv) > 1 else 730
stop_after = int(sys.argv[2]) if len(sys.argv) > 2 else 30  # consecutive days with no file
base_url = os.environ["JRISS_DAILY_URL"].rstrip("/")
auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])

today = datetime.now(JST).date()
missing_run, earliest = 0, None
for i in range(1, days + 1):
    d = today - timedelta(days=i)
    if redis_cmd("HEXISTS", f"day:{d:%Y%m%d}", "_done"):
        earliest = d
        missing_run = 0
        print(f"{d} already stored")
        continue
    summary = build_day(d, base_url, auth)
    if summary is None:
        mark_missing(d)
        missing_run += 1
        print(f"{d} no file ({missing_run} in a row)")
        if missing_run >= stop_after:
            print(f"Stopping: {stop_after} days in a row without a file.")
            break
        continue
    store_day(d, summary)
    earliest, missing_run = d, 0
    print(f"{d} stored ({len(summary)} sensors)")

print(f"Done. Earliest day with data: {earliest}")