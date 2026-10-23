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
from _academic_calendar import lookup, SEMESTERS

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


def with_description(day):
    info = lookup(day)
    return {**info, "description": describe(info)}


def resolve_semester(day, target):
    """Same week # and weekday in another semester of the same term."""
    src = lookup(day)
    if not src["semester"] or src["week"] is None:
        raise BadRequest("override=semester needs a date inside a class or exam week "
                         f"(that date is: {src['phase']})")
    sem = next(s for s in SEMESTERS if s["name"] == src["semester"])

    if target == "prev":
        older = [s for s in SEMESTERS if s["term"] == sem["term"] and s["start"] < sem["start"]]
        if not older:
            raise DataUnavailable()
        tgt = older[-1]
    elif target.isdigit():
        tgt = next((s for s in SEMESTERS
                    if s["term"] == sem["term"] and s["start"].year == int(target)), None)
        if not tgt:
            raise DataUnavailable()
    else:
        raise BadRequest("target must be 'prev' or a 4-digit year")

    first = tgt["classes"][0]
    monday = first - timedelta(days=first.weekday())
    resolved = monday + timedelta(days=(src["week"] - 1) * 7 + day.weekday())

    check = lookup(resolved)
    if check["semester"] != tgt["name"] or check["week"] is None:
        raise BadRequest(f"Week {src['week']} doesn't exist in {tgt['name']} "
                         f"(maps to {resolved}, which is {check['phase']})")
    return resolved


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
                req_date = date.fromisoformat(param(q, "date", ""))
                hour = datetime.strptime(param(q, "time", ""), "%H:%M").hour
            except ValueError:
                raise BadRequest("date must be YYYY-MM-DD and time must be HH:MM")

            override = param(q, "override", "none")
            if override not in ("none", "semester"):
                raise BadRequest("override must be 'none' or 'semester'")
            target = param(q, "target", "prev")

            used_date = resolve_semester(req_date, target) if override == "semester" else req_date

            # 14:35 -> the hour 14:00-15:00
            hour_start = datetime(used_date.year, used_date.month, used_date.day, hour)
            hour_end = hour_start + timedelta(hours=1)

            base_url = os.environ["JRISS_DAILY_URL"].rstrip("/")
            auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])
            resp = requests.get(f"{base_url}/{used_date:%Y%m%d}.csv", auth=auth, timeout=30)
            if resp.status_code in (404, 410):
                raise DataUnavailable(used_date)
            resp.raise_for_status()

            reader = csv.DictReader(io.StringIO(resp.text))
            if not reader.fieldnames or "TIMESTAMP" not in reader.fieldnames:
                raise DataUnavailable(used_date)

            sets = [set() for _ in range(SLOTS)]
            signals = 0
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
                if hour_start <= ts < hour_end:
                    sets[int((ts - hour_start).total_seconds() // 300)].add(mac)
                    signals += 1

            slot_counts = [len(s) for s in sets]
            now = datetime.now(JST).replace(tzinfo=None)
            complete = hour_end <= now

            return self._send(200, {
                "sensor": sensor,
                "request": {"date": req_date.isoformat(), "time": param(q, "time"),
                            "override": override, "target": target if override == "semester" else None},
                "requested_date": with_description(req_date),
                "used_date": with_description(used_date),
                "hour": {"start": f"{hour_start:%H:%M}", "end": f"{hour_end:%H:%M}",
                         "complete": complete},
                "crowding": {
                    "average_5min": round(sum(slot_counts) / SLOTS, 1),
                    "signals_per_5min": round(signals / SLOTS, 1),
                    "slot_counts": slot_counts,
                    "slots_with_data": sum(1 for c in slot_counts if c),
                    "signal_rows": signals,
                },
            }, max_age=86400 if complete else 60)

        except BadRequest as e:
            return self._send(400, {"error": str(e)})
        except DataUnavailable as e:
            return self._send(404, {
                "error": "data_not_available",
                "message": "Data was not available that far back.",
                "used_date": e.used_date.isoformat() if e.used_date else None,
            }, max_age=300)
        except requests.RequestException as e:
            return self._send(502, {"error": "Failed to retrieve data", "detail": str(e)})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": type(e).__name__, "detail": str(e)})