
import { useEffect, useState } from "react";
import { useContainerWidth, GridLayout } from "react-grid-layout";

import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import "./dashboard.css";

const STORAGE_KEY = "katsura-dashboard-layout";

const defaultLayout = [
  { i: "daychart", x: 0, y: 0, w: 8, h: 12, minW: 4, minH: 7 },
  { i: "livemap", x: 8, y: 0, w: 4, h: 12, minW: 3, minH: 6 },
  { i: "weekday", x: 0, y: 12, w: 12, h: 9, minW: 4, minH: 6 },
];

function withMissingWidgets(saved) {
  if (!Array.isArray(saved)) return defaultLayout;

  const valid = saved.filter((item) =>
    defaultLayout.some((d) => d.i === item.i)
  );

  let bottom = Math.max(
    0,
    ...valid.map((item) => item.y + item.h)
  );

  const missing = defaultLayout
    .filter((d) => !valid.some((s) => s.i === d.i))
    .map((d) => {
      const item = { ...d, y: bottom };
      bottom += d.h;
      return item;
    });

  return [...valid, ...missing];
}

function loadLayout() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved
      ? withMissingWidgets(JSON.parse(saved))
      : defaultLayout;
  } catch {
    return defaultLayout;
  }
}

function Widget({ title, children }) {
  return (
    <div className="widget">
      <div className="widget-header">
        <span className="widget-title">{title}</span>
        <span className="widget-drag-handle" aria-hidden="true">
          ⠿
        </span>
      </div>
      <div className="widget-content">{children}</div>
    </div>
  );
}

export default function Dashboard({
  dayChart,
  liveMap,
  weekdayProfile,
  weatherCrowding,
}) {
  const { width, containerRef, mounted } = useContainerWidth();

  const [layout, setLayout] = useState(loadLayout);
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== "undefined" &&
      window.matchMedia("(max-width: 767px)").matches
  );

  useEffect(() => {
    const media = window.matchMedia("(max-width: 767px)");

    const update = () => setIsMobile(media.matches);

    update();
    media.addEventListener("change", update);

    return () => media.removeEventListener("change", update);
  }, []);

  function saveLayout(newLayout) {
    setLayout(newLayout);

    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify(newLayout)
      );
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

  const widgets = [
    {
      id: "daychart",
      title: "Daily Crowding",
      content: dayChart,
    },
    {
      id: "livemap",
      title: "Live Map",
      content: liveMap,
    },
    {
      id: "weekday",
      title: "Weekday Profile",
      content: weekdayProfile,
    },
    // Uncomment when you want the weather widget back:
    // {
    //   id: "weather",
    //   title: "Weather and Crowding",
    //   content: weatherCrowding,
    // },
  ];

  return (
    <section className="dashboard">
      <div className="dashboard-toolbar">

        {!isMobile && (
          <button
            type="button"
            className="btn dashboard-reset"
            onClick={resetLayout}
          >
            Reset layout
          </button>
        )}
      </div>

      {isMobile ? (
        <div className="dashboard-mobile">
          {widgets.map((widget) => (
            <div
              className="dashboard-mobile-item"
              key={widget.id}
            >
              <Widget title={widget.title}>
                {widget.content}
              </Widget>
            </div>
          ))}
        </div>
      ) : (
        <div ref={containerRef} className="dashboard-grid">
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
              {widgets.map((widget) => (
                <div key={widget.id} className="widget">
                  <div className="widget-header">
                    <span className="widget-title">
                      {widget.title}
                    </span>
                    <span
                      className="widget-drag-handle"
                      aria-hidden="true"
                    >
                      ⠿
                    </span>
                  </div>

                  <div className="widget-content">
                    {widget.content}
                  </div>
                </div>
              ))}
            </GridLayout>
          )}
        </div>
      )}
    </section>
  );
}
