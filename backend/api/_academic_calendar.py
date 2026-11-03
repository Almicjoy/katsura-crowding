from datetime import date, datetime, timedelta
from functools import lru_cache

CLASS_WEEKDAYS = {0, 1, 2, 3, 4}  # Mon-Fri; add 5 if Saturday classes run

# Dates are ISO strings so they're easy to copy from the official calendar.
# term: "spring" = April-September, "fall" = October-March
_RAW = [
    # {
    #     "name": "2021/22 April-September", "term": "spring",
    #     "start": "2021-04-01",
    #     "adjustment-period": ("2021-04-01", "2021-04-07"),
    #     "classes": ("2021-04-08", "2021-07-21"),
    #     "exams-feedback": ("2021-07-26", "2021-08-04"),
    #     "breaks": [("2021-08-05", "2021-09-30")],
    #     "events": {
    #         "2021-04-07": "Entrance Ceremonies",
    #         "2021-04-29": "Date Available for Make-up Classes",
    #         "2021-06-18": "Date Available for Make-up Classes",
    #         "2021-09-24": "Completion Ceremonies",
    #     },
    #     "no_class": {
    #         "2021-04-29": "Showa Day",
    #         "2021-05-03": "Constitution Memorial Day",
    #         "2021-05-04": "Greenery Day",
    #         "2021-05-05": "Children's Day",
    #         "2021-06-18": "University Foundation Day",
    #         "2021-07-22": "Marine Day",
    #         "2021-07-23": "Sports Day",
    #         "2021-08-09": "Mountain Day",
    #         "2021-09-20": "Respect for the Aged Day",
    #         "2021-09-23": "Autumnal Equinox Day",
    #     },
    # },
    {
        "name": "2021/22 October-March", "term": "fall",
        "start": "2021-10-01",
        "classes": ("2021-10-01", "2022-01-24"),
        "exams-feedback": ("2022-01-25", "2022-02-07"),
        "breaks": [("2021-12-29", "2022-01-03"), ("2022-02-08", "2022-03-31")],
        "events": {
            "2021-10-02": "Entrance Ceremonies",
            "2022-01-04": "Date Available for Make-up Classes",
            "2022-01-20": "Date Available for Make-up Classes",
            "2022-01-14": "Day before Common Test for University Admissions",
            "2022-01-15": "Common Test for University Admissions (1st day)",
            "2022-01-16": "Common Test for University Admissions (2nd day)",  
            "2022-03-24": "Completion Ceremonies",
            "2022-03-25": "Graduation Ceremonies",
        },
        "no_class": {
            "2021-11-03": "Culture Day",
            "2021-11-19": "November Festival",
            "2021-11-22": "November Festival",
            "2021-11-23": "Labor Thanksgiving Day",
            "2022-01-10": "Coming of Age Day",
            "2022-02-11": "National Foundation Day",
            "2022-02-23": "Emperor's Birthday",
            "2022-03-21": "Vernal Equinox Day",
        },
    },
        {
        "name": "2022/23 April-September", "term": "spring",
        "start": "2022-04-01",
        "adjustment-period": ("2022-04-01", "2022-04-07"),
        "classes": ("2022-04-08", "2022-07-21"),
        "exams-feedback": ("2022-07-22", "2022-08-04"),
        "breaks": [("2022-08-05", "2022-09-30")],
        "events": {
            "2022-04-07": "Entrance Ceremonies",
            "2022-09-24": "Completion Ceremonies", # missing data
        },
        "no_class": {
            "2022-04-29": "Showa Day",
            "2022-05-03": "Constitution Memorial Day",
            "2022-05-04": "Greenery Day",
            "2022-05-05": "Children's Day",
            "2022-06-18": "University Foundation Day",
            "2022-07-18": "Marine Day",
            "2022-07-23": "Sports Day",
            "2022-08-11": "Mountain Day",
            "2022-09-19": "Respect for the Aged Day",
            "2022-09-23": "Autumnal Equinox Day",
        },
    },
    {
        "name": "2022/23 October-March", "term": "fall",
        "start": "2022-10-01",
        "classes": ("2022-10-03", "2023-01-24"),
        "exams-feedback": ("2023-01-25", "2023-02-07"),
        "breaks": [("2022-12-29", "2023-01-03"), ("2023-02-08", "2023-03-31")],
        "rescheduling": {
            "2023-01-10": (0, 12),  # rescheduled to 12th Monday class
        },
        "events": {
            "2022-10-02": "Entrance Ceremonies",    # missing data
            "2022-12-03": "TOEFL Test Day",
            "2023-01-04": "Date Available for Make-up Classes",
            "2023-01-14": "Research and Exercise-based Class Day",
            "2023-01-13": "Day before Common Test for University Admissions",
            "2023-01-14": "Common Test for University Admissions (1st day)",
            "2023-01-15": "Common Test for University Admissions (2nd day)",  
            "2023-03-24": "Completion Ceremonies",
            "2023-03-25": "Graduation Ceremonies", # missing data
        },
        "no_class": {
            "2022-10-10": "Sports Day",
            "2022-11-03": "Culture Day",
            "2022-11-21": "November Festival",
            "2022-11-22": "November Festival",
            "2022-11-23": "Labor Thanksgiving Day",
            "2023-01-09": "Coming of Age Day",
            "2023-02-11": "National Foundation Day",
            "2023-02-23": "Emperor's Birthday",
            "2023-03-21": "Vernal Equinox Day",
        },
    },
    {
        "name": "2023/24 April-September", "term": "spring",
        "start": "2023-04-01",
        "adjustment-period": ("2023-04-03", "2023-04-07"),
        "classes": ("2023-04-10", "2023-07-21"),
        "exams-feedback": ("2023-07-24", "2023-08-04"),
        "breaks": [("2023-08-05", "2023-09-30")],
        "events": {
            "2023-04-07": "Entrance Ceremonies",
            "2023-07-18": "Date Available for Make-up Classes",
            "2023-09-25": "Completion Ceremonies",
        },
        "no_class": {
            "2023-04-29": "Showa Day",
            "2023-05-03": "Constitution Memorial Day",
            "2023-05-04": "Greenery Day",
            "2023-05-05": "Children's Day",
            "2023-06-18": "University Foundation Day",
            "2023-07-17": "Marine Day",
            "2023-08-11": "Mountain Day",
            "2023-09-18": "Respect for the Aged Day",
            "2023-09-23": "Autumnal Equinox Day",
        },
    },
    {
        "name": "2023/24 October-March", "term": "fall",
        "start": "2023-10-01",
        "classes": ("2023-10-02", "2024-01-23"),
        "exams-feedback": ("2024-01-24", "2024-02-06"),
        "breaks": [("2023-12-29", "2024-01-03"), ("2024-02-07", "2024-03-31")],
        "rescheduling": {
            "2023-12-26": (4, 11),  # rescheduled to 11th Friday class
            "2024-01-23": (4, 14), # rescheduled to 14th Friday class
        },
        "events": {
            "2023-10-07": "Entrance Ceremonies",
            "2024-01-04": "Date Available for Make-up Classes",
            "2024-01-12": "Day before Common Test for University Admissions",
            "2024-01-13": "Common Test for University Admissions (1st day)",
            "2024-01-14": "Common Test for University Admissions (2nd day)",
            "2024-03-25": "Completion Ceremonies",
            "2024-03-26": "Graduation Ceremonies",
        },
        "no_class": {
            "2023-10-09": "Sports Day",
            "2023-11-03": "Culture Day",
            "2023-11-22": "November Festival",
            "2023-11-23": "Labor Thanksgiving Day",
            "2023-11-24": "November Festival",
            "2024-01-08": "Coming of Age Day",
            "2024-02-12": "National Foundation Day",
            "2024-02-23": "Emperor's Birthday",
            "2024-03-20": "Vernal Equinox Day",
        },
    },
    {
        "name": "2024/25 April-September", "term": "spring",
        "start": "2024-04-01",
        "adjustment-period": ("2024-04-01", "2024-04-05"),
        "classes": ("2024-04-08", "2024-07-22"),
        "exams-feedback": ("2024-07-23", "2024-08-05"),
        "breaks": [("2024-08-06", "2024-09-30")],
        "rescheduling": {
            "2024-05-02": (0, 4),  # rescheduled to 4th Monday class
        },
        "events": {
            "2024-04-05": "Entrance Ceremonies",
            "2024-07-17": "Date Available for Make-up Classes",
            "2024-09-24": "Completion Ceremonies",
        },
        "no_class": {
            "2024-04-29": "Showa Day",
            "2024-05-03": "Constitution Memorial Day",
            "2024-05-06": "Children's Day",
            "2024-06-18": "University Foundation Day",
            "2024-07-15": "Marine Day",
            "2024-08-12": "Mountain Day",
            "2024-09-16": "Respect for the Aged Day",
            "2024-09-23": "Autumnal Equinox Day",
        },
    },
    {
        "name": "2024/25 October-March", "term": "fall",
        "start": "2024-10-01",
        "classes": ("2024-10-01", "2025-01-24"),
        "exams-feedback": ("2025-01-27", "2025-02-07"),
        "breaks": [("2024-12-30", "2025-01-03"), ("2025-02-08", "2025-03-31")],
        "rescheduling": {
            "2024-10-15": (0, 2),  # rescheduled to 2nd Monday class
            "2025-01-15": (0, 13),  # rescheduled to 13th Monday class
        },  
        "events": {
            "2024-10-05": "Entrance Ceremonies",
            "2025-01-17": "Day before Common Test for University Admissions",
            "2025-01-18": "Common Test for University Admissions (1st day)",
            "2025-01-19": "Common Test for University Admissions (2nd day)",
            "2025-01-21": "Date Available for Make-up Classes",
            "2025-01-23": "Date Available for Make-up Classes",
            "2025-03-24": "Completion Ceremonies",
            "2025-03-25": "Graduation Ceremonies",
        },
        "no_class": {
            "2024-10-14": "Sports Day",
            "2024-11-04": "Culture Day",
            "2024-11-20": "November Festival",
            "2024-11-21": "November Festival",
            "2024-11-22": "November Festival",
            "2025-01-13": "Coming of Age Day",
            "2025-02-11": "National Foundation Day",
            "2025-02-24": "Emperor's Birthday",
            "2025-03-20": "Vernal Equinox Day",
        },
    },
    {
        "name": "2025/26 April-September", "term": "spring",
        "start": "2025-04-01",
        "adjustment-period": ("2025-04-01", "2025-04-07"),
        "classes": ("2025-04-08", "2025-07-22"),
        "exams-feedback": ("2025-07-23", "2025-08-05"),
        "breaks": [("2025-08-06", "2025-09-30")],
        "rescheduling": {
            "2025-07-17": (0, 14),  # rescheduled to 14th Monday class
        },
        "events": {
            "2025-04-07": "Entrance Ceremonies",
            "2025-07-18": "Date Available for Make-up Classes",
            "2025-09-24": "Completion Ceremonies",
        },
        "no_class": {
            "2025-04-29": "Showa Day",
            "2025-05-05": "Children's Day",
            "2025-05-06": "Greenery Day",
            "2025-06-18": "University Foundation Day",
            "2025-07-21": "Marine Day",
            "2025-08-11": "Mountain Day",
            "2025-09-15": "Respect for the Aged Day",
            "2025-09-23": "Autumnal Equinox Day",
        },
    },
    {
        "name": "2025/26 October-March", "term": "fall",
        "start": "2025-10-01",
        "classes": ("2025-10-01", "2026-01-26"),
        "exams-feedback": ("2026-01-27", "2026-02-09"),
        "breaks": [("2025-12-29", "2026-01-03"), ("2026-02-10", "2026-03-31")],
        "rescheduling": {
            "2025-10-15": (0, 2),  # rescheduled to 2nd Monday class
            "2025-11-06": (0, 5),  # rescheduled to 5th Monday class
        },
        "events": {
            "2025-10-04": "Entrance Ceremonies",
            "2026-01-16": "Day before Common Test for University Admissions",
            "2026-01-17": "Common Test for University Admissions (1st day)",
            "2026-01-18": "Common Test for University Admissions (2nd day)",
            "2026-01-21": "Date Available for Make-up Classes",
            "2026-01-22": "Date Available for Make-up Classes",
            "2026-03-23": "Graduation Ceremonies",
        },
        "no_class": {
            "2025-10-13": "Sports Day",
            "2025-11-03": "Culture Day",
            "2025-11-21": "November Festival",
            "2025-11-24": "Labor Thanksgiving Day",
            "2025-11-25": "November Festival",
            "2026-01-12": "Coming of Age Day",
            "2026-02-11": "National Foundation Day",
            "2026-02-23": "Emperor's Birthday",
            "2026-03-20": "Vernal Equinox Day",
        },
    },
    {
        "name": "2026/27 April-September", "term": "spring",
        "start": "2026-04-01",
        "adjustment-period": ("2026-04-01", "2026-04-07"),
        "classes": ("2026-04-08", "2026-07-22"),
        "exams-feedback": ("2026-07-23", "2026-08-05"),
        "breaks": [("2026-08-06", "2026-09-30")],
        "rescheduling": {
            "2026-05-01": (0, 4),  # rescheduled to 4th Monday class
        },
        "events": {
            "2026-04-07": "Entrance Ceremonies",
            "2026-09-24": "Completion Ceremonies",
        },
        "no_class": {
            "2026-04-29": "Showa Day",
            "2026-05-04": "Greenery Day",
            "2026-05-05": "Children's Day",
            "2026-05-06": "Constitution Memorial Day",
            "2026-06-18": "University Foundation Day",
            "2026-07-20": "Marine Day",
            "2026-08-11": "Mountain Day",
            "2026-09-21": "Respect for the Aged Day",
            "2026-09-22": "Citizens' Holiday",
            "2026-09-23": "Autumnal Equinox Day"
        },
    },
    {
        "name": "2026/27 October-March", "term": "fall",
        "start": "2026-10-01",
        "classes": ("2026-10-01", "2027-01-22"),
        "exams-feedback": ("2027-01-25", "2027-02-05"),
        "breaks": [("2026-12-29", "2027-01-03"), ("2027-02-08", "2027-03-31")],
        "rescheduling": {
            "2026-10-15": (0, 2),  # rescheduled to 2nd Monday class
            "2026-11-26": (1, 7),  # rescheduled to 7th Tuesday class
        },
        "events": {
            "2026-10-03": "Entrance Ceremonies",
            "2027-01-15": "Day before Common Test for University Admissions",
            "2027-01-16": "Common Test for University Admissions (1st day)",
            "2027-01-17": "Common Test for University Admissions (2nd day)",
            "2027-01-20": "Date Available for Make-up Classes",
            "2027-03-23": "Graduation Ceremonies",
        },
        # days inside the class period with no classes -> reason shown to the frontend
        "no_class": {
            "2026-10-12": "Sports Day",
            "2026-11-03": "Culture Day",
            "2026-11-20": "November Festival",
            "2026-11-23": "Labor Thanksgiving Day",
            "2026-11-24": "November Festival",
            "2027-01-11": "Coming of Age Day",
            "2027-02-11": "National Foundation Day",
            "2027-02-23": "Emperor's Birthday",
            "2027-03-22": "Vernal Equinox Day",
        },
    },
    {
        "name": "2027/28 April-September", "term": "spring",
        "start": "2027-04-01",
        "adjustment-period": ("2027-04-01", "2027-04-07"),
        "classes": ("2027-04-08", "2027-07-22"),
        "exams-feedback": ("2027-07-23", "2027-08-05"),
        "breaks": [("2027-08-06", "2027-09-30")],
        "rescheduling": {
            "2027-07-22": (0, 14),  # rescheduled to 14th Monday class
        },
        "events": {
            "2027-04-07": "Entrance Ceremonies",
            "2027-09-24": "Completion Ceremonies",
        },
        "no_class": {
            "2027-04-29": "Showa Day",
            "2027-05-03": "Constitution Memorial Day",
            "2027-05-04": "Greenery Day",
            "2027-05-05": "Children's Day",
            "2027-06-18": "University Foundation Day",
            "2027-07-19": "Marine Day",
            "2027-08-11": "Mountain Day",
            "2027-09-20": "Respect for the Aged Day",
            "2027-09-23": "Autumnal Equinox Day"
        },
    },
    {
        "name": "2027/28 October-March", "term": "fall",
        "start": "2027-10-01",
        "classes": ("2027-10-01", "2028-01-24"),
        "exams-feedback": ("2028-01-25", "2028-02-07"),
        "breaks": [("2027-12-29", "2028-01-03"), ("2028-02-08", "2028-03-31")],
        "rescheduling": {
            "2027-10-14": (0, 2),  # rescheduled to 2nd Monday class
        },
        "events": {
            "2027-10-02": "Entrance Ceremonies",
            "2028-01-04": "Date Available for Make-up Classes",
            "2028-01-14": "Day before Common Test for University Admissions",
            "2028-01-15": "Common Test for University Admissions (1st day)",
            "2028-01-16": "Common Test for University Admissions (2nd day)",
            "2028-03-23": "Graduation Ceremonies",
        },
        "no_class": {
            "2027-10-11": "Sports Day",
            "2027-11-03": "Culture Day",
            "2027-11-19": "November Festival",
            "2027-11-22": "November Festival",
            "2027-11-23": "Labor Thanksgiving Day",
            "2028-01-10": "Coming of Age Day",
            "2028-02-11": "National Foundation Day",
            "2028-02-23": "Emperor's Birthday",
            "2028-03-20": "Vernal Equinox Day",
        },
    },
]


DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
PROBLEMS = []  # data mistakes found while loading; run `python _academic_calendar.py` to see them


def _d(s):
    return date.fromisoformat(s)


def _rng(r):
    return (_d(r[0]), _d(r[1]))


def _within(day, rng):
    return rng[0] <= day <= rng[1]


def _resched(name, raw):
    """{'YYYY-MM-DD': (weekday 0-6, session)}: days held as another weekday's class."""
    out = {}
    for key, value in (raw or {}).items():
        try:
            day, (wd, n) = _d(key), value
            if not (0 <= int(wd) <= 6 and int(n) >= 1):
                raise ValueError("weekday must be 0-6 and session 1 or more")
            out[day.isoformat()] = (int(wd), int(n))
        except (ValueError, TypeError) as e:
            PROBLEMS.append(f"{name}: bad rescheduling entry {key!r}: {value!r} ({e})")
    return out


SEMESTERS = [
    {
        "name": r["name"], "term": r["term"], "start": _d(r["start"]),
        "classes": _rng(r["classes"]), "exams-feedback": _rng(r["exams-feedback"]),
        "breaks": [_rng(b) for b in r["breaks"]],
        "events": r["events"], "no_class": r["no_class"],
        "rescheduling": _resched(r["name"], r.get("rescheduling")),
    }
    for r in sorted(_RAW, key=lambda r: r["start"])
]
# A semester runs until the day before the next one starts (default = break)
for i, s in enumerate(SEMESTERS):
    if i + 1 < len(SEMESTERS):
        s["end"] = SEMESTERS[i + 1]["start"] - timedelta(days=1)
    else:
        s["end"] = max([s["exams-feedback"][1]] + [b[1] for b in s["breaks"]])


def _is_class_day(sem, day):
    """A regular class day: in the class period, Mon-Fri, and not a break, holiday or event."""
    iso = day.isoformat()
    return (
        _within(day, sem["classes"])
        and day.weekday() in CLASS_WEEKDAYS
        and not any(_within(day, b) for b in sem["breaks"])
        and iso not in sem["no_class"]
        and iso not in sem["events"]
    )


def _number_sessions(sem):
    """{'YYYY-MM-DD': (session, weekday the day is held as)}.

    Sessions are counted per weekday: Monday class 1, 2, 3 ... and Friday class 1, 2, 3 ...
    A rescheduled day takes the weekday and session number the university gave it, and later
    days of that weekday carry on counting from there. Exam/feedback days and events
    (such as make-up class dates) get no session."""
    out, count = {}, {}
    day = sem["classes"][0]
    while day <= sem["classes"][1]:
        iso = day.isoformat()
        in_break = any(_within(day, b) for b in sem["breaks"])
        if iso in sem["rescheduling"] and not in_break:
            wd, n = sem["rescheduling"][iso]
            if count.get(wd, 0) + 1 != n:
                PROBLEMS.append(
                    f"{sem['name']}: {iso} is set as {DAY_NAMES[wd]} session {n}, "
                    f"but counting the {DAY_NAMES[wd]} classes gives {count.get(wd, 0) + 1}"
                )
            count[wd] = n
            out[iso] = (n, wd)
        elif _is_class_day(sem, day):
            wd = day.weekday()
            count[wd] = count.get(wd, 0) + 1
            out[iso] = (count[wd], wd)
        day += timedelta(days=1)
    return out


for s in SEMESTERS:
    s["sessions"] = _number_sessions(s)


@lru_cache(maxsize=4096)
def _lookup(day):
    base = {"date": day.isoformat(), "weekday": day.strftime("%A")}
    sem = next((s for s in SEMESTERS if s["start"] <= day <= s["end"]), None)
    if sem is None:
        return {**base, "semester": None, "term": None, "phase": "unknown",
                "is_class_day": False, "reason": "outside calendar",
                "events": [], "session": None, "schedule_weekday": None, "rescheduled": False}

    # Precedence: explicit break > exams > classes > default break
    if any(_within(day, b) for b in sem["breaks"]):
        phase = "break"
    elif _within(day, sem["exams-feedback"]):
        phase = "exams-feedback"
    elif _within(day, sem["classes"]):
        phase = "classes"
    else:
        phase = "break"


    iso = day.isoformat()
    event = sem["events"].get(iso)                  # events are separate from class / no-class status
    held = sem["sessions"].get(iso)                 # (session, weekday) for days that have a session
    rescheduled = held is not None and iso in sem["rescheduling"]

    no_class_detail = sem["no_class"].get(iso)

    detail_parts = []
    if no_class_detail:
        detail_parts.append(str(no_class_detail))
    if event:
        detail_parts.append(str(event))

    detail = "; ".join(dict.fromkeys(detail_parts)) or None

    if rescheduled:
        reason = None  # held as a regular class day, even on a weekend or a holiday
    elif day.weekday() not in CLASS_WEEKDAYS:
        reason = "weekend"
    elif phase == "break":
        reason = "break"
    elif phase == "exams-feedback":
        reason = "exams-feedback"
    else:
        reason = sem["no_class"].get(iso)

    return {
        **base,
        "semester": sem["name"],
        "term": sem["term"],
        "phase": phase,
        "is_class_day": reason is None and (event is None or rescheduled),
        "reason": reason,
        "events": [event] if event else [],
        "session": held[0] if held else None,
        "schedule_weekday": DAY_NAMES[held[1]] if held else None,
        "rescheduled": rescheduled,
    }


def lookup(day):
    """Accepts a date, datetime or 'YYYY-MM-DD' string."""
    if isinstance(day, datetime):
        day = day.date()
    elif isinstance(day, str):
        day = date.fromisoformat(day)
    return _lookup(day)

PHASE_LABEL = {"classes": "in session", "exams-feedback": "exam/feedback week",
               "break": "break", "unknown": "outside calendar"}


def describe(info):
    head = f"{info['weekday']}, {info['date']}: "
    if not info["semester"]:
        return head + "outside the academic calendar"
    bits = [info["semester"]]
    bits.append(PHASE_LABEL.get(info["phase"], info["phase"]))
    if info["phase"] == "classes":
        if info["is_class_day"]:
            bits.append("class day")
            if info["session"]:
                if info["rescheduled"]:
                    bits.append(f"held as a {info['schedule_weekday']} class, session {info['session']}")
                else:
                    bits.append(f"{info['schedule_weekday']} session {info['session']}")
        else:
            bits.append(f"no classes ({info['reason'] or 'event'})")
    bits.extend(info["events"])
    return head + ", ".join(bits)



def equivalents(day):
    """Find comparable dates, prioritizing named events and holidays."""

    if isinstance(day, datetime):
        day = day.date()
    elif isinstance(day, str):
        day = date.fromisoformat(day)

    src = _lookup(day)
    if not src["semester"]:
        return []

    source_sem = next(
        s for s in SEMESTERS if s["name"] == src["semester"]
    )
    source_iso = day.isoformat()

    def normalize(value):
        return " ".join(str(value).strip().casefold().split())

    def labels(value):
        """Normalize a label or collection of labels into a set."""
        if not value:
            return set()
        if isinstance(value, (list, tuple, set)):
            values = value
        else:
            values = [value]
        return {normalize(v) for v in values if v}

    source_events = labels(source_sem["events"].get(source_iso))
    source_no_class = labels(
        source_sem["no_class"].get(source_iso)
    )

    # Named events and holidays take precedence over sessions.
    if source_events:
        match_type = "event"
        match_labels = source_events
    elif source_no_class:
        match_type = "no_class"
        match_labels = source_no_class
    elif src.get("detail"):
        match_type = "detail"
        match_labels = labels(src["detail"])
    elif (
        src["session"] is not None
        and src["schedule_weekday"] is not None
    ):
        match_type = "session"
        match_labels = set()
    else:
        return []

    out = []
    seen_dates = set()

    for target in SEMESTERS:
        if (
            target["term"] != source_sem["term"]
            or target["name"] == source_sem["name"]
        ):
            continue

        candidates = []

        if match_type == "event":
            for iso, event in target["events"].items():
                if labels(event) == match_labels:
                    candidates.append(
                        (date.fromisoformat(iso), "Same event")
                    )

        elif match_type == "no_class":
            for iso, reason in target["no_class"].items():
                if labels(reason) == match_labels:
                    candidates.append(
                        (date.fromisoformat(iso), "Same no-class reason")
                    )

        elif match_type == "detail":
            special_dates = (
                set(target["events"]) | set(target["no_class"])
            )
            for iso in special_dates:
                candidate_day = date.fromisoformat(iso)
                info = _lookup(candidate_day)
                if (
                    info.get("detail")
                    and labels(info["detail"]) == match_labels
                ):
                    candidates.append(
                        (candidate_day, "Same detail")
                    )

        elif match_type == "session":
            for iso, (session, weekday_idx) in target["sessions"].items():
                if (
                    session == src["session"]
                    and DAY_NAMES[weekday_idx] == src["schedule_weekday"]
                ):
                    candidates.append(
                        (date.fromisoformat(iso), "Same class session")
                    )

        for candidate_day, match_description in candidates:
            iso = candidate_day.isoformat()

            if iso == source_iso or iso in seen_dates:
                continue

            info = _lookup(candidate_day)

            if info["semester"] != target["name"]:
                continue

            seen_dates.add(iso)
            out.append({
                **info,
                "description": describe(info),
                "match_reason": match_description,
            })

    return sorted(out, key=lambda x: x["date"])



def check():
    """Print likely mistakes in the calendar data and the session counts per weekday."""
    problems = list(PROBLEMS)
    for s in SEMESTERS:
        span = (s["start"], s["end"])
        for label, dates in (("events", s["events"]), ("no_class", s["no_class"]),
                             ("rescheduling", s["rescheduling"])):
            for iso in dates:
                try:
                    if not _within(_d(iso), span):
                        problems.append(f"{s['name']}: {label} date {iso} is outside this semester "
                                        f"({span[0]} to {span[1]}). Wrong year?")
                except ValueError:
                    problems.append(f"{s['name']}: {label} key {iso!r} is not a valid date")
        for iso in s["rescheduling"]:
            if iso not in s["sessions"]:
                problems.append(f"{s['name']}: rescheduled day {iso} is not inside the class period "
                                f"(or falls in a break), so it gets no session")
    print(f"{len(problems)} problem(s) found")
    for p in problems:
        print(" -", p)
    print()
    for s in SEMESTERS:
        top = {}
        for n, wd in s["sessions"].values():
            top[wd] = max(top.get(wd, 0), n)
        print(f"{s['name']}: last session per weekday: "
              + ", ".join(f"{DAY_NAMES[w][:3]} {top[w]}" for w in sorted(top)))
    return problems


if __name__ == "__main__":
    check()