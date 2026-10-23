import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

JST = ZoneInfo("Asia/Tokyo")
LAT = float(os.environ.get("WEATHER_LAT", "34.98"))    # approx. Kyoto Katsura; set your own
LON = float(os.environ.get("WEATHER_LON", "135.70"))

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
RECENT_DAYS = 10  # archive lags; use the forecast API for anything newer

HOURLY = ["temperature_2m", "apparent_temperature", "relative_humidity_2m",
          "precipitation", "rain", "snowfall", "cloud_cover",
          "wind_speed_10m", "wind_gusts_10m", "weather_code"]
DAILY = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum",
         "rain_sum", "snowfall_sum", "precipitation_hours",
         "wind_speed_10m_max", "weather_code"]

# WMO weather interpretation codes
CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "heavy freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "heavy freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light showers", 81: "showers", 82: "heavy showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm with hail",
}


def category(code):
    if code is None:
        return None
    if code in (95, 96, 99):
        return "thunderstorm"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (56, 57, 66, 67):
        return "freezing_rain"
    if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
        return "rain"
    if code in (45, 48):
        return "fog"
    return None


_cache = {}


def _fetch(day):
    now = time.time()
    hit = _cache.get(day)
    if hit and hit[0] > now:
        return hit[1]

    today = datetime.now(JST).date()
    age = (today - day).days
    url = FORECAST_URL if age <= RECENT_DAYS else ARCHIVE_URL
    resp = requests.get(url, params={
        "latitude": LAT, "longitude": LON,
        "start_date": day.isoformat(), "end_date": day.isoformat(),
        "hourly": ",".join(HOURLY), "daily": ",".join(DAILY),
        "timezone": "Asia/Tokyo",
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _cache[day] = (now + (86400 if age > RECENT_DAYS else 900), data)
    return data


def get_weather(day, hour=None, include_hours=False):
    """Weather for a date. `hour` (0-23) adds that hour; include_hours adds all 24."""
    data = _fetch(day)
    h, d = data["hourly"], data["daily"]

    hours = []
    for i in range(len(h["time"])):
        code = h["weather_code"][i]
        hours.append({
            "hour": int(h["time"][i][11:13]),
            "temp_c": h["temperature_2m"][i],
            "feels_like_c": h["apparent_temperature"][i],
            "humidity_pct": h["relative_humidity_2m"][i],
            "precipitation_mm": h["precipitation"][i],
            "rain_mm": h["rain"][i],
            "snowfall_cm": h["snowfall"][i],
            "cloud_cover_pct": h["cloud_cover"][i],
            "wind_kmh": h["wind_speed_10m"][i],
            "gusts_kmh": h["wind_gusts_10m"][i],
            "weather_code": code,
            "condition": CODES.get(code),
        })

    events = []
    for x in hours:
        c = category(x["weather_code"])
        if c and c not in events:
            events.append(c)

    code = d["weather_code"][0]
    daily = {
        "high_c": d["temperature_2m_max"][0],
        "low_c": d["temperature_2m_min"][0],
        "precipitation_mm": d["precipitation_sum"][0],
        "rain_mm": d["rain_sum"][0],
        "snowfall_cm": d["snowfall_sum"][0],
        "precipitation_hours": d["precipitation_hours"][0],
        "max_wind_kmh": d["wind_speed_10m_max"][0],
        "summary": CODES.get(code),     # the day's most severe condition
        "events": events,               # e.g. ["rain", "thunderstorm"]
    }

    out = {
        "source": "open-meteo",
        "location": {"lat": LAT, "lon": LON},
        "is_forecast": day > datetime.now(JST).date(),
        "daily": daily,
    }
    if hour is not None:
        out["hour"] = hours[hour] if 0 <= hour < len(hours) else None
    if include_hours:
        out["hours"] = hours
    return out