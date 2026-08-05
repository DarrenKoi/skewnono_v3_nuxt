"""Route → feature-slug classification.

The slugs this returns are written into the OpenSearch usage_events index and
the Redis HINCRBY hashes, so they are not an implementation detail: renaming
one splits the historical series, and mapping two tool families to different
slugs turns one popular page into two unpopular ones. The module says both in
prose; these pin them.
"""

import re

import pytest

from back_dev_home import create_app
from back_dev_home._logging.feature_map import (
    _FEATURE_RULES,
    _TOOL_PAGE_RULES,
    _TOOL_SLUGS,
    page_to_feature,
    route_to_feature,
)
from back_dev_home._logging.policy import PAGE_VIEW_PATH


@pytest.mark.parametrize("page,slug", _TOOL_PAGE_RULES)
def test_cdsem_and_hvsem_share_one_page_slug(page, slug):
    """Granularity is per Nuxt page, not per tool family: the ranking answers
    "which page is popular". A page wired for only one tool would silently
    halve its own count."""
    assert route_to_feature(f"/api/cdsem/{page}") == slug
    assert route_to_feature(f"/api/hvsem/{page}") == slug


def test_aliases_collapse_into_the_slug_they_belong_to():
    """ppid-unavailable is StorageView's side panel, not a page of its own."""
    assert route_to_feature("/api/cdsem/ppid-unavailable") == "storage"
    assert route_to_feature("/api/cdsem/storage") == "storage"


def test_the_msr_apis_all_count_as_skewvoir():
    for path in (
        "/api/msr-file",
        "/api/msr-files",
        "/api/msr-image",
        # Plural: a sibling of /api/msr-image, not a child of it, so the
        # singular rule never covered it.
        "/api/msr-images",
        "/api/msr-images/job-1",
    ):
        assert route_to_feature(path) == "skewvoir", path


def test_the_two_vocabularies_agree_on_live_alarm():
    """The API map and the page map are halves of one vocabulary.

    live-alarm shipped with a page rule and no API rule, so the board's poll
    was filed under the tool fallback while its page views were filed under
    live_alarm — one feature reading as two in the same log.
    """
    assert route_to_feature("/api/cdsem/live-alarm") == "live_alarm"
    assert route_to_feature("/api/hvsem/live-alarm") == "live_alarm"
    assert page_to_feature("/ebeam/cd-sem/M14/live-alarm") == "live_alarm"


def test_a_rule_matches_its_own_subtree():
    assert route_to_feature("/api/sem-list") == "sem_list"
    assert route_to_feature("/api/sem-list/detail") == "sem_list"
    assert route_to_feature("/api/account/api-tokens/abc") == "api_tokens"


def test_a_rule_does_not_match_a_merely_similar_path():
    """The lookup is prefix-based, so the boundary check is the whole safety of
    it: /api/sem-listing is a different endpoint and must not inherit
    sem_list's series."""
    assert route_to_feature("/api/sem-listing") == "sem-listing"
    assert route_to_feature("/api/healthz") == "healthz"


def test_unknown_api_paths_group_by_their_first_segment():
    """A new endpoint lands in a reasonable bucket instead of a nameless one,
    which keeps the dashboard usable between "route shipped" and "rule added"."""
    assert route_to_feature("/api/brand-new/thing") == "brand-new"
    assert route_to_feature("/api/brand-new") == "brand-new"


def test_non_api_and_degenerate_paths_are_tagged_not_dropped():
    """SPA and asset requests pass through the same middleware in cloud mode;
    they get a label the dashboard can filter out rather than a slug that
    inflates a real feature."""
    assert route_to_feature("/sem-list") == "(non-api)"
    assert route_to_feature("/login") == "(non-api)"
    assert route_to_feature("/") == "(non-api)"
    assert route_to_feature("") == "(empty)"
    assert route_to_feature("/api/") == "(root)"


def test_every_rule_is_an_api_prefix_mapped_to_a_stable_slug():
    """Structural guard for rules added later: a prefix without /api/ can never
    match (the middleware only sees request paths), and a slug with a slash or
    a dash breaks the index field and the Redis hash key convention."""
    for prefix, slug in _FEATURE_RULES:
        assert prefix.startswith("/api/"), prefix
        assert not prefix.endswith("/"), prefix
        assert slug.replace("_", "").isalnum() and slug.islower(), slug


def test_more_specific_rules_are_ordered_first():
    """Longest prefix wins is implemented by ORDER, not by length — the first
    match returns. Any rule that is a prefix of an earlier one is unreachable."""
    for i, (prefix, slug) in enumerate(_FEATURE_RULES):
        for earlier_prefix, earlier_slug in _FEATURE_RULES[:i]:
            shadowed = prefix == earlier_prefix or prefix.startswith(
                earlier_prefix + "/"
            )
            assert not shadowed or slug == earlier_slug, (
                f"{prefix} is unreachable behind {earlier_prefix}"
            )


def test_no_registered_route_still_needs_the_fallback():
    """The guard this module was missing.

    The first-segment fallback is a safety net for a route that shipped ahead
    of its rule; a route already in the url_map must not still be leaning on
    it. Both ways that shows up have happened here: an /api/<tool>/... path
    landing on the bare tool slug, which reads as "an e-beam page nobody
    mapped" (live-alarm), and a dashed slug, which the index field and Redis
    hash key convention forbid (msr-images).
    """
    routes = [str(rule) for rule in create_app().url_map.iter_rules()]
    unmapped = []
    for raw in routes:
        if not raw.startswith("/api/"):
            continue
        for tool in _TOOL_SLUGS:
            # Both tool spellings, and any other converter filled with a value
            # that cannot itself match a rule.
            path = re.sub(r"<[^>]+>", "x", raw.replace("<tool_slug>", tool))
            # The beacon's feature is the page it REPORTS, not its own path —
            # the middleware overrides route_to_feature for it.
            if path == PAGE_VIEW_PATH:
                continue
            slug = route_to_feature(path)
            if slug in _TOOL_SLUGS or "-" in slug:
                unmapped.append((path, slug))
    assert not unmapped


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        # The three pages this work exists for.
        ("/mag-pixel", "mag_pixel"),
        ("/chat", "chat"),
        ("/ebeam/cd-sem/M14/live-alarm", "live_alarm"),
        ("/ebeam/hv-sem/M16B/live-alarm", "live_alarm"),
        # recipe-status is one route carrying two features.
        ("/ebeam/cd-sem/M14/recipe-status?tab=tat", "recipe_tat"),
        ("/ebeam/cd-sem/M14/recipe-status?tab=align", "fail_issue"),
        ("/ebeam/cd-sem/M14/recipe-status?tab=meas", "fail_issue"),
        # Deeper routes win over their parent.
        ("/ebeam/cd-sem/M14/recipe-search/meas-hist", "meas_hist"),
        ("/ebeam/cd-sem/M14/recipe-search", "recipe_search"),
        ("/ebeam/cd-sem/M14/recipe-search/compare", "recipe_search"),
        # Fab is a variable segment; both tools share page slugs.
        ("/ebeam/cd-sem/M14/storage", "storage"),
        ("/ebeam/hv-sem/M11/hardware", "hardware"),
        ("/ebeam/cd-sem/R3/skew-check", "skew_check"),
        ("/ebeam/cd-sem/M15/pm-planning", "pm_planning"),
        # Fabless ebeam pages.
        ("/ebeam/cd-sem/device-statistics", "device_statistics"),
        ("/ebeam/cd-sem/device-statistics/comparison", "device_statistics"),
        ("/ebeam/hv-sem/skewvoir/analysis", "skewvoir"),
        # Standalone pages.
        ("/tool-roster", "sem_list"),
        ("/afm/HVM1", "afm"),
        ("/", "home"),
        # Legacy routes that redirect; mapped defensively so a beacon that
        # beats the redirect is not misfiled.
        ("/ebeam/cd-sem/M14/recipe-tat", "recipe_tat"),
        ("/ebeam/cd-sem/M14/fail-issue", "fail_issue"),
    ],
)
def test_page_to_feature_maps_frontend_paths(path, expected):
    assert page_to_feature(path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "/activity",
        "/admin/logs",
        "/admin/access",
        "/settings",
        "/endpoints",
        "/identify",
        "/intro",
    ],
)
def test_ops_pages_are_not_ranked(path):
    assert page_to_feature(path) is None


def test_recipe_status_without_a_tab_is_unresolved():
    """RecipeStatusView writes ?tab= back on mount, so the beacon waits.

    Firing on the bare path AND again after the router.replace would count
    one visit twice.
    """
    assert page_to_feature("/ebeam/cd-sem/M14/recipe-status") is None


def test_unknown_pages_fall_back_to_a_derived_slug():
    """Same policy as route_to_feature: a new page groups sanely until mapped."""
    assert page_to_feature("/thickness") == "thickness"
    assert page_to_feature("/ebeam/verity-sem/M14") == "verity_sem"
