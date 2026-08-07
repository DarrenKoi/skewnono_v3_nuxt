"""Route → feature-slug classifier for usage analytics.

This is the *only* place that decides what counts as a distinct feature.
When a route moves between path hierarchies, update the mapping here so both
old and new paths resolve to the same slug — that preserves continuity in the
OpenSearch usage_events index and the Redis HINCRBY hashes.

Never rename an existing slug after it has been written; that splits the
historical series. Add aliases instead (multiple paths → same slug).
"""

from __future__ import annotations

import re


# Ordered list of (path_prefix, slug). Longest prefix wins, so put more
# specific rules first. Trailing slashes in the prefix are stripped at lookup.
#
# Granularity is PAGE-LEVEL on purpose: one slug per Nuxt page/tab, not per
# endpoint. CD-SEM and HV-SEM share page slugs (recipe_search covers both
# /api/cdsem/recipe-search and /api/hvsem/recipe-search) because the ranking
# should answer "which page is popular", not "which tool family".
_TOOL_SLUGS = ("cdsem", "hvsem")

# Shared Hitachi e-beam pages mounted at /api/<tool_slug>/<page>.
_TOOL_PAGE_RULES: tuple[tuple[str, str], ...] = (
    ("device-statistics", "device_statistics"),
    ("recipe-search",     "recipe_search"),
    ("recipe-tat",        "recipe_tat"),
    ("fail-issue",        "fail_issue"),
    ("storage",           "storage"),
    ("ppid-unavailable",  "storage"),   # StorageView side panel
    ("hardware",          "hardware"),
    ("live-alarm",        "live_alarm"),
    ("skew",              "skew_check"),
    ("pm-planning",       "pm_planning"),
)

_FEATURE_RULES: tuple[tuple[str, str], ...] = tuple(
    (f"/api/{tool}/{page}", slug)
    for tool in _TOOL_SLUGS
    for page, slug in _TOOL_PAGE_RULES
) + (
    # Skewvoir workspace (MSR file/image APIs).
    ("/api/msr-file",           "skewvoir"),
    ("/api/msr-files",          "skewvoir"),
    ("/api/msr-image",          "skewvoir"),
    # Plural, and NOT a subtree of the singular rule above: the lookup only
    # matches an exact path or a `prefix + "/"` child, so /api/msr-images
    # needs its own line. Without it the fallback emitted the slug
    # "msr-images" — dashed, which the index field and Redis hash key
    # convention forbid, and a phantom feature beside skewvoir's own.
    ("/api/msr-images",         "skewvoir"),
    # Standalone pages.
    ("/api/sem-list",           "sem_list"),
    ("/api/meas-hist",          "meas_hist"),
    ("/api/afm",                "afm"),
    ("/api/afm-files",          "afm"),
    ("/api/announcements",      "announcements"),
    ("/api/health",             "health"),
    ("/api/account/api-tokens", "api_tokens"),
    ("/api/activity",           "activity"),
    ("/api/admin/logs",         "admin_logs"),
)


def route_to_feature(path: str) -> str:
    """Map a request path to a stable feature slug.

    Unknown /api/* paths fall back to the first path segment after /api/ so
    new endpoints get reasonable grouping until they're added explicitly.
    Non-API paths return "(non-api)" — useful for filtering them out.
    """
    if not path:
        return "(empty)"
    for prefix, slug in _FEATURE_RULES:
        if path == prefix or path.startswith(prefix + "/"):
            return slug
    if not path.startswith("/api/"):
        return "(non-api)"
    parts = [p for p in path.split("/") if p]
    return parts[1] if len(parts) >= 2 else "(root)"


# ---------------------------------------------------------------------------
# Frontend page paths → the SAME slugs as above.
#
# This is a second map rather than a rewrite of route_to_feature because the
# two vocabularies are genuinely different shapes: /ebeam/<tool>/<fab>/
# recipe-status is ONE route carrying TWO features (?tab=), which has no
# counterpart on the API side. Slug constants are shared, so the historical
# series stays continuous.
#
# Paths arrive query-inclusive. Only recipe-status reads the query.
_OPS_PAGE_PREFIXES = (
    "/activity",
    "/admin",
    "/settings",
    "/endpoints",
    "/identify",
    "/intro",
)

# Page segment (after /ebeam/<tool>/<fab>/) → slug. Longest match wins, so the
# nested recipe-search children are listed before their parent.
_PAGE_RULES: tuple[tuple[str, str], ...] = (
    ("recipe-search/meas-hist", "meas_hist"),
    ("recipe-search",           "recipe_search"),
    ("device-statistics",       "device_statistics"),
    ("skewvoir",                "skewvoir"),
    ("storage",                 "storage"),
    ("hardware",                "hardware"),
    ("live-alarm",              "live_alarm"),
    ("skew-check",              "skew_check"),
    ("pm-planning",             "pm_planning"),
    # Legacy routes; middleware redirects them to recipe-status, but a beacon
    # that beats the redirect must still land on the right slug.
    ("recipe-tat",              "recipe_tat"),
    ("fail-issue",              "fail_issue"),
)

_STANDALONE_PAGE_RULES: tuple[tuple[str, str], ...] = (
    ("/tool-roster", "sem_list"),
    ("/mag-pixel",   "mag_pixel"),
    ("/chat",        "chat"),
    ("/afm",         "afm"),
)

# Frontend tool segment → the slug route_to_feature already emits for the same
# tool (/api/cdsem/... → "cdsem"). One tool, one slug, in both vocabularies.
_TOOL_SEGMENT_SLUGS = {
    "cd-sem": "cdsem",
    "hv-sem": "hvsem",
}

# Fab segments are [fab] route params. Same shape the frontend uses in
# plugins/persist-fab.client.ts, so the two stay in agreement about what a fab
# looks like.
_FAB_SEGMENT = re.compile(r"^[RM]\d{1,2}[A-C]?$", re.IGNORECASE)

# ?tab= on recipe-status is the real identity. align and meas are two views of
# one feature: /api/<tool>/fail-issue returns align_fail_* and meas_fail_*
# together.
_RECIPE_STATUS_TABS = {
    "tat":   "recipe_tat",
    "align": "fail_issue",
    "meas":  "fail_issue",
}


def _split_query(path: str) -> tuple[str, str]:
    head, _, query = path.partition("?")
    return head.rstrip("/") or "/", query


def _query_value(query: str, key: str) -> str | None:
    for pair in query.split("&"):
        name, _, value = pair.partition("=")
        if name == key and value:
            return value
    return None


def page_to_feature(path: str) -> str | None:
    """Map a FRONTEND route path to a feature slug for page-view ranking.

    ``path`` includes the query string. Returns None for ops pages (logged but
    never ranked, matching _OPERATION_PREFIXES) and for a page whose identity
    is not yet resolvable — the caller must not record a page view for None.
    """
    if not path:
        return None
    clean, query = _split_query(path)
    if any(
        clean == prefix or clean.startswith(prefix + "/")
        for prefix in _OPS_PAGE_PREFIXES
    ):
        return None
    if clean == "/":
        # The hub everyone passes through on the way somewhere else. A real
        # page, but not a rankable one: its count is "who opened the app",
        # which DAU/WAU/MAU already report, and leaving it in pushes a genuine
        # feature out of the Top 10.
        #
        # Not in _OPS_PAGE_PREFIXES because it is product surface, not an ops
        # screen — the exclusion is for a different reason and says so here.
        return None
    for prefix, slug in _STANDALONE_PAGE_RULES:
        if clean == prefix or clean.startswith(prefix + "/"):
            return slug

    parts = [part for part in clean.split("/") if part]
    if parts and parts[0] == "ebeam":
        # /ebeam/<tool>/[<fab>/]<page...> — the fab is a [fab] route param,
        # present on most pages and absent on the fabless ones
        # (device-statistics, skewvoir). Drop it FIRST so both shapes reduce to
        # the same page segment; checking for a page before dropping the fab
        # would compare "M14" against the page rules and never match.
        rest = parts[2:]
        if rest and _FAB_SEGMENT.match(rest[0]):
            rest = rest[1:]
        # Nothing left after the fab: /ebeam/<tool> and /ebeam/<tool>/<fab> are
        # both [fab]/index.vue, which renders EbeamToolInventoryView (장비 상태)
        # for all four tool families. One page, so one slug — the tool-segment
        # fallback at the bottom of this branch used to catch it and split it
        # four ways, which is the whole reason CD-SEM appeared in the ranking.
        #
        # `len(parts) >= 2` because a bare /ebeam names no tool and is not that
        # page; it keeps the fallback, which the frontend matches with its own
        # /ebeam early return.
        if len(parts) >= 2 and not rest:
            return "tool_inventory"
        if rest and rest[0] == "recipe-status":
            tab = _query_value(query, "tab")
            # No tab yet: RecipeStatusView's mount-time router.replace supplies
            # one within a tick. Waiting is what stops one visit counting twice.
            return _RECIPE_STATUS_TABS.get(tab) if tab else None
        joined = "/".join(rest)
        for prefix, slug in _PAGE_RULES:
            if joined == prefix or joined.startswith(prefix + "/"):
                return slug
        # Unmapped ebeam page: group by tool, matching route_to_feature's
        # fallback, which yields cdsem/hvsem for unmapped API paths. The tool
        # segment is spelled with a hyphen in the frontend route and without
        # one in the API path, so it is translated rather than underscored —
        # writing cd_sem here would be a SECOND spelling of a slug that has
        # already been written, and this module forbids that (see header).
        tool = parts[1] if len(parts) >= 2 else "ebeam"
        return _TOOL_SEGMENT_SLUGS.get(tool, tool.replace("-", "_"))

    return parts[0].replace("-", "_") if parts else None
