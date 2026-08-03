# 사용 통계 Page-View Beacon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rank `/activity` (사용 통계) pages by page opens instead of `/api/*` request volume, so `mag-pixel` (zero API calls) becomes visible and `live-alarm` (15 s poller) stops distorting the ranking.

**Architecture:** A client-only Nuxt plugin POSTs `/api/page-view` when the *page identity* changes. That endpoint returns `204` and exists only to be logged — the existing `_logging/activity.py` middleware already ships every request to OpenSearch (office) or the in-memory mock (home), so no new store and no office write path are introduced. A new `activity_kind` value, `page_view`, carries weight 1; the ranking aggregations switch to it while every other metric stays request-based. Spec: `docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md`.

**Tech Stack:** Python 3.14, Flask, pytest (`.venv/bin/python -m pytest`), TypedDict contracts. Nuxt 4 SPA (`ssr: false`), `node --test` over `app/**/*.test.ts`. No new dependencies on either side.

## Global Constraints

- Run pytest from the repo root as `.venv/bin/python -m pytest` — `-m` is what puts the root on `sys.path`.
- Never rename an existing feature slug. `feature_map.py` states this: renaming splits the historical series. `recipe_tat` and `fail_issue` stay as they are.
- `back_dev_home/activity/providers/office.py` is gitignored. Only ever edit the tracked `office_example.py`; the office copy is made with `cp` there.
- The task list below touches more than one file, so per `CLAUDE.md` do the whole thing in a `git worktree` (`git worktree add ../skewnono-page-view -b work/page-view`) and tear it down after the merge.
- Commit with explicit pathspecs only. `git add -A`, `git add .`, and `git commit -a` are banned in this repo.
- Run `npm run lint:md` from the repo root after any Markdown edit.
- Only the **ranking** aggregations change unit. `dau`/`wau`/`mau`, `this_month.requests`, the `daily[]` sparkline and the FAB page rankings stay request-based (`entry`/`feature`).

**Known consequence, accepted:** a user who only ever opens zero-API pages (e.g. `mag-pixel`) appears in the page ranking but not in `dau`/`wau`/`mau`, because those stay request-based by decision. Do not "fix" this by letting `page_view` increment the request-based counters — that would silently change what `this_month.requests` means.

---

### Task 1: Stop counting `/api/announcements` as usage

Independent of the beacon and ships on its own. The announcements banner is mounted in both layouts, so it fires once per page load and measures sessions, not interest in a page.

**Files:**

- Modify: `back_dev_home/_logging/policy.py:21-25`
- Test: `back_dev_home/_logging/tests/test_policy.py`

**Interfaces:**

- Consumes: nothing.
- Produces: nothing new. `classify_activity` keeps its signature.

- [ ] **Step 1: Write the failing test**

Append to `back_dev_home/_logging/tests/test_policy.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/_logging/tests/test_policy.py::test_announcements_banner_is_background_not_a_counted_feature -v`

Expected: FAIL — `assert ('feature', 1) == ('background', 0)`

- [ ] **Step 3: Write minimal implementation**

In `back_dev_home/_logging/policy.py`, replace the `_BACKGROUND_EXACT` block:

```python
_BACKGROUND_EXACT = {
    # Mounted in both layouts (default.vue, hub.vue), so it fires once per
    # page load for every user on every page. Counting it would rank session
    # volume rather than interest in any one page.
    "/api/announcements",
    "/api/cdsem/live-alarm",
    "/api/hvsem/live-alarm",
    "/api/msr-image",
}
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest back_dev_home/_logging -q`

Expected: PASS, no regressions.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/_logging/policy.py back_dev_home/_logging/tests/test_policy.py
git commit -m "fix(activity): stop counting the announcements banner as usage"
```

---

### Task 2: Add the `page_view` activity kind

**Files:**

- Modify: `back_dev_home/_logging/policy.py:7`, `:15-20`, `:42-69`
- Test: `back_dev_home/_logging/tests/test_policy.py`

**Interfaces:**

- Consumes: Task 1's `_BACKGROUND_EXACT`.
- Produces: `ActivityKind` now includes `"page_view"`. `classify_activity(path="/api/page-view", ...)` returns `ActivityDecision("page_view", 1)`. Tasks 4, 6 and 7 depend on this exact string.

- [ ] **Step 1: Write the failing test**

Append to `back_dev_home/_logging/tests/test_policy.py`:

```python
def test_page_view_beacon_is_its_own_counted_kind():
    assert classify_activity(
        user_id="u1",
        api_token_id=None,
        method="POST",
        path="/api/page-view",
        status=204,
        feature="mag_pixel",
    ) == ("page_view", 1)


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
        ) == ("operation", 0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/_logging/tests/test_policy.py -k page_view -v`

Expected: FAIL — the first returns `('feature', 1)`.

- [ ] **Step 3: Write minimal implementation**

In `back_dev_home/_logging/policy.py`, widen the kind union:

```python
ActivityKind = Literal["entry", "feature", "background", "operation", "page_view"]
```

Add the constant next to `_BACKGROUND_EXACT`:

```python
# The beacon endpoint. Mounted at the top level rather than under
# /api/activity on purpose: that prefix is in _OPERATION_PREFIXES, and
# nesting the beacon there would need a carve-out inside the precedence
# chain below — the one place in this module that must stay readable.
PAGE_VIEW_PATH = "/api/page-view"
```

Then, in `classify_activity`, insert the page-view branch immediately after the
disqualifier block and before the `_BACKGROUND_EXACT` check:

```python
    if path == PAGE_VIEW_PATH:
        return ActivityDecision("page_view", 1)
    if path in _BACKGROUND_EXACT or any(
```

The disqualifier block above it already handles anonymous, token, `OPTIONS`/`HEAD`
and `status >= 400`, so those cases fall through to `operation` unchanged.

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest back_dev_home/_logging -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/_logging/policy.py back_dev_home/_logging/tests/test_policy.py
git commit -m "feat(activity): add the page_view activity kind"
```

---

### Task 3: Map frontend paths to feature slugs

**Files:**

- Modify: `back_dev_home/_logging/feature_map.py` (append; do not alter `route_to_feature`)
- Test: `back_dev_home/_logging/tests/test_feature_map.py`

**Interfaces:**

- Consumes: nothing.
- Produces: `page_to_feature(path: str) -> str | None`. Takes a **query-inclusive** path (`"/ebeam/cd-sem/M14/recipe-status?tab=tat"`). Returns a slug, or `None` when the path is an ops page or the identity is not yet resolvable. Task 5 calls it.

- [ ] **Step 1: Write the failing test**

Append to `back_dev_home/_logging/tests/test_feature_map.py`:

```python
import pytest

from back_dev_home._logging.feature_map import page_to_feature


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/_logging/tests/test_feature_map.py -v`

Expected: FAIL at import — `cannot import name 'page_to_feature'`.

- [ ] **Step 3: Write minimal implementation**

Append to `back_dev_home/_logging/feature_map.py`:

```python
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
        return "home"
    for prefix, slug in _STANDALONE_PAGE_RULES:
        if clean == prefix or clean.startswith(prefix + "/"):
            return slug

    parts = [part for part in clean.split("/") if part]
    if parts and parts[0] == "ebeam":
        # /ebeam/<tool>/<rest...>; <rest> may or may not start with a fab.
        rest = parts[2:]
        if rest and rest[0] == "recipe-status":
            tab = _query_value(query, "tab")
            # No tab yet: RecipeStatusView's mount-time router.replace supplies
            # one within a tick. Waiting is what stops one visit counting twice.
            return _RECIPE_STATUS_TABS.get(tab) if tab else None
        # Drop a leading fab segment so /ebeam/cd-sem/M14/storage and
        # /ebeam/cd-sem/device-statistics both reduce to their page segment.
        for candidate in (rest, rest[1:]):
            joined = "/".join(candidate)
            for prefix, slug in _PAGE_RULES:
                if joined == prefix or joined.startswith(prefix + "/"):
                    return slug
        # Unmapped ebeam page: group by tool, matching route_to_feature's
        # fallback, which yields cdsem/hvsem for unmapped API paths.
        return parts[1].replace("-", "_") if len(parts) >= 2 else "ebeam"

    return parts[0].replace("-", "_") if parts else None
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest back_dev_home/_logging -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/_logging/feature_map.py back_dev_home/_logging/tests/test_feature_map.py
git commit -m "feat(activity): map frontend page paths to feature slugs"
```

---

### Task 4: Let a handler promote the page slug onto the log row

The middleware derives `feature` from `request.path`, which for a beacon is
`/api/page-view`. The handler must be able to say "file this under `mag_pixel`".

**Files:**

- Modify: `back_dev_home/_logging/activity.py:55-58`, `:150-156`
- Test: `back_dev_home/_logging/tests/test_activity_middleware.py`

**Interfaces:**

- Consumes: Task 2's `page_view` kind.
- Produces: `promote_page_view(slug: str) -> None`, importable from
  `back_dev_home._logging.activity`. Task 5 calls it.

- [ ] **Step 1: Write the failing test**

Read `back_dev_home/_logging/tests/test_activity_middleware.py` first — reuse its
existing `make_app` / `records` / `recorded` fixtures rather than building a new
app. Append:

```python
def test_a_promoted_page_slug_becomes_the_logged_feature(make_app, records):
    """Without this the beacon would rank a feature called "page-view"."""
    from back_dev_home._logging.activity import promote_page_view

    app = make_app()

    @app.post("/api/page-view")
    def _beacon():
        promote_page_view("mag_pixel")
        return "", 204

    app.test_client().post("/api/page-view", json={"path": "/mag-pixel"})

    record = records[-1]
    assert record.feature == "mag_pixel"
    assert (record.activity_kind, record.activity_weight) == ("page_view", 1)


def test_an_unpromoted_request_still_uses_the_path(make_app, records):
    make_app().test_client().get("/api/cdsem/recipe-search")

    assert records[-1].feature == "recipe_search"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/_logging/tests/test_activity_middleware.py -k promoted -v`

Expected: FAIL — `cannot import name 'promote_page_view'`.

- [ ] **Step 3: Write minimal implementation**

In `back_dev_home/_logging/activity.py`, add beside `promote_request_fab_names`:

```python
def promote_page_view(slug: str) -> None:
    """Declare which PAGE this request represents, overriding the path.

    The beacon's own path is /api/page-view, which says nothing about what
    the user opened. Same mechanism as promote_request_fab_names: the handler
    puts it on ``g``, the after_request middleware reads it.
    """
    g._activity_page_slug = slug
```

In `_emit`, replace the `feature` line:

```python
        feature = getattr(g, "_activity_page_slug", None) or route_to_feature(path)
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest back_dev_home/_logging -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/_logging/activity.py back_dev_home/_logging/tests/test_activity_middleware.py
git commit -m "feat(activity): let a handler promote the page slug onto the log row"
```

---

### Task 5: Add the `POST /api/page-view` endpoint

**Files:**

- Modify: `back_dev_home/activity/routes.py`
- Test: `back_dev_home/activity/tests/test_routes.py`

**Interfaces:**

- Consumes: `page_to_feature` (Task 3), `promote_page_view` (Task 4).
- Produces: `POST /api/page-view` with body `{"path": "<query-inclusive path>"}`
  → `204` on success, `400` on a missing/blank path. Task 8's plugin calls it.

- [ ] **Step 1: Write the failing test**

Append to `back_dev_home/activity/tests/test_routes.py` (reuse the module's
existing client fixture):

```python
def test_page_view_beacon_returns_204(client):
    response = client.post("/api/page-view", json={"path": "/mag-pixel"})

    assert response.status_code == 204
    assert response.get_data() == b""


def test_page_view_beacon_rejects_a_missing_path(client):
    assert client.post("/api/page-view", json={}).status_code == 400
    assert client.post("/api/page-view", json={"path": ""}).status_code == 400
    assert client.post("/api/page-view", data="not json").status_code == 400


def test_an_unresolvable_page_is_accepted_but_not_ranked(client):
    """An ops page or a tab-less recipe-status is a 204 that records nothing.

    A 400 here would make the browser console noisy for a case that is not an
    error — the plugin cannot know which paths the backend ranks.
    """
    assert client.post("/api/page-view", json={"path": "/settings"}).status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/activity/tests/test_routes.py -k page_view -v`

Expected: FAIL — 404, the route does not exist.

- [ ] **Step 3: Write minimal implementation**

In `back_dev_home/activity/routes.py`, extend the imports:

```python
from flask import Blueprint, g, jsonify, request

from .._logging.activity import promote_page_view
from .._logging.feature_map import page_to_feature
```

and append the route:

```python
# Deliberately NOT under /api/activity: that prefix is in _OPERATION_PREFIXES,
# so nesting the beacon there would classify every page view as weight 0.
#
# The handler does no work. Its entire purpose is to exist so the after_request
# middleware logs a row, which is what carries the page view to OpenSearch at
# the office and to the mock store at home — no new store, and no office write
# path, which no office_example.py in this repo has.
@bp.post("/page-view")
def page_view():
    payload = request.get_json(silent=True)
    path = payload.get("path") if isinstance(payload, dict) else None
    if not isinstance(path, str) or not path.strip():
        return error_json("bad_request", "path is required", 400)
    slug = page_to_feature(path)
    if slug:
        promote_page_view(slug)
    # An unresolvable path (ops page, tab not yet in the URL) is still a 204:
    # the client cannot know which paths rank, and a 400 would be console noise
    # for something that is not an error.
    return "", 204
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest back_dev_home/activity -q`

Expected: PASS.

- [ ] **Step 5: Verify the whole hop by hand**

```bash
.venv/bin/python index.py &
sleep 4
curl -s -o /dev/null -w "%{http_code}\n" -b "LASTUSER=local-dev" \
  -H 'Content-Type: application/json' -d '{"path":"/mag-pixel"}' \
  http://localhost:5050/api/page-view
curl -s -b "LASTUSER=local-dev" http://localhost:5050/api/activity/me | head -c 400
```

Expected: `204`, and the Flask log line for the beacon shows `path=/api/page-view`
while its structured `feature` is `mag_pixel`. Kill the server afterwards.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/activity/routes.py back_dev_home/activity/tests/test_routes.py
git commit -m "feat(activity): add the POST /api/page-view beacon endpoint"
```

---

### Task 6: Rank from page views in the mock provider

**Files:**

- Modify: `back_dev_home/activity/providers/mock.py:139-177` (`record_request`),
  `:347-400` (`_DEMO_USERS`, `_seed_feature`), and the module docstring
- Test: `back_dev_home/activity/tests/test_mock_provider.py`

**Interfaces:**

- Consumes: the `"page_view"` kind string from Task 2.
- Produces: no signature change. `record_request(user_id, feature, activity_kind, fab_name_list)` keeps its four parameters — `data.py` and the middleware are untouched.

- [ ] **Step 1: Write the failing test**

Append to `back_dev_home/activity/tests/test_mock_provider.py`:

```python
def test_rankings_come_from_page_views_not_requests(reset_state):
    """A poller must not outrank a page someone actually opened."""
    for _ in range(50):
        mock.record_request("u1", "live_alarm", "feature", ["M14"])
    mock.record_request("u1", "mag_pixel", "page_view", [])

    top = mock.get_me("u1")["top_features"]

    assert [row["feature"] for row in top] == ["mag_pixel"]


def test_page_views_do_not_inflate_the_request_counters(reset_state):
    """this_month.requests and the sparkline stay request-based by decision."""
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "mag_pixel", "page_view", [])

    assert mock.get_me("u1")["this_month"]["requests"] == 1


def test_fab_page_rankings_stay_request_based(reset_state):
    """Beacons carry no fab_name, so FAB pages must keep counting requests."""
    mock.record_request("u1", "storage", "feature", ["M14"])
    mock.record_request("u1", "mag_pixel", "page_view", ["M14"])

    fabs = {row["fab"]: row for row in mock.get_fab_page_usage()["fabs_30d"]}

    assert [row["feature"] for row in fabs["M14"]["pages"]] == ["storage"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/activity/tests/test_mock_provider.py -k "page_view or rankings" -v`

Expected: FAIL — the first returns `["live_alarm"]`; page views are dropped entirely by the `activity_kind not in {"entry", "feature"}` guard.

- [ ] **Step 3: Write minimal implementation**

Replace `record_request` in `back_dev_home/activity/providers/mock.py`:

```python
def record_request(
    user_id: str,
    feature: str,
    activity_kind: str,
    fab_name_list: list[str],
) -> None:
    """Record one already-classified human entry, feature or page-view event.

    Two units live in this store on purpose and must not be mixed:

    * request rows (entry/feature) drive the daily series, this_month,
      active-user counts and the FAB page rankings;
    * page_view rows drive the feature rankings ONLY.

    Mixing them would silently redefine this_month.requests. See
    docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md.
    """

    if activity_kind not in {"entry", "feature", "page_view"}:
        return

    now = _now()
    today = _kst_date(now)
    fabs = fab_name_list or ["미지정"]

    with _lock:
        state = _users.get(user_id)
        if state is None:
            state = _UserState(
                user_id=user_id,
                first_seen=now,
            )
            _users[user_id] = state

        if activity_kind == "page_view":
            # Rankings only. A page open is not a request, so it must not
            # touch state.daily / daily_fabs / last_seen.
            state.by_feature[feature] = state.by_feature.get(feature, 0) + 1
            daily_features = state.daily_features.setdefault(today, {})
            daily_features[feature] = daily_features.get(feature, 0) + 1
            _prune_old_days(state, today)
            return

        state.daily[today] = state.daily.get(today, 0) + 1
        state.daily_fabs.setdefault(today, set()).update(fabs)
        state.last_seen = now
        _prune_old_days(state, today)

        if activity_kind != "feature":
            return

        daily_fab_features = state.daily_fab_features.setdefault(today, {})
        for fab in fabs:
            fab_features = daily_fab_features.setdefault(fab, {})
            fab_features[feature] = fab_features.get(feature, 0) + 1
```

Note what moved: `state.by_feature` and `state.daily_features` are now written
**only** by the `page_view` branch, and `daily_fab_features` **only** by the
request branch.

- [ ] **Step 4: Seed demo page views**

Home has no real traffic, so the rankings would render empty. Give `_DEMO_USERS`
an explicit page-view column rather than deriving one from the request totals —
a derived number would teach a false correlation between requests and opens.

Change the `_DEMO_USERS` type annotation and add a fifth element to each tuple:

```python
# (user_id, fab, request feature totals, page-view totals, days of activity
# ending today). ``sem_list`` stands in for entry traffic — see _seed_feature.
#
# Page-view totals are listed separately, not derived from the request totals:
# the two have no fixed ratio in reality (mag-pixel makes no requests at all,
# live-alarm makes hundreds per open), and a derived number would teach a
# relationship the office data does not have.
_DEMO_USERS: list[tuple[str, str, dict[str, int], dict[str, int], int]] = [
    (
        "kim.minju",
        "M14",
        {"sem_list": 220, "recipe_search": 160, "meas_hist": 45, "fail_issue": 30},
        {"recipe_search": 34, "meas_hist": 12, "fail_issue": 9, "mag_pixel": 4},
        14,
    ),
    (
        "park.jinho",
        "M16B",
        {"recipe_search": 190, "sem_list": 120, "recipe_tat": 65, "storage": 25},
        {"recipe_search": 28, "recipe_tat": 15, "storage": 11, "live_alarm": 6},
        12,
    ),
    (
        "lee.soyoung",
        "M11",
        {"sem_list": 140, "storage": 80, "fail_issue": 55, "hardware": 20},
        {"storage": 22, "fail_issue": 14, "hardware": 8, "live_alarm": 5},
        9,
    ),
    (
        "choi.eunwoo",
        "R3",
        {"recipe_tat": 70, "sem_list": 60, "recipe_search": 40, "device_statistics": 25},
        {"recipe_tat": 12, "recipe_search": 9, "device_statistics": 7, "chat": 3},
        6,
    ),
    (
        "jung.hari",
        "M15",
        {"skewvoir": 90, "sem_list": 30, "afm": 25, "meas_hist": 15},
        {"skewvoir": 19, "afm": 6, "meas_hist": 5, "mag_pixel": 3},
        4,
    ),
]
```

Then update `seed_demo_users` (currently at `mock.py:443-460`) to unpack the new
element. Replace its loop body:

```python
    with _lock:
        for user_id, fab, features, page_views, days_back in _DEMO_USERS:
            if user_id in _users:
                continue
            state = _UserState(
                user_id=user_id,
                first_seen=now - timedelta(days=days_back),
                last_seen=now - timedelta(hours=1),
            )
            for feature, total in features.items():
                _seed_feature(state, fab, feature, total, days_back, today)
            for feature, total in page_views.items():
                _seed_page_views(state, feature, total, days_back, today)
            _users[user_id] = state
```

Add the seeding helper next to `_seed_feature`:

```python
def _seed_page_views(
    state: _UserState,
    feature: str,
    total: int,
    days_back: int,
    today: date,
) -> None:
    """Spread ``total`` page opens evenly over the last ``days_back`` days.

    Deliberately does NOT touch state.daily or daily_fab_features: page views
    feed the rankings only, exactly as record_request splits them.
    """
    if days_back <= 0 or total <= 0:
        return
    per_day, remainder = divmod(total, days_back)
    for offset in range(days_back):
        count = per_day + (1 if offset < remainder else 0)
        if count == 0:
            continue
        day = today - timedelta(days=offset)
        state.by_feature[feature] = state.by_feature.get(feature, 0) + count
        daily = state.daily_features.setdefault(day, {})
        daily[feature] = daily.get(feature, 0) + count
```

Then remove the `by_feature` / `daily_features` writes from `_seed_feature`, so
seeded requests stop feeding the rankings — leave its `daily`, `daily_fabs` and
`daily_fab_features` writes alone.

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest back_dev_home/activity -q`

Expected: PASS. If a pre-existing seed test asserts a ranking built from request
totals, update its expectation to the page-view totals above — that test is
asserting the behaviour this task deliberately changes.

- [ ] **Step 6: Commit**

```bash
git add back_dev_home/activity/providers/mock.py back_dev_home/activity/tests/test_mock_provider.py
git commit -m "feat(activity): rank from page views in the mock provider"
```

---

### Task 7: Split the kind filters in the OpenSearch reader

**Files:**

- Modify: `back_dev_home/activity/providers/opensearch_reader.py:38-46`, `:138`,
  `:158`, `:173-184`, `:264-282`, `:284-310`, and the two `feature_only` blocks
- Test: `back_dev_home/activity/tests/test_office_template.py`

**Interfaces:**

- Consumes: the `"page_view"` kind string from Task 2.
- Produces: no signature change. The reader's public functions keep their contracts.

- [ ] **Step 1: Write the failing test**

`test_office_template.py` already injects a fake search client:
`_reader(responses)` returns `(reader, search, aliases)` and `search.bodies` is
the list of query bodies sent. Reuse it — do not invent a second harness. Append:

```python
def _kind_terms(node, found=None):
    """Every activity_kind value asserted anywhere in a query body."""
    found = [] if found is None else found
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("term", "terms") and isinstance(value, dict) and "activity_kind" in value:
                entry = value["activity_kind"]
                found.extend(entry if isinstance(entry, list) else [entry])
            else:
                _kind_terms(value, found)
    elif isinstance(node, list):
        for item in node:
            _kind_terms(item, found)
    return found


def test_summary_ranks_page_views_but_counts_users_from_requests():
    reader, search, _ = _reader([_summary_response()])

    reader.get_summary()

    body = search.bodies[-1]
    ranking = body["aggs"]["top_features_7d"]["filter"]
    assert _kind_terms(ranking) == ["page_view"]

    dau = body["aggs"]["dau"]["filter"]
    assert sorted(_kind_terms(dau)) == ["entry", "feature"]


def test_fab_page_ranking_stays_request_based():
    """Beacons carry no fab_name, so this aggregation cannot switch."""
    reader, search, _ = _reader([_fab_response()])

    reader.get_fab_page_usage()

    fab_agg = search.bodies[-1]["aggs"]
    assert "page_view" not in _kind_terms(fab_agg)
    assert "feature" in _kind_terms(fab_agg)
```

Build `_summary_response()` / `_fab_response()` from the aggregation payloads the
existing `test_summary_normalizes_cardinality_and_trailing_windows` and
`test_fab_totals_use_distinct_users_and_normalize_missing_keys` already construct
inline — extract them into helpers rather than duplicating the literals.

**Two existing tests assert the behaviour this task changes and must be updated,
not deleted:**

- `test_history_query_uses_kst_bounds_and_feature_only_ranking` (`:87`) — its
  ranking assertion moves to `page_view`, and the name should become
  `..._page_view_ranking`.
- `test_users_are_paged_sorted_and_favorite_is_feature_only` (`:189`) —
  `favorite_feature` now comes from page views; rename to `..._favorite_is_page_view_only`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/activity/tests/test_office_template.py -k "page_view or fab_usage" -v`

Expected: FAIL — the ranking filter still says `feature`.

- [ ] **Step 3: Write minimal implementation**

At the top of `opensearch_reader.py`, next to `COMPOSITE_PAGE_SIZE`:

```python
# Two units share one index. Request rows answer "how much work happened";
# page_view rows answer "which page did people open". Every aggregation must
# say which it means — see the beacon design spec.
REQUEST_KINDS = ["entry", "feature"]
RANKING_KIND = "page_view"


def _kind_window(start: datetime, now: datetime, kinds: list[str]) -> dict[str, Any]:
    return {
        "bool": {
            "filter": [
                {
                    "range": {
                        "@timestamp": {
                            "gte": start.isoformat(),
                            "lte": now.isoformat(),
                        }
                    }
                },
                {"terms": {"activity_kind": kinds}},
            ]
        }
    }
```

Widen the base query so page-view rows are reachable at all:

```python
def _activity_filters(user_id: str | None = None) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"term": {"event": "request"}},
        {"term": {"activity_weight": 1}},
        # Widened for page views. Because this is the TOP-LEVEL query, every
        # aggregation below must now state its own kind — a request-based agg
        # that omits it would silently start counting page views.
        {"terms": {"activity_kind": ["entry", "feature", "page_view"]}},
    ]
    if user_id is not None:
        filters.append({"term": {"user_id": user_id}})
    return filters
```

Then, in `_history_query`, make the two request-based windows explicit:

```python
                "this_month": {
                    "filter": _kind_window(month_start, now, REQUEST_KINDS),
```

```python
                "daily": {
                    "filter": _kind_window(day_30, now, REQUEST_KINDS),
```

and switch the ranking agg:

```python
                "features": {
                    "filter": {"term": {"activity_kind": RANKING_KIND}},
```

In `get_summary`, replace both inner helpers:

```python
        def user_window(start: datetime) -> dict[str, Any]:
            return {
                "filter": _kind_window(start, now, REQUEST_KINDS),
                "aggs": {
                    "users": {
                        "cardinality": {
                            "field": "user_id",
                            "precision_threshold": CARDINALITY_PRECISION,
                        }
                    }
                },
            }

        def feature_window(start: datetime) -> dict[str, Any]:
            return {
                "filter": _kind_window(start, now, [RANKING_KIND]),
                "aggs": {
                    "items": {
                        "terms": {
                            "field": "feature",
                            "size": TOP_FEATURES_CAP,
                            "order": {"_count": "desc"},
                        }
                    }
                },
            }
```

Finally the two `feature_only` blocks — they look identical but must diverge:

- the one inside the **users-list** aggregation (feeding `favorite_feature`)
  becomes `{"term": {"activity_kind": RANKING_KIND}}`;
- the one inside the **fab-usage** aggregation (feeding `pages`) stays
  `{"term": {"activity_kind": "feature"}}` and gains this comment:

```python
                                # Stays request-based: beacons carry no
                                # fab_name (it is only known once the user has
                                # picked a fab and a data request goes out), so
                                # page views cannot answer a per-FAB question.
```

Note that `_hits_total` on the history query now counts page-view rows too;
`this_month.requests` reads from the `this_month` agg, not from the total, so
the response is unaffected. Confirm with the existing history test.

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest back_dev_home/activity tests/test_office_adapter_parity.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/activity/providers/opensearch_reader.py back_dev_home/activity/tests/test_office_template.py
git commit -m "feat(activity): rank from page views in the OpenSearch reader"
```

---

### Task 8: Resolve page identity on the client

Pure function, separately tested. `npm test` runs `node --test` over
`app/**/*.test.ts` and handles pure functions only — which is exactly why the
rules live here rather than inside the plugin.

**Files:**

- Create: `front-dev-home/app/utils/pageIdentity.ts`
- Create: `front-dev-home/app/utils/pageIdentity.test.ts`

**Interfaces:**

- Consumes: nothing.
- Produces: `resolvePageIdentity(path: string, query: Record<string, unknown>): string | null`
  and `buildPageViewPath(path: string, query: Record<string, unknown>): string`.
  Task 9's plugin imports both.

- [ ] **Step 1: Write the failing test**

Create `front-dev-home/app/utils/pageIdentity.test.ts`:

```typescript
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { resolvePageIdentity, buildPageViewPath } from './pageIdentity.ts'

test('a fab switch on the same page is the same identity', () => {
  const a = resolvePageIdentity('/ebeam/cd-sem/M14/storage', {})
  const b = resolvePageIdentity('/ebeam/cd-sem/M16B/storage', {})

  assert.equal(a, b)
})

test('a filter query change is the same identity', () => {
  const a = resolvePageIdentity('/ebeam/cd-sem/M14/storage', {})
  const b = resolvePageIdentity('/ebeam/cd-sem/M14/storage', { ppid: 'X1' })

  assert.equal(a, b)
})

test('different pages are different identities', () => {
  assert.notEqual(
    resolvePageIdentity('/ebeam/cd-sem/M14/storage', {}),
    resolvePageIdentity('/ebeam/cd-sem/M14/hardware', {})
  )
})

test('recipe-status tabs are three different identities', () => {
  const tat = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat' })
  const align = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'align' })
  const meas = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'meas' })

  assert.equal(new Set([tat, align, meas]).size, 3)
})

test('recipe-status without a tab is unresolved', () => {
  // RecipeStatusView writes ?tab= back on mount; firing before that would
  // count one visit twice.
  assert.equal(resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', {}), null)
})

test('an array-valued tab takes its first entry', () => {
  // Vue router surfaces a repeated query key as an array.
  assert.equal(
    resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: ['tat', 'align'] }),
    resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat' })
  )
})

test('the reported path carries the tab and nothing else', () => {
  assert.equal(
    buildPageViewPath('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat', ppid: 'X1' }),
    '/ebeam/cd-sem/M14/recipe-status?tab=tat'
  )
  assert.equal(
    buildPageViewPath('/ebeam/cd-sem/M14/storage', { ppid: 'X1' }),
    '/ebeam/cd-sem/M14/storage'
  )
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `front-dev-home/`): `npm test`

Expected: FAIL — cannot resolve `./pageIdentity.ts`.

- [ ] **Step 3: Write minimal implementation**

Create `front-dev-home/app/utils/pageIdentity.ts`:

```typescript
/** Page identity for usage beaconing — see
 *  docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md
 *
 *  Identity answers ONE question: "is this the same page as a moment ago?"
 *  It is not a feature slug. Slug vocabulary lives on the backend
 *  (`_logging/feature_map.py`) so the two can never drift apart.
 *
 *  Almost every query param is state within a page (fab, ppid, filters) and
 *  must not re-fire the beacon. `tab` on recipe-status is the exception: that
 *  route is a shell over two genuinely different features. */

// Fab segments are `[fab]` route params, so the same page under two fabs has
// two paths. Matches fab_name shape, same as plugins/persist-fab.client.ts.
const FAB_SEGMENT = /^[RM]\d{1,2}[A-C]?$/i

const TAB_ROUTE = 'recipe-status'
const VALID_TABS = new Set(['tat', 'align', 'meas'])

const firstValue = (raw: unknown): string | null => {
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value ? value : null
}

const canonicalPath = (path: string): string =>
  path
    .split('/')
    .filter(segment => segment && !FAB_SEGMENT.test(segment))
    .join('/')

export const resolvePageIdentity = (
  path: string,
  query: Record<string, unknown>
): string | null => {
  const canonical = canonicalPath(path)
  if (!canonical.endsWith(TAB_ROUTE)) return canonical

  // No tab yet — RecipeStatusView's mount-time router.replace supplies one
  // within a tick, and that navigation is the one worth counting.
  const tab = firstValue(query.tab)
  if (!tab || !VALID_TABS.has(tab)) return null
  return `${canonical}?tab=${tab}`
}

export const buildPageViewPath = (
  path: string,
  query: Record<string, unknown>
): string => {
  const tab = firstValue(query.tab)
  if (path.includes(TAB_ROUTE) && tab && VALID_TABS.has(tab)) {
    return `${path}?tab=${tab}`
  }
  return path
}
```

- [ ] **Step 4: Run the tests**

Run (from `front-dev-home/`): `npm test && npm run typecheck && npm run lint`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/pageIdentity.ts front-dev-home/app/utils/pageIdentity.test.ts
git commit -m "feat(activity): resolve page identity for usage beaconing"
```

---

### Task 9: Fire the beacon and label the new pages

**Files:**

- Create: `front-dev-home/app/plugins/pageView.client.ts`
- Modify: `front-dev-home/app/utils/activity.ts:5-25`
- Test: manual browser verification (there is no component/plugin test harness in this repo)

**Interfaces:**

- Consumes: `resolvePageIdentity` / `buildPageViewPath` (Task 8), `POST /api/page-view` (Task 5).
- Produces: nothing other tasks depend on.

- [ ] **Step 1: Add the new feature labels**

In `front-dev-home/app/utils/activity.ts`, add to `FEATURE_LABELS`, keeping the
existing alphabetical order by key:

```typescript
  chat: 'AI 어시스턴트',
  home: '홈',
  live_alarm: 'Live Alarm',
  mag_pixel: 'Mag/Pixel 가이드',
```

Leave the `announcements: '공지사항'` entry in place — historical rows already
carry that slug, so the label is still needed to render them in 운영 로그 even
though nothing new will be counted under it.

Update the file's header comment, which currently claims `cdsem`/`hvsem` only
appear via the unmapped-endpoint fallback:

```typescript
// Page-level slugs — see back_dev_home/_logging/feature_map.py, which owns both
// the API-path map and the frontend-path map used by the page-view beacon.
// `cdsem` / `hvsem` only appear via the fallback for unmapped paths.
```

- [ ] **Step 2: Write the plugin**

Create `front-dev-home/app/plugins/pageView.client.ts`:

```typescript
import { resolvePageIdentity, buildPageViewPath } from '~/utils/pageIdentity'
import { joinApiPath } from '~/utils/apiPath'

/** Reports page opens for 사용 통계. See
 *  docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md
 *
 *  Fire-and-forget by design: usage telemetry must never block navigation or
 *  surface an error. A dropped beacon costs one row. */
export default defineNuxtPlugin(() => {
  const router = useRouter()
  const config = useRuntimeConfig()
  const url = joinApiPath(config.public.apiBase, '/page-view')

  let lastIdentity: string | null = null

  const report = (path: string, query: Record<string, unknown>) => {
    const identity = resolvePageIdentity(path, query)
    // null = identity not resolvable yet (recipe-status before its tab lands).
    // Unchanged = a fab switch or a filter change, not a new page open.
    if (!identity || identity === lastIdentity) return
    lastIdentity = identity

    $fetch(url, {
      method: 'POST',
      body: { path: buildPageViewPath(path, query) }
    }).catch(() => {
      // Swallowed on purpose. A 429 from the shared rate limiter is the
      // expected failure under fast tab-flipping and is not worth a console
      // line the user cannot act on.
    })
  }

  router.afterEach((to) => {
    report(to.path, to.query)
  })

  // afterEach does not run for the first load.
  const start = router.currentRoute.value
  report(start.path, start.query)
})
```

- [ ] **Step 3: Verify in the browser**

Start both servers per the `verify` skill (`.venv/bin/python index.py`, then
`npm run dev` from `front-dev-home/`), then with the network panel open:

1. Load `/mag-pixel` → exactly one `POST /api/page-view` with `{"path":"/mag-pixel"}`, status 204.
2. Navigate to `/ebeam/cd-sem/M14/storage`, then switch the fab to M16B → the fab switch fires **no** second beacon.
3. Navigate to `/ebeam/cd-sem/M14/recipe-status` → exactly **one** beacon, carrying `?tab=`, not two.
4. Click the Align Fail tab → one more beacon with `?tab=align`.
5. Open `/activity` → `mag_pixel` and `live_alarm` appear in 페이지 순위 with the labels from Step 1, and `live_alarm` is not inflated after leaving the page open for a minute.

- [ ] **Step 4: Run the checks**

Run (from `front-dev-home/`): `npm test && npm run typecheck && npm run lint`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/plugins/pageView.client.ts front-dev-home/app/utils/activity.ts
git commit -m "feat(activity): fire the page-view beacon on route change"
```

---

### Task 10: Say on screen when page-view collection started

Spec §7: rankings start empty and fill over 30 days. Without a caption, an
almost-empty 인기 기능 Top 10 reads as a broken page rather than a young one.

**Files:**

- Modify: `front-dev-home/app/utils/activity.ts`
- Modify: `front-dev-home/app/pages/activity.vue:220-240`
- Test: `front-dev-home/app/utils/activity.test.ts` (create if absent)

**Interfaces:**

- Consumes: nothing.
- Produces: `PAGE_VIEW_SINCE` and
  `pageViewNotice(windowDays: number, today: Date): string | null`.

- [ ] **Step 1: Write the failing test**

```typescript
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { pageViewNotice, PAGE_VIEW_SINCE } from './activity.ts'

test('the notice shows while the window reaches before collection started', () => {
  const since = new Date(`${PAGE_VIEW_SINCE}T00:00:00+09:00`)
  const threeDaysIn = new Date(since.getTime() + 3 * 86_400_000)

  assert.match(pageViewNotice(7, threeDaysIn) ?? '', /2026/)
})

test('the notice disappears once the window is fully covered', () => {
  const since = new Date(`${PAGE_VIEW_SINCE}T00:00:00+09:00`)
  const wellAfter = new Date(since.getTime() + 40 * 86_400_000)

  assert.equal(pageViewNotice(7, wellAfter), null)
  assert.equal(pageViewNotice(30, wellAfter), null)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `front-dev-home/`): `npm test`

Expected: FAIL — `pageViewNotice` is not exported.

- [ ] **Step 3: Write minimal implementation**

Append to `front-dev-home/app/utils/activity.ts`:

```typescript
/** The day page-view ranking began. Rows logged before this are
 *  activity_kind "feature" and are deliberately not backfilled, so a window
 *  reaching further back than this is showing a partial picture and must say
 *  so — an almost-empty ranking otherwise reads as a bug. */
export const PAGE_VIEW_SINCE = '2026-08-04'

export const pageViewNotice = (
  windowDays: number,
  today: Date
): string | null => {
  const since = new Date(`${PAGE_VIEW_SINCE}T00:00:00+09:00`)
  const windowStart = new Date(today.getTime() - (windowDays - 1) * 86_400_000)
  if (windowStart >= since) return null
  return `${PAGE_VIEW_SINCE}부터 페이지 조회 기준으로 집계합니다`
}
```

Set `PAGE_VIEW_SINCE` to the actual deploy date if it is not the day this lands.

- [ ] **Step 4: Render it**

In `front-dev-home/app/pages/activity.vue`, add below the
`<ActivityFeatureBarList>` at `:236`:

```vue
        <p
          v-if="rankingNotice"
          class="mt-2 text-xs text-(--sk-ink-subtle)"
        >
          {{ rankingNotice }}
        </p>
```

and in the script block, beside `topFeaturesForWindow` (`:673`):

```typescript
const rankingNotice = computed(() =>
  pageViewNotice(windowKey.value === '7d' ? 7 : 30, new Date())
)
```

adding `pageViewNotice` to the existing `~/utils/activity` import at `:524`.
Confirm the `--sk-ink-subtle` token exists in `DESIGN.md`; if it does not, use
`--sk-ink-muted`, which the header at `:224` already uses. Never inline a hex
colour.

- [ ] **Step 5: Run the checks**

Run (from `front-dev-home/`): `npm test && npm run typecheck && npm run lint`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/activity.ts front-dev-home/app/utils/activity.test.ts front-dev-home/app/pages/activity.vue
git commit -m "feat(activity): note when page-view ranking started collecting"
```

---

### Task 11: Record the office-DB facts and the new contract

Per `CLAUDE.md`, a new log field or value convention must land in the datatables
doc **and** the feature docs, or the next office session contradicts it.

**Files:**

- Modify: `docs/datatables/skewnono_logging.txt:43-44`
- Modify: `back_dev_home/activity/MIGRATION.md`
- Modify: `docs/api-contracts/activity.yaml`

**Interfaces:**

- Consumes: everything above.
- Produces: nothing executable.

- [ ] **Step 1: Update the logging datatable**

In `docs/datatables/skewnono_logging.txt`, replace the `activity_kind` line:

```text
activity_kind -> keyword: entry | feature | background | operation | page_view
  page_view 는 POST /api/page-view beacon 이 남기는 행이며 feature 필드에는
  beacon 경로가 아니라 사용자가 연 페이지의 slug 이 들어갑니다
  (_logging/activity.py 의 promote_page_view). 순위 집계는 page_view 를,
  요청 총계·활성 사용자·FAB 순위는 entry|feature 를 읽습니다. (2026-08-04)
```

- [ ] **Step 2: Update the activity MIGRATION.md**

Document, in the office-behavior section: the base query now admits
`page_view`; every aggregation states its own kind; the feature rankings read
`page_view` while the FAB `pages` aggregation deliberately still reads
`feature`, because beacons carry no `fab_name`. Note that rankings start empty
at deploy — pre-existing rows are `activity_kind: "feature"` and are not
backfilled.

- [ ] **Step 3: Add the endpoint to the API contract**

In `docs/api-contracts/activity.yaml`, add `POST /api/page-view`: request body
`{"path": string}` (query-inclusive frontend path), responses `204` (recorded or
deliberately unranked) and `400` (missing/blank path). Match the file's existing
style.

- [ ] **Step 4: Lint**

Run from the repo root: `npm run lint:md`

Expected: `0 error(s)`.

- [ ] **Step 5: Commit**

```bash
git add docs/datatables/skewnono_logging.txt back_dev_home/activity/MIGRATION.md docs/api-contracts/activity.yaml
git commit -m "docs(activity): record the page_view kind and beacon contract"
```

---

## Finishing

- [ ] Full backend suite from the repo root: `.venv/bin/python -m pytest -q`
  (expect ~2457 passed; a worktree legitimately skips more than the main
  checkout because gitignored `office.py` copies are absent).
- [ ] Frontend: `npm test && npm run typecheck && npm run lint` from `front-dev-home/`.
- [ ] `npm run lint:md` from the repo root.
- [ ] Merge and tear down the worktree in the same session:

```bash
git -C . merge --ff-only work/page-view && git push
git worktree remove ../skewnono-page-view && git branch -d work/page-view
git worktree list   # must show the main tree alone
```
