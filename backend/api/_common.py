"""Shared helpers: Upstash Redis (REST) and the per-day crowding summaries."""

import csv
import io
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

JST = ZoneInfo("Asia/Tokyo")
SLOTS_PER_DAY = 288  # 24 hours x 12 five-minute slots


class BadRequest(Exception):
    pass


def param(q, key, default=None):
    return (q.get(key) or [default])[0]


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
    return redis_pipeline([cmd])[0]


def redis_pipeline(cmds):
    """Run commands in one round trip; returns the list of results."""
    url, headers = redis_cfg()
    r = requests.post(
        f"{url}/pipeline",
        headers=headers,
        json=[[str(c) for c in cmd] for cmd in cmds],
        timeout=15,
    )
    r.raise_for_status()
    out = []
    for item in r.json():
        if "error" in item:
            raise RuntimeError(item["error"])
        out.append(item["result"])
    return out


# ---------- Per-day summaries ----------
# Redis hash  day:YYYYMMDD  ->  { sensor: "[288 counts]", ..., "_done": "1" }
# Each count is the unique devices seen by that sensor in one 5-minute slot.
# Past days never change, so these keys have no expiry.

def build_day(day, base_url, auth):
    """All sensors' 5-minute counts for one past day, or None if there is no file."""
    resp = requests.get(f"{base_url}/{day:%Y%m%d}.csv", auth=auth, timeout=40)
    if resp.status_code in (404, 410):
        return None
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    if not reader.fieldnames or "TIMESTAMP" not in reader.fieldnames:
        return None

    sets = {}
    for r in reader:
        sensor = (r.get("AMPID") or "").strip()
        mac = (r.get("AMAC") or "").strip()
        if not sensor or not mac:
            continue
        try:
            ts = datetime.fromisoformat((r.get("TIMESTAMP") or "").strip()).replace(tzinfo=None)
        except ValueError:
            continue
        if ts.date() != day:
            continue
        slots = sets.setdefault(sensor, [set() for _ in range(SLOTS_PER_DAY)])
        slots[ts.hour * 12 + ts.minute // 5].add(mac)
    return {s: [len(x) for x in slots] for s, slots in sets.items()}


def store_day(day, summary):
    cmd = ["HSET", f"day:{day:%Y%m%d}", "_done", "1"]
    for sensor, counts in summary.items():
        cmd += [sensor, json.dumps(counts, separators=(",", ":"))]
    redis_pipeline([cmd])


def mark_missing(day):
    # Short expiry: a file that is late today may exist tomorrow
    redis_cmd("SET", f"daymissing:{day:%Y%m%d}", "1", "EX", 6 * 3600)


def load_days(sensor, days):
    """State for each date: ready (with counts), nodata (day processed, sensor absent),
    missing (no file), or unknown (not processed yet)."""
    cmds = []
    for d in days:
        cmds.append(["HMGET", f"day:{d:%Y%m%d}", sensor, "_done"])
        cmds.append(["EXISTS", f"daymissing:{d:%Y%m%d}"])
    res = redis_pipeline(cmds)
    out = {}
    for i, d in enumerate(days):
        (value, done), missing = res[2 * i], res[2 * i + 1]
        if value:
            out[d] = {"state": "ready", "counts": json.loads(value)}
        elif done:
            out[d] = {"state": "nodata"}
        elif missing:
            out[d] = {"state": "missing"}
        else:
            out[d] = {"state": "unknown"}
    return out


def fill_days(days, base_url, auth, budget_s=8, workers=4):
    """Compute and store summaries for unprocessed days until the time budget runs out."""
    started, handled = time.monotonic(), 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i in range(0, len(days), workers):
            if time.monotonic() - started > budget_s:
                break
            batch = days[i:i + workers]
            futures = [pool.submit(build_day, d, base_url, auth) for d in batch]
            for d, f in zip(batch, futures):
                try:
                    summary = f.result()
                except requests.RequestException:
                    continue  # stays unknown; retried on the next request
                if summary is None:
                    mark_missing(d)
                else:
                    store_day(d, summary)
                handled += 1
    return handled