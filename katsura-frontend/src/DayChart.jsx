import { useEffect, useRef, useState } from "react";
import { dl, wd, hl, tl, fmt, aggregateSlots, aggregateHour } from "./lib.js";

/**
 * 5- or 15-minute histogram for the selected day and historical comparison days,
 * plus the weather, rain and comparison details for the hovered / selected hour underneath.
 *
 * Props: date, data (the day's response), comps (the comparison days that are switched on),
 *        range (list of hours to show), aggregation (5 or 15), children (rendered under the legend)
 * Give it key={`${sensorId}-${date}`} so the selected hour resets when the day or sensor changes.
 */
export default function DayChart({
  date,
  data,
  comps = [],
  range = [],
  aggregation = 5,
  children,
}) {
  const box = useRef(null);
  const [w, setW] = useState(1);
  const [sel, setSel] = useState(null);
  const [hov, setHov] = useState(null);
  const [selectedSlot, setSelectedSlot] = useState(null);

  // Always work with a valid, non-empty list of hours.
  const hours = Array.isArray(range)
    ? [...new Set(range.filter(
        (h) => Number.isInteger(h) && h >= 0 && h < 24
      ))].sort((a, b) => a - b)
    : [];

  // Only allow the supported aggregation intervals.
  const interval = aggregation === 15 ? 15 : 5;

    useEffect(() => {
    if (!box.current || typeof ResizeObserver === "undefined") return;

    const ro = new ResizeObserver(([entry]) => {
        const width = Math.floor(entry.contentRect.width);
        setW((previous) => width > 0 && width !== previous ? width : previous);
    });

    ro.observe(box.current);

    return () => ro.disconnect();
    }, []);


  if (hours.length === 0) {
    return (
      <div>
        {children}
        <p className="muted">No hours selected. Please select a valid time range.</p>
      </div>
    );
  }

  const n = hours.length;
  const t0 = hours[0];
  const t1 = hours[n - 1] + 1;
  const slotH = interval / 60;

  const hourData = (h) => data?.hours?.[h];

  // Align every historical day to the same time slots as the selected day.
  const mainAvg = hours.map((h) => aggregateHour(hourData(h), interval));
  const rain = hours.map((h) => hourData(h)?.weather?.precipitation_mm ?? null);
  const bars = hours.flatMap((h) =>
    aggregateSlots(hourData(h)?.slot_counts ?? [], interval).map((v, j) => ({ h, j, v }))
  );
  const historical = comps.map((c) => ({
    ...c,
    slots: hours.flatMap((h) =>
      aggregateSlots(c.data?.hours?.[h]?.slot_counts ?? [], interval).map((v, j) => ({ h, j, v }))
    ),
  }));
  const slotValue = (day, h, j) =>
    aggregateSlots(day?.hours?.[h]?.slot_counts ?? [], interval)[j] ?? null;
  const historyAt = (h, j) => historical
    .map((c) => slotValue(c.data, h, j))
    .filter((v) => v != null && Number.isFinite(v));
  const referenceAt = (h, j) => {
    const values = historyAt(h, j);
    return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  };
  const positive = "#ffe0e4"; // near-white, soft red tint: above history
  const negative = "#dcecff"; // near-white, soft blue tint: below history
  const neutral = "#ffffff"; // white: equal or no historical reference
  const currentColor = (b) => {
    const ref = referenceAt(b.h, b.j);
    if (b.v == null || ref == null) return neutral;
    return b.v > ref ? positive : b.v < ref ? negative : neutral;
  };

  // Geometry: one time axis, so a bar sits exactly under the hour it belongs to
  const H = 300,
    m = { l: 38, r: 10, t: 10, b: 26 };
  const iw = Math.max(1, w - m.l - m.r),
    ih = H - m.t - m.b;
  const peak = Math.max(
    1,
    ...bars.map((b) => b.v ?? 0),
    ...mainAvg.map((v) => v ?? 0),
    ...historical.flatMap((c) => c.slots.map((b) => b.v ?? 0)),
  );
  // Keep the tallest observed bar close to the top, with 6% headroom.
  // Avoid niceMax(), which can round the axis far above the observed peak.
  const max = peak * 1.06;
  const X = (t) => m.l + ((t - t0) / (t1 - t0)) * iw;
  const Y = (v) => m.t + ih - (v / max) * ih;
  const xi = (i) => X(hours[i] + 0.5); // center of each hour for rain bars
  const barW = Math.max(0.6, (iw * slotH) / (t1 - t0) - 1);
  const rainMax = Math.max(0, ...rain.filter((v) => v != null));
  const rmax = Math.max(2, rainMax);
  const step = Math.ceil(n / (w < 480 ? 5 : 10));

  // Selected hour defaults to the latest hour that has data
  const last = [...hours].reverse().find((h) => aggregateHour(hourData(h), interval) != null);
  const hour = hours.includes(sel) ? sel : (last ?? t0);

  // The latest available slot is based on actual counts, not the wall clock.
  const latest = [...bars].reverse().find((b) => b.v != null && Number.isFinite(b.v)) ?? null;
  const sameSlot = (a, b) => a && b && a.h === b.h && a.slot === b.slot;
  const slotFromPointer = (e) => {
    if (!box.current) return null;
    const r = box.current.getBoundingClientRect();
    const px = (e.clientX - r.left) * (w / Math.max(1, r.width));
    const t = Math.min(t1 - 1e-6, Math.max(t0, t0 + ((px - m.l) / iw) * (t1 - t0)));
    const h = Math.floor(t);
    return { h, slot: Math.min(Math.floor(((t - h) * 60) / interval), 60 / interval - 1) };
  };
  const pick = (e) => setHov(slotFromPointer(e));
  const selectBar = (e) => {
    const next = slotFromPointer(e);
    if (!next) return;
    setSelectedSlot(next);
    setSel(next.h);
    setHov(next);
  };
  const activeSlot = hov ?? selectedSlot;
  const selectedValue = selectedSlot ? slotValue(data, selectedSlot.h, selectedSlot.slot) : null;

  const barOpacity = (b) =>
    hov && hov.h === b.h && hov.slot === b.j ? 1 : b.h === hour ? 0.92 : 0.78;

  // Tooltip while hovering
  let tip = null;
  if (activeSlot) {
    const hd = hourData(activeSlot.h);
    const block = slotValue(data, activeSlot.h, activeSlot.slot);
    const reference = referenceAt(activeSlot.h, activeSlot.slot);
    const wt = hd?.weather;
    tip = (
      <>
        <b>
          {hl(activeSlot.h)} to {hl(activeSlot.h + 1)}
        </b>
        <div>
          {tl(activeSlot.h, activeSlot.slot * interval)} block: {block == null ? "no data" : `${fmt(block)} devices`}
        </div>
        <div>
          <i className="dot" style={{ background: currentColor({ h: activeSlot.h, j: activeSlot.slot, v: block }) }} />
          Selected day: {block == null ? "no data" : `${fmt(block)} devices`}
        </div>
        {comps.map((c) => {
          const v = slotValue(c.data, activeSlot.h, activeSlot.slot);
          return (
            <div key={c.date}>
              <i className="dot" style={{ background: c.color }} />
              {dl(c.date)}: {v == null ? "no data" : `${fmt(v)} devices`}
            </div>
          );
        })}
        {reference != null && block != null && (
          <div>Historical mean: {fmt(reference, 1)} devices ({block >= reference ? "+" : ""}{fmt(block - reference, 1)})</div>
        )}
        {wt && (
          <div className="muted">
            {wt.condition}, {fmt(wt.temp_c, 1)} °C
            {wt.precipitation_mm > 0 ? `, ${fmt(wt.precipitation_mm, 1)} mm rain` : ""}
          </div>
        )}
      </>
    );
  }
  const tipX = activeSlot ? X(activeSlot.h + (activeSlot.slot + 0.5) * slotH) : 0;

  // Details for the selected hour
  const h = hourData(hour);
  const average = aggregateHour(h, interval);
  const blocks = aggregateSlots(h?.slot_counts ?? [], interval).filter((v) => v != null);
  const w0 = h?.weather;

  return (
    <div>
      <div ref={box} className="chartbox">
        <svg
          viewBox={`0 0 ${w} ${H}`}
          height={H}
          onPointerMove={pick}
          onPointerDown={selectBar}
          onPointerLeave={(e) => e.pointerType === "mouse" && setHov(null)}
          role="img"
          aria-label="Device counts in 5- or 15-minute blocks for selected and historical days"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((t) => (
            <g key={t}>
              <line x1={m.l} x2={w - m.r} y1={Y(max * t)} y2={Y(max * t)} stroke="var(--line)" />
              <text className="axis" x={m.l - 6} y={Y(max * t) + 4} textAnchor="end">
                {Math.round(max * t)}
              </text>
            </g>
          ))}

          {/* the selected hour */}
          {range.includes(hour) && (
            <rect x={X(hour)} y={m.t} width={X(hour + 1) - X(hour)} height={ih} fill="var(--mute)" opacity=".08" />
          )}

          {/* Persistent selection band and outline across the entire plot. */}
          {selectedSlot && (
            <g pointerEvents="none">
              <rect x={X(selectedSlot.h + selectedSlot.slot * slotH)} y={m.t}
                width={Math.max(1, X(slotH) - X(0))} height={ih}
                fill="#38bdf8" fillOpacity="0.13" stroke="#0284c7"
                strokeWidth="1.5" />
            </g>
          )}

          {/* Historical bars are drawn first, translucent and slightly wider. */}
          {historical.map((c, ci) => c.slots.map((b) =>
            b.v != null && b.v > 0 && (
              <rect
                key={`history-${ci}-${b.h}-${b.j}`}
                x={X(b.h + b.j * slotH)}
                y={Y(b.v)}
                width={barW + 1}
                height={Y(0) - Y(b.v)}
                fill={c.color}
                opacity={0.15 + 0.12 / Math.max(1, historical.length)}
              />
            )
          ))}

          {/* Current bars are narrower, color-coded against the historical mean. */}
          {bars.map((b) => b.v != null && b.v > 0 && (
            <rect
              key={`current-${b.h}-${b.j}`}
              x={X(b.h + b.j * slotH) + 0.5 + barW * 0.18}
              y={Y(b.v)}
              width={Math.max(0.4, barW * 0.64)}
              height={Y(0) - Y(b.v)}
              fill={currentColor(b)}
              stroke={currentColor(b) === positive ? "#d85c73" : currentColor(b) === negative ? "#568bc6" : "#8995a4"}
              strokeWidth={Math.min(0.9, barW * 0.12)}
              opacity={barOpacity(b)}
            />
          ))}

          {/* The latest available interval gets a distinct guide and marker. */}
          {latest && (() => {
            const cx = X(latest.h + (latest.j + 0.5) * slotH);
            const cy = Y(latest.v);
            const labelX = Math.max(m.l + 39, Math.min(w - m.r - 39, cx));
            return (
              <g pointerEvents="none">
                <line x1={cx} x2={cx} y1={m.t + 19} y2={Y(0)}
                  stroke="#0891b2" strokeWidth="1.8" strokeDasharray="4 3" />
                <circle cx={cx} cy={cy} r="5" fill="#ffffff" stroke="#0891b2" strokeWidth="2.5" />
                <rect x={labelX - 38} y={m.t - 2} width="76" height="20" rx="5" fill="#0e7490" />
                <text x={labelX} y={m.t + 12} textAnchor="middle" fontSize="10" fontWeight="700" fill="white">LATEST</text>
              </g>
            );
          })()}

          {/* rain, per hour */}
          {rain.map(
            (v, i) =>
              v > 0 && (
                <rect
                  key={`rain-${i}`}
                  x={xi(i) - Math.max(3, (iw / n) * 0.3)}
                  width={Math.max(6, (iw / n) * 0.6)}
                  y={m.t + ih - (v / rmax) * 50}
                  height={(v / rmax) * 50}
                  fill="var(--rain)"
                  opacity=".65"
                />
              ),
          )}

          {range.map(
            (hh, i) =>
              i % step === 0 && (
                <text key={hh} className="axis" x={X(hh)} y={H - 8} textAnchor="middle">
                  {hl(hh)}
                </text>
              ),
          )}

          {mainAvg.every((v) => v == null) && (
            <text x={w / 2} y={H / 2} textAnchor="middle" className="axis">
              No data yet for these hours
            </text>
          )}
        </svg>
        {tip && (
          <div
            className="tip"
            style={{
              left: tipX,
              transform: tipX > w * 0.55 ? "translateX(calc(-100% - 12px))" : "translateX(12px)",
            }}
          >
            {tip}
          </div>
        )}
      </div>

      <div className="legend">
        <span><i className="sw barbox" style={{ background: positive }} />Above historical mean (soft red)</span>
        <span><i className="sw barbox" style={{ background: negative }} />Below historical mean (soft blue)</span>
        <span><i className="sw barbox" style={{ background: "var(--main)" }} />Equal / no historical data (white)</span>
        {comps.map((c) => (
          <span key={c.date}><i className="sw barbox" style={{ background: c.color, opacity: 0.45 }} />{dl(c.date)} (historical)</span>
        ))}
        <span><i className="sw barbox" style={{ background: "#0e7490" }} />Latest available interval</span>
        <span><i className="sw barbox" style={{ background: "#38bdf8" }} />Clicked interval</span>
        <span><i className="sw rainbox" />Rain, mm per hour{rainMax > 0 ? ` (tallest bar ${rainMax.toFixed(1)} mm)` : " (none)"}</span>
      </div>

      {latest && (
        <div className="hour-info" style={{ borderLeft: "4px solid #0891b2", paddingLeft: 12, marginTop: 10 }}>
          <strong>Latest available {interval}-minute interval</strong>
          <div>{tl(latest.h, latest.j * interval)}–{tl(latest.h, (latest.j + 1) * interval)}: <b>{fmt(latest.v)} devices</b></div>
          <div className="muted">Latest reported observation (not necessarily a live, in-progress count).</div>
        </div>
      )}
      {selectedSlot && (
        <div className="hour-info" style={{ borderLeft: "4px solid #0284c7", paddingLeft: 12, marginTop: 10 }}>
          <strong>Selected interval: {tl(selectedSlot.h, selectedSlot.slot * interval)}–{tl(selectedSlot.h, (selectedSlot.slot + 1) * interval)}</strong>
          <div>Selected day: {selectedValue == null ? "no data" : `${fmt(selectedValue)} devices`}</div>
          {referenceAt(selectedSlot.h, selectedSlot.slot) != null && selectedValue != null && (
            <div>Historical mean: {fmt(referenceAt(selectedSlot.h, selectedSlot.slot), 1)} devices</div>
          )}
        </div>
      )}

      {children}

      {/* details for the selected hour */}
      <div className="hour-info">
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
                <b>{Math.max(0, ...blocks)}</b>
                <span className="muted">highest {interval}-minute block</span>
              </div>
            </div>
            {!h.complete && (
              <p className="muted">Hour in progress: {h.slots_final} finished 5-minute period(s) so far.</p>
            )}
          </>
        )}

        {comps.length > 0 && <h2 className="sec">Same hour on comparison days</h2>}
        {comps.map((c) => {
          const v = aggregateHour(c.data?.hours?.[hour], interval);
          const pct = average != null && v > 0 ? Math.round(((average - v) / v) * 100) : null;
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

        {w0 && (
          <>
            <h2 className="sec">Weather{w0.forecast ? " (forecast)" : ""}</h2>
            <div className="stats">
              <div>
                <b style={{ fontSize: 18 }}>{w0.condition}</b>
                <span className="muted">conditions</span>
              </div>
              <div>
                <b>{fmt(w0.temp_c, 1)} °C</b>
                <span className="muted">feels like {fmt(w0.feels_like_c)} °C</span>
              </div>
              <div>
                <b>{fmt(w0.precipitation_mm, 1)} mm</b>
                <span className="muted">rain this hour</span>
              </div>
              <div>
                <b>{fmt(w0.wind_kmh)} km/h</b>
                <span className="muted">
                  humidity {fmt(w0.humidity_pct)}%, cloud {fmt(w0.cloud_cover_pct)}%
                </span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}