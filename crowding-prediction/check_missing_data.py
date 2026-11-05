#!/usr/bin/env python3
"""Report missing or invalid cached Wi-Fi sensor/day JSON files."""
import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path

DEFAULT_SENSORS = [f"AMPM18-KJ{x:03d}" for x in (8, 9, 11, 12, 13, 14, 16)]


def days_between(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def check_file(path, sensor, day):
    if not path.is_file():
        return "missing_file", "No cached JSON file"
    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return "invalid_json", str(exc)
    if not isinstance(payload, dict):
        return "invalid_response", "JSON root is not an object"
    if payload.get("error"):
        return "endpoint_error", str(payload["error"])
    if payload.get("sensor") not in (None, sensor) and payload.get("sensor_id") not in (None, sensor):
        return "wrong_sensor", f"Response sensor: {payload.get('sensor') or payload.get('sensor_id')}"
    info = payload.get("date")
    response_day = info.get("date") if isinstance(info, dict) else info
    if response_day and response_day != day.isoformat():
        return "wrong_date", f"Response date: {response_day}"
    hours = payload.get("hours")
    if not isinstance(hours, list):
        return "missing_hours", "No hours array"
    hour_map = {h.get("hour"): h for h in hours if isinstance(h, dict)}
    for hour in range(24):
        h = hour_map.get(hour)
        if h is None:
            return "incomplete_day", f"Missing hour {hour:02d}"
        slots = h.get("slot_counts")
        if not isinstance(slots, list) or len(slots) != 12:
            return "incomplete_day", f"Hour {hour:02d} has {len(slots) if isinstance(slots, list) else 0} slots (expected 12)"
        if any(value is None for value in slots):
            return "incomplete_day", f"Hour {hour:02d} contains null slots"
    return None, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/wifi"))
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 4, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 31))
    parser.add_argument("--sensors", nargs="+", default=DEFAULT_SENSORS)
    parser.add_argument("--output", type=Path, default=Path("data/processed/missing_wifi_days.csv"))
    args = parser.parse_args()
    if args.start > args.end:
        parser.error("--start must not be after --end")
    rows = []
    for sensor in args.sensors:
        for day in days_between(args.start, args.end):
            path = args.cache_dir / sensor / f"{day.isoformat()}.json"
            status, reason = check_file(path, sensor, day)
            if status:
                rows.append({"sensor_id": sensor, "date": day.isoformat(), "status": status, "reason": reason, "expected_path": str(path)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["sensor_id", "date", "status", "reason", "expected_path"])
        writer.writeheader()
        writer.writerows(rows)
    total = len(args.sensors) * sum(1 for _ in days_between(args.start, args.end))
    print(f"Checked {total} sensor-days. Missing/invalid/incomplete: {len(rows)}")
    for sensor in args.sensors:
        count = sum(row["sensor_id"] == sensor for row in rows)
        print(f"  {sensor}: {count}")
    print(f"Report: {args.output.resolve()}")


if __name__ == "__main__":
    main()
