import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { SENSORS, CAMPUS } from "./config.js";
import { api, tl } from "./lib.js";

const POLL_MS = 60000; // /api/live is cached for about a minute, so polling faster gains nothing
const BAR_PX = 56;
const LOW = "#1b9e77", MID = "#e8890c", HIGH = "#c2402f"; // no blue: blue means rain
const shade = (f) => (f < 0.4 ? LOW : f < 0.7 ? MID : HIGH);
const clock = (hhmm) => {
  const [h, m] = hhmm.split(":").map(Number);
  return tl(h, m);
};
const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

function iconFor(count, frac, selected) {
  const h = count == null ? 0 : Math.max(4, Math.round(frac * BAR_PX));
  const color = count == null ? "#9aa5b1" : shade(frac);
  return L.divIcon({
    className: "",
    iconSize: [36, 100],
    iconAnchor: [18, 93], // the dot at the bottom sits on the sensor's coordinates
    html: `<div class="mk ${selected ? "sel" : ""}"><div class="mk-num">${count ?? "–"}</div><div class="mk-bar"><i style="height:${h}px;background:${color}"></i></div><div class="mk-dot"></div></div>`,
  });
}

export default function LiveMap({ selectedId, onSelect }) {
  const el = useRef(null);
  const map = useRef(null);
  const markers = useRef({});
  const pick = useRef(onSelect);
  pick.current = onSelect;
  const [live, setLive] = useState(null);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);

  // Create the map once
  useEffect(() => {
    const m = L.map(el.current);
    const street = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    });
    const sat = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      { maxZoom: 19, attribution: "Imagery &copy; Esri" },
    );
    street.addTo(m);
    L.control.layers({ "Street map": street, Satellite: sat }).addTo(m);
    const pts = SENSORS.filter((s) => s.loc).map((s) => s.loc);
    if (pts.length)
      m.fitBounds(pts, { paddingTopLeft: [40, 100], paddingBottomRight: [40, 30], maxZoom: 18 });
    else m.setView([CAMPUS.lat, CAMPUS.lon], 16);
    const ro = new ResizeObserver(() => m.invalidateSize());
    ro.observe(el.current);
    map.current = m;
    return () => {
      ro.disconnect();
      m.remove();
      map.current = null;
      markers.current = {};
    };
  }, []);

  // Fetch live levels now, then every minute (a manual refresh skips the edge cache)
  useEffect(() => {
    let dead = false;
    const load = (bust) => {
      if (document.hidden) return;
      api(bust ? `/api/all_sensors_5min_live?_=${Date.now()}` : "/api/all_sensors_5min_live").then(
        (d) => !dead && (setLive(d), setError(null)),
        (e) => !dead && setError(e),
      );
    };
    load(tick > 0);
    const t = setInterval(() => load(false), POLL_MS);
    return () => {
      dead = true;
      clearInterval(t);
    };
  }, [tick]);

  // Draw or update one bar marker per sensor
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const counts = SENSORS.map((s) => live?.sensors?.[s.id]?.count).filter((c) => c != null);
    const top = Math.max(1, ...counts);
    SENSORS.forEach((s) => {
      if (!s.loc) return;
      const count = live?.sensors?.[s.id]?.count ?? null;
      const frac = count == null ? 0 : Math.sqrt(count / top); // square root keeps quiet sensors visible
      const icon = iconFor(count, frac, s.id === selectedId);
      let mk = markers.current[s.id];
      if (!mk) {
        mk = L.marker(s.loc, { icon }).addTo(m);
        mk.on("click", () => pick.current(s.id));
        markers.current[s.id] = mk;
      } else mk.setIcon(icon);
      mk.setZIndexOffset(s.id === selectedId ? 1000 : 0);
      mk.unbindTooltip();
      mk.bindTooltip(`<b>${esc(s.name)}</b><br>${count == null ? "no data" : `${count} devices`}`, {
        direction: "right",
        offset: [14, -45],
      });
    });
  }, [live, selectedId]);

  const sel = live?.sensors?.[selectedId];
  const name = SENSORS.find((s) => s.id === selectedId)?.name;
  const [a, b] = live?.window?.split("-") ?? [];

  return (
    <div className="card">
      <div className="bar">
        <h2>Campus right now</h2>
        <div className="refresh">
          {live && (
            <span className="muted">
              {clock(a)} to {clock(b)} ({Math.round(live.minutes_ago)} min ago)
            </span>
          )}
          <button className="btn" onClick={() => setTick(tick + 1)}>
            Refresh
          </button>
        </div>
      </div>
      {error && <p className="err">Could not load live levels: {error.message}</p>}
      <div ref={el} className="livemap" />
      <div className="legend">
        <span><i className="dot" style={{ background: LOW, marginRight: 6 }} />Quieter</span>
        <span><i className="dot" style={{ background: MID, marginRight: 6 }} />Busier</span>
        <span><i className="dot" style={{ background: HIGH, marginRight: 6 }} />Busiest</span>
        <span>
          Bars compare sensors with each other right now (square-root scale). Numbers are devices
          in the latest finished 5 minutes. Tap a bar to select a sensor.
        </span>
      </div>
      {name && (
        <p className="muted" style={{ margin: "8px 0 0" }}>
          <b>{name}:</b>{" "}
          {sel?.count == null ? "no data in the latest period" : `${sel.count} devices`}
        </p>
      )}
    </div>
  );
}