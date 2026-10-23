import csv
import io
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import requests
from requests.auth import HTTPBasicAuth

JST = ZoneInfo("Asia/Tokyo")


def fetch_rows(url, auth):
    """Parsed CSV rows, or None if the file doesn't exist."""
    resp = requests.get(url, auth=auth, timeout=15)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return list(csv.DictReader(io.StringIO(resp.text)))


def parse_ts(value):
    try:
        return datetime.fromisoformat((value or "").strip()).replace(tzinfo=None)
    except ValueError:
        return None


def inspect(rows, sensor, slot_start, slot_end):
    """Return (count, None) if the file is valid for its slot, else (None, reason)."""
    if rows is None:
        return None, "not found"
    if not rows:
        return None, "empty"
    stamps = [t for t in (parse_ts(r.get("TIMESTAMP")) for r in rows) if t]
    if not stamps:
        return None, "no valid timestamps"
    latest = max(stamps)
    # File hhmm covers the 5 minutes before hhmm; anything outside is stale
    if not (slot_start <= latest < slot_end + timedelta(minutes=1)):
        return None, f"stale (latest row {latest:%Y-%m-%d %H:%M})"
    count = len({
        (r.get("AMAC") or "").strip()
        for r in rows
        if (r.get("AMPID") or "").strip() == sensor and (r.get("AMAC") or "").strip()
    })
    return count, None


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "s-maxage=60, stale-while-revalidate=60")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            sensor = (query.get("sensor") or [None])[0]
            if not sensor or not sensor.startswith("AMPM18-KJ"):
                return self._send(400, {"error": "A valid sensor parameter is required"})
            try:
                periods = min(max(int((query.get("periods") or ["5"])[0]), 1), 12)
                discard = min(max(int((query.get("discard") or ["1"])[0]), 0), 3)
            except ValueError:
                return self._send(400, {"error": "periods and discard must be integers"})

            base_url = os.environ["JRISS_API_URL"].rstrip("/")
            auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])

            now = datetime.now(JST).replace(tzinfo=None)
            end = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)

            # Newest first, plus 2 spare slots in case some files are missing or stale
            slots = [end - timedelta(minutes=5 * i) for i in range(periods + discard + 2)]

            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [
                    pool.submit(fetch_rows, f"{base_url}/{t:%H%M}.csv", auth)
                    for t in slots
                ]
                results = [f.result() for f in futures]

            valid, skipped = [], []
            for t, rows in zip(slots, results):
                count, reason = inspect(rows, sensor, t - timedelta(minutes=5), t)
                entry = {"timeCode": f"{t:%H%M}", "window": f"{t - timedelta(minutes=5):%H:%M}-{t:%H:%M}"}
                if reason:
                    skipped.append({**entry, "reason": reason})
                else:
                    valid.append({**entry, "count": count})

            discarded = valid[:discard]
            used = valid[discard:discard + periods]

            if not used:
                return self._send(503, {"error": "No usable readings found", "skipped": skipped})

            average = round(sum(r["count"] for r in used) / len(used), 1)

            return self._send(200, {
                "sensor": sensor,
                "average": average,
                "periods_requested": periods,
                "periods_used": len(used),
                "readings": used,          # newest first
                "discarded": discarded,
                "skipped": skipped,
            })

        except requests.RequestException as e:
            return self._send(502, {"error": "Failed to retrieve sensor data", "detail": str(e)})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": type(e).__name__, "detail": str(e)})