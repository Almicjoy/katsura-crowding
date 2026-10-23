import json
import os
import sys
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(__file__))
from _academic_calendar import lookup, equivalents, describe

JST = ZoneInfo("Asia/Tokyo")


def with_description(d):
    info = lookup(d)
    return {**info, "description": describe(info)}


def one_year_back(d):
    try:
        return d.replace(year=d.year - 1)
    except ValueError:                       # Feb 29
        return d.replace(year=d.year - 1, day=28)


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body, max_age=300):
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
            explicit = bool((q.get("date") or [""])[0])
            try:
                day = date.fromisoformat((q.get("date") or [today.isoformat()])[0])
            except ValueError:
                return self._send(400, {"error": "date must be YYYY-MM-DD"})

            matches = []
            for e in equivalents(day):
                matches.append({**e, "in_future": date.fromisoformat(e["date"]) > today})

            body = {
                **with_description(day),
                # same week # and weekday in other semesters of the same term
                "equivalents": matches,
                "last_year": {
                    "same_date": with_description(one_year_back(day)),
                    # 364 days back = same weekday, closest calendar date
                    "same_weekday": with_description(day - timedelta(days=364)),
                },
            }
            return self._send(200, body, max_age=3600 if explicit else 300)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return self._send(500, {"error": type(e).__name__, "detail": str(e)})