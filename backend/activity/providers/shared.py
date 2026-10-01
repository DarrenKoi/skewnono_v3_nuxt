"""Constants and definitions both activity adapters must agree on.

The mock (home) and the OpenSearch reader (office) aggregate the same
semantics, so the calendar timezone, the window/cap sizes and the rolling
visitor arithmetic live here — importing them from one adapter into the other
would couple home boot to office-only code.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from ..contracts import DailyVisitors

KST = ZoneInfo("Asia/Seoul")
TOP_FEATURES_CAP = 10
#: How many distinct features the "최근 쓴 기능" lists show. Distinct is
#: the point — five rows of the same page is not a history.
RECENT_FEATURES_CAP = 5
SPARKLINE_DAYS = 30
VISIT_DAYS = 90
#: How far back the admin 방문자 추이 chart reads. The page offers 2주 /
#: 1개월 / 2개월 and slices this one series for all three.
VISITOR_DAYS = 60
WAU_DAYS = 7
MAU_DAYS = 30
#: How much request history the chart needs behind it: its first day's MAU
#: looks ``MAU_DAYS`` back from there, so both adapters read (and the mock
#: retains) this many days rather than ``VISITOR_DAYS``.
VISITOR_LOOKBACK_DAYS = VISITOR_DAYS + MAU_DAYS - 1


def daily_visitor_rows(
    active_days_by_user: Iterable[Collection[date]],
    today: date,
) -> list[DailyVisitors]:
    """DAU, rolling WAU and rolling MAU for each of the last ``VISITOR_DAYS``.

    Takes one collection of active KST dates per person — which is all either
    adapter has to supply — and does the counting here, so home and office
    cannot disagree about what a weekly user is.

    A person active on day ``a`` is a weekly user of ``a`` through ``a + 6``
    and a monthly user of ``a`` through ``a + 29``. Spreading each active day
    forward into a set and counting membership is that rule, with the set
    absorbing overlaps: someone active on two days of one week is still one
    weekly user. Summing daily counts instead would count them twice.
    """
    spans = {"visitors": 1, "wau": WAU_DAYS, "mau": MAU_DAYS}
    counts: dict[str, Counter[date]] = {name: Counter() for name in spans}
    for days in active_days_by_user:
        for name, span in spans.items():
            counts[name].update(
                {
                    day + timedelta(days=offset)
                    for day in days
                    for offset in range(span)
                }
            )
    return [
        {
            "date": day.isoformat(),
            "visitors": counts["visitors"][day],
            "wau": counts["wau"][day],
            "mau": counts["mau"][day],
        }
        for day in (
            today - timedelta(days=offset)
            for offset in range(VISITOR_DAYS - 1, -1, -1)
        )
    ]
