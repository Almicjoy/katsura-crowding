import { useEffect, useRef, useState } from "react";
import { CAMPUS, SENSORS } from "./config.js";

import WeekdayProfile from "./WeekdayProfile.jsx";
import LiveMap from "./Livemap.jsx";
import Survey from "./Survey.jsx";

import {
  COLORS,
  today,
  dl,
  wd,
  hl,
  tl,
  fmt,
  niceMax,
  toPath,
  dayKind,
  dayUrl,
  cached,
  TODAY_MAX_AGE_MS,
  INFO_MAX_AGE_MS,
  aggregateSlots,
  aggregateHour,
} from "./lib.js";

function useDay(sensor, date, refresh) {
  const [s, set] = useState({ loading: true, comps: [] });
  const seen = useRef(refresh);
  useEffect(() => {
    let dead = false;
    const force = refresh !== seen.current; // true only when the Refresh button was pressed
    seen.current = refresh;
    const patch = (fn) => !dead && set(fn);
    const ageFor = (d) => (d === today() ? TODAY_MAX_AGE_MS : null);

    set((p) => (force ? { ...p, refreshing: true } : { loading: true, comps: [] }));

    cached(dayUrl(sensor, date), { date, maxAge: ageFor(date), force }).then(
      (e) =>
        patch((p) => ({
          ...p,
          data: e.body,
          updated: e.t,
          loading: false,
          refreshing: false,
          error: undefined,
        })),
      (error) => patch((p) => ({ ...p, error, loading: false, refreshing: false })),
    );

    const fill = (d, data) =>
      patch((p) => ({
        ...p,
        comps: p.comps.map((c) => (c.date === d ? { ...c, data, pending: false } : c)),
      }));

    cached(`/api/day_info?date=${date}`, { date, maxAge: INFO_MAX_AGE_MS, force })
      .then(({ body: info }) => {
        const cands = [];
        const add = (e, label) => {
          if (e.date !== date && e.date <= today() && !cands.some((c) => c.date === e.date))
            cands.push({ date: e.date, label, kind: dayKind(e) });
        };
        info.equivalents.forEach((e) => add(e, `${e.semester}, week ${e.week}`));
        add(info.last_year.same_weekday, "Last year, same weekday");
        add(info.last_year.same_date, "Last year, same date");
        const list = cands.slice(0, 5).map((c, i) => ({ ...c, color: COLORS[i % COLORS.length] }));
        patch((p) => ({
          ...p,
          info,
          comps: list.map((c) => ({
            ...c,
            data: force ? p.comps.find((o) => o.date === c.date)?.data : undefined,
            pending: true,
          })),
        }));
        list.forEach((c) =>
          cached(dayUrl(sensor, c.date), { date: c.date, maxAge: ageFor(c.date), force }).then(
            (e) => fill(c.date, e.body),
            () => fill(c.date, null),
          ),
        );
      })
      .catch(() => patch((p) => ({ ...p, info: null })));

    return () => {
      dead = true;
    };
  }, [sensor, date, refresh]);
  return s;
}

function Chart({ range, series, rain, sel, onSel, empty, tip, mainLabel }) {
  const box = useRef(null);
  const [w, setW] = useState(640);
  const [hov, setHov] = useState(null);
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, e.contentRect.width)));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);
  const H = 300,
    m = { l: 38, r: 10, t: 10, b: 26 };
  const iw = w - m.l - m.r,
    ih = H - m.t - m.b,
    n = range.length;
  const max = niceMax(Math.max(1, ...series.flatMap((s) => s.values).filter((v) => v != null)));
  const x = (i) => m.l + (n === 1 ? iw / 2 : (i / (n - 1)) * iw);
  const y = (v) => m.t + ih - (v / max) * ih;
  const rainMax = Math.max(0, ...rain.filter((v) => v != null));
  const rmax = Math.max(2, rainMax);
  const step = Math.ceil(n / (w < 480 ? 5 : 10));
  const pick = (e) => {
    const r = box.current.getBoundingClientRect();
    const i = Math.round(((e.clientX - r.left - m.l) / iw) * (n - 1));
    const h = range[Math.min(n - 1, Math.max(0, i || 0))];
    onSel(h);
    setHov(h);
  };
  const si = sel - range[0];
  const hi = hov != null && range.includes(hov) ? x(hov - range[0]) : null;
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
          aria-label="Average devices per 5 minutes by hour"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line x1={m.l} x2={w - m.r} y1={y(max * t)} y2={y(max * t)} stroke="var(--line)" />
              <text className="axis" x={m.l - 6} y={y(max * t) + 4} textAnchor="end">
                {Math.round(max * t)}
              </text>
            </g>
          ))}
          {rain.map(
            (v, i) =>
              v > 0 && (
                <rect
                  key={i}
                  x={x(i) - Math.max(3, (iw / n) * 0.3)}
                  width={Math.max(6, (iw / n) * 0.6)}
                  y={m.t + ih - (v / rmax) * 50}
                  height={(v / rmax) * 50}
                  fill="var(--rain)"
                  opacity=".65"
                />
              ),
          )}
          {range.map(
            (h, i) =>
              i % step === 0 && (
                <text key={h} className="axis" x={x(i)} y={H - 8} textAnchor="middle">
                  {hl(h)}
                </text>
              ),
          )}
          {si >= 0 && si < n && (
            <line
              x1={x(si)}
              x2={x(si)}
              y1={m.t}
              y2={m.t + ih}
              stroke="var(--mute)"
              strokeDasharray="3 3"
            />
          )}
          {series.map((s) => (
            <g key={s.key}>
              <path
                d={toPath(s.values, x, y)}
                fill="none"
                stroke={s.color}
                strokeWidth={s.main ? 3 : 2}
                strokeDasharray={s.main ? undefined : "5 4"}
                strokeLinejoin="round"
              />
              {s.main &&
                s.values.map(
                  (v, i) =>
                    v != null && (
                      <circle
                        key={i}
                        cx={x(i)}
                        cy={y(v)}
                        r={s.partial[i] ? 4.5 : 3}
                        fill={s.partial[i] ? "var(--card)" : s.color}
                        stroke={s.color}
                        strokeWidth="2"
                      />
                    ),
                )}
            </g>
          ))}
          {empty && (
            <text x={w / 2} y={H / 2} textAnchor="middle" className="axis">
              No data yet for these hours
            </text>
          )}
        </svg>
        {hi != null && (
          <div
            className="tip"
            style={{
              left: hi,
              transform: hi > w * 0.55 ? "translateX(calc(-100% - 12px))" : "translateX(12px)",
            }}
          >
            {tip(hov)}
          </div>
        )}
      </div>
      <div className="legend">
        <span>
          <i className="sw" />
          {mainLabel}
        </span>
        <span>
          <i className="sw dash" />
          Comparison days (toggle below)
        </span>
        <span>
          <i className="sw rainbox" />
          Rain, mm per hour{rainMax > 0 ? ` (tallest bar ${rainMax.toFixed(1)} mm)` : " (none)"}
        </span>
        <span>
          <i className="sw hollow" />
          Hour still in progress
        </span>
      </div>
    </div>
  );
}

function Detail({ hour, date, day, comps, aggregation }) {
  const h = day?.hours?.[hour];
  const w = h?.weather;
  const rawSlots = h?.slot_counts ?? [];
  const slots = aggregateSlots(rawSlots, aggregation);
  const cols = { gridTemplateColumns: `repeat(${slots.length}, 1fr)` };
  const vals = slots.filter((v) => v != null);
  const average = aggregateHour(h, aggregation);
  const mx = Math.max(1, ...vals);
  return (
    <div className="card">
      <h2>
        {hl(hour)} to {hl(hour + 1)}
      </h2>
      <p className="muted" style={{ margin: "2px 0 0" }}>
        {dl(date, true)}
      </p>
      {average == null ? (
        <p className="muted">No data yet for this hour.</p>
      ) : (
        <>
          <div className="stats">
            <div>
              <b>{fmt(average)}</b>
              <span className="muted">avg devices per 5 minutes</span>
            </div>
            <div>
              <b>{Math.max(0, ...vals)}</b>
              <span className="muted">highest {aggregation}-minute block</span>
            </div>
          </div>
          {!h.complete && (
            <p className="muted">
              Hour in progress: {h.slots_final} finished 5-minute period(s) so far.
            </p>
          )}
          <div className="ticks" style={cols}>
            {slots.map((v, i) => (
              <span key={i}>{v ?? "–"}</span>
            ))}
          </div>
          <div className="bars" style={cols} aria-label={`Devices in each ${aggregation}-minute block`}>
            {slots.map((v, i) => (
              <div
                key={i}
                className={v == null ? "none" : ""}
                style={{ height: v == null ? 2 : `${(v / mx) * 100}%` }}
                title={`${tl(hour, i * aggregation)}: ${v ?? "no data"}`}
              />
            ))}
          </div>
          <div className={`slotlabels ${slots.length <= 6 ? "wide" : ""}`} style={cols}>
            {slots.map((v, i) => (
              <span key={i}>{tl(hour, i * aggregation)}</span>
            ))}
          </div>
          <p className="muted">
            Each bar is the average number of devices per 5 minutes across the{" "}
            {aggregation}-minute block starting at the time shown.
          </p>
        </>
      )}
      {comps.length > 0 && <h2 className="sec">Same hour on comparison days</h2>}
      {comps.map((c) => {
        const v = aggregateHour(c.data?.hours?.[hour], aggregation);
        const cur = average;
        const pct = cur != null && v > 0 ? Math.round(((cur - v) / v) * 100) : null;
        return (
          <div className="row" key={c.date}>
            <span>
              <i className="dot" style={{ background: c.color }} />
              {dl(c.date)}
              {wd(c.date) !== wd(date) && <em className="warn">different weekday</em>}
            </span>
            <span>
              {fmt(v)} devices{pct != null && ` (selected day ${pct >= 0 ? "+" : ""}${pct}%)`}
            </span>
          </div>
        );
      })}
      {w && (
        <>
          <h2 className="sec">Weather{w.forecast ? " (forecast)" : ""}</h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            {w.condition}, {fmt(w.temp_c, 1)} °C (feels like {fmt(w.feels_like_c)} °C),{" "}
            {fmt(w.precipitation_mm, 1)} mm rain, wind {fmt(w.wind_kmh)} km/h, humidity{" "}
            {fmt(w.humidity_pct)}%, cloud cover {fmt(w.cloud_cover_pct)}%
          </p>
        </>
      )}
    </div>
  );
}

export default function App() {
  const [sensorId, setSensorId] = useState("AMPM18-KJ016");
  const [date, setDate] = useState(today());
  const [from, setFrom] = useState(6);
  const [to, setTo] = useState(22);
  const [selHour, setSelHour] = useState(null);
  const [shown, setShown] = useState({});
  const [refresh, setRefresh] = useState(0);
  const [aggregation, setAggregation] = useState(5);
  const sensor = SENSORS.find((s) => s.id === sensorId);
  const {
    data,
    info,
    comps = [],
    updated,
    error,
    loading,
    refreshing,
  } = useDay(sensorId, date, refresh);
  const busy = loading || refreshing || comps.some((c) => c.pending);
  useEffect(() => setSelHour(null), [sensorId, date]);

  const lo = Math.min(from, to),
    hi = Math.max(from, to);
  const range = Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
  const pick = (d) =>
    range.map((h) => aggregateHour(d?.hours?.[h], aggregation));
  const isOn = (c, i) => c.data && (shown[c.date] ?? i < 2);
  const mainVals = pick(data);
  const last = [...range]
    .reverse()
    .find((h) => aggregateHour(data?.hours?.[h], aggregation) != null);
  const hour = range.includes(selHour) ? selHour : (last ?? lo);
  const series = [
    ...comps
      .map((c, i) => isOn(c, i) && { key: c.date, color: c.color, values: pick(c.data) })
      .filter(Boolean),
    {
      key: "main",
      main: true,
      color: "var(--main)",
      values: mainVals,
      partial: range.map((h) => data?.hours?.[h]?.average_5min != null && !data.hours[h].complete),
    },
  ];
  const rain = range.map((h) => data?.hours?.[h]?.weather?.precipitation_mm ?? null);
  const daily = data?.weather?.daily;
  const kind = dayKind(info);

  const tip = (h) => {
    const x = data?.hours?.[h];
    const wt = x?.weather;
    return (
      <>
        <b>
          {hl(h)} to {hl(h + 1)}
        </b>
        <div>
          <i className="dot" style={{ background: "var(--main)" }} />
          {wd(date)}, {dl(date).split(", ").slice(1).join(", ")}:{" "}
          {aggregateHour(x, aggregation) == null
              ? "no data yet"
              : `${fmt(aggregateHour(x, aggregation))} devices per ${aggregation} min`}
        </div>
        {comps.map(
          (c, i) =>
            isOn(c, i) && (
              <div key={c.date}>
                <i className="dot" style={{ background: c.color }} />
                {dl(c.date)}: {fmt(aggregateHour(c.data?.hours?.[h], aggregation))} devices
              </div>
            ),
        )}
        {wt && (
          <div className="muted">
            {wt.condition}, {fmt(wt.temp_c, 1)} °C
            {wt.precipitation_mm > 0 ? `, ${fmt(wt.precipitation_mm, 1)} mm rain` : ""}
          </div>
        )}
      </>
    );
  };

  return (
    <div className="wrap">
      <header className="site-header">
        <div className="header-brand">
          <img
            src="/kyodai-logo.svg"
            alt="Katsura campus crowding logo"
            className="header-logo"
          />
        </div>

        <div className="header-divider" aria-hidden="true" />

        <div className="header-content">
          <h1>Katsura Campus WiFi Times</h1>
        </div>
      </header>
      <div className="page-subheader">
        <Survey/>
      </div>

      <div className="page-subheader">
        <p className="date">{dl(date, true)}</p>

        <p className="sub">
          {kind && (
            <span className={`badge ${info?.is_class_day ? "yes" : ""}`}>
              {kind}
            </span>
          )}
          {info
            ? info.semester
              ? `${info.semester}${info.week ? `, week ${info.week}` : ""}`
              : "Outside the academic calendar"
            : "Loading…"}
        </p>
      </div>

      <div className="controls">
        <label className="wide">
          Sensor
          <select value={sensorId} onChange={(e) => setSensorId(e.target.value)}>
            {SENSORS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Aggregation
          <select
            value={aggregation}
            onChange={(e) => setAggregation(Number(e.target.value))}
          >
            <option value={5}>5 minutes</option>
            <option value={15}>15 minutes</option>
          </select>
        </label>
        <label className="wide">
          Date
          <input
            type="date"
            value={date}
            max={today()}
            onChange={(e) => e.target.value && setDate(e.target.value)}
          />
        </label>
        <div className="time-range">
          <label>
            From
            <select value={from} onChange={(e) => setFrom(+e.target.value)}>
              {Array.from({ length: 24 }, (_, h) => (
                <option key={h} value={h}>
                  {tl(h, 0)}
                </option>
              ))}
            </select>
          </label>

          <label>
            To
            <select value={to} onChange={(e) => setTo(+e.target.value)}>
              {Array.from({ length: 24 }, (_, h) => (
                <option key={h} value={h}>
                  {tl(h, 0)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="grid">
        <div>
          <div className="card">
            {daily && (
              <div className="stats">
                <div>
                  <b>
                    {fmt(daily.high_c)} / {fmt(daily.low_c)} °C
                  </b>
                  <span className="muted">daily high / low</span>
                </div>
                <div>
                  <b>{fmt(daily.precipitation_mm, 1)} mm</b>
                  <span className="muted">rain that day</span>
                </div>
                <div>
                  <b style={{ fontSize: 18 }}>
                    {daily.events?.length ? daily.events.join(", ") : (daily.summary ?? "–")}
                  </b>
                  <span className="muted">conditions</span>
                </div>
              </div>
            )}
            <div className="bar">
              <h2 className="sec">
                Average devices per {aggregation} minutes, by hour
              </h2>
              <div className="refresh">
                {updated && (
                  <span className="muted">
                    Updated{" "}
                    {new Date(updated).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </span>
                )}
                <button className="btn" onClick={() => setRefresh(refresh + 1)} disabled={busy}>
                  {busy ? "Loading…" : "Refresh data"}
                </button>
              </div>
            </div>
            {error ? (
              <p className="err">
                {error.status === 404
                  ? "No data is available for this date and sensor."
                  : `Could not load data: ${error.message}`}
              </p>
            ) : loading ? (
              <p className="muted">Loading…</p>
            ) : (
              <>
                <Chart
                  range={range}
                  series={series}
                  rain={rain}
                  sel={hour}
                  onSel={setSelHour}
                  empty={mainVals.every((v) => v == null)}
                  tip={tip}
                  mainLabel={`Selected day (${wd(date)}, ${dl(date).split(", ").slice(1).join(", ")})`}
                />
                <div className="chips" aria-label="Comparison days">
                  {comps.map((c, i) => (
                    <button
                      key={c.date}
                      className={`chip ${isOn(c, i) ? "on" : ""}`}
                      style={{ "--c": c.color }}
                      disabled={!c.data}
                      onClick={() => setShown({ ...shown, [c.date]: !isOn(c, i) })}
                      title={c.data ? "" : "No data for this day"}
                    >
                      {dl(c.date)}, {c.label}
                      {c.kind && `, ${c.kind}`}
                      {wd(c.date) !== wd(date) && ", different weekday"}
                      {c.pending ? " (loading…)" : !c.data && " (no data)"}
                    </button>
                  ))}
                  {info === undefined && <span className="muted">Finding comparison days…</span>}
                </div>
              </>
            )}
          </div>
          <WeekdayProfile
            sensorId={sensorId}
            date={date}
            isClassDay={info?.is_class_day}
            from={lo}
            to={hi}
            refresh={refresh}
            overlay={Array.from({ length: 24 }, (_, h) =>
              aggregateHour(data?.hours?.[h], aggregation)
            )}
          />

        </div>

        <div>
          <div>
            {!error && !loading && (
              <Detail
                hour={hour}
                date={date}
                day={data}
                comps={comps.filter((c, i) => isOn(c, i))}
                aggregation={aggregation}
              />

            )}
          </div>
            

          <div>
            <LiveMap 
              sensorId={sensorId} 
              date={date} 
              from={lo} 
              to={hi} 
              refresh={refresh} 
            />
          </div>
        </div>

      </div>

      <footer className="site-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <img
              src="/its-lab-logo.png"
              alt="ITS Lab, Kyoto University"
              className="footer-logo"
            />
          </div>

          <div className="footer-content">
            <p className="footer-description">
              Katsura Campus Crowding Research by ITS Lab, Kyoto University.
            </p>

            <div className="footer-meta">
              <span>© {new Date().getFullYear()} ITS Lab.</span>
              <a href="/acknowledgements">Acknowledgments</a>
            </div>
          </div>
        </div>
      </footer>


    </div>
  );
}
