# activity — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/activity/me

- Handler: `routes.py` → `data.get_me(user_id)` (user id from LASTUSER cookie,
  passed in as `g.user_id`)
- Contract: `MeResponse` —

  ```python
  class MeResponse(TypedDict):
      user_id: str
      is_admin: bool
      this_month: MeThisMonth        # {requests: int, days_active: int}
      top_features: list[FeatureCount]  # [{feature: str, count: int}]
      daily: list[DailyCount]         # [{date: str, count: int}]
      first_seen: str | None
      last_seen: str | None
  ```

- Mock behavior: looks up the in-memory `_users[user_id]` state. `is_admin` is
  computed independently via `_auth.admin.is_admin(user_id)`, not stored on
  the user state. `this_month` sums only days from the 1st of the current
  calendar month through today with `count > 0`. `top_features` is the top 10
  lifetime `by_feature` counts, sorted by `(-count, feature)` (count
  descending, feature name ascending as tie-break). `daily` is always exactly
  30 entries (oldest → newest, today last), one per calendar day, missing
  days filled with `count: 0`.
- Office data source: <!-- OFFICE: OpenSearch activity index name + query -->
- Notes: `get_me` never 404s — an unknown `user_id` returns a fully-zeroed
  response (`this_month: {requests: 0, days_active: 0}`, `top_features: []`,
  `daily` still the 30-day zero series, `first_seen`/`last_seen: null`), not
  an error. Dates in `daily[].date` are `YYYY-MM-DD` (`date.isoformat()`).
  `first_seen`/`last_seen` are UTC ISO-8601 with seconds precision and a
  literal `Z` suffix (`"+00:00"` replaced with `"Z"` — see `_iso()`), or
  `null` if the user has never been recorded.

## Endpoint: GET /api/activity/summary

- Handler: `routes.py` → `data.get_summary()`
- Contract: `SummaryResponse` —

  ```python
  class SummaryResponse(TypedDict):
      generated_at: str
      dau: int
      wau: int
      mau: int
      top_features_7d: list[FeatureCount]
      top_features_30d: list[FeatureCount]
  ```

- Mock behavior: iterates every user in memory. `dau` counts users with
  `count > 0` on the exact current date. `wau` counts users with any activity
  in the trailing 7-day window (today − 6 days through today). `mau` counts
  users active at any point since the 1st of the current calendar month.
  `top_features_7d`/`top_features_30d` are NOT true per-window feature
  tallies — the mock only stores lifetime `by_feature` totals per user, so it
  *approximates* the window breakdown by scaling each user's lifetime feature
  map by that user's share of activity in the window (`_scale_features`).
  Each is capped to the top 10 by `(-count, feature)`.
- Office data source: <!-- OFFICE: OpenSearch usage_events aggregation query / Redis HINCRBY counters -->
- Notes: `generated_at` is stamped at request time (UTC ISO-8601 + `Z`) and is
  a volatile field scrubbed by the parity harness — office does not need to
  match it byte-for-byte, only produce the same shape. The office
  implementation can and should replace the scaling approximation with real
  per-day feature counters (e.g. Redis HINCRBY keyed by day+feature) since
  that data is not available in the home mock.

## Endpoint: GET /api/activity/fabs

- Handler: `routes.py` → `data.get_fab_page_usage()`
- Contract: `FabUsageResponse` —

  ```python
  class FabUsageResponse(TypedDict):
      generated_at: str
      fabs_7d: list[FabUsageRow]   # {fab: str, total: int, pages: list[FabPageCount]}
      fabs_30d: list[FabUsageRow]
  ```

- Mock behavior: buckets users by `state.fab` (falling back to the literal
  string `"미지정"` — "unassigned" — for users with no fab set), then applies
  the same 7-day/30-day windowing and lifetime-scaling approximation as
  `/summary` per fab bucket. Fabs whose windowed total is `<= 0` are dropped
  entirely (not returned as zero rows). Rows are sorted by
  `(-total, fab)` (total descending, fab name ascending as tie-break); each
  row's `pages` list is the same top-10 `(-count, feature)` shape used
  elsewhere.
- Office data source: <!-- OFFICE: OpenSearch usage_events aggregated by fab + feature -->
- Notes: the `"미지정"` placeholder string must be preserved verbatim if the
  frontend renders it directly — do not translate or rename it without
  checking `front-dev-home` usages first. `generated_at` is volatile
  (scrubbed by the parity harness).

## Endpoint: GET /api/activity/users

- Handler: `routes.py` → `data.get_users_list()`
- Contract: `UserListResponse` —

  ```python
  class UserListResponse(TypedDict):
      generated_at: str
      users: list[UserListRow]  # {user_id, requests_30d, days_active_30d, last_seen, favorite_feature}
  ```

- Mock behavior: iterates every user in memory, sums requests and counts
  active days over the trailing 30-day window (today − 29 through today).
  Users whose 30-day total is exactly `0` are **excluded from the list
  entirely** (not returned as zero rows), even if they exist in the
  in-memory user table. `favorite_feature` is the single feature with the
  highest lifetime count (`None` if the user has no feature counts at all).
  Rows are sorted by `(-requests_30d, user_id)` (requests descending, user id
  ascending as tie-break).
- Office data source: <!-- OFFICE: OpenSearch usage_events aggregation by user_id, 30-day window -->
- Notes: `last_seen` uses the same UTC ISO-8601 + `Z` format as `/me`. An
  empty result is a valid response: `{"generated_at": ..., "users": []}`, not
  an error. A freshly-connected office backend may legitimately have no users
  yet; the `/me`+history contract check derives its user id from this list, so
  it exercises identity only when at least one user is present.

## Endpoint: GET /api/activity/users/<user_id>

- Handler: `routes.py` → `data.get_user_history(user_id)`; a `None` result is
  translated to a `404 not_found` JSON error by the route (not by
  `data.py`/the provider itself).
- Contract: `UserHistoryResponse` —

  ```python
  class UserHistoryResponse(TypedDict):
      user_id: str
      this_month: MeThisMonth
      top_features: list[FeatureCount]
      daily: list[DailyCount]
      first_seen: str | None
      last_seen: str | None
  ```

- Mock behavior: identical field derivation to `/me` (same `_history_fields`
  helper), minus `is_admin`. Unlike `/me`, an unknown `user_id` returns
  `None` from the provider (not a zeroed object) — the 404 happens at the
  route layer, so the office adapter must also return `None` for unknown
  users rather than raising or fabricating a response.
- Office data source: <!-- OFFICE: OpenSearch usage_events filtered by user_id -->
- Notes: same date/timestamp formats as `/me`. Returning `None` (not an
  empty dict or `{}`) is required so the existing 404 branch in `routes.py`
  keeps working unmodified.

## Write path: record_request(...)

- Called by `_logging` middleware (`back_dev_home/_logging/activity.py`) on
  every recordable request, after checking `data.is_recordable(user_id, path,
  status)` — a user_id of `None`/`"-"`, non-`/api/` paths, the
  `/api/activity/*` and `/api/admin/logs` prefixes (to avoid the dashboard
  inflating its own counters), and any `status >= 400` are all excluded.
- Mock behavior: `record_request(user_id, method, path, status, feature)`
  unconditionally updates the in-memory `_users[user_id]` state (creates the
  user on first sight, bumps `total`, `by_feature[feature]`,
  `daily[today]`, and `last_seen`) — it does **not** re-check
  `is_recordable` itself despite what `is_recordable`'s docstring claims; the
  middleware's pre-call check is the only gate. Any office reimplementation
  should preserve that division of responsibility rather than double-gating.
- `is_recordable` policy lives in `data.py` (provider-independent) and is
  NOT reimplemented per-provider.
- Office data source: <!-- OFFICE: index/pipeline name -->

## Verify

    SKEWNONO_ACTIVITY_PROVIDER=office .venv/bin/pytest back_dev_home/activity
