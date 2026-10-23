import json
import os
import statistics
import sys
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, os.path.dirname(__file__))
from _academic_calendar import lookup, CLASS_WEEKDAYS
from _common import JST, BadRequest, param, load_days, fill_days

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def parse_weekday(value):
    if value.isdigit() and 0 <= int(value) <= 6:
        return int(value)
    names = [n[:3].lower() for n in DAY_NAMES]
    if value[:3].lower() in names:
        return names.index(value[:3].lower())
    raise BadRequest("weekday must be 0-6 (Monday=0) or a day name")


def matching_dates(today, weekday, kind, days_back):
    """Past dates with this weekday and day type, newest first. Dates outside the
    academic calendar are skipped because their day type is unknown."""
    out = []
    for i in range(1, days_back + 1):
        d = today - timedelta(days=i)
        if d.weekday() != weekday:
            continue
        info = lookup(d)
        if info["phase"] == "unknown":
            continue
        if info["is_class_day"] == (kind == "class"):
            out.append(d)
    return out


def series_for(counts, resolution):
    if resolution == "5min":
        return counts
    return [round(sum(counts[h * 12:(h + 1) * 12]) / 12, 1) for h in range(24)]


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

            resolution = param(q, "resolution", "hour")
            if resolution not in ("hour", "5min"):
                raise BadRequest("resolution must be 'hour' or '5min'")
            try:
                days_back = min(max(int(param(q, "days", "365")), 28), 400)
            except ValueError:
                raise BadRequest("days must be an integer")

            today = datetime.now(JST).date()

            # Weekday and day type come from `date` (preferred) or explicit params
            if param(q, "date"):
                try:
                    ref = date.fromisoformat(param(q, "date"))
                except ValueError:
                    raise BadRequest("date must be YYYY-MM-DD")
                info = lookup(ref)
                if info["phase"] == "unknown":
                    raise BadRequest("That date is outside the academic calendar, so its day type is unknown")
                weekday = ref.weekday()
                kind = "class" if info["is_class_day"] else "non_class"
            else:
                weekday = parse_weekday(param(q, "weekday", str(today.weekday())))
                kind = "class" if weekday in CLASS_WEEKDAYS else "non_class"
            kind = param(q, "kind", kind)
            if kind not in ("class", "non_class"):
                raise BadRequest("kind must be 'class' or 'non_class'")

            dates = matching_dates(today, weekday, kind, days_back)
            label = f"{'Class-day' if kind == 'class' else 'Non-class'} {DAY_NAMES[weekday]}s"
            if not dates:
                return self._send(404, {"error": "no_matching_days", "message": f"No {label} in the last {days_back} days of the academic calendar."}, 300)

            base_url = os.environ["JRISS_DAILY_URL"].rstrip("/")
            auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])

            states = load_days(sensor, dates)
            unknown = [d for d in dates if states[d]["state"] == "unknown"]
            if unknown and fill_days(unknown, base_url, auth):
                states = load_days(sensor, dates)
            pending = sum(1 for d in dates if states[d]["state"] == "unknown")

            days_out = []
            for d in dates:
                if states[d]["state"] != "ready":
                    continue
                info = lookup(d)
                days_out.append({
                    "date": d.isoformat(),
                    "semester": info["semester"],
                    "week": info["week"],
                    "phase": info["phase"],
                    "reason": info["reason"],
                    "values": series_for(states[d]["counts"], resolution),
                })

            count_state = lambda s: sum(1 for d in dates if states[d]["state"] == s)
            coverage = {
                "matching_dates": len(dates),
                "loaded": len(days_out),
                "no_file": count_state("missing"),
                "sensor_had_no_rows": count_state("nodata"),
                "pending": pending,
                "window_days": days_back,
                "oldest": dates[-1].isoformat(),
                "newest": dates[0].isoformat(),
            }
            if not days_out and not pending:
                return self._send(404, {"error": "data_not_available", "message": "Data was not available for these days.", "coverage": coverage}, 300)

            n = len(days_out[0]["values"]) if days_out else 0
            stats = {k: [] for k in ("min", "max", "median", "mean", "min_date", "max_date")}
            for i in range(n):
                col = [(x["values"][i], x["date"]) for x in days_out]
                vals = [v for v, _ in col]
                lo, hi = min(col), max(col)
                stats["min"].append(lo[0])
                stats["min_date"].append(lo[1])
                stats["max"].append(hi[0])
                stats["max_date"].append(hi[1])
                stats["median"].append(round(statistics.median(vals), 1))
                stats["mean"].append(round(sum(vals) / len(vals), 1))

            x = ([f"{h:02d}:00" for h in range(24)] if resolution == "hour"
                 else [f"{i // 12:02d}:{(i % 12) * 5:02d}" for i in range(288)])

            return self._send(200, {
                "sensor": sensor,
                "weekday": DAY_NAMES[weekday],
                "kind": kind,
                "label": label,
                "resolution": resolution,
                "x": x,
                "days": days_out,
                "stats": stats,
                "coverage": coverage,
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