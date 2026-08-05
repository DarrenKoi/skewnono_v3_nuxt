from back_dev_home._logging.policy import (
    classify_activity,
    normalize_fab_name_list,
    sanitize_query_string,
)


def test_activity_precedence_is_operation_background_entry_feature():
    assert classify_activity(
        user_id="u1",
        api_token_id="tok",
        method="GET",
        path="/api/sem-list",
        status=200,
        feature="sem_list",
        page_slug=None,
    ) == ("operation", 0)
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="GET",
        path="/api/cdsem/live-alarm",
        status=200,
        feature="live_alarm",
        page_slug=None,
    ) == ("background", 0)
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="GET",
        path="/api/sem-list",
        status=200,
        feature="sem_list",
        page_slug=None,
    ) == ("entry", 1)
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="GET",
        path="/api/cdsem/recipe-search",
        status=200,
        feature="recipe_search",
        page_slug=None,
    ) == ("feature", 1)


def test_failed_anonymous_and_internal_requests_are_operation():
    cases = [
        (None, None, "GET", "/api/cdsem/storage", 200),
        ("u1", None, "GET", "/api/cdsem/storage", 404),
        ("u1", None, "OPTIONS", "/api/cdsem/storage", 200),
        ("u1", None, "HEAD", "/api/sem-list", 200),
        ("u1", None, "GET", "/api/activity/summary", 200),
        ("u1", None, "GET", "/api/admin/logs", 200),
        ("u1", None, "GET", "/api/health/services", 200),
        ("u1", None, "GET", "/login", 200),
    ]
    for user_id, token_id, method, path, status in cases:
        assert classify_activity(
            user_id=user_id,
            api_token_id=token_id,
            method=method,
            path=path,
            status=status,
            feature="x",
            page_slug=None,
        ) == ("operation", 0)


def test_fab_list_is_uppercase_ordered_and_deduplicated():
    assert normalize_fab_name_list(["M14,m16", " M14 ", "", None]) == [
        "M14",
        "M16",
    ]


def test_query_redacts_sensitive_values_and_caps_length():
    sanitized = sanitize_query_string(
        b"fab_name=M14&access_token=secret&password=pw&q=recipe"
    )
    assert "fab_name=M14" in sanitized
    assert "q=recipe" in sanitized
    assert "secret" not in sanitized
    assert "pw" not in sanitized
    assert sanitized.count("%5BREDACTED%5D") == 2
    assert len(sanitize_query_string(("q=" + "x" * 3000).encode())) == 2048


def test_announcements_banner_is_background_not_a_counted_feature():
    """The banner is in both layouts, so it fires on every page load.

    Counting it would rank "how many pages were loaded", not "which page
    people wanted" — the same distortion live-alarm's poller would cause.
    """
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="GET",
        path="/api/announcements",
        status=200,
        feature="announcements",
        page_slug=None,
    ) == ("background", 0)


def test_page_view_beacon_is_its_own_counted_kind():
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="POST",
        path="/api/page-view",
        status=204,
        feature="mag_pixel",
        page_slug="mag_pixel",
    ) == ("page_view", 1)


def test_a_beacon_with_no_promoted_slug_records_nothing():
    """An unresolvable page is still a 204, but it must not become a feature.

    Without a promoted slug the middleware falls back to
    route_to_feature("/api/page-view") — the literal slug "page-view" — so
    counting the row would rank the beacon endpoint itself alongside real
    pages. Promotion is the signal: no slug, no page view.
    """
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="POST",
        path="/api/page-view",
        status=204,
        feature="page-view",
        page_slug=None,
    ) == ("operation", 0)


def test_page_view_beacon_obeys_the_usual_disqualifiers():
    """An unidentified, token-driven or failed beacon is not a page open."""
    for user_id, token_id, status in [
        (None, None, 204),
        ("u1", "tok", 204),
        ("u1", None, 429),
    ]:
        assert classify_activity(
            user_id=user_id,
            api_token_id=token_id,
            method="POST",
            path="/api/page-view",
            status=status,
            feature="mag_pixel",
            page_slug="mag_pixel",
        ) == ("operation", 0)


def test_identity_plumbing_is_never_a_counted_feature():
    """/api/me and /api/identify are the auth gate, not product usage.

    route_to_feature has no rule for either, so its first-segment fallback
    named them "me" and "identify" and the ranking humanized those into "Me"
    and "Identify" — endpoint names sitting in a list of pages. They also
    inflated this_month.requests, which counts deliberate human actions.

    The frontend /identify page is already in _OPS_PAGE_PREFIXES; these are
    its API counterparts, so both vocabularies now agree.
    """
    for method, path in [
        ("GET", "/api/me"),
        ("POST", "/api/identify"),
        ("DELETE", "/api/identify"),
    ]:
        assert classify_activity(
            user_id="u1",
            api_token_id=None,
            method=method,
            path=path,
            status=200,
            feature="x",
            page_slug=None,
        ) == ("operation", 0)


def test_meas_hist_is_not_swallowed_by_the_me_prefix():
    """/api/me is prefix-matched, so a route that merely starts with "me"
    must keep counting. _at_or_below requires a "/" boundary — this is the
    test that holds that boundary in place."""
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="GET",
        path="/api/meas-hist",
        status=200,
        feature="meas_hist",
        page_slug=None,
    ) == ("feature", 1)
