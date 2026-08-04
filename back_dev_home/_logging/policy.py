"""Canonical request-activity classification and safe field normalization."""

from collections.abc import Iterable
from typing import Literal, NamedTuple
from urllib.parse import parse_qsl, urlencode

ActivityKind = Literal["entry", "feature", "background", "operation", "page_view"]


class ActivityDecision(NamedTuple):
    kind: ActivityKind
    weight: int


_OPERATION_PREFIXES = (
    "/api/activity",
    "/api/admin",
    "/api/health",
    "/api/account/api-tokens",
)
_BACKGROUND_EXACT = {
    # Mounted in both layouts (default.vue, hub.vue), so it fires once per
    # page load for every user on every page. Counting it would rank session
    # volume rather than interest in any one page.
    "/api/announcements",
    "/api/cdsem/live-alarm",
    "/api/hvsem/live-alarm",
    "/api/msr-image",
}
# The beacon endpoint. Mounted at the top level rather than under
# /api/activity on purpose: that prefix is in _OPERATION_PREFIXES, and
# nesting the beacon there would need a carve-out inside the precedence
# chain below — the one place in this module that must stay readable.
PAGE_VIEW_PATH = "/api/page-view"
_BACKGROUND_CHILD_PREFIXES = ("/api/msr-images",)
_SENSITIVE_QUERY_PARTS = (
    "password",
    "passwd",
    "token",
    "api_key",
    "secret",
    "authorization",
    "cookie",
)


def _at_or_below(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def classify_activity(
    *,
    user_id: str | None,
    api_token_id: str | None,
    method: str,
    path: str,
    status: int,
    feature: str,
    page_slug: str | None,
) -> ActivityDecision:
    if (
        not user_id
        or user_id == "-"
        or api_token_id
        # CORS preflights and probes run the full middleware pipeline but are
        # browser plumbing, not a person using the product.
        or method in ("OPTIONS", "HEAD")
        or status >= 400
        or not path.startswith("/api/")
        or any(_at_or_below(path, prefix) for prefix in _OPERATION_PREFIXES)
    ):
        return ActivityDecision("operation", 0)
    if path == PAGE_VIEW_PATH:
        # Promotion is the signal. The handler calls promote_page_view() only
        # when page_to_feature resolved the reported path, so no slug means the
        # page was unrankable (an ops page, a recipe-status without its tab).
        # Recording it anyway would rank the beacon's own path as a feature.
        return (
            ActivityDecision("page_view", 1)
            if page_slug
            else ActivityDecision("operation", 0)
        )
    if path in _BACKGROUND_EXACT or any(
        path.startswith(prefix + "/") for prefix in _BACKGROUND_CHILD_PREFIXES
    ):
        return ActivityDecision("background", 0)
    if feature == "sem_list":
        return ActivityDecision("entry", 1)
    return ActivityDecision("feature", 1)


def normalize_fab_name_list(
    values: Iterable[str | None],
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        for candidate in value.split(","):
            fab_name = candidate.strip().upper()
            if fab_name and fab_name not in seen:
                seen.add(fab_name)
                normalized.append(fab_name)
    return normalized


def sanitize_query_string(raw: bytes) -> str:
    decoded = raw.decode(errors="replace")
    safe_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(decoded, keep_blank_values=True):
        normalized_key = key.lower().replace("-", "_")
        if any(part in normalized_key for part in _SENSITIVE_QUERY_PARTS):
            value = "[REDACTED]"
        safe_pairs.append((key, value))
    return urlencode(safe_pairs)[:2048]
