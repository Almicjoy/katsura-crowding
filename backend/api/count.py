import csv
import io
import json
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from zoneinfo import ZoneInfo

import requests
from requests.auth import HTTPBasicAuth


class handler(BaseHTTPRequestHandler):
    def _send(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "s-maxage=60, stale-while-revalidate=60")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        sensor = (query.get("sensor") or [None])[0]

        if not sensor or not sensor.startswith("AMPM18-KJ"):
            return self._send(400, {"error": "A valid sensor parameter is required"})

        now = datetime.now(ZoneInfo("Asia/Tokyo"))
        minute = (now.minute // 5) * 5
        time_code = f"{now.hour:02d}{minute:02d}"

        try:
            base_url = os.environ["JRISS_API_URL"].rstrip("/")
            username = os.environ["JRISS_USERNAME"]
            password = os.environ["JRISS_PASSWORD"]

            resp = requests.get(
                f"{base_url}/{time_code}.csv",
                auth=HTTPBasicAuth(username, password),
                timeout=10,
            )
            resp.raise_for_status()

            reader = csv.DictReader(io.StringIO(resp.text))
            devices = {
                row["AMAC"].strip()
                for row in reader
                if row.get("AMPID", "").strip() == sensor
                and row.get("AMAC", "").strip()
            }

            return self._send(200, {
                "sensor": sensor,
                "count": len(devices),
                "timeCode": time_code,
                "interval": "5-minute CSV",
            })

        except requests.RequestException:
            return self._send(502, {"error": "Failed to retrieve sensor data"})
        except (KeyError, ValueError):
            return self._send(500, {"error": "Invalid CSV format or missing configuration"})