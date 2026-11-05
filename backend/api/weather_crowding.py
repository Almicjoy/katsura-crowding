import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, os.path.dirname(__file__))
from _academic_calendar import lookup, SEMESTERS
from _common import JST, BadRequest, param, load_days, fill_days
from _weather import LAT, LON, ARCHIVE_URL, FORECAST_URL, RECENT_DAYS

_weather_cache = {}


def current_semester(today):
    for s in SEMESTERS:
        if s["start"] <= today <= s["end"]:
            return s
    started = [s for s in SEMESTERS if s["start"] <= today]
    return started[-1] if started else SEMESTERS[0]


def hourly_range(start, end):
    """{'YYYY-MM-DD': {'temp': [24], 'rain': [24]}} for start..end, from Open-Meteo.
    Older days come from the archive API, the last few days from the forecast API."""
    key = (start, end)
    hit = _weather_cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    today = datetime.now(JST).date()
    cut = today - timedelta(days=RECENT_DAYS)  # this day and later: forecast API
    out = {}
    for lo, hi, url in (
        (start, min(end, cut - timedelta(days=1)), ARCHIVE_URL),
        (max(start, cut), end, FORECAST_URL),
    ):
        if lo > hi:
            continue
        resp = requests.get(url, params={
            "latitude": LAT, "longitude": LON,
            "start_date": lo.isoformat(), "end_date": hi.isoformat(),
            "hourly": "temperature_2m,precipitation", "timezone": "Asia/Tokyo",
        }, timeout=30)
        resp.raise_for_status()
        h = resp.json()["hourly"]
        for i, ts in enumerate(h["time"]):
            day = out.setdefault(ts[:10], {"temp": [None] * 24, "rain": [None] * 24})
            hr = int(ts[11:13])
            day["temp"][hr] = h["temperature_2m"][i]
            day["rain"][hr] = h["precipitation"][i]
    _weather_cache[key] = (time.time() + 3600, out)
    return out


def hourly_average(counts):
    return [round(sum(counts[h * 12:(h + 1) * 12]) / 12, 1) for h in range(24)]


def rounded(values):
    return [None if v is None else round(v, 1) for v in values]


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body, max_age=3600):
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

            today = datetime.now(JST).date()
            cur = current_semester(today)
            name = param(q, "semester")
            sem = next((s for s in SEMESTERS if s["name"] == name), None) if name else cur
            if sem is None:
                raise BadRequest(f"Unknown semester: {name}")

            semesters = [
                {"name": s["name"], "term": s["term"], "start": s["start"].isoformat(),
                 "end": s["end"].isoformat(), "current": s is cur}
                for s in SEMESTERS if s["start"] <= today  # semesters that have not started have no data
            ]

            # Completed days only: the daily file is not final for today
            last = min(sem["end"], today - timedelta(days=1))
            if last < sem["start"]:
                return self._send(404, {"error": "no_days_yet", "message": "That semester has no completed days yet.",
                                        "semesters": semesters}, 300)
            dates = [sem["start"] + timedelta(days=i) for i in range((last - sem["start"]).days + 1)]

            base_url = os.environ["JRISS_DAILY_URL"].rstrip("/")
            auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])
            states = load_days(sensor, dates)
            unknown = [d for d in dates if states[d]["state"] == "unknown"]
            if unknown and fill_days(unknown, base_url, auth):
                states = load_days(sensor, dates)
            pending = sum(1 for d in dates if states[d]["state"] == "unknown")

            weather, weather_error = {}, None
            try:
                weather = hourly_range(dates[0], dates[-1])
            except (requests.RequestException, KeyError, ValueError) as e:
                weather_error = str(e)

            days_out = []
            for d in dates:
                if states[d]["state"] != "ready":
                    continue
                info = lookup(d)
                wx = weather.get(d.isoformat(), {})
                days_out.append({
                    "date": d.isoformat(),
                    "weekday": info["weekday"],
                    "is_class_day": info["is_class_day"],
                    "phase": info["phase"],
                    "reason": info["reason"],
                    "events": info["events"],
                    "session": info.get("session"),
                    "schedule_weekday": info.get("schedule_weekday"),
                    "crowd": hourly_average(states[d]["counts"]),
                    "temp": rounded(wx.get("temp", [None] * 24)),
                    "rain": rounded(wx.get("rain", [None] * 24)),
                })

            count_state = lambda s: sum(1 for d in dates if states[d]["state"] == s)
            return self._send(200, {
                "sensor": sensor,
                "semester": sem["name"],
                "semesters": semesters,
                "range": {"start": dates[0].isoformat(), "end": dates[-1].isoformat()},
                "days": days_out,
                "coverage": {
                    "days_in_range": len(dates), "loaded": len(days_out),
                    "no_file": count_state("missing"), "sensor_had_no_rows": count_state("nodata"),
                    "pending": pending,
                },
                "weather_error": weather_error,
                "partial": pending > 0,
            }, max_age=10 if pending else 3600)

        except BadRequest as e:
            return self._send(400, {"error": str(e)}, 60)
        except KeyError as e:
            return self._send(500, {"error": "server_misconfigured", "detail": f"Missing environment variable: {e.args[0]}"}, 0)
        except requests.RequestException as e:
            return self._send(502, {"error": "Failed to retrieve data", "detail": str(e)}, 0)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": type(e).__name__, "detail": str(e)}, 0)