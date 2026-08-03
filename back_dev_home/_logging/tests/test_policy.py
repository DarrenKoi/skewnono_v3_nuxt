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
    ) == ("operation", 0)
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="GET",
        path="/api/cdsem/live-alarm",
        status=200,
        feature="live_alarm",
    ) == ("background", 0)
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="GET",
        path="/api/sem-list",
        status=200,
        feature="sem_list",
    ) == ("entry", 1)
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="GET",
        path="/api/cdsem/recipe-search",
        status=200,
        feature="recipe_search",
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
    ) == ("background", 0)
