import csv
import io
import json
import os
import sys
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, os.path.dirname(__file__))
from _academic_calendar import lookup

JST = ZoneInfo("Asia/Tokyo")
SLOTS = 12  # 5-minute slots per hour
PHASE_LABEL = {"classes": "in session", "exams": "exam/feedback week",
               "break": "break", "unknown": "outside calendar"}


class BadRequest(Exception):
    pass


class DataUnavailable(Exception):
    def __init__(self, used_date=None):
        super().__init__("Data was not available that far back.")
        self.used_date = used_date


def param(q, key, default=None):
    return (q.get(key) or [default])[0]


def describe(info):
    head = f"{info['weekday']}, {info['date']}: "
    if not info["semester"]:
        return head + "outside the academic calendar"
    bits = [info["semester"]]
    if info["week"]:
        bits.append(f"week {info['week']}")
    bits.append(PHASE_LABEL[info["phase"]])
    if info["phase"] == "classes":
        bits.append("class day" if info["is_class_day"] else f"no classes ({info['reason']})")
    bits.extend(info["events"])
    return head + ", ".join(bits)


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

            sensor = param(q, "sensor")
            if not sensor or not sensor.startswith("AMPM18-KJ"):
                raise BadRequest("A valid sensor parameter is required")
            try:
                day = date.fromisoformat(param(q, "date", ""))
            except ValueError:
                raise BadRequest("date must be YYYY-MM-DD")

            now = datetime.now(JST).replace(tzinfo=None)
            if day > now.date():
                raise DataUnavailable(day)

            base_url = os.environ["JRISS_DAILY_URL"].rstrip("/")
            auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])
            resp = requests.get(f"{base_url}/{day:%Y%m%d}.csv", auth=auth, timeout=30)
            if resp.status_code in (404, 410):
                raise DataUnavailable(day)
            resp.raise_for_status()

            reader = csv.DictReader(io.StringIO(resp.text))
            if not reader.fieldnames or "TIMESTAMP" not in reader.fieldnames:
                raise DataUnavailable(day)

            midnight = datetime(day.year, day.month, day.day)
            sets = [[set() for _ in range(SLOTS)] for _ in range(24)]
            rows_per_hour = [0] * 24

            for r in reader:
                if (r.get("AMPID") or "").strip() != sensor:
                    continue
                mac = (r.get("AMAC") or "").strip()
                if not mac:
                    continue
                try:
                    ts = datetime.fromisoformat((r.get("TIMESTAMP") or "").strip()).replace(tzinfo=None)
                except ValueError:
                    continue
                if ts.date() != day:
                    continue
                slot = ts.minute // 5
                sets[ts.hour][slot].add(mac)
                rows_per_hour[ts.hour] += 1

            if sum(rows_per_hour) == 0:
                raise DataUnavailable(day)

            hours = []
            for h in range(24):
                counts = [len(s) for s in sets[h]]
                hour_end = midnight + timedelta(hours=h + 1)
                hours.append({
                    "hour": h,
                    "label": f"{h:02d}:00-{(h + 1) % 24:02d}:00",
                    "average_5min": round(sum(counts) / SLOTS, 1),
                    "signals_per_5min": round(rows_per_hour[h] / SLOTS, 1),
                    "slot_counts": counts,
                    "slots_with_data": sum(1 for c in counts if c),
                    "signal_rows": rows_per_hour[h],
                    "complete": hour_end <= now,
                })

            with_data = [x for x in hours if x["slots_with_data"]]
            peak = max(with_data, key=lambda x: x["average_5min"])
            info = lookup(day)
            is_past = day < now.date()

            return self._send(200, {
                "sensor": sensor,
                "date": {**info, "description": describe(info)},
                "hours": hours,
                "summary": {
                    "peak_hour": peak["hour"],
                    "peak_average_5min": peak["average_5min"],
                    "hours_with_data": len(with_data),
                    "day_complete": is_past,
                },
            }, max_age=86400 if is_past else 60)

        except BadRequest as e:
            return self._send(400, {"error": str(e)})
        except DataUnavailable as e:
            return self._send(404, {
                "error": "data_not_available",
                "message": "Data was not available that far back.",
                "date": e.used_date.isoformat() if e.used_date else None,
            }, max_age=300)
        except KeyError as e:
            return self._send(500, {"error": "server_misconfigured",
                                    "detail": f"Missing environment variable: {e.args[0]}"})
        except requests.RequestException as e:
            return self._send(502, {"error": "Failed to retrieve data", "detail": str(e)})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": type(e).__name__, "detail": str(e)})