"""Constants both activity adapters must agree on.

The mock (home) and the OpenSearch reader (office) aggregate the same
semantics, so the calendar timezone and the window/cap sizes live here —
importing them from one adapter into the other would couple home boot to
office-only code.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")
TOP_FEATURES_CAP = 10
#: How many distinct features the "최근 쓴 기능" lists show. Distinct is
#: the point — five rows of the same page is not a history.
RECENT_FEATURES_CAP = 5
SPARKLINE_DAYS = 30
