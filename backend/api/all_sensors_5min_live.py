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
KNOWN = [f"AMPM18-KJ{n:03d}" for n in range(8, 18)]  # KJ008 ... KJ017


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


def summarize(rows, slot_start, slot_end):
    """({sensor: unique devices}, None) if the file belongs to this slot, else (None, reason)."""
    if rows is None:
        return None, "not found"
    if not rows:
        return None, "empty"
    parsed = [(r, parse_ts(r.get("TIMESTAMP"))) for r in rows]
    stamps = [t for _, t in parsed if t]
    if not stamps:
        return None, "no valid timestamps"
    latest = max(stamps)
    # File hhmm covers the 5 minutes before hhmm. Names carry no date, so anything
    # outside the expected window means the file is stale (e.g. yesterday's).
    limit = slot_end + timedelta(minutes=1)
    if not (slot_start <= latest < limit):
        return None, f"stale (latest row {latest:%Y-%m-%d %H:%M})"
    macs = {}
    for r, t in parsed:
        sensor = (r.get("AMPID") or "").strip()
        mac = (r.get("AMAC") or "").strip()
        if sensor and mac and t and slot_start <= t < limit:
            macs.setdefault(sensor, set()).add(mac)  # each device once per sensor per slot
    return {s: len(m) for s, m in macs.items()}, None


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body, max_age=60):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", f"s-maxage={max_age}, stale-while-revalidate=60")
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
            q = parse_qs(urlparse(self.path).query)
            try:
                discard = min(max(int((q.get("discard") or ["1"])[0]), 0), 3)
            except ValueError:
                return self._send(400, {"error": "discard must be an integer"}, 0)
            only = {s.strip() for v in q.get("sensor", []) for s in v.split(",") if s.strip()}

            base_url = os.environ["JRISS_API_URL"].rstrip("/")
            auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])

            now = datetime.now(JST).replace(tzinfo=None)
            end = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0)
            # Newest first, plus spares in case some files are missing or stale
            slots = [end - timedelta(minutes=5 * i) for i in range(discard + 3)]

            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = [pool.submit(fetch_rows, f"{base_url}/{t:%H%M}.csv", auth) for t in slots]
                results = [f.result() for f in futures]

            valid, skipped = [], []
            for t, rows in zip(slots, results):
                counts, reason = summarize(rows, t - timedelta(minutes=5), t)
                info = {"timeCode": f"{t:%H%M}", "window": f"{t - timedelta(minutes=5):%H:%M}-{t:%H:%M}"}
                if reason:
                    skipped.append({**info, "reason": reason})
                else:
                    valid.append((t, counts, info))

            # The newest period may still be filling, so skip `discard` valid files
            if len(valid) <= discard:
                return self._send(503, {"error": "No usable 5-minute file found", "skipped": skipped}, 0)
            slot_end, counts, info = valid[discard]

            ids = sorted(set(KNOWN) | set(counts))
            if only:
                ids = [s for s in ids if s in only]
            sensors = {
                s: {"count": counts.get(s), "status": "ok" if s in counts else "no_data"}
                for s in ids
            }

            return self._send(200, {
                "window": info["window"],
                "slot_start": (slot_end - timedelta(minutes=5)).isoformat(),
                "slot_end": slot_end.isoformat(),
                "minutes_ago": round((now - slot_end).total_seconds() / 60, 1),
                "generated_at": now.isoformat(),
                "sensors": sensors,
                "discarded": [i for _, _, i in valid[:discard]],
                "skipped": skipped,
            })

        except KeyError as e:
            return self._send(500, {"error": "server_misconfigured", "detail": f"Missing environment variable: {e.args[0]}"}, 0)
        except requests.RequestException as e:
            return self._send(502, {"error": "Failed to retrieve sensor data", "detail": str(e)}, 0)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": type(e).__name__, "detail": str(e)}, 0)