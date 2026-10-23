from datetime import date, datetime, timedelta

# Fill in from the official academic calendar. One entry per semester.
TERMS = [
    {"name": "2026-fall", "term": "fall",
     "start": date(2026, 10, 1), "end": date(2027, 1, 31),
     "finals": (date(2027, 1, 20), date(2027, 1, 31)),
     "holidays": [date(2026, 11, 3), date(2026, 11, 23)]},
    {"name": "2026-spring", "term": "spring",
     "start": date(2026, 4, 8), "end": date(2026, 8, 7),
     "finals": (date(2026, 7, 27), date(2026, 8, 7)),
     "holidays": [date(2026, 5, 4)]},
    # add earlier semesters here so history can be matched
]


def classify(d):
    """Return {term, phase, week, name} for a date."""
    for t in TERMS:
        if t["start"] <= d <= t["end"]:
            monday = t["start"] - timedelta(days=t["start"].weekday())
            week = (d - monday).days // 7 + 1
            if d in t["holidays"]:
                phase = "holiday"
            elif t["finals"][0] <= d <= t["finals"][1]:
                phase = "finals"
            else:
                phase = "classes"
            return {"term": t["term"], "phase": phase, "week": week, "name": t["name"]}
    return {"term": None, "phase": "break", "week": None, "name": None}


def select_dates(today, query, limit, lookback_weeks=120):
    """Past same-weekday dates matching the requested calendar filters."""
    want = {k: (query.get(k) or [None])[0] for k in ("term", "phase", "week")}
    if (query.get("period") or [None])[0] == "auto":
        cur = classify(today)
        want = {"term": cur["term"], "phase": cur["phase"],
                "week": str(cur["week"]) if cur["phase"] == "classes" and cur["week"] else None}
    filtered = any(want.values())

    picked = []
    for i in range(1, lookback_weeks + 1):
        d = today - timedelta(days=7 * i)
        if filtered:
            c = classify(d.date() if isinstance(d, datetime) else d)
            if c["phase"] == "holiday":
                continue  # holidays distort averages
            if want["term"] and c["term"] != want["term"]:
                continue
            if want["phase"] and c["phase"] != want["phase"]:
                continue
            if want["week"] and str(c["week"]) != want["week"]:
                continue
        picked.append(d)
        if len(picked) == limit:
            break
    return picked, want if filtered else None