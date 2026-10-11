"""Business-day calendar for phone agents. Generic: every rule value (holidays, weekend, windows) is a parameter.

The source of this file is pasted into a code node of the workflow, so it must stay safe there:
standard library `datetime` only, no double curly braces anywhere, and no function that raises on bad input.

    cal = make_calendar(holidays=["2026-12-25"], weekend=[5, 6])
    nth_business_day_after(d("2026-10-14"), 7, cal)            # today never counts
    check_date(d("2026-10-26"), d("2026-10-14"), d("2026-11-02"), cal)
"""
import datetime

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def d(value):
    """A date from a date, a datetime or a string that starts with YYYY-MM-DD. None when it cannot be read."""
    try:
        if isinstance(value, datetime.datetime): return value.date()
        if isinstance(value, datetime.date): return value
        return datetime.date.fromisoformat(str(value).strip()[:10])
    except Exception:
        return None


def make_calendar(holidays=(), weekend=(5, 6)):
    """holidays: dates or ISO strings. weekend: weekday numbers that are never business days (Monday is 0)."""
    return dict(holidays=set(x for x in (d(h) for h in holidays) if x), weekend=set(int(w) for w in weekend))


def is_business_day(day, cal):
    return day.weekday() not in cal["weekend"] and day not in cal["holidays"]


def day_status(day, cal):
    if day in cal["holidays"]: return "holiday"
    if day.weekday() in cal["weekend"]: return "weekend"
    return "business day"


def next_business_day(day, cal, include_today=False):
    """The first business day after `day` (or `day` itself when include_today and it is one)."""
    x = day if include_today else day + datetime.timedelta(days=1)
    for _ in range(400):
        if is_business_day(x, cal): return x
        x += datetime.timedelta(days=1)
    return None


def nth_business_day_after(day, n, cal):
    """The n-th business day after `day`. `day` itself never counts: n=1 is the next business day."""
    x, count = day, 0
    for _ in range(800):
        x += datetime.timedelta(days=1)
        if is_business_day(x, cal):
            count += 1
            if count >= n: return x
    return None


def business_days_between(start, end, cal):
    """Business days after `start` up to and including `end`."""
    n, x = 0, start
    while x < end:
        x += datetime.timedelta(days=1)
        if is_business_day(x, cal): n += 1
    return n


def week_start(day):
    return day - datetime.timedelta(days=day.weekday())


def last_business_day_of_week(day, cal):
    """The latest business day in the Monday-to-Sunday week of `day`. None when the week has none."""
    monday = week_start(day)
    for i in range(6, -1, -1):
        x = monday + datetime.timedelta(days=i)
        if is_business_day(x, cal): return x
    return None


def this_weekday(day, weekday):
    """'this <weekday>': that weekday in the Monday-to-Sunday week of `day` (can be before `day`)."""
    return week_start(day) + datetime.timedelta(days=weekday)


def next_weekday(day, weekday):
    """'next <weekday>': that weekday in the following calendar week."""
    return week_start(day) + datetime.timedelta(days=7 + weekday)


def end_of_month(day):
    first_next = (day.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    return first_next - datetime.timedelta(days=1)


def check_date(proposed, today, deadline, cal, earliest=None, adjust="next_business_day"):
    """Judge a date the customer proposed for a payment or an appointment.

    Returns (verdict, date to offer or record):
      ("ok", proposed)                 a business day from `earliest` (default today) to `deadline`, both included
      ("before_earliest", x)           before `earliest`; x is the first allowed business day
      ("not_business_day", x)          a weekend day or holiday not after the deadline; x per `adjust`
      ("after_deadline", deadline)     after the deadline, or adjusting would pass it
      ("unreadable", None)
    `deadline` may be None for no deadline. `adjust` is "next_business_day" or "previous_business_day".
    """
    p, t = d(proposed), d(today)
    if p is None or t is None: return ("unreadable", None)
    first = d(earliest) or t
    if p < first:
        return ("before_earliest", next_business_day(first, cal, include_today=True))
    if deadline is not None and p > deadline:
        return ("after_deadline", deadline)
    if is_business_day(p, cal):
        return ("ok", p)
    if adjust == "previous_business_day":
        x = p - datetime.timedelta(days=1)
        while x >= first and not is_business_day(x, cal): x -= datetime.timedelta(days=1)
        if x >= first: return ("not_business_day", x)
    x = next_business_day(p, cal)
    if deadline is not None and (x is None or x > deadline):
        return ("after_deadline", deadline)
    return ("not_business_day", x)


def in_time_window(hhmm, start="00:00", end="23:59"):
    """True when HH:MM is from start to end, both included."""
    try:
        h, m = str(hhmm).strip()[:5].split(":")
        t = int(h) * 60 + int(m)
        a = int(start[:2]) * 60 + int(start[3:5]); b = int(end[:2]) * 60 + int(end[3:5])
        return a <= t <= b
    except Exception:
        return False


def say(day, with_year=False):
    """A date for speech: 'Friday 23 October' (or with the year)."""
    if day is None: return ""
    s = WEEKDAYS[day.weekday()] + " " + str(day.day) + " " + MONTHS[day.month - 1]
    return s + " " + str(day.year) if with_year else s


def relative_dates_text(today, cal):
    """What relative day words mean today, one line each, for a prompt."""
    lines = ["today = " + say(today) + " (" + day_status(today, cal) + ")",
             "tomorrow = " + say(today + datetime.timedelta(days=1)),
             "end of this month = " + say(end_of_month(today))]
    for i, name in enumerate(WEEKDAYS):
        lines.append("this " + name + " = " + say(this_weekday(today, i)) + "; next " + name + " = " + say(next_weekday(today, i)))
    return "\n".join(lines)


def date_table_text(today, deadlines, cal, days=35, earliest=None):
    """One line per calendar day from today: its status and what to offer if the customer proposes it, per deadline.

    deadlines: an ordered list of (label, deadline date or None), for example [("early band", d1), ("late band", d2)].
    The model reads the answer instead of computing it.
    """
    lines = []
    for i in range(days + 1):
        x = today + datetime.timedelta(days=i)
        parts = [x.isoformat() + " " + WEEKDAYS[x.weekday()][:3] + " " + day_status(x, cal)]
        for label, dl in deadlines:
            verdict, y = check_date(x, today, dl, cal, earliest=earliest)
            if verdict == "ok": what = "OK"
            elif verdict == "not_business_day": what = "offer " + say(y)
            elif verdict == "after_deadline": what = "after deadline, offer " + say(y)
            else: what = "offer " + say(y)
            parts.append(label + ": " + what)
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def source():
    """This file's source, to paste into a code node in front of the node's own code."""
    import inspect, sys
    return inspect.getsource(sys.modules[__name__])
