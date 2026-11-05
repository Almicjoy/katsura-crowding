import { useEffect, useRef, useState } from "react";
import { cached, dl, hl, fmt, niceMax, toPath } from "./lib.js";

const ENDPOINT = "/api/weather_crowding";

// Colors avoid blue except for rain, because blue means rain across the app
const METRICS = {
  temp: {
    label: "Temperature", unit: "°C", step: 0.5,
    hi: "#d9485f", lo: "#6a4fbf",
    hiName: "Warmer", loName: "Cooler", hiPhrase: "warmer hours", loPhrase: "cooler hours",
  },
  rain: {
    label: "Rain", unit: "mm/h", step: 0.1,
    hi: "var(--rain)", lo: "#d9a521",
    hiName: "Raining", loName: "Dry", hiPhrase: "rainy hours", loPhrase: "dry hours",
  },
};

const quantile = (sorted, q) => {
  const pos = (sorted.length - 1) * q;
  const a = Math.floor(pos), b = Math.ceil(pos);
  return sorted[a] + (sorted[b] - sorted[a]) * (pos - a);
};

function summarize(values, mode) {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b);
  const wide = mode === "wide"; // middle 80% instead of the full range
  return {
    n: s.length,
    low: wide ? quantile(s, 0.1) : s[0],
    high: wide ? quantile(s, 0.9) : s[s.length - 1],
    median: quantile(s, 0.5),
  };
}

/**
 * For every hour of the day, split the days' crowding values into the group whose weather at
 * that hour is at or above the threshold and the group below it. A single day can land in both
 * groups (warm at 2 PM, cool at 8 AM), because each hour is classified on its own.
 */
export function groupStats(days, hours, key, threshold, mode) {
  const hi = hours.map(() => []);
  const lo = hours.map(() => []);
  days.forEach((d) =>
    hours.forEach((h, i) => {
      const crowd = d.crowd?.[h];
      const v = d[key]?.[h];
      if (crowd == null || v == null) return;
      (v >= threshold ? hi : lo)[i].push(crowd);
    }),
  );
  return { hi: hi.map((a) => summarize(a, mode)), lo: lo.map((a) => summarize(a, mode)) };
}

// Shaded area between each hour's low and high value, drawn in separate runs
function bandPath(stats, x, y) {
  let d = "";
  let run = [];
  const flush = () => {
    if (run.length > 1) {
      const top = run.map((i) => `${x(i).toFixed(1)},${y(stats[i].high).toFixed(1)}`);
      const bottom = run.map((i) => `${x(i).toFixed(1)},${y(stats[i].low).toFixed(1)}`).reverse();
      d += `M${top.join("L")}L${bottom.join("L")}Z`;
    }
    run = [];
  };
  stats.forEach((s, i) => (s && s.n >= 2 ? run.push(i) : flush()));
  flush();
  return d;
}

export function WeatherChart({ hours, stats, hiColor, loColor, hiLabel, loLabel, rangeLabel }) {
  const box = useRef(null);
  const [w, setW] = useState(640);
  const [hov, setHov] = useState(null);
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, e.contentRect.width)));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);

  const n = hours.length;
  const H = 300,
    m = { l: 38, r: 10, t: 10, b: 26 };
  const iw = w - m.l - m.r,
    ih = H - m.t - m.b;
  const max = niceMax(Math.max(1, ...[...stats.hi, ...stats.lo].map((s) => s?.high ?? 0)));
  const x = (i) => m.l + ((i + 0.5) / n) * iw; // middle of the hour
  const y = (v) => m.t + ih - (v / max) * ih;
  const step = Math.ceil(n / (w < 480 ? 5 : 10));
  const pick = (e) => {
    const r = box.current.getBoundingClientRect();
    const i = Math.floor(((e.clientX - r.left - m.l) / iw) * n);
    setHov(Math.min(n - 1, Math.max(0, i)));
  };

  const layers = [
    { key: "lo", color: loColor, label: loLabel, st: stats.lo },
    { key: "hi", color: hiColor, label: hiLabel, st: stats.hi },
  ];

  return (
    <div>
      <div ref={box} className="chartbox">
        <svg
          viewBox={`0 0 ${w} ${H}`}
          height={H}
          onPointerMove={pick}
          onPointerDown={pick}
          onPointerLeave={(e) => e.pointerType === "mouse" && setHov(null)}
          role="img"
          aria-label="Crowding range by hour, split by weather"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line x1={m.l} x2={w - m.r} y1={y(max * t)} y2={y(max * t)} stroke="var(--line)" />
              <text className="axis" x={m.l - 6} y={y(max * t) + 4} textAnchor="end">
                {Math.round(max * t)}
              </text>
            </g>
          ))}
          {hov != null && (
            <rect x={m.l + (hov / n) * iw} y={m.t} width={iw / n} height={ih} fill="var(--mute)" opacity=".08" />
          )}

          {layers.map((l) => (
            <path key={`${l.key}-band`} d={bandPath(l.st, x, y)} fill={l.color} opacity=".25" />
          ))}
          {layers.map((l) => (
            <g key={`${l.key}-median`}>
              <path
                d={toPath(l.st.map((s) => s?.median ?? null), x, y)}
                fill="none"
                stroke={l.color}
                strokeWidth="3"
                strokeLinejoin="round"
              />
              {l.st.map(
                (s, i) => s && <circle key={i} cx={x(i)} cy={y(s.median)} r="3" fill={l.color} />,
              )}
            </g>
          ))}

          {hours.map(
            (h, i) =>
              i % step === 0 && (
                <text key={h} className="axis" x={m.l + (i / n) * iw} y={H - 8} textAnchor="middle">
                  {hl(h)}
                </text>
              ),
          )}
        </svg>

        {hov != null && (
          <div
            className="tip"
            style={{
              left: x(hov),
              maxWidth: 280,
              transform: x(hov) > w * 0.55 ? "translateX(calc(-100% - 12px))" : "translateX(12px)",
            }}
          >
            <b>
              {hl(hours[hov])} to {hl(hours[hov] + 1)}
            </b>
            {[...layers].reverse().map((l) => {
              const s = l.st[hov];
              return (
                <div key={l.key} style={{ marginTop: 4 }}>
                  <i className="dot" style={{ background: l.color }} />
                  {l.label}:{" "}
                  {s
                    ? `median ${fmt(s.median)}, range ${fmt(s.low)} to ${fmt(s.high)} (${s.n} day${s.n === 1 ? "" : "s"})`
                    : "no days"}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="legend">
        {[...layers].reverse().map((l) => (
          <span key={l.key}>
            <i className="sw" style={{ borderTopColor: l.color }} />
            {l.label}
          </span>
        ))}
        <span>Solid line is the median, shaded area is the {rangeLabel}</span>
      </div>
    </div>
  );
}

export default function WeatherCrowding({ sensorId, from, to, refresh, onRefresh }) {
  const [semester, setSemester] = useState(""); // "" means the current semester
  const [semesters, setSemesters] = useState([]);
  const [dayType, setDayType] = useState("class");
  const [metric, setMetric] = useState("temp");
  const [thr, setThr] = useState({ temp: null, rain: null }); // null = the default for this data
  const [mode, setMode] = useState("full");
  const [state, setState] = useState({ loading: true });
  const seen = useRef(refresh);

  useEffect(() => {
    let dead = false,
      timer,
      tries = 0;
    const force0 = refresh !== seen.current; // Refresh button pressed
    seen.current = refresh;
    const load = async (force) => {
      try {
        const url = `${ENDPOINT}?sensor=${sensorId}${semester ? `&semester=${encodeURIComponent(semester)}` : ""}`;
        const e = await cached(url, { date: "2000-01-01", maxAge: 3600 * 1000, force });
        if (dead) return;
        setState({ data: e.body });
        setSemesters(e.body.semesters ?? []);
        // The backend fills in missing days a little at a time; ask again until it is done
        if (e.body.partial && tries++ < 6) timer = setTimeout(() => load(true), 4000);
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
  }, [sensorId, semester, refresh]);

  const data = state.data;
  const M = METRICS[metric];
  const selected = semester || semesters.find((s) => s.current)?.name || "";
  const hours = Array.from({ length: to - from + 1 }, (_, i) => from + i);
  const days = (data?.days ?? []).filter(
    (d) => dayType === "all" || (dayType === "class") === d.is_class_day,
  );

  // Slider range and default come from the weather values actually in view
  const values = days.flatMap((d) => hours.map((h) => d[metric]?.[h])).filter((v) => v != null).sort((a, b) => a - b);
  const sliderMin = metric === "temp" ? Math.floor(values[0] ?? 0) : 0.1;
  const sliderMax = metric === "temp" ? Math.ceil(values[values.length - 1] ?? 30) : Math.max(1, Math.ceil(values[values.length - 1] ?? 1));
  const defaultThr = metric === "temp" ? (values.length ? Math.round(quantile(values, 0.5) * 2) / 2 : 15) : 0.1;
  const t = Math.min(sliderMax, Math.max(sliderMin, thr[metric] ?? defaultThr));

  const stats = groupStats(days, hours, metric, t, mode);
  const count = (list) => list.reduce((s, x) => s + (x?.n ?? 0), 0);
  const nHi = count(stats.hi), nLo = count(stats.lo);

  // Difference between the two groups' medians, hour by hour, then averaged
  const diffs = hours
    .map((_, i) => {
      const a = stats.hi[i], b = stats.lo[i];
      return a && b && a.n >= 3 && b.n >= 3 && b.median > 0 ? (a.median - b.median) / b.median : null;
    })
    .filter((v) => v != null);
  const avgDiff = diffs.length ? Math.round((diffs.reduce((s, v) => s + v, 0) / diffs.length) * 100) : null;

  const op = metric === "temp" ? ["≥", "<"] : ["≥", "<"];
  const hiLabel = `${M.hiName} (${op[0]} ${t.toFixed(1)} ${M.unit})`;
  const loLabel = `${M.loName} (${op[1]} ${t.toFixed(1)} ${M.unit})`;

  let body;
  if (state.error) {
    body = <p className="err">{state.error.status === 404 ? state.error.message : `Could not load data: ${state.error.message}`}</p>;
  } else if (state.loading) {
    body = <p className="muted">Loading…</p>;
  } else if (!days.length) {
    body = <p className="muted">{data?.partial ? "Still collecting days…" : "No days of this type with data in this semester."}</p>;
  } else if (!nHi && !nLo) {
    body = <p className="muted">No weather data for these days. {data?.weather_error ? `(${data.weather_error})` : ""}</p>;
  } else {
    body = (
      <>
        <p className="muted" style={{ margin: "0 0 6px" }}>
          {days.length} {dayType === "class" ? "class" : dayType === "off" ? "no-class" : ""} days
          ({dl(data.range.start)} to {dl(data.range.end)}). Each hour of each day is placed in the
          group its own weather falls in, so one day can appear in both.
          {data.partial && " Still loading more days…"}
        </p>
        <WeatherChart
          hours={hours}
          stats={stats}
          hiColor={M.hi}
          loColor={M.lo}
          hiLabel={hiLabel}
          loLabel={loLabel}
          rangeLabel={mode === "wide" ? "middle 80% of days" : "quietest to busiest day"}
        />
        <p style={{ margin: "10px 0 0" }}>
          {avgDiff == null
            ? "Not enough days in both groups to compare yet. Try moving the threshold."
            : `At the same time of day, ${M.hiPhrase} were ${Math.abs(avgDiff)}% ${avgDiff >= 0 ? "busier" : "quieter"} than ${M.loPhrase} (median, averaged over ${diffs.length} hours that have at least 3 days in each group).`}
        </p>
        <p className="muted" style={{ margin: "4px 0 0" }}>
          {nHi} {M.hiPhrase} and {nLo} {M.loPhrase} in view. Weather is modeled data (Open-Meteo).
          Compare within one semester, since season and weather move together.
        </p>
      </>
    );
  }

  return (
    <div>
      <div className="bar">
        <h2>Weather and crowding</h2>
        {onRefresh && (
          <button className="btn" onClick={onRefresh}>
            Refresh data
          </button>
        )}
      </div>
      <p className="muted" style={{ margin: "2px 0 0" }}>
        How the crowding range changes when the weather at that hour is above or below your threshold.
      </p>

      <div className="pcontrols">
        <label>
          Semester
          <select value={selected} onChange={(e) => setSemester(e.target.value)} disabled={!semesters.length}>
            {!semesters.length && <option value="">Loading…</option>}
            {semesters.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
                {s.current ? " (current)" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          Days
          <select value={dayType} onChange={(e) => setDayType(e.target.value)}>
            <option value="class">Class days</option>
            <option value="off">No-class days</option>
            <option value="all">All days</option>
          </select>
        </label>
        <label>
          Range shown
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="full">Quietest to busiest</option>
            <option value="wide">Middle 80%</option>
          </select>
        </label>
      </div>

      <div className="wc-row">
        <div className="seg" role="group" aria-label="Weather measure">
          {Object.entries(METRICS).map(([key, v]) => (
            <button key={key} className={metric === key ? "on" : ""} onClick={() => setMetric(key)}>
              {v.label}
            </button>
          ))}
        </div>
        <label className="wc-thr">
          {M.label} threshold:{" "}
          <b>
            {t.toFixed(1)} {M.unit}
          </b>
          <input
            type="range"
            min={sliderMin}
            max={sliderMax}
            step={M.step}
            value={t}
            onChange={(e) => setThr({ ...thr, [metric]: +e.target.value })}
          />
        </label>
        <button className="btn" onClick={() => setThr({ ...thr, [metric]: null })}>
          Reset
        </button>
      </div>

      {body}
    </div>
  );
}