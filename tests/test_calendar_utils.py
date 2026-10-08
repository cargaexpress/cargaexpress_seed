"""Unit tests for the business-day math (RN-03). No database needed."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from seed.calendar_utils import BusinessCalendar, quincena_end, quincena_start
from seed.reference_data import HOLIDAYS

BOGOTA = ZoneInfo("America/Bogota")
calendar = BusinessCalendar(HOLIDAYS)


def test_ca02_example_friday_after_cutoff_with_monday_holiday():
    # Friday 2026-03-20 17:00, SLA 2 days, Monday 2026-03-23 is a holiday.
    dispatch = datetime(2026, 3, 20, 17, 0, tzinfo=BOGOTA)
    start = calendar.sla_start_day("CO", dispatch)
    assert start == date(2026, 3, 21)                                   # Saturday = day 0
    assert calendar.sla_deadline_day("CO", start, 2) == date(2026, 3, 25)  # Wednesday


def test_dispatch_before_cutoff_starts_the_same_day():
    dispatch = datetime(2026, 3, 10, 15, 59, tzinfo=BOGOTA)   # Tuesday
    assert calendar.sla_start_day("CO", dispatch) == date(2026, 3, 10)


def test_exactly_16_00_is_not_after_the_cutoff():
    assert calendar.sla_start_day("CO", datetime(2026, 3, 10, 16, 0, tzinfo=BOGOTA)) == date(2026, 3, 10)
    assert calendar.sla_start_day("CO", datetime(2026, 3, 10, 16, 1, tzinfo=BOGOTA)) == date(2026, 3, 11)


def test_dispatch_on_sunday_or_holiday_starts_the_next_business_day():
    sunday = datetime(2026, 3, 22, 9, 0, tzinfo=BOGOTA)
    holiday = datetime(2026, 3, 23, 9, 0, tzinfo=BOGOTA)
    assert calendar.sla_start_day("CO", sunday) == date(2026, 3, 24)    # Monday is a holiday
    assert calendar.sla_start_day("CO", holiday) == date(2026, 3, 24)


def test_holidays_depend_on_the_country():
    assert calendar.is_holiday("MX", date(2026, 3, 16))
    assert not calendar.is_holiday("PE", date(2026, 3, 16))


def test_late_days_skip_sundays_and_holidays():
    # Deadline Thursday 2026-04-09, delivered Monday 2026-04-13: Fri, Sat, Mon = 3 days.
    assert calendar.business_days_late("CO", date(2026, 4, 9), date(2026, 4, 13)) == 3
    assert calendar.business_days_late("CO", date(2026, 4, 9), date(2026, 4, 9)) == 0


def test_business_hours_ignore_sundays():
    tz = BOGOTA
    start = datetime(2026, 6, 20, 12, 0, tzinfo=tz)   # Saturday noon
    end = datetime(2026, 6, 22, 12, 0, tzinfo=tz)     # Monday noon
    assert calendar.business_hours_between("CO", tz, start, end) == 24.0   # 12h Sat + 12h Mon


def test_half_months():
    assert quincena_start(date(2026, 4, 15)) == date(2026, 4, 1)
    assert quincena_start(date(2026, 4, 16)) == date(2026, 4, 16)
    assert quincena_end(date(2026, 4, 1)) == date(2026, 4, 15)
    assert quincena_end(date(2026, 2, 16)) == date(2026, 2, 28)
