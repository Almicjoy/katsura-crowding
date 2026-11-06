"""Seven-day, per-sensor aggregate AMAC recurrence audit for Vercel.

GET /api/device_week_audit?date=2026-11-05&gap=30
The window includes the selected date and its six preceding days (JST).
Only aggregated statistics are returned; no device-level identifiers.
"""
import csv
import io
import json
import math
import os
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import requests
from requests.auth import HTTPBasicAuth

JST = ZoneInfo("Asia/Tokyo")
NAMES = {
    "AMPM18-KJ008": "C Cluster: C1 Building Entrance",
    "AMPM18-KJ009": "C Cluster: Main Entrance",
    "AMPM18-KJ010": "C Cluster: ITS Lab",
    "AMPM18-KJ011": "C Cluster: Cenatio Silva (Cafeteria)",
    "AMPM18-KJ012": "B Cluster: Main Student Library",
    "AMPM18-KJ013": "A Cluster: A4 Building Rear Entrance",
    "AMPM18-KJ014": "A Cluster: P3P Parking Mae",
    "AMPM18-KJ015": "B Cluster: Boulangerie Seri Bakery",
    "AMPM18-KJ016": "B Cluster: Cafeteria Entrance",
    "AMPM18-KJ017": "B Cluster: Cafeteria Exit",
}
BINS = [(0, 5), (5, 15), (15, 30), (30, 60), (60, 120), (120, 240), (240, 720), (720, 1440), (1440, None)]


def parse_timestamp(raw):
    try:
        ts = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        return ts.replace(tzinfo=JST) if ts.tzinfo is None else ts.astimezone(JST)
    except (ValueError, AttributeError):
        return None


def stats(values):
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None, "p90": None}
    values.sort()
    n = len(values)
    position = (n - 1) * .9
    low = math.floor(position)
    high = math.ceil(position)
    p90 = values[low] + (values[high] - values[low]) * (position - low)
    return {"count": n, "mean": round(statistics.fmean(values), 2),
            "median": round(statistics.median(values), 2),
            "min": round(values[0], 2), "max": round(values[-1], 2),
            "p90": round(p90, 2)}


def distribution(values):
    result = {}
    for lower, upper in BINS:
        label = f"{lower}-{upper}m" if upper is not None else f">={lower}m"
        result[label] = sum(lower <= v < upper if upper is not None else v >= lower for v in values)
    return result


def summarize(sightings, gap_minutes):
    output = []
    for sensor in sorted(set(NAMES) | set(sightings)):
        devices = sightings.get(sensor, {})
        repeated = single = multi_day = 0
        day_counts = Counter()
        intervals = []
        returns = []
        durations = []
        multi_durations = []
        sessions_total = single_sessions = multi_sessions = 0
        for timestamps in devices.values():
            times = sorted(set(timestamps))
            if not times:
                continue
            if len(times) == 1:
                single += 1
            else:
                repeated += 1
            days = sorted({t.date() for t in times})
            day_counts[len(days)] += 1
            if len(days) > 1:
                multi_day += 1
            first_by_day = {}
            for t in times:
                first_by_day.setdefault(t.date(), t)
            firsts = [first_by_day[d] for d in days]
            returns.extend((b-a).total_seconds()/60 for a, b in zip(firsts, firsts[1:]))
            start = previous = times[0]
            count = 1
            for t in times[1:]:
                delta = (t-previous).total_seconds()/60
                intervals.append(delta)
                if delta > gap_minutes:
                    duration = (previous-start).total_seconds()/60
                    durations.append(duration)
                    sessions_total += 1
                    if count == 1:
                        single_sessions += 1
                    else:
                        multi_sessions += 1
                        multi_durations.append(duration)
                    start, count = t, 1
                else:
                    count += 1
                previous = t
            duration = (previous-start).total_seconds()/60
            durations.append(duration)
            sessions_total += 1
            if count == 1:
                single_sessions += 1
            else:
                multi_sessions += 1
                multi_durations.append(duration)
        total = len(devices)
        output.append({
            "sensor": sensor, "name": NAMES.get(sensor),
            "unique_devices": total, "repeated_devices": repeated,
            "single_sighting_devices": single, "multi_day_devices": multi_day,
            "repeat_rate_percent": round(100*repeated/total, 1) if total else 0,
            "multi_day_rate_percent": round(100*multi_day/total, 1) if total else 0,
            "days_seen_distribution": {str(i): day_counts[i] for i in range(1, 8)},
            "detection_intervals_minutes": stats(intervals),
            "detection_interval_distribution": distribution(intervals),
            "return_intervals_minutes": stats(returns),
            "sessions": {
                "total": sessions_total, "single_detection": single_sessions,
                "multiple_detection": multi_sessions,
                "observed_durations_minutes": stats(durations),
                "observed_duration_distribution": distribution(durations),
                "repeated_detection_durations_minutes": stats(multi_durations),
            },
        })
    return output


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
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
                end = date.fromisoformat((q.get("date") or [(today-timedelta(days=1)).isoformat()])[0])
                gap = float((q.get("gap") or ["30"])[0])
            except ValueError:
                return self._send(400, {"error": "date must be YYYY-MM-DD and gap must be numeric"})
            if end >= today:
                return self._send(400, {"error": "Selected date must be before today"})
            if not math.isfinite(gap) or not 5 <= gap <= 240:
                return self._send(400, {"error": "gap must be 5-240 minutes"})
            start = end-timedelta(days=6)
            base = os.environ["JRISS_DAILY_URL"].rstrip("/")
            auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])
            sightings = defaultdict(lambda: defaultdict(list))
            missing_dates, loaded_dates = [], []
            invalid_rows = rows = 0
            with requests.Session() as session:
                session.auth = auth
                for offset in range(7):
                    day = start+timedelta(days=offset)
                    response = session.get(f"{base}/{day:%Y%m%d}.csv", timeout=60)
                    if response.status_code in (404, 410):
                        missing_dates.append(day.isoformat())
                        continue
                    response.raise_for_status()
                    reader = csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
                    if not reader.fieldnames or not {"TIMESTAMP", "AMPID", "AMAC"}.issubset(reader.fieldnames):
                        return self._send(502, {"error": "Invalid CSV columns", "date": day.isoformat()})
                    loaded_dates.append(day.isoformat())
                    for row in reader:
                        sensor = (row.get("AMPID") or "").strip()
                        mac = (row.get("AMAC") or "").strip().lower()
                        ts = parse_timestamp(row.get("TIMESTAMP") or "")
                        if not sensor or not mac or ts is None or ts.date() != day:
                            invalid_rows += 1
                            continue
                        sightings[sensor][mac].append(ts)
                        rows += 1
            return self._send(200, {
                "start_date": start.isoformat(), "end_date": end.isoformat(),
                "window_days": 7, "gap_minutes": gap,
                "loaded_dates": loaded_dates, "missing_dates": missing_dates,
                "rows_processed": rows, "invalid_rows": invalid_rows,
                "note": "Durations are observed spans between detections, not confirmed physical stays. AMAC recurrence does not prove the same person's return.",
                "by_sensor": summarize(sightings, gap),
            })
        except KeyError as e:
            return self._send(500, {"error": "Missing environment variable", "name": e.args[0]})
        except requests.RequestException as e:
            return self._send(502, {"error": "Failed to retrieve daily CSV", "detail": str(e)})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": type(e).__name__, "detail": str(e)})
