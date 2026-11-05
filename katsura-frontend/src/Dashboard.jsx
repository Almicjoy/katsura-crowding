import { useState } from "react";
import { useContainerWidth, GridLayout } from "react-grid-layout";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";

const defaultLayout = [
  { i: "daychart", x: 0, y: 0, w: 8, h: 12, minW: 4, minH: 7 },
  { i: "livemap", x: 8, y: 0, w: 4, h: 12, minW: 3, minH: 6 },
  { i: "weekday", x: 0, y: 12, w: 12, h: 9, minW: 4, minH: 6 },
  { i: "weather", x: 0, y: 21, w: 12, h: 12, minW: 4, minH: 8 },
];

const STORAGE_KEY = "katsura-dashboard-layout";

// A layout saved before a widget existed has no entry for it: add the missing ones at the bottom
function withMissingWidgets(saved) {
  let bottom = Math.max(0, ...saved.map((l) => l.y + l.h));
  const extra = defaultLayout
    .filter((d) => !saved.some((s) => s.i === d.i))
    .map((d) => {
      const item = { ...d, y: bottom };
      bottom += d.h;
      return item;
    });
  return [...saved, ...extra];
}

export default function Dashboard({ dayChart, liveMap, weekdayProfile, weatherCrowding }) {
  const { width, containerRef, mounted } = useContainerWidth();

  const [layout, setLayout] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? withMissingWidgets(JSON.parse(saved)) : defaultLayout;
    } catch {
      return defaultLayout;
    }
  });

  function saveLayout(newLayout) {
    setLayout(newLayout);

    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(newLayout));
    } catch (error) {
      console.warn("Could not save dashboard layout:", error);
    }
  }

  function resetLayout() {
    setLayout(defaultLayout);

    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.warn("Could not reset dashboard layout:", error);
    }
  }

  return (
    <div className="dashboard">
      <div className="dashboard-toolbar">
        <h2>Dashboard</h2>

        <button className="btn" onClick={resetLayout}>
          Reset layout
        </button>
      </div>

      <div ref={containerRef}>
        {mounted && width > 0 && (
          <GridLayout
            width={width}
            layout={layout}
            onLayoutChange={saveLayout}
            gridConfig={{
              cols: 12,
              rowHeight: 30,
              margin: [12, 12],
            }}
            dragConfig={{
              enabled: true,
              handle: ".widget-header",
            }}
            resizeConfig={{
              enabled: true,
              handles: ["se", "sw", "ne", "nw"],
            }}
            compactor={null}
          >
            <div key="daychart" className="widget">
              <div className="widget-header">
                <span>Daily Crowding</span>
                <span>⠿</span>
              </div>
              <div className="widget-content">{dayChart}</div>
            </div>

            <div key="livemap" className="widget">
              <div className="widget-header">
                <span>Live Map</span>
                <span>⠿</span>
              </div>
              <div className="widget-content">{liveMap}</div>
            </div>

            <div key="weekday" className="widget">
              <div className="widget-header">
                <span>Weekday Profile</span>
                <span>⠿</span>
              </div>
              <div className="widget-content">{weekdayProfile}</div>
            </div>

            {/* <div key="weather" className="widget">
              <div className="widget-header">
                <span>Weather and Crowding</span>
                <span>⠿</span>
              </div>
              <div className="widget-content">{weatherCrowding}</div>
            </div> */}
          </GridLayout>
        )}
      </div>
    </div>
  );
}