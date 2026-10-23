import { API_BASE, DAY_ENDPOINT } from "./config.js";

export const COLORS = ["#d9822b", "#b0449a", "#2f9e6b", "#c2402f", "#8a8f2e"];
export const today = () =>
  new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Tokyo" }).format(new Date());
export const asDate = (iso) => new Date(`${iso}T12:00:00`);
export const dl = (iso, long) =>
  asDate(iso).toLocaleDateString("en-US", {
    weekday: long ? "long" : "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
export const wd = (iso) => asDate(iso).toLocaleDateString("en-US", { weekday: "short" });
export const hl = (h) => `${h % 12 || 12} ${h % 24 < 12 ? "AM" : "PM"}`;
export const tl = (h, m) =>
  `${h % 12 || 12}:${String(m).padStart(2, "0")} ${h % 24 < 12 ? "AM" : "PM"}`;
export const fmt = (v, d = 0) => (v == null ? "–" : Number(v).toFixed(d));
export const niceMax = (v) => {
  const p = 10 ** Math.floor(Math.log10(v)),
    n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
};
export const toPath = (vals, x, y) => {
  let d = "",
    pen = false;
  vals.forEach((v, i) => {
    if (v == null) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    pen = true;
  });
  return d;
};
export const dayKind = (i) =>
  !i
    ? ""
    : i.phase === "classes"
      ? i.is_class_day
        ? "class day"
        : `no classes${i.reason ? ` (${i.reason})` : ""}`
      : i.phase === "exams"
        ? "exam week"
        : i.phase === "break"
          ? "break"
          : "";

export async function api(path) {
  const r = await fetch(API_BASE + path);
  const body = await r.json().catch(() => ({}));
  if (!r.ok)
    throw Object.assign(new Error(body.message || body.error || `HTTP ${r.status}`), {
      status: r.status,
    });
  return body;
}
export const dayUrl = (sensor, date) => `${DAY_ENDPOINT}?sensor=${sensor}&date=${date}`;

// ---------- Browser cache (localStorage) ----------
// Past days never change, so they are kept until the Refresh button is pressed.
// TODAY_MAX_AGE_MS = null means today's data also only refreshes with the button;
// set it to e.g. 5 * 60 * 1000 to make today's data expire after 5 minutes.
export const TODAY_MAX_AGE_MS = null;
export const INFO_MAX_AGE_MS = 24 * 3600 * 1000; // calendar info
export const NONE_MAX_AGE_MS = 6 * 3600 * 1000; // remembers "no data" answers for a while
export const PREFIX = "kc:v1:";

export function readCache(key, date, maxAge) {
  try {
    const e = JSON.parse(localStorage.getItem(PREFIX + key));
    if (!e) return null;
    const age = Date.now() - e.t;
    if (e.none) return age < NONE_MAX_AGE_MS ? e : null;
    if (maxAge != null && age > maxAge) return null;
    if (date < today() && !e.final) return null; // saved while the day was still in progress
    return e;
  } catch {
    return null;
  }
}

export function writeCache(key, entry) {
  const save = () => localStorage.setItem(PREFIX + key, JSON.stringify(entry));
  try {
    save();
  } catch {
    try {
      // Storage full: drop the 30 oldest entries and retry once
      Object.keys(localStorage)
        .filter((k) => k.startsWith(PREFIX))
        .map((k) => [k, JSON.parse(localStorage.getItem(k) || "{}").t || 0])
        .sort((a, b) => a[1] - b[1])
        .slice(0, 30)
        .forEach(([k]) => localStorage.removeItem(k));
      save();
    } catch {
      /* caching is optional */
    }
  }
}

export async function cached(path, { date, maxAge = null, force = false }) {
  const key = API_BASE + path;
  if (!force) {
    const hit = readCache(key, date, maxAge);
    if (hit) {
      if (hit.none) throw Object.assign(new Error("No data"), { status: 404 });
      return hit;
    }
  }
  try {
    // A forced refresh also bypasses Vercel's edge cache with a throwaway parameter
    const body = await api(
      force ? `${path}${path.includes("?") ? "&" : "?"}_=${Date.now()}` : path,
    );
    const entry = { t: Date.now(), body, final: date < today() };
    writeCache(key, entry);
    return entry;
  } catch (e) {
    if (e.status === 404) writeCache(key, { t: Date.now(), none: true });
    throw e;
  }
}

export function aggregateSlots(slots = [], interval = 5) {
  const size = interval / 5;

  if (size === 1) {
    return slots;
  }

  const result = [];

  for (let i = 0; i < slots.length; i += size) {
    const group = slots.slice(i, i + size);

    // Keep the window missing if any of its slots are missing.
    if (group.length < size || group.some((v) => v == null)) {
      result.push(null);
      continue;
    }

    result.push(
      Math.round(group.reduce((sum, v) => sum + v, 0))
    );
  }

  return result;
}

export function aggregateHour(hourData, interval = 5) {
  if (!hourData) return null;

  const slots = aggregateSlots(hourData.slot_counts ?? [], interval);
  const available = slots.filter((v) => v != null);

  return available.length
    ? Math.round(
        available.reduce((sum, v) => sum + v, 0) / available.length
      )
    : null;
}