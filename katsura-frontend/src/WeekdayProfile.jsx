import { useEffect, useRef, useState } from "react";
import { PROFILE_ENDPOINT } from "./config.js";
import { dl, hl, fmt, niceMax, toPath, cached } from "./lib.js";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

// Colors avoid blue, because blue means rain elsewhere in the app
const GROUPS = [
  { key: "class", label: "Class days", color: "#8a4fbf" },
  { key: "off", label: "No-class days", color: "#1b9e77" },
];

// Exam weeks, class days, and everything else (holidays, breaks, festival days, weekends)
const groupOf = (d) => {
  // Explicit campus events remain a separate category.
  const events = Array.isArray(d.events)
    ? d.events
    : d.events
      ? [d.events]
      : d.event
        ? [d.event]
        : [];

  if (events.length > 0) return "event";

  // Determine the weekday directly from the date.
  // This prevents exam phase from overriding weekends.
  const dayOfWeek = new Date(`${d.date}T12:00:00`).getDay();
  const isWeekend = dayOfWeek === 0 || dayOfWeek === 6;

  if (isWeekend) return "off";

  // Breaks and other explicitly designated no-class days.
  if (
    d.phase === "break" ||
    (d.reason && d.reason !== "exams")
  ) {
    return "off";
  }

  // Weekday exam days count as class days.
  if (d.phase === "exams") return "class";

  if (d.phase === "classes" && !d.reason) return "class";

  return "off";
};


const mondayIndex = (iso) => (new Date(`${iso}T12:00:00`).getDay() + 6) % 7;

function statsAt(days, h) {
  if (!days.length) return null;
  const col = days.map((d) => [d.values[h], d.date]);
  const sorted = col.map((c) => c[0]).sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  const lo = col.reduce((a, b) => (b[0] < a[0] ? b : a));
  const hi = col.reduce((a, b) => (b[0] > a[0] ? b : a));
  return {
    n: col.length,
    min: lo[0],
    minDate: lo[1],
    max: hi[0],
    maxDate: hi[1],
    median: sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2,
  };
}

export default function WeekdayProfile({ sensorId, date, from, to, overlay, refresh }) {
  const [weekday, setWeekday] = useState(mondayIndex(date));
  const [period, setPeriod] = useState("all");
  const [on, setOn] = useState({
    class: true,
    event: false,
    off: true,
  });
  const [contrast, setContrast] = useState(1.5);
  const [showRange, setShowRange] = useState(true);
  const [state, setState] = useState({ loading: true });
  const [hov, setHov] = useState(null);
  const [w, setW] = useState(640);
  const box = useRef(null);
  const seen = useRef(refresh);

  // Follow the main date's weekday
  useEffect(() => {
    setWeekday(mondayIndex(date));
    setPeriod("all");
  }, [date]);

  // Class days and non-class days are two requests, merged so they can be overlaid
  useEffect(() => {
    let dead = false,
      timer,
      tries = 0;
    const force0 = refresh !== seen.current; // Refresh button pressed
    seen.current = refresh;
    const get = (kind, force) =>
      cached(`${PROFILE_ENDPOINT}?sensor=${sensorId}&weekday=${weekday}&kind=${kind}&days=730`, {
        date: "2000-01-01",
        maxAge: 3600 * 1000,
        force,
      }).then(
        (e) => e.body,
        (err) => {
          if (err.status === 404) return null; // e.g. no class days on a Saturday
          throw err;
        },
      );
    const load = async (force) => {
      try {
        const [a, b] = await Promise.all([get("class", force), get("non_class", force)]);
        if (dead) return;
        const partial = !!(a?.partial || b?.partial);
        setState({ days: [...(a?.days ?? []), ...(b?.days ?? [])], partial });
        // The backend fills in missing days a little at a time; ask again until it is done
        if (partial && tries++ < 6) timer = setTimeout(() => load(true), 4000);
      } catch (error) {
        if (!dead) setState({ error });
      }
    };
    setState({ loading: true });
    load(force0);
    return () => {
      dead = true;
      clearTimeout(timer);
    };
  }, [sensorId, weekday, refresh]);

  // Period filter options come from the days that actually have data
  const days = state.days ?? [];
  const years = [...new Set(days.map((d) => d.date.slice(0, 4)))].sort();
  const sems = [...new Set(days.map((d) => d.semester).filter(Boolean))];
  const periods = [
    { value: "all", label: "All available days" },
    ...years.map((y) => ({ value: `y:${y}`, label: `Year ${y}` })),
    ...sems.map((s) => ({ value: `s:${s}`, label: s })),
  ];
  const active = periods.some((p) => p.value === period) ? period : "all";
  const shown = days.filter(
    (d) =>
      active === "all" ||
      (active.startsWith("y:")
        ? d.date.startsWith(active.slice(2))
        : d.semester === active.slice(2)),
  );

  const hours = Array.from({ length: to - from + 1 }, (_, i) => from + i);
  const layers = GROUPS.map((g) => {
    const gd = shown.filter((d) => groupOf(d) === g.key);
    return {
      ...g,
      days: gd,
      st: hours.map((h) => statsAt(gd, h)),
      visible: on[g.key] && gd.length > 0,
    };
  });
  const vis = layers.filter((l) => l.visible);
  const line = overlay && weekday === mondayIndex(date) ? hours.map((h) => overlay[h]) : null;
  const hasChart = !state.loading && !state.error && vis.length > 0;

  useEffect(() => {
    if (!hasChart || !box.current) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, e.contentRect.width)));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, [hasChart]);

  // Chart geometry
  const H = 300,
    m = { l: 38, r: 10, t: 10, b: 26 };
  const iw = w - m.l - m.r,
    ih = H - m.t - m.b,
    n = hours.length;
  const peak = Math.max(
    1,
    ...vis.flatMap((l) => l.st.map((s) => s.max)),
    ...(line ?? []).map((v) => v ?? 0),
  );
  const max = niceMax(peak);
  const x = (i) => m.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
  const y = (v) => m.t + ih - (v / max) * ih;
  const step = Math.ceil(n / (w < 480 ? 5 : 10));

  // Each group's lines share the opacity budget of that group, so a spot crossed by many
  // days builds up to a dark color while a spot crossed by one day stays pale.
  const opFor = (count) => Math.min(0.6, Math.max(0.03, contrast / Math.max(1, count)));

  const pick = (e) => {
    const r = box.current.getBoundingClientRect();
    const i = Math.round(((e.clientX - r.left - m.l) / iw) * (n - 1));
    setHov(Math.min(n - 1, Math.max(0, i || 0)));
  };
  const hx = hov != null ? x(hov) : null;
  const dates = shown.map((d) => d.date).sort();

  let body;
  if (state.error) {
    body = <p className="err">Could not load data: {state.error.message}</p>;
  } else if (state.loading) {
    body = <p className="muted">Loading…</p>;
  } else if (!days.length) {
    body = (
      <p className="muted">
        {state.partial ? "Still collecting days…" : `No stored days found for ${DAYS[weekday]}s.`}
      </p>
    );
  } else if (!vis.length) {
    body = <p className="muted">Turn on at least one day type that has days in this period.</p>;
  } else {
    body = (
      <>
        <p className="muted" style={{ margin: "0 0 6px" }}>
          Showing {layers.map((l) => `${l.days.length} ${l.label.toLowerCase()}`).join(", ")} (
          {dl(dates[0])} to {dl(dates[dates.length - 1])}).
          {state.partial && " Still loading more days…"}
        </p>
        <div ref={box} className="chartbox">
          <svg
            viewBox={`0 0 ${w} ${H}`}
            height={H}
            onPointerMove={pick}
            onPointerDown={pick}
            onPointerLeave={(e) => e.pointerType === "mouse" && setHov(null)}
            role="img"
            aria-label={`Average devices per 5 minutes on ${DAYS[weekday]}s by day type`}
          >
            {[0, 0.25, 0.5, 0.75, 1].map((t) => (
              <g key={t}>
                <line x1={m.l} x2={w - m.r} y1={y(max * t)} y2={y(max * t)} stroke="var(--line)" />
                <text className="axis" x={m.l - 6} y={y(max * t) + 4} textAnchor="end">
                  {Math.round(max * t)}
                </text>
              </g>
            ))}

            {/* one faint line per past day, per group */}
            {vis.map((l) =>
              l.days.map((d) => (
                <path
                  key={`${l.key}-${d.date}`}
                  d={toPath(
                    hours.map((h) => d.values[h]),
                    x,
                    y,
                  )}
                  fill="none"
                  stroke={l.color}
                  strokeOpacity={opFor(l.days.length)}
                  strokeWidth="2.5"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              )),
            )}

            {/* quietest and busiest day at each hour */}
            {showRange &&
              vis.map((l) =>
                ["min", "max"].map((k) => (
                  <path
                    key={`${l.key}-${k}`}
                    d={toPath(
                      l.st.map((s) => s[k]),
                      x,
                      y,
                    )}
                    fill="none"
                    stroke={l.color}
                    strokeDasharray="4 3"
                    strokeWidth="1.5"
                    opacity=".75"
                  />
                )),
              )}

            {/* median day */}
            {vis.map((l) => (
              <path
                key={`${l.key}-median`}
                d={toPath(
                  l.st.map((s) => s.median),
                  x,
                  y,
                )}
                fill="none"
                stroke={l.color}
                strokeWidth="3"
                strokeLinejoin="round"
              />
            ))}

            {line && (
              <path
                d={toPath(line, x, y)}
                fill="none"
                stroke="var(--main)"
                strokeWidth="3"
                strokeLinejoin="round"
              />
            )}
            {hours.map(
              (h, i) =>
                i % step === 0 && (
                  <text key={h} className="axis" x={x(i)} y={H - 8} textAnchor="middle">
                    {hl(h)}
                  </text>
                ),
            )}
            {hx != null && (
              <line
                x1={hx}
                x2={hx}
                y1={m.t}
                y2={m.t + ih}
                stroke="var(--mute)"
                strokeDasharray="3 3"
              />
            )}
          </svg>

          {hov != null && (
            <div
              className="tip"
              style={{
                left: hx,
                maxWidth: 280,
                transform: hx > w * 0.55 ? "translateX(calc(-100% - 12px))" : "translateX(12px)",
              }}
            >
              <b>
                {hl(hours[hov])} to {hl(hours[hov] + 1)}
              </b>
              {vis.map((l) => {
                const s = l.st[hov];
                return (
                  <div key={l.key} style={{ marginTop: 4 }}>
                    <i className="dot" style={{ background: l.color }} />
                    {l.label}: median {fmt(s.median)}, range {fmt(s.min)} to {fmt(s.max)}
                    <div className="muted">
                      busiest {dl(s.maxDate)}, quietest {dl(s.minDate)} ({s.n} days)
                    </div>
                  </div>
                );
              })}
              {line && line[hov] != null && (
                <div style={{ marginTop: 4 }}>Selected day: {fmt(line[hov])}</div>
              )}
            </div>
          )}
        </div>

        <div className="legend">
          {vis.map((l) => (
            <span key={l.key}>
              <i className="sw" style={{ borderTopColor: l.color }} />
              {l.label}
            </span>
          ))}
          <span>Darker color means more days overlap there</span>
          <span>Solid line is the median day{showRange && ", dashed lines the quietest and busiest"}</span>
          {line && (
            <span>
              <i className="sw" />
              Selected day ({dl(date)})
            </span>
          )}
        </div>
      </>
    );
  }

  return (
    <div className="card" style={{ marginTop: 16 }}>
      <h2>Weekday patterns</h2>
      <p className="muted" style={{ margin: "2px 0 0" }}>
        Every past {DAYS[weekday]} on top of each other, average devices per 5 minutes by hour.
        No-class days include holidays, breaks and weekends.
      </p>

      <div className="pcontrols">
        <label>
          Weekday
          <select value={weekday} onChange={(e) => setWeekday(+e.target.value)}>
            {DAYS.map((d, i) => (
              <option key={d} value={i}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label>
          Period
          <select value={active} onChange={(e) => setPeriod(e.target.value)}>
            {periods.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Contrast
          <input
            type="range"
            min="0.5"
            max="4"
            step="0.5"
            value={contrast}
            onChange={(e) => setContrast(+e.target.value)}
            style={{ padding: 0 }}
          />
        </label>
        <label style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <input
            type="checkbox"
            checked={showRange}
            onChange={(e) => setShowRange(e.target.checked)}
            style={{ padding: 0 }}
          />
          Show quietest and busiest lines
        </label>
      </div>

      <div className="chips" aria-label="Day types to show" style={{ marginBottom: 10 }}>
        {layers.map((l) => (
          <button
            key={l.key}
            className={`chip ${l.visible ? "on" : ""}`}
            style={{ "--c": l.color }}
            disabled={!l.days.length}
            onClick={() => setOn({ ...on, [l.key]: !on[l.key] })}
            title={l.days.length ? "" : "No days of this type in this period"}
          >
            {l.label} ({l.days.length})
          </button>
        ))}
      </div>

      {body}
    </div>
  );
}