from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


TOKYO_TZ = ZoneInfo("Asia/Tokyo")


def today_in_tokyo() -> date:
    return datetime.now(TOKYO_TZ).date()
