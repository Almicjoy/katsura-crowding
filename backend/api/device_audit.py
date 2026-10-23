import csv
import io
import json
import os
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import requests
from requests.auth import HTTPBasicAuth

JST = ZoneInfo("Asia/Tokyo")
NAMES = {
    "AMPM18-KJ008": "C Cluster Administration Office",
    "AMPM18-KJ009": "C1 Bldng Entrance",
    "AMPM18-KJ010": "Inside Main Cafeteria",
    "AMPM18-KJ011": "B Cluster Administration Office",
    "AMPM18-KJ012": "Katsura Main Student Library",
    "AMPM18-KJ013": "A4 Rear Entrance",
    "AMPM18-KJ014": "P3P Parking Mae",
    "AMPM18-KJ015": "Boulangerie Seri Bakery",
    "AMPM18-KJ016": "Main Cafeteria Entrance",
    "AMPM18-KJ017": "Main Cafeteria Exit",
}


def longest_stay(minutes, gap):
    """Longest stretch (minutes) of sightings with no gap larger than `gap`."""
    minutes.sort()
    best, start = 0.0, minutes[0]
    for a, b in zip(minutes, minutes[1:]):
        if b - a > gap:
            best, start = max(best, a - start), b
    return max(best, minutes[-1] - start)


def audit(csv_text, stay_hours, gap_min):
    """Count stationary devices and one-row devices in one day's CSV (all sensors)."""
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames or not {"TIMESTAMP", "AMPID", "AMAC"} <= set(reader.fieldnames):
        return None

    rows = 0
    seen = {}    # device -> number of rows in the whole file, all sensors
    where = {}   # device -> sensor of its latest row (for one-row devices, its only row)
    sight = {}   # (sensor, device) -> sighting times in minutes
    for r in reader:
        sensor = (r.get("AMPID") or "").strip()
        mac = (r.get("AMAC") or "").strip()
        if not sensor or not mac:
            continue
        rows += 1
        seen[mac] = seen.get(mac, 0) + 1
        where[mac] = sensor
        try:
            ts = datetime.fromisoformat((r.get("TIMESTAMP") or "").strip())
        except ValueError:
            continue
        sight.setdefault((sensor, mac), []).append(
            ts.toordinal() * 1440 + ts.hour * 60 + ts.minute + ts.second / 60
        )

    per = {}
    new = lambda: {"unique_devices": 0, "stationary_devices": 0, "seen_once_devices": 0}
    stationary = set()
    for (sensor, mac), minutes in sight.items():
        st = per.setdefault(sensor, new())
        st["unique_devices"] += 1
        if longest_stay(minutes, gap_min) > stay_hours * 60:
            st["stationary_devices"] += 1
            stationary.add(mac)
    once = [m for m, c in seen.items() if c == 1]
    for m in once:
        per.setdefault(where[m], new())["seen_once_devices"] += 1

    total = len(seen)
    pct = lambda n: round(100 * n / total, 1) if total else 0
    return {
        "file": {"rows": rows, "unique_devices": total, "sensors": len(per)},
        "totals": {
            "stationary_devices": len(stationary),
            "stationary_percent": pct(len(stationary)),
            "seen_once_devices": len(once),
            "seen_once_percent": pct(len(once)),
        },
        "by_sensor": [{"sensor": s, "name": NAMES.get(s), **per[s]} for s in sorted(per)],
    }


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body, max_age=0):
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
            today = datetime.now(JST).date()
            try:
                day = date.fromisoformat((q.get("date") or [(today - timedelta(days=1)).isoformat()])[0])
                hours = float((q.get("hours") or ["6"])[0])
                gap = float((q.get("gap") or ["30"])[0])
            except ValueError:
                return self._send(400, {"error": "date must be YYYY-MM-DD; hours and gap must be numbers"})
            if day >= today:
                return self._send(400, {"error": "The daily file is only complete once the day has ended. Use yesterday or earlier."})
            if not (1 <= hours <= 24 and 5 <= gap <= 240):
                return self._send(400, {"error": "hours must be 1-24 and gap 5-240 (minutes)"})

            base_url = os.environ["JRISS_DAILY_URL"].rstrip("/")
            auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])
            resp = requests.get(f"{base_url}/{day:%Y%m%d}.csv", auth=auth, timeout=60)
            if resp.status_code in (404, 410):
                return self._send(404, {"error": "data_not_available", "message": "No daily file exists for that date.", "date": day.isoformat()}, 300)
            resp.raise_for_status()

            result = audit(resp.text, hours, gap)
            if result is None:
                return self._send(502, {"error": "Unexpected file format: missing TIMESTAMP, AMPID or AMAC column"})

            return self._send(200, {
                "date": day.isoformat(),
                "thresholds": {"stationary_hours": hours, "max_gap_minutes": gap},
                **result,
            }, max_age=86400)

        except KeyError as e:
            return self._send(500, {"error": "server_misconfigured", "detail": f"Missing environment variable: {e.args[0]}"})
        except requests.RequestException as e:
            return self._send(502, {"error": "Failed to retrieve data", "detail": str(e)})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": type(e).__name__, "detail": str(e)})