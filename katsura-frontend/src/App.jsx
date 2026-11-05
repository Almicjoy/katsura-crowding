import { useEffect, useRef, useState } from "react";
import { CAMPUS, SENSORS } from "./config.js";

import WeekdayProfile from "./WeekdayProfile.jsx";
import LiveMap from "./LiveMap.jsx";
import DayChart from "./DayChart.jsx";
import Survey from "./Survey.jsx";
import WeatherCrowding from "./WeatherCrowding.jsx";
import Dashboard from "./Dashboard.jsx";

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

function useDay(sensor, date, dayRefresh) {
  const [s, set] = useState({ loading: true, comps: [] });
  const seen = useRef(dayRefresh);
  useEffect(() => {
    let dead = false;
    const force = dayRefresh !== seen.current; // true only when the Refresh button was pressed
    seen.current = dayRefresh;
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
        info.equivalents.forEach((e) =>
          add(
            e,
            `${e.semester}${
              e.session != null &&
              e.session !== "null" &&
              e.weekday
                ? `, ${ordinal(e.session)} ${e.weekday}`
                : ""
            }`
          )
        );
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
  }, [sensor, date, dayRefresh]);
  return s;
}

function ordinal(n) {
  const num = Number(n);
  if (num % 100 >= 11 && num % 100 <= 13) return `${num}th`;

  switch (num % 10) {
    case 1: return `${num}st`;
    case 2: return `${num}nd`;
    case 3: return `${num}rd`;
    default: return `${num}th`;
  }
}


export default function App() {
  const [sensorId, setSensorId] = useState("AMPM18-KJ016");
  const [date, setDate] = useState(today());
  const [from, setFrom] = useState(6);
  const [to, setTo] = useState(22);
  const [selHour, setSelHour] = useState(null);
  const [shown, setShown] = useState({});
  const [dayRefresh, setDayRefresh] = useState(0);
  const [weekdayRefresh, setWeekdayRefresh] = useState(0);
  const [mapRefresh, setMapRefresh] = useState(0);
  const [aggregation, setAggregation] = useState(5);
  const [comparisonDate, setComparisonDate] = useState("");
  const [comparisonData, setComparisonData] = useState(null);
  const [customDate, setCustomDate] = useState("");
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [comparisonError, setComparisonError] = useState("");
  const sensor = SENSORS.find((s) => s.id === sensorId);
  const {
    data,
    info,
    comps = [],
    updated,
    error,
    loading,
    refreshing,
  } = useDay(sensorId, date, dayRefresh);

  useEffect(() => {
    let cancelled = false;

    setComparisonData(null);
    setComparisonError("");

    if (!comparisonDate || comparisonDate === date) {
      setComparisonLoading(false);
      return;
    }

    setComparisonLoading(true);

    cached(dayUrl(sensorId, comparisonDate), {
      date: comparisonDate,
      maxAge: null,
    })
      .then(({ body }) => {
        if (!cancelled) {
          setComparisonData(body);
          setComparisonLoading(false);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setComparisonData(null);
          setComparisonError(
            error.status === 404
              ? "No data is available for the selected comparison date."
              : `Could not load comparison data: ${error.message}`
          );
          setComparisonLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sensorId, date, comparisonDate]);

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
      .map((c, i) => isOn(c, i) && {
        key: c.date,
        color: c.color,
        values: pick(c.data),
      })
      .filter(Boolean),

    ...(comparisonData && comparisonDate !== date
      ? [{
          key: "user-comparison",
          color: "#16a085",
          values: pick(comparisonData),
        }]
      : []),

    {
      key: "main",
      main: true,
      color: "var(--main)",
      values: mainVals,
      partial: range.map((h) =>
        data?.hours?.[h]?.average_5min != null &&
        !data.hours[h].complete
      ),
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
        {comparisonData && comparisonDate !== date && (
          <div>
            <i
              className="dot"
              style={{
                background: "#16a085",
              }}
            />
            {dl(comparisonDate)}:{" "}
            {fmt(aggregateHour(comparisonData?.hours?.[h], aggregation))}
            {" "}devices
          </div>
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
            ? `Semester ${info.semester}${
                info.session != null &&
                info.session !== "null" &&
                info.weekday
                  ? `, ${ordinal(info.session)} ${info.weekday}`
                  : ""
              }`
            : "Outside the academic calendar"
          : "Loading…"}
          {info?.detail && (
            <div className="page-subheader">
              <p className="sub">{info.detail}</p>
            </div>
          )}
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
      <Dashboard
        dayChart={
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
                    {daily.events?.length
                      ? daily.events.join(", ")
                      : (daily.summary ?? "–")}
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

                <button
                  className="btn"
                  onClick={() => setDayRefresh(prev => prev + 1)}
                  disabled={busy}
                >
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
              <DayChart
                key={`${sensorId}-${date}`}
                date={date}
                data={data}
                comps={comps.filter((c, i) => isOn(c, i))}
                range={range}
                aggregation={aggregation}
              >
                {/* Custom comparison date controls */}
                <div className="custom-compare">
                  <label>
                    Compare with another day

                    <input
                      type="date"
                      value={customDate}
                      max={today()}
                      onChange={(e) => {
                        const selectedDate = e.target.value;
                        setCustomDate(selectedDate);
                        setComparisonDate(selectedDate);
                      }}
                    />
                  </label>

                  {customDate && (
                    <button
                      className="btn"
                      onClick={() => {
                        setCustomDate("");
                        setComparisonDate("");
                        setComparisonData(null);
                        setComparisonError("");
                      }}
                    >
                      Clear
                    </button>
                  )}
                </div>

                {/* Automatically suggested comparison days */}
                <div className="chips" aria-label="Comparison days">
                  {comps.map((c, i) => (
                    <button
                      key={c.date}
                      className={`chip ${isOn(c, i) ? "on" : ""}`}
                      style={{ "--c": c.color }}
                      disabled={!c.data}
                      onClick={() =>
                        setShown({
                          ...shown,
                          [c.date]: !isOn(c, i),
                        })
                      }
                      title={c.data ? "" : "No data for this day"}
                    >
                      {dl(c.date)}, {c.label}
                      {c.kind && `, ${c.kind}`}
                      {wd(c.date) !== wd(date) && ", different weekday"}
                      {c.pending
                        ? " (loading…)"
                        : !c.data
                          ? " (no data)"
                          : ""}
                    </button>
                  ))}

                  {info === undefined && (
                    <span className="muted">
                      Finding comparison days…
                    </span>
                  )}
                </div>

                {/* Custom comparison loading/error messages */}
                {comparisonLoading && (
                  <p className="muted">
                    Loading comparison data…
                  </p>
                )}

                {comparisonError && (
                  <p className="err">
                    {comparisonError}
                  </p>
                )}
              </DayChart>
            )}
          </div>
        }

        liveMap={
          <LiveMap
            sensorId={sensorId}
            date={date}
            from={lo}
            to={hi}
            refresh={mapRefresh}
          />
        }

        weekdayProfile={
          <WeekdayProfile
            sensorId={sensorId}
            date={date}
            isClassDay={info?.is_class_day}
            from={lo}
            to={hi}
            refresh={weekdayRefresh}
            onRefresh={() => setWeekdayRefresh(prev => prev + 1)}
            overlay={Array.from({ length: 24 }, (_, h) =>
              aggregateHour(data?.hours?.[h], aggregation)
            )}
          />
        }
        weatherCrowding={
          <WeatherCrowding
            sensorId={sensorId}
            from={lo}
            to={hi}
          />
}
      />

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
