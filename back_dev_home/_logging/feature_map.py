"""Route → feature-slug classifier for usage analytics.

This is the *only* place that decides what counts as a distinct feature.
When a route moves between path hierarchies, update the mapping here so both
old and new paths resolve to the same slug — that preserves continuity in the
OpenSearch usage_events index and the Redis HINCRBY hashes.

Never rename an existing slug after it has been written; that splits the
historical series. Add aliases instead (multiple paths → same slug).
"""

from __future__ import annotations


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
