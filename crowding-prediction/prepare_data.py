"""Download/cache Katsura historical endpoint responses and build a five-minute ML CSV.

Run from project root: python prepare_data.py
Dependencies: pip install requests pandas numpy
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter

START = date(2026, 4, 1)
END = date(2026, 10, 31)
SENSORS = [f"AMPM18-KJ{x:03d}" for x in (8, 9, 10, 11, 12, 13, 14, 15, 16, 17)]
BASE_URL = os.environ.get('CROWDING_API_URL', 'http://localhost:3000').rstrip('/')
CACHE = Path('data/cache')
OUTPUT = Path('data/processed/crowding_5min.csv')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def get_json(session, url, params, attempts=4, timeout=45):
    for attempt in range(attempts):
        try:
            response = session.get(url, params=params, timeout=timeout)
            if response.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f'HTTP {response.status_code}', response=response)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == attempts - 1:
                raise
            delay = min(30, 2 ** attempt + random.uniform(0, 0.5))
            print(f'  Retry {attempt + 1}/{attempts - 1} after {delay:.1f}s: {exc}', flush=True)
            time.sleep(delay)


def days_between(start, end):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def wifi_path(sensor, day):
    return CACHE / 'wifi' / sensor / f'{day.isoformat()}.json'


def valid_day(payload, sensor, day):
    if not isinstance(payload, dict) or payload.get('sensor') != sensor:
        return False
    info = payload.get('date')
    reported_date = info.get('date') if isinstance(info, dict) else info
    if reported_date != day.isoformat():
        return False
    hours = payload.get('hours')
    return (isinstance(hours, list) and len(hours) == 24 and
            all(isinstance(h, dict) and isinstance(h.get('slot_counts'), list)
                and len(h['slot_counts']) == 12 for h in hours))


def download_wifi(session, start, end, sensors, delay, refresh=False):
    total = (end - start).days * len(sensors) + len(sensors)
    done = skipped = missing = failed = 0
    for day in days_between(start, end):
        for sensor in sensors:
            path = wifi_path(sensor, day)
            if path.exists() and not refresh:
                try:
                    cached = read_json(path)
                    if valid_day(cached, sensor, day):
                        skipped += 1
                        continue
                    print(f'Invalid cached response, refetching: {path}', flush=True)
                except (OSError, ValueError):
                    print(f'Unreadable cached response, refetching: {path}', flush=True)
            try:
                data = get_json(session, f'{BASE_URL}/api/history_day_cache',
                                {'sensor': sensor, 'date': day.isoformat()})
                if not valid_day(data, sensor, day):
                    raise ValueError('Endpoint response missing matching sensor/date or five-minute slot_counts')
                write_json(path, data)
                done += 1
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    missing += 1
                    print(f'No data: {sensor} {day}', flush=True)
                else:
                    failed += 1
                    print(f'Wi-Fi error {sensor} {day}: {exc}', flush=True)
            except (requests.RequestException, ValueError, OSError) as exc:
                failed += 1
                print(f'Wi-Fi error {sensor} {day}: {exc}', flush=True)
            if delay:
                time.sleep(delay)
        print(f'Wi-Fi through {day}: saved={done}, cached={skipped}, unavailable={missing}, errors={failed} / {total}', flush=True)
    return done, skipped, missing, failed


def parse_day(payload, sensor, day):
    info = payload.get('date') or {}
    info = info if isinstance(info, dict) else {'date': info}
    raw_session = info.get('session', payload.get('session'))
    try:
        session_number = int(raw_session) if raw_session not in (None, '') else None
    except (ValueError, TypeError):
        session_number = None
    is_class = info.get('is_class_day', payload.get('is_class_day'))
    if isinstance(is_class, str):
        is_class = is_class.lower() in ('true', '1', 'yes')
    weekday = info.get('weekday', day.weekday())
    if not isinstance(weekday, (int, float)):
        weekday = day.weekday()
    rows = []
    for entry in payload.get('hours', []):
        hour = int(entry['hour'])
        if not 0 <= hour <= 23:
            continue
        hourly_weather = entry.get('weather') or {}
        temp = hourly_weather.get('temp_c')
        rain = hourly_weather.get('rain_mm')
        precipitation = hourly_weather.get('precipitation_mm')
        slots = entry.get('slot_counts')
        if not isinstance(slots, list):
            # Summary endpoint responses do not have per-5-minute observations.
            continue
        for idx, count in enumerate(slots[:12]):
            if count is None:
                continue
            stamp = f'{day.isoformat()} {hour:02d}:{idx * 5:02d}:00'
            rows.append({
                'timestamp': stamp, 'date': day.isoformat(), 'sensor_id': sensor,
                'count': float(count), 'hour': hour, 'minute': idx * 5,
                'weekday': int(weekday),
                'semester': info.get('semester', payload.get('semester')),
                'term': info.get('term', payload.get('term')),
                'phase': info.get('phase', payload.get('phase')),
                'day_reason': info.get('reason', payload.get('reason')),
                'is_class_day': int(is_class) if is_class is not None else None,
                'session_number': session_number,
                'temperature_c': temp, 'rainfall_mm': rain,
                'precipitation_mm': precipitation,
                'slots_with_data': entry.get('slots_with_data'),
                'slots_final': entry.get('slots_final'),
                'hour_complete': entry.get('complete'),
            })
    return rows


def build_csv(start, end, sensors):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix('.csv.tmp')
    n = 0
    header = True
    missing_slots = 0
    missing_weather = 0
    # Stream one day at a time to avoid keeping ~400k rows in RAM.
    with tmp.open('w', newline='', encoding='utf-8') as output:
        for day in days_between(start, end):
            for sensor in sensors:
                path = wifi_path(sensor, day)
                if not path.exists():
                    continue
                try:
                    rows = parse_day(read_json(path), sensor, day)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    print(f'Invalid Wi-Fi cache {path}: {exc}', flush=True)
                    continue
                if not rows:
                    missing_slots += 1
                    continue
                missing_weather += sum(r['temperature_c'] is None or r['rainfall_mm'] is None for r in rows)
                df = pd.DataFrame(rows)
                minutes = df['hour'] * 60 + df['minute']
                df['minute_of_day_sin'] = np.sin(2 * np.pi * minutes / 1440)
                df['minute_of_day_cos'] = np.cos(2 * np.pi * minutes / 1440)
                df.to_csv(output, index=False, header=header)
                header = False
                n += len(df)
    if not n:
        tmp.unlink(missing_ok=True)
        raise ValueError('No five-minute observations found. Check endpoint responses and cached files.')
    tmp.replace(OUTPUT)
    print(f'Saved {n:,} observations to {OUTPUT} ({missing_slots} cached responses without slots; {missing_weather:,} rows with missing temperature or rainfall).')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start', type=date.fromisoformat, default=START)
    p.add_argument('--end', type=date.fromisoformat, default=END)
    p.add_argument('--sensors', nargs='+', default=SENSORS)
    p.add_argument('--delay', type=float, default=0.35, help='Seconds between Wi-Fi requests')
    p.add_argument('--refresh-wifi', action='store_true')
    p.add_argument('--offline', action='store_true', help='Only use existing caches')
    args = p.parse_args()
    if args.end < args.start or args.delay < 0:
        p.error('Invalid date range or negative delay')
    with requests.Session() as session:
        if not args.offline:
            download_wifi(session, args.start, args.end, args.sensors, args.delay, args.refresh_wifi)
    build_csv(args.start, args.end, args.sensors)


if __name__ == '__main__':
    main()
