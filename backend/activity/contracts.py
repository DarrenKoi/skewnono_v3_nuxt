"""Stable response contracts for activity endpoints."""

from __future__ import annotations

from typing import TypedDict


__all__ = [
    "FeatureCount",
    "FeatureUse",
    "DailyCount",
    "VisitCount",
    "MeThisMonth",
    "MeResponse",
    "SummaryResponse",
    "UserListRow",
    "UserListResponse",
    "NamedUserListRow",
    "NamedUserListResponse",
    "UserHistoryResponse",
    "FabPageCount",
    "FabUsageRow",
    "FabUsageResponse",
    "FamilyUsageRow",
    "FamilyUsageResponse",
    "DailyVisitors",
    "VisitorsResponse",
]


class FeatureCount(TypedDict):
    feature: str
    count: int


class FeatureUse(TypedDict):
    """One feature and when this person last opened it.

    Separate from ``FeatureCount`` on purpose: that one answers "how often",
    this one answers "how recently", and a shape carrying both would invite a
    reader to rank by the field the query did not order on.
    """

    feature: str
    at: str


class DailyCount(TypedDict):
    """One day of the 30일 활동 series, plus what was called that day.

    ``count`` is every request row (entry + feature kinds). ``features``
    breaks down the feature-kind ones only and is capped, so the parts do NOT
    sum to ``count`` — which is why ``other_count`` is sent rather than left
    to the caller to subtract: entry traffic belongs to no single feature,
    and on a day with more features than the cap a subtraction would fold the
    dropped ones into it silently.
    """

    date: str
    count: int
    features: list[FeatureCount]
    other_count: int


class MeThisMonth(TypedDict):
    requests: int
    days_active: int


class MeResponse(TypedDict):
    user_id: str
    is_admin: bool
    this_month: MeThisMonth
    recent_features: list[FeatureUse]
    daily: list[DailyCount]
    visits: list[VisitCount]
    first_seen: str | None
    last_seen: str | None


class VisitCount(TypedDict):
    """Daily page opens, independent of API request volume (KST)."""

    date: str
    count: int


class SummaryResponse(TypedDict):
    generated_at: str
    dau: int
    wau: int
    mau: int
    top_features_7d: list[FeatureCount]
    top_features_30d: list[FeatureCount]


class UserListRow(TypedDict):
    user_id: str
    requests_30d: int
    days_active_30d: int
    last_seen: str | None
    #: The feature opened most recently, or None for someone whose only rows
    #: are requests (a page whose beacon never fired, or traffic older than
    #: the page-view rollout).
    recent_feature: str | None


class UserListResponse(TypedDict):
    generated_at: str
    users: list[UserListRow]


class NamedUserListRow(UserListRow):
    """A listed user after the route joined the member directory onto it.

    Split from ``UserListRow`` on purpose. The activity providers read the
    logging store, which knows employee numbers and no names or teams at all,
    so making them promise these would be a promise neither adapter could
    keep. They are added in ``routes.py`` from ``_auth.directory``, and this
    is the shape that reaches the SPA.

    Both are None whenever the directory could not answer — no row for that
    empno, Redis unreachable, a malformed document — and either can be None on
    its own, because a member row may be partial. The frontend falls back to
    the employee number alone for the name, and to a dash for the team.

    The directory also carries ``organ_cd`` and ``upper_organ_nm``; they stay
    out of this shape because nothing renders them, and an API field with no
    reader is a field that quietly rots.
    """

    emp_nm: str | None
    dept_nm: str | None


class NamedUserListResponse(TypedDict):
    generated_at: str
    users: list[NamedUserListRow]


class UserHistoryResponse(TypedDict):
    user_id: str
    this_month: MeThisMonth
    recent_features: list[FeatureUse]
    daily: list[DailyCount]
    visits: list[VisitCount]
    first_seen: str | None
    last_seen: str | None


class FabPageCount(TypedDict):
    feature: str
    count: int


class FabUsageRow(TypedDict):
    fab: str
    total: int
    pages: list[FabPageCount]


class FabUsageResponse(TypedDict):
    generated_at: str
    fabs_7d: list[FabUsageRow]
    fabs_30d: list[FabUsageRow]


class DailyVisitors(TypedDict):
    """How many distinct people were active on, and up to, one KST day.

    Not ``VisitCount``: that one counts one person's page opens, this one
    counts people. A person counts on a day they made at least one request —
    the summary cards' definition — so the last entry's three numbers equal
    ``SummaryResponse``'s ``dau``, ``wau`` and ``mau``.

    ``visitors`` is that day alone. ``wau`` and ``mau`` are the distinct people
    over the 7 and 30 days ENDING that day, which is why they are sent rather
    than left to the reader: days are not additive (someone active on two days
    is in both), so no sum of ``visitors`` reproduces them.
    """

    date: str
    visitors: int
    wau: int
    mau: int


class VisitorsResponse(TypedDict):
    """``VISITOR_DAYS`` consecutive KST days, oldest first, today last."""

    generated_at: str
    days: list[DailyVisitors]


class FamilyUsageRow(TypedDict):
    """Page opens under one tool family.

    Both numbers come from ``page_view`` rows — unlike ``FabUsageRow``, whose
    beacons carry no fab and so had to count requests. A beacon names the page
    that was opened, and the page names its family, so this is exact.

    ``total`` is the distinct people who opened a page of this family. It is
    NOT a DAU-style active-user count (that one reads request rows) and the
    families do not add up: someone who works in two is in both.
    """

    #: ``cdsem | hvsem | veritysem | provision | afm`` — the registry slug
    #: that appears in the beacon URL, never the dashed page segment.
    family: str
    total: int
    pages: list[FeatureCount]


class FamilyUsageResponse(TypedDict):
    """Every family, in registry order, including the ones nobody opened.

    A family with no pages built yet is a row of zeros rather than a missing
    row: the page lists all five so a new family's first visit has somewhere
    to appear.
    """

    generated_at: str
    families_7d: list[FamilyUsageRow]
    families_30d: list[FamilyUsageRow]
