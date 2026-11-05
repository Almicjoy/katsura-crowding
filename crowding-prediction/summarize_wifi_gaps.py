#!/usr/bin/env python3
"""Summarize consecutive missing/incomplete cached Wi-Fi sensor days as JSON.

Run from the project root: python summarize_wifi_gaps.py
Optional: --cache-dir data/cache/wifi --output data/processed/wifi_gap_summary.json
"""
import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

SENSORS = [f"AMPM18-KJ{x:03d}" for x in (8, 9, 11, 12, 13, 14, 16)]


def inspect(path, sensor, day):
    if not path.is_file():
        return "missing_file"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "invalid_json"
    if not isinstance(payload, dict) or payload.get("error"):
        return "endpoint_error"
    if payload.get("sensor") != sensor:
        return "sensor_mismatch"
    info = payload.get("date")
    actual_day = info.get("date") if isinstance(info, dict) else info
    if actual_day != day.isoformat():
        return "date_mismatch"
    hours = payload.get("hours")
    if not isinstance(hours, list) or len(hours) != 24:
        return "incomplete_hours"
    by_hour = {h.get("hour"): h for h in hours if isinstance(h, dict)}
    if len(by_hour) != 24 or any(h not in by_hour for h in range(24)):
        return "incomplete_hours"
    for h in range(24):
        slots = by_hour[h].get("slot_counts")
        if not isinstance(slots, list) or len(slots) != 12 or any(v is None for v in slots):
            return "incomplete_slots"
    return None


def ranges(entries):
    """Group adjacent problem dates, retaining per-status counts."""
    result = []
    for day, status in entries:
        if result and day == date.fromisoformat(result[-1]["end_date"]) + timedelta(days=1):
            r = result[-1]
            r["end_date"] = day.isoformat()
            r["days"] += 1
            r["reasons"][status] = r["reasons"].get(status, 0) + 1
        else:
            result.append({"start_date": day.isoformat(), "end_date": day.isoformat(),
                           "days": 1, "reasons": {status: 1}})
    return result

from collections import defaultdict

def print_range_summary(sensors):
    grouped = defaultdict(list)

    for sensor_id, info in sensors.items():
        for gap in info.get("unavailable_ranges", []):
            key = (gap["start_date"], gap["end_date"])
            grouped[key].append(sensor_id)

    print("\n" + "=" * 60)
    print("WI-FI SENSOR UNAVAILABILITY SUMMARY")
    print("=" * 60)

    for index, ((start, end), sensor_ids) in enumerate(
        sorted(grouped.items()), start=1
    ):
        print(f"\nRange {index}: {start} to {end}")
        print(f"Unavailable sensors ({len(sensor_ids)}):")

        for sensor_id in sorted(sensor_ids):
            print(f"  - {sensor_id}")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/cache/wifi"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/wifi_gap_summary.json"))
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 4, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 31))
    parser.add_argument("--sensors", nargs="+", default=SENSORS)
    args = parser.parse_args()
    if args.end < args.start:
        parser.error("--end must be on or after --start")
    if not args.cache_dir.is_dir():
        parser.error(f"Cache directory not found: {args.cache_dir}")
    total_days = (args.end - args.start).days + 1
    report = {"start_date": args.start.isoformat(), "end_date": args.end.isoformat(),
              "definition": "Unavailable or incomplete cached data; not proof of sensor inactivity",
              "sensors": {}}
    for sensor in args.sensors:
        failures = []
        counts = Counter()
        for offset in range(total_days):
            day = args.start + timedelta(days=offset)
            status = inspect(args.cache_dir / sensor / f"{day.isoformat()}.json", sensor, day)
            if status:
                failures.append((day, status))
                counts[status] += 1
        report["sensors"][sensor] = {
            "total_days": total_days,
            "complete_days": total_days - len(failures),
            "unavailable_days": len(failures),
            "reason_counts": dict(sorted(counts.items())),
            "unavailable_ranges": ranges(failures),
        }
        print(f"{sensor}: {len(failures)} unavailable days across {len(report['sensors'][sensor]['unavailable_ranges'])} ranges")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Saved {args.output}")
    with open("data/processed/wifi_gap_summary.json", "r", encoding="utf-8") as f:
        gap_summary = json.load(f)
    print_range_summary(gap_summary["sensors"])




if __name__ == "__main__":
    main()
