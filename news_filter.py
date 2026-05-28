"""
SMC Trading Bot - News Filter (No API Required)
All times in WAT (West African Time, UTC+1).
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from settings import HIGH_IMPACT_EVENTS, NEWS_BLACKOUT_MINUTES

WAT = timezone(timedelta(hours=1))

def now_wat():
    return datetime.now(WAT)

class NewsFilter:
    def __init__(self):
        self.known_events = {
            "NFP": self._is_nfp_time,
            "FOMC": self._is_fomc_time,
            "CPI": self._is_cpi_time,
        }

    def is_high_impact_time(self, symbol: str = "", check_time: Optional[datetime] = None) -> bool:
        if check_time is None:
            check_time = now_wat()

        # Convert to UTC for event checking (events are in UTC)
        if check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=WAT)
        utc_time = check_time.astimezone(timezone.utc)

        for event_name, check_func in self.known_events.items():
            if check_func(utc_time):
                return True
        if self._is_central_bank_time(utc_time):
            return True
        return False

    def _is_nfp_time(self, dt: datetime) -> bool:
        if dt.weekday() != 4:
            return False
        if dt.day > 7:
            return False
        return 12 <= dt.hour < 14 or (dt.hour == 11 and dt.minute >= 30)

    def _is_fomc_time(self, dt: datetime) -> bool:
        if dt.weekday() != 2:
            return False
        week_num = dt.isocalendar()[1]
        if week_num % 6 != 0:
            return False
        return (dt.hour == 17 and dt.minute >= 30) or dt.hour == 18 or (dt.hour == 19 and dt.minute <= 30)

    def _is_cpi_time(self, dt: datetime) -> bool:
        if dt.day < 13 or dt.day > 15:
            return False
        if dt.weekday() not in [1, 2]:
            return False
        return 12 <= dt.hour < 14

    def _is_central_bank_time(self, dt: datetime) -> bool:
        if dt.weekday() == 3 and 10 <= dt.hour < 14:
            return True
        return False

    def get_next_event_warning(self) -> Optional[str]:
        now = now_wat()
        utc_now = now.astimezone(timezone.utc)
        if utc_now.weekday() == 3 and utc_now.day <= 7:
            return "NFP tomorrow - expect volatility"
        if utc_now.weekday() == 4 and utc_now.day <= 7 and utc_now.hour < 12:
            return "NFP today at 13:30 WAT - blackout active"
        return None

_filter = None

def get_news_filter():
    global _filter
    if _filter is None:
        _filter = NewsFilter()
    return _filter
