"""Constants and definitions both activity adapters must agree on.

The mock (home) and the OpenSearch reader (office) aggregate the same
semantics, so the calendar timezone, the window/cap sizes and the rolling
visitor arithmetic live here — importing them from one adapter into the other
would couple home boot to office-only code.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Mapping
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from ..._logging.feature_map import TOOL_FAMILIES
from ..._logging.policy import page_view_path
from ..contracts import DailyVisitors, FamilyUsageRow, FeatureCount

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
    # Keyed by day NUMBER (date.toordinal), not by date: spreading a day
    # forward is then integer addition, about seven times cheaper than
    # building a date per step, and the sets work the same.
    counts: dict[str, Counter[int]] = {name: Counter() for name in spans}
    for days in active_days_by_user:
        ordinals = [day.toordinal() for day in days]
        for name, span in spans.items():
            counts[name].update(
                {ordinal + offset for ordinal in ordinals for offset in range(span)}
            )
    return [
        {
            "date": day.isoformat(),
            "visitors": counts["visitors"][day.toordinal()],
            "wau": counts["wau"][day.toordinal()],
            "mau": counts["mau"][day.toordinal()],
        }
        for day in (
            today - timedelta(days=offset)
            for offset in range(VISITOR_DAYS - 1, -1, -1)
        )
    ]


#: Beacon URL → tool family. A page open's family is the URL it was posted to
#: (/api/page-view/<family>), which is the log row's ``path``. Both adapters
#: read it from here: the office maps its ``terms`` buckets, the mock maps the
#: path the middleware hands it.
FAMILY_BY_BEACON_PATH = {
    page_view_path(family): family for family in TOOL_FAMILIES
}


def family_usage_rows(
    openers: Mapping[str, int],
    pages: Mapping[str, list[FeatureCount]],
) -> list[FamilyUsageRow]:
    """Every family, in registry order, whether or not anyone opened it.

    The guarantee ``FamilyUsageResponse`` makes, kept in one place: an adapter
    supplies whatever it counted, keyed by family, and a family it has nothing
    for is a row of zeros rather than a missing row.
    """
    return [
        {
            "family": family,
            "total": openers.get(family, 0),
            "pages": pages.get(family, []),
        }
        for family in TOOL_FAMILIES
    ]
