"""Tests for calendar_kit. Run: python3 lib/test_calendar_kit.py

The expected values are worked out by hand from the rule shapes of the practice brief (holidays, nth business day after
today, last business day of the week). They test the module, not any brief: a final brief passes its own values."""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from calendar_kit import *

cal = make_calendar(holidays=["2026-10-26", "2026-11-11", "2026-11-26", "2026-12-25", "2027-01-01"])
fails = 0
def eq(got, want, what):
    global fails
    if got != want: fails += 1; print("FAIL", what, "got", got, "want", want)

# nth business day after today; today never counts; holidays skipped
eq(nth_business_day_after(d("2026-10-14"), 7, cal), d("2026-10-23"), "7th after Wed 14 Oct")
eq(nth_business_day_after(d("2026-10-14"), 12, cal), d("2026-11-02"), "12th after Wed 14 Oct skips 26 Oct")
eq(nth_business_day_after(d("2026-10-16"), 7, cal), d("2026-10-28"), "7th after Fri 16 Oct skips 26 Oct")
eq(nth_business_day_after(d("2026-10-16"), 12, cal), d("2026-11-04"), "12th after Fri 16 Oct")
eq(nth_business_day_after(d("2026-12-24"), 7, cal), d("2027-01-06"), "7th after 24 Dec skips 25 Dec and 1 Jan")
eq(nth_business_day_after(d("2026-10-17"), 1, cal), d("2026-10-19"), "1st after a Saturday")

# status and next business day
eq(is_business_day(d("2026-10-26"), cal), False, "holiday")
eq(day_status(d("2026-10-17"), cal), "weekend", "Saturday")
eq(next_business_day(d("2026-10-23"), cal), d("2026-10-27"), "after Fri 23 Oct skips weekend and holiday")
eq(next_business_day(d("2026-10-14"), cal, include_today=True), d("2026-10-14"), "today counts when asked")

# last business day of the week
eq(last_business_day_of_week(d("2026-10-14"), cal), d("2026-10-16"), "Friday of this week")
eq(last_business_day_of_week(d("2026-12-21"), cal), d("2026-12-24"), "Thursday when Friday is a holiday")
eq(last_business_day_of_week(d("2026-12-31") + (d("2027-01-01") - d("2026-12-31")) * 0, cal), d("2026-12-31"), "week of 1 Jan")

# this / next weekday
eq(this_weekday(d("2026-10-14"), 4), d("2026-10-16"), "this Friday on a Wednesday")
eq(next_weekday(d("2026-10-14"), 4), d("2026-10-23"), "next Friday on a Wednesday")
eq(next_weekday(d("2026-10-16"), 4), d("2026-10-23"), "next Friday said on a Friday")
eq(end_of_month(d("2026-10-14")), d("2026-10-31"), "end of October")
eq(end_of_month(d("2026-12-03")), d("2026-12-31"), "end of December")

# judging a proposed date
today, late, early = d("2026-10-14"), d("2026-10-23"), d("2026-11-02")
eq(check_date("2026-10-23", today, late, cal), ("ok", late), "the deadline itself is allowed")
eq(check_date("2026-10-17", today, late, cal), ("not_business_day", d("2026-10-19")), "Saturday -> Monday")
eq(check_date("2026-10-26", today, early, cal), ("not_business_day", d("2026-10-27")), "holiday -> next business day")
eq(check_date("2026-10-26", today, late, cal), ("after_deadline", late), "holiday after the deadline")
eq(check_date("2026-10-24", today, late, cal), ("after_deadline", late), "Saturday after deadline Friday: next business day passes it")
eq(check_date("2026-10-13", today, late, cal), ("before_earliest", today), "yesterday -> today")
eq(check_date("2026-10-14", today, late, cal), ("ok", today), "today")
eq(check_date("not a date", today, late, cal), ("unreadable", None), "garbage")
eq(check_date("2027-03-01", today, None, cal), ("ok", d("2027-03-01")), "no deadline")
eq(check_date("2026-10-17", today, late, cal, adjust="previous_business_day"), ("not_business_day", d("2026-10-16")), "previous business day")

# time windows
eq(in_time_window("10:00", "10:00", "19:00"), True, "start included")
eq(in_time_window("19:00", "10:00", "19:00"), True, "end included")
eq(in_time_window("19:01", "10:00", "19:00"), False, "after end")
eq(in_time_window("9", "10:00", "19:00"), False, "unreadable")

# speech and prompt texts
eq(say(d("2026-10-23")), "Friday 23 October", "say")
table = date_table_text(today, [("early", early), ("late", late)], cal, days=14)
eq("2026-10-26 Mon holiday | early: offer Tuesday 27 October | late: after deadline, offer Friday 23 October" in table, True, "table holiday row")
eq("next Friday = Friday 23 October" in relative_dates_text(today, cal), True, "relative text")

# the source must be safe to paste into a code node
src = source()
eq("{" + "{" in src or "}" + "}" in src, False, "no double braces in the source")
eq([l for l in src.splitlines() if l.startswith("import ") or l.startswith("from ")], ["import datetime"], "only datetime is imported at top level")

print("all passed" if not fails else f"{fails} failed")
sys.exit(1 if fails else 0)
