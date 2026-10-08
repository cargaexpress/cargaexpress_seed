"""Business-day math for the SLA (RN-03 and RN-04).

Rules used here:
  - Sundays and destination-country holidays are not business days.
  - Saturday IS a business day (the CA-02 example in the project counts Saturday).
  - Dispatch after 16:00 (local time of the CD) starts counting the next business day.
  - The SLA deadline is the end of the last SLA day (23:59:59, destination time).
"""

import calendar as _calendar
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo


@lru_cache(maxsize=None)
def get_tz(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def local_to_utc(tz_name: str, text: str) -> datetime:
    """Convert 'YYYY-MM-DD HH:MM' written in a local time zone into UTC."""
    naive = datetime.strptime(text, "%Y-%m-%d %H:%M")
    return naive.replace(tzinfo=get_tz(tz_name)).astimezone(timezone.utc)


def quincena_start(day: date) -> date:
    """First day of the calendar half-month that contains `day`."""
    return day.replace(day=1) if day.day <= 15 else day.replace(day=16)


def quincena_end(start: date) -> date:
    if start.day == 1:
        return start.replace(day=15)
    return start.replace(day=_calendar.monthrange(start.year, start.month)[1])


class BusinessCalendar:
    def __init__(self, holidays_by_country: dict):
        self._holidays = {c: frozenset(days) for c, days in holidays_by_country.items()}

    def is_holiday(self, country: str, day: date) -> bool:
        return day in self._holidays.get(country, frozenset())

    def is_business_day(self, country: str, day: date) -> bool:
        return day.weekday() != 6 and not self.is_holiday(country, day)

    def next_business_day(self, country: str, day: date) -> date:
        day += timedelta(days=1)
        while not self.is_business_day(country, day):
            day += timedelta(days=1)
        return day

    def add_business_days(self, country: str, day: date, amount: int) -> date:
        for _ in range(amount):
            day = self.next_business_day(country, day)
        return day

    def sla_start_day(self, country: str, dispatch_local: datetime, cutoff_hour: int = 16) -> date:
        """Day 0 of the SLA. `dispatch_local` is the dispatch time in the CD time zone."""
        day = dispatch_local.date()
        after_cutoff = dispatch_local.time() > time(cutoff_hour, 0)
        if after_cutoff or not self.is_business_day(country, day):
            return self.next_business_day(country, day)
        return day

    def sla_deadline_day(self, country: str, start_day: date, sla_days: int) -> date:
        return self.add_business_days(country, start_day, sla_days)

    def business_days_late(self, country: str, deadline_day: date, delivered_day: date) -> int:
        late = 0
        day = deadline_day
        while day < delivered_day:
            day += timedelta(days=1)
            if self.is_business_day(country, day):
                late += 1
        return late

    def business_hours_between(self, country: str, tz: ZoneInfo, start_utc: datetime, end_utc: datetime) -> float:
        """Hours between two moments, counting only business days (RN-04)."""
        if end_utc <= start_utc:
            return 0.0
        start = start_utc.astimezone(tz)
        end = end_utc.astimezone(tz)
        total = 0.0
        day = start.date()
        while day <= end.date():
            if self.is_business_day(country, day):
                day_start = datetime.combine(day, time.min, tzinfo=tz)
                day_end = day_start + timedelta(days=1)
                low, high = max(start, day_start), min(end, day_end)
                if high > low:
                    total += (high - low).total_seconds() / 3600
            day += timedelta(days=1)
        return total
