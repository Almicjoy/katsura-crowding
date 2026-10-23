import csv
import io
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, time as dtime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, os.path.dirname(__file__))
from _academic_calendar import lookup
from _weather import get_weather
from _common import load_days, build_day, store_day, mark_missing

JST = ZoneInfo("Asia/Tokyo")
SLOTS = 12            # 5-minute slots per hour
BATCH = 16            # parallel JRISS requests
FETCH_BUDGET_S = 8    # stop backfilling after this; the next request continues
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


def parse_ts(value):
    try:
        return datetime.fromisoformat((value or "").strip()).replace(tzinfo=None)
    except ValueError:
        return None


# ---------- Upstash Redis (REST) ----------

def redis_cfg():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url:
        raise KeyError("KV_REST_API_URL (or UPSTASH_REDIS_REST_URL)")
    if not token:
        raise KeyError("KV_REST_API_TOKEN (or UPSTASH_REDIS_REST_TOKEN)")
    return url.rstrip("/"), {"Authorization": f"Bearer {token}"}


def redis_cmd(*cmd):
    url, headers = redis_cfg()
    r = requests.post(url, headers=headers, json=[str(c) for c in cmd], timeout=10)
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(body["error"])
    return body["result"]


def redis_pipeline(cmds):
    url, headers = redis_cfg()
    r = requests.post(f"{url}/pipeline", headers=headers,
                      json=[[str(c) for c in cmd] for cmd in cmds], timeout=10)
    r.raise_for_status()
    for item in r.json():
        if "error" in item:
            raise RuntimeError(item["error"])


# ---------- Today: 5-minute files with a Redis cache ----------

def fetch_slot(base_url, auth, end):
    """Per-sensor [unique devices, rows] for the 5 minutes ending at `end`."""
    start = end - timedelta(minutes=5)
    resp = requests.get(f"{base_url}/{end:%H%M}.csv", auth=auth, timeout=15)
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    macs, rows = {}, {}
    for r in csv.DictReader(io.StringIO(resp.text)):
        sensor = (r.get("AMPID") or "").strip()
        mac = (r.get("AMAC") or "").strip()
        ts = parse_ts(r.get("TIMESTAMP"))
        if not sensor or not mac or ts is None:
            continue
        # Files are named hhmm only, so drop rows outside this slot (stale data)
        if not (start <= ts < end + timedelta(minutes=1)):
            continue
        macs.setdefault(sensor, set()).add(mac)
        rows[sensor] = rows.get(sensor, 0) + 1
    return {s: [len(m), rows[s]] for s, m in macs.items()}


def todays_hours(sensor, day, now, base_url, auth):
    midnight = datetime(day.year, day.month, day.day)
    # The newest file may be partial, so only slots ending before the latest one are final
    cutoff = now.replace(minute=(now.minute // 5) * 5, second=0, microsecond=0) - timedelta(minutes=5)
    key = f"slots:{day:%Y%m%d}"

    flat = redis_cmd("HGETALL", key) or []
    stored = {flat[i]: json.loads(flat[i + 1]) for i in range(0, len(flat), 2)}

    # Slot end times 00:05 ... 23:55 that are final. (23:55-24:00 lives in tomorrow's 0000.csv)
    wanted = []
    t = midnight + timedelta(minutes=5)
    while t <= cutoff and t.date() == day:
        wanted.append(t)
        t += timedelta(minutes=5)
    missing = [t for t in wanted if f"{t:%H%M}" not in stored]

    fetched, failed, started = {}, 0, time.monotonic()
    with ThreadPoolExecutor(max_workers=BATCH) as pool:
        for i in range(0, len(missing), BATCH):
            if time.monotonic() - started > FETCH_BUDGET_S:
                break
            batch = missing[i:i + BATCH]
            futures = [pool.submit(fetch_slot, base_url, auth, t) for t in batch]
            for t, f in zip(batch, futures):
                try:
                    fetched[f"{t:%H%M}"] = f.result()
                except requests.RequestException:
                    failed += 1  # not cached, retried on the next request

    if fetched:
        cmd = ["HSET", key]
        for code, value in fetched.items():
            cmd += [code, json.dumps(value)]
        # The whole day's cache disappears at midnight JST
        expire_at = int(datetime.combine(day + timedelta(days=1), dtime.min, tzinfo=JST).timestamp())
        redis_pipeline([cmd, ["EXPIREAT", key, expire_at]])
        stored.update(fetched)

    hours = []
    for h in range(24):
        slot_counts, rows = [], 0
        for s in range(SLOTS):
            end = midnight + timedelta(hours=h, minutes=5 * (s + 1))
            entry = stored.get(f"{end:%H%M}")
            if entry is None:
                slot_counts.append(None)  # not final yet (or not fetched yet)
            else:
                unique, n = entry.get(sensor, [0, 0])
                slot_counts.append(unique)
                rows += n
        known = [c for c in slot_counts if c is not None]
        expected = 11 if h == 23 else SLOTS
        hours.append({
            "hour": h,
            "label": f"{h:02d}:00-{(h + 1) % 24:02d}:00",
            "average_5min": round(sum(known) / len(known), 1) if known else None,
            "signals_per_5min": round(rows / len(known), 1) if known else None,
            "slot_counts": slot_counts,
            "slots_with_data": sum(1 for c in known if c),
            "slots_final": len(known),
            "signal_rows": rows,
            "complete": len(known) == expected,
        })

    status = {"source": "5min_files", "cached_slots": len(stored) - len(fetched),
              "fetched_now": len(fetched), "pending": len(missing) - len(fetched),
              "failed": failed, "final_through": f"{cutoff:%H:%M}"}
    return hours, status


# ---------- Past days: the daily file ----------

def past_hours(sensor, day, base_url, auth):
    state = load_days(sensor, [day])[day]
    if state["state"] == "ready":
        counts, source = state["counts"], "redis"
    elif state["state"] in ("nodata", "missing"):
        raise DataUnavailable(day)
    else:
        # Not stored yet: download once and keep the summary for every sensor
        summary = build_day(day, base_url, auth)
        if summary is None:
            mark_missing(day)
            raise DataUnavailable(day)
        store_day(day, summary)
        counts, source = summary.get(sensor), "daily_file"
        if counts is None:
            raise DataUnavailable(day)

    hours = []
    for h in range(24):
        slots = counts[h * 12 : (h + 1) * 12]
        hours.append({
            "hour": h,
            "label": f"{h:02d}:00-{(h + 1) % 24:02d}:00",
            "average_5min": round(sum(slots) / 12, 1),
            "signals_per_5min": None,
            "slot_counts": slots,
            "slots_with_data": sum(1 for c in slots if c),
            "slots_final": 12,
            "signal_rows": None,
            "complete": True,
        })
    return hours, {"source": source}


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
            detail = param(q, "detail", "summary")   # "summary" or "full"

            sensor = param(q, "sensor")
            if not sensor or not sensor.startswith("AMPM18-KJ"):
                raise BadRequest("A valid sensor parameter is required")

            now = datetime.now(JST).replace(tzinfo=None)
            try:
                day = date.fromisoformat(param(q, "date", now.date().isoformat()))
            except ValueError:
                raise BadRequest("date must be YYYY-MM-DD")
            if day > now.date():
                raise DataUnavailable(day)

            auth = HTTPBasicAuth(os.environ["JRISS_USERNAME"], os.environ["JRISS_PASSWORD"])
            is_today = day == now.date()
            if is_today:
                hours, status = todays_hours(
                    sensor, day, now, os.environ["JRISS_API_URL"].rstrip("/"), auth)
            else:
                hours, status = past_hours(
                    sensor, day, os.environ["JRISS_DAILY_URL"].rstrip("/"), auth)

            with_data = [x for x in hours if x["average_5min"] is not None and x["slots_with_data"]]
            peak = max(with_data, key=lambda x: x["average_5min"]) if with_data else None
            info = lookup(day)

            if not is_today:
                max_age = 86400
            elif status["pending"]:
                max_age = 10   # still backfilling; let the next request continue
            else:
                max_age = 120
            try:
                weather = get_weather(day, include_hours=True)
            except Exception:
                weather = {"error": "weather_unavailable"}

            hours_out, weather_out = hours, weather
            if detail != "full":
                wmap = {w["hour"]: w for w in weather.get("hours", [])}
                hours_out = []
                for x in hours:
                    w = wmap.get(x["hour"], {})
                    hours_out.append({
                        "hour": x["hour"],
                        "avg": x["average_5min"],
                        "slots": x["slots_final"],        # < 12 means partial
                        "temp_c": w.get("temp_c"),
                        "rain_mm": w.get("precipitation_mm"),
                        "condition": w.get("condition"),
                        "forecast": is_today and x["hour"] > now.hour,
                    })
                weather_out = {k: v for k, v in weather.items() if k != "hours"}

            try:
                weather = get_weather(day, include_hours=True)
            except Exception:
                weather = {"error": "weather_unavailable"}

            # Attach each hour's weather to its crowding entry
            wmap = {w["hour"]: w for w in weather.get("hours", [])}
            for x in hours:
                w = wmap.get(x["hour"])
                x["weather"] = None if w is None else {
                    **{k: v for k, v in w.items() if k != "hour"},
                    "forecast": is_today and x["hour"] > now.hour,
                }

            # Daily summary only (the per-hour list now lives inside `hours`)
            weather_daily = {k: v for k, v in weather.items() if k != "hours"}

            return self._send(200, {
                "sensor": sensor,
                "date": {**info, "description": describe(info)},
                "hours": hours,
                "weather": weather_daily,
                "summary": {
                    "peak_hour": peak["hour"] if peak else None,
                    "peak_average_5min": peak["average_5min"] if peak else None,
                    "hours_with_data": len(with_data),
                    "day_complete": not is_today,
                },
                "data": status,
            }, max_age=max_age)

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