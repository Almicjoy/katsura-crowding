from datetime import date, datetime, timedelta
from functools import lru_cache

CLASS_WEEKDAYS = {0, 1, 2, 3, 4}  # Mon-Fri; add 5 if Saturday classes run

# Dates are ISO strings so they're easy to copy from the official calendar.
# term: "spring" = April-September, "fall" = October-March
_RAW = [
    {
        "name": "2024/25 October-March", "term": "fall",
        "start": "2024-10-01",
        "classes": ("2024-10-01", "2025-02-02"),
        "exams": ("2025-02-03", "2025-02-09"),
        "breaks": [("2024-12-29", "2025-01-03")],
        "events": {
            "2024-10-04": "Autumn Graduate School Entrance Ceremony",
            "2025-03-23": "Degree Conferment and Graduation Ceremony",
        },
        "no_class": {
            "2024-10-14": "Health and Sports Day",
            "2024-11-04": "Culture Day",
            "2024-11-21": "November Festival",
            "2024-11-22": "November Festival",
            "2025-01-13": "Coming of Age Day",
        },
    },
    {
        "name": "2025/26 April-September", "term": "spring",
        "start": "2025-04-01",
        "classes": ("2025-04-08", "2025-07-29"),
        "exams": ("2025-07-30", "2025-08-05"),
        "breaks": [("2025-08-06", "2025-09-30")],
        "events": {
            "2025-04-08": "Entrance Ceremonies",
            "2025-09-24": "Autumn Degree Conferment Ceremony",
        },
        "no_class": {
            "2025-04-29": "Showa Day",
            "2025-05-05": "Children's Day",
            "2025-05-06": "Greenery Day (Observed)",
            "2025-06-18": "University Foundation Day",
            "2025-07-21": "Marine Day",
        },
    },
    {
        "name": "2025/26 October-March", "term": "fall",
        "start": "2025-10-01",
        "classes": ("2025-10-01", "2026-02-02"),
        "exams": ("2026-02-03", "2026-02-09"),
        "breaks": [("2025-12-29", "2026-01-03")],
        "events": {
            "2025-10-04": "Autumn Graduate School Entrance Ceremony",
            "2026-03-23": "Degree Conferment and Graduation Ceremony",
        },
        "no_class": {
            "2025-10-13": "Health and Sports Day",
            "2025-11-03": "Culture Day",
            "2025-11-20": "November Festival",
            "2025-11-21": "November Festival",
            "2025-11-24": "November Festival",
            "2026-01-12": "Coming of Age Day",
        },
    },
    {
        "name": "2026/27 April-September", "term": "spring",
        "start": "2026-04-01",
        "classes": ("2026-04-08", "2026-07-22"),
        "exams": ("2026-07-23", "2026-08-05"),
        "breaks": [("2026-08-06", "2026-09-30")],
        "events": {
            "2026-04-07": "Entrance Ceremonies",
            "2026-09-24": "Autumn Degree Conferment Ceremony",
        },
        "no_class": {
            "2026-04-29": "Showa Day",
            "2026-05-04": "Greenery Day",
            "2026-05-05": "Children's Day",
            "2026-05-06": "Constitution Memorial Day (Observed)",
            "2026-06-18": "University Foundation Day",
            "2026-07-20": "Marine Day"
        },
    },
    {
        "name": "2026/27 October-March", "term": "fall",
        "start": "2026-10-01",
        "classes": ("2026-10-01", "2027-01-22"),
        "exams": ("2027-01-25", "2027-02-05"),
        "breaks": [("2026-12-29", "2027-01-03"), ("2027-02-08", "2027-03-31")],
        "events": {
            "2026-10-03": "Autumn Graduate School Entrance Ceremony",
            "2027-03-23": "Degree Conferment and Graduation Ceremony",
        },
        # days inside the class period with no classes -> reason shown to the frontend
        "no_class": {
            "2026-10-12": "Health and Sports Day",
            "2026-11-03": "Culture Day",
            "2026-11-20": "November Festival",
            "2026-11-23": "November Festival",
            "2026-11-24": "November Festival",
            "2027-01-11": "Coming of Age Day"
        },
    },
    {
        "name": "2027/28 April-September", "term": "spring",
        "start": "2027-04-01",
        "classes": ("2027-04-08", "2027-07-22"),
        "exams": ("2027-07-23", "2027-08-05"),
        "breaks": [("2027-08-06", "2027-09-30")],
        "events": {
            "2027-04-07": "Entrance Ceremonies",
            "2027-09-24": "Autumn Degree Conferment Ceremony",
        },
        # days inside the class period with no classes -> reason shown to the frontend
        "no_class": {
            "2027-04-29": "Showa Day",
            "2027-05-03": "Constitution Memorial Day",
            "2027-05-04": "Greenery Day",
            "2027-05-05": "Children's Day",
            "2027-06-18": "University Foundation Day",
            "2027-07-19": "Marine Day"
        },
    },
    {
        "name": "2027/28 October-March", "term": "fall",
        "start": "2027-10-01",
        "classes": ("2027-10-01", "2028-01-24"),
        "exams": ("2028-01-25", "2028-02-07"),
        "breaks": [("2027-12-29", "2028-01-03"), ("2028-02-08", "2028-03-31")],
        "events": {
            "2027-10-02": "Autumn Graduate School Entrance Ceremony",
            "2028-03-23": "Degree Conferment and Graduation Ceremony",
        },
        # days inside the class period with no classes -> reason shown to the frontend
        "no_class": {
            "2027-10-11": "Health and Sports Day",
            "2027-11-03": "Culture Day",
            "2027-11-19": "November Festival",
            "2027-11-22": "November Festival",
            "2027-11-23": "November Festival",
            "2028-01-10": "Coming of Age Day"
        },
    },
]


def _d(s):
    return date.fromisoformat(s)


def _rng(r):
    return (_d(r[0]), _d(r[1]))


SEMESTERS = [
    {
        "name": r["name"], "term": r["term"], "start": _d(r["start"]),
        "classes": _rng(r["classes"]), "exams": _rng(r["exams"]),
        "breaks": [_rng(b) for b in r["breaks"]],
        "events": r["events"], "no_class": r["no_class"],
    }
    for r in sorted(_RAW, key=lambda r: r["start"])
]
# A semester runs until the day before the next one starts (default = break)
for i, s in enumerate(SEMESTERS):
    if i + 1 < len(SEMESTERS):
        s["end"] = SEMESTERS[i + 1]["start"] - timedelta(days=1)
    else:
        s["end"] = max([s["exams"][1]] + [b[1] for b in s["breaks"]])


def _within(day, rng):
    return rng[0] <= day <= rng[1]


@lru_cache(maxsize=4096)
def _lookup(day):
    base = {"date": day.isoformat(), "weekday": day.strftime("%A")}
    sem = next((s for s in SEMESTERS if s["start"] <= day <= s["end"]), None)
    if sem is None:
        return {**base, "semester": None, "term": None, "phase": "unknown",
                "week": None, "is_class_day": False,
                "reason": "outside calendar", "events": []}

    # Precedence: explicit break > exams > classes > default break
    if any(_within(day, b) for b in sem["breaks"]):
        phase = "break"
    elif _within(day, sem["exams"]):
        phase = "exams"
    elif _within(day, sem["classes"]):
        phase = "classes"
    else:
        phase = "break"

    # Week 1 = the Monday-based week containing the first class day
    first = sem["classes"][0]
    monday = first - timedelta(days=first.weekday())
    week = (day - monday).days // 7 + 1 if phase in ("classes", "exams") else None


    iso = day.isoformat()

    # Event dates are tracked separately from class/no-class status.
    event = sem["events"].get(iso)

    # Weekends take priority over the exam/classes phase.
    # Breaks remain no-class days as well.
    if day.weekday() not in CLASS_WEEKDAYS:
        reason = "weekend"
    elif phase == "break":
        reason = "break"
    elif phase == "exams":
        reason = "exams"
    else:
        reason = sem["no_class"].get(iso)

    return {
        **base,
        "semester": sem["name"],
        "term": sem["term"],
        "phase": phase,
        "week": week,
        "is_class_day": reason is None and event is None,
        "reason": reason,
        "events": [event] if event else [],
    }



def lookup(day):
    """Accepts a date, datetime or 'YYYY-MM-DD' string."""
    if isinstance(day, datetime):
        day = day.date()
    elif isinstance(day, str):
        day = date.fromisoformat(day)
    return _lookup(day)

PHASE_LABEL = {"classes": "in session", "exams": "exam/feedback week",
               "break": "break", "unknown": "outside calendar"}


def describe(info):
    head = f"{info['weekday']}, {info['date']}: "
    if not info["semester"]:
        return head + "outside the academic calendar"
    bits = [info["semester"]]
    if info["week"]:
        bits.append(f"week {info['week']}")
    bits.append(PHASE_LABEL[info["phase"]])
    if info["phase"] == "classes":
        bits.append("class day" if info["is_class_day"] else f"no classes ({info['reason']})")
    bits.extend(info["events"])
    return head + ", ".join(bits)


def equivalents(day):
    """Same week # and weekday in the other semesters of the same term."""
    if isinstance(day, datetime):
        day = day.date()
    elif isinstance(day, str):
        day = date.fromisoformat(day)
    src = _lookup(day)
    if src["week"] is None:
        return []
    sem = next(s for s in SEMESTERS if s["name"] == src["semester"])
    out = []
    for t in SEMESTERS:
        if t["term"] != sem["term"] or t["name"] == sem["name"]:
            continue
        first = t["classes"][0]
        monday = first - timedelta(days=first.weekday())
        d = monday + timedelta(days=(src["week"] - 1) * 7 + day.weekday())
        info = _lookup(d)
        if info["semester"] == t["name"] and info["week"] is not None:
            out.append({**info, "description": describe(info)})
    return out