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
_FEATURE_RULES: tuple[tuple[str, str], ...] = (
    ("/api/ebeam/cdsem/recipe-search",     "recipe_search"),
    ("/api/ebeam/cdsem/recipe-tat",        "recipe_tat"),
    ("/api/ebeam/cdsem/device-statistics", "cdsem_device_statistics"),
    ("/api/ebeam/cdsem/storage",           "cdsem_storage"),
    ("/api/ebeam/hvsem/storage",           "hvsem_storage"),
    ("/api/ebeam/cdsem",                   "cdsem"),
    ("/api/ebeam/hvsem",                   "hvsem"),
    ("/api/afm",                           "afm"),
    ("/api/sem-list",                      "sem_list"),
    ("/api/equipment",                     "equipment"),
    ("/api/announcements",                 "announcements"),
    ("/api/fail-issue",                    "fail_issue"),
    ("/api/health",                        "health"),
    ("/api/api-tokens",                    "api_tokens"),
    ("/api/activity",                      "activity"),
    ("/api/admin/logs",                    "admin_logs"),
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
