# activity — office migration

## Current implementation

The `activity` office adapter aggregates the canonical request log out of the
in-house OpenSearch. It uses neither Redis counters nor a separate
`usage_events` index. A failed office query does **not** fall back to mock — the
route returns `503 activity_query_failed`.

The per-environment source alias is selected by `SKEWNONO_LOG_ENV`:

- `local`: `skewnono_logging_local`
- `production`: `skewnono_logging`

Both aliases live in the same in-house cluster, and
`back_dev_home/_logging/target.py` hands the same target to the writer and the
reader. Connection settings are read from the `OPENSEARCH_*` environment
variables.

`providers/shared.py` holds the four constants both adapters must agree on —
the `Asia/Seoul` calendar zone, the top-features cap of 10, the
recent-features cap of 5, and the 30-day sparkline window. It exists so the home adapter never imports the office
module: `mock.py` used to take `KST` from `opensearch_reader.py`, which made
every home boot load office-only code. Change a window size there, not in one
adapter.

## What the data means

The base query behind every aggregation (`_activity_filters()` in
`providers/opensearch_reader.py`) requires:

- `event=request`
- `activity_weight=1`
- `activity_kind` in `entry`, `feature`, `page_view` by default
- it carries an identified person's `user_id`

That default admits `page_view`, so **every aggregation nested under it
re-states its own kind** — nothing may rely on the top-level filter alone, or
it would silently start counting page views. `providers/opensearch_reader.py`
defines two kind groups: `REQUEST_KINDS = ["entry", "feature"]` (request
volume) and `RANKING_KIND = "page_view"` (which page someone opened):

- **Request-volume aggregations** — `this_month`, `daily`, `dau`/`wau`/`mau`,
  the 30-day user list's `requests_only` (and the `days_active_30d` histogram
  nested under it) — filter to `REQUEST_KINDS`. `entry` (the landing request
  on `/api/sem-list`) counts here, so it contributes to active-user counts,
  personal request totals and the daily sparkline, but not to any ranking.
- **Feature-ranking aggregations** — `features` (the personal
  `recent_features` list), `top_features_7d`/`top_features_30d` (site-wide),
  and the user list's `feature_only` (`recent_feature`) — filter to
  `RANKING_KIND`, i.e. `page_view` only. `feature` (API-request) documents no
  longer feed these rankings; only a fired beacon does.

  The two personal ones are ordered by **recency**, not count: their `terms`
  agg carries `"order": {"last_at": "desc"}` over a `max(@timestamp)`
  sub-agg. Ordering a `terms` agg by a sub-aggregation is approximate — each
  shard returns its own top `shard_size` before the comparison — so both pass
  `shard_size: FEATURE_SHARD_SIZE` (100), comfortably above the few dozen
  slugs in `_logging/feature_map.py`, which makes the order exact. Dropping
  that clause turns the card back into a popularity list without failing
  anything.
- **The per-day breakdown** (`daily.days.features`) is a third kind split:
  it sits *inside* the `REQUEST_KINDS` window and narrows again to
  `activity_kind: "feature"`, because the 30일 활동 bar is clickable and has
  to say what was called that day. Its parts deliberately do **not** sum to
  the bar, so `DailyCount.other_count` carries the difference — read from the
  filter agg's own `doc_count`, never subtracted from the capped bucket list,
  or a day with more features than the cap would fold the dropped ones into
  the entry figure. The mock keeps its own day-grain counter for this rather
  than flattening `daily_fab_features`, which counts a request once per FAB
  it names.
- **`first_seen` and `last_seen`** (in `_history_query`, and the per-user
  `last_seen` in the users-list composite) are deliberately **not**
  kind-filtered. "When did we last see this person" is a presence question,
  not a request-volume one, so `page_view` rows count — a user who only opens
  a page issuing no API calls (e.g. the mag-pixel calculator) would otherwise
  show a null `last_seen` while still appearing in the page list.
- **The FAB page ranking is the one deliberate exception.** `_fab_window()`
  narrows its whole query to `REQUEST_KINDS` (not even `entry`, just
  `["entry", "feature"]` filtered again to the `feature`-only `pages` sub-agg)
  and never admits `page_view`: a beacon carries no `fab_name`, because the
  fab is only known once the user has picked one and a data request goes
  out. Admitting page views here would either drop them into a fabricated
  "미지정" bucket or drop them silently — both wrong — so `get_fab_page_usage`
  stays request-based end to end.

**No backfill, so rankings start empty.** Rows logged before this feature
shipped all carry `activity_kind: "feature"` (`page_view` did not exist as a
classification outcome), so the feature-ranking aggregations above return
nothing for pre-existing history. The site-wide and personal top-feature
lists — and `recent_feature` in the user list — start at zero on deploy and
fill in as real beacons land over the following 30 days. The frontend shows a
caption noting when collection started. This has not been run against a
real office OpenSearch cluster; the aggregation shapes above are read
directly from `opensearch_reader.py` but the resulting numbers are
`OFFICE-VERIFY`.

### Deploy step: `PAGE_VIEW_SINCE`

`front-dev-home/app/utils/activity.ts` holds
`PAGE_VIEW_SINCE = '2026-08-04'` — the day the beacon started collecting **at
home**. Home and office deploy separately by design, so that date is wrong at
the office the moment it is conveyed.

**Set it to the date of the office deploy, as part of that deploy**, before
building the frontend. It is not cosmetic: the constant decides when the
"페이지 조회 기준으로 집계합니다" caption appears. Left at the home date, the
caption claims collection began weeks before any office beacon existed, and it
disappears from the 7-day view while that view is still mostly empty — which is
exactly the "almost-empty ranking reads as a bug" case the caption exists to
prevent.

The same applies again to the production deploy if local and production are
switched on separately: the date belongs to whichever alias the ranking reads
(`SKEWNONO_LOG_ENV`).

Document timestamps are stored in UTC. The following calendar windows are
computed in `Asia/Seoul`:

- DAU: today 00:00 until now.
- WAU and the 7-day rankings: the last 7 calendar days, today included.
- MAU, the 30-day rankings, the user list and the 30-day FAB aggregation: the
  last 30 calendar days, today included.
- Personal `this_month`: the 1st of this month 00:00 until now.
- Personal daily series: 30 dates including today; days with no activity are 0.

`first_seen` is the earliest activity **within the window the alias actually
retains** — roughly 365–372 days in production and 30–37 days in local. It
therefore does not mean the account's permanent first-ever use.

## Endpoint contracts

### `GET /api/activity/me`

Returns the signed-in user's request count for this month, active days, the
five most recently opened features (`recent_features`, newest first, each with
the `at` it was last opened), the 30-day daily series — every day carrying its
own `features` breakdown — and retained-window first/last seen. An unknown
user gets a zero response of the **same shape**, not a 404. `is_admin` is
computed by `_auth.admin.is_admin()`.

### `GET /api/activity/summary`

Returns KST DAU, 7-day WAU, 30-day MAU, and the 7-day and 30-day feature
rankings. Active-user counts are computed as `user_id` cardinality.

### `GET /api/activity/fabs`

Returns per-FAB activity over the last 7 and 30 days. `total` is the count of
**distinct active users**, not of requests. A single request naming several FABs
contributes once to each FAB's bucket. A missing or empty FAB is normalized to
`"미지정"`. Only `feature` documents are included in `pages`.

### `GET /api/activity/users`

**Admin only** (`403 forbidden` otherwise). Reads the full 30-day user
composite aggregation, page by page. Returns `requests_30d`,
`days_active_30d`, `last_seen` and the feature-only `recent_feature` (the
page this person opened most recently), sorted by `(-requests_30d, user_id)`.

The response also carries `emp_nm` and `dept_nm`, but **an office adapter must
not produce them**. The logging store records employee numbers and no names or
teams, so the provider contract stays `UserListRow`; `routes.py` joins the
member directory on top and returns `NamedUserListRow`. That join is one
`HMGET members <empnos…>` via `_auth.directory.lookup_members()`, which decides
for itself whether to dial office Redis or fabricate home rows — so it needs
nothing from either adapter. Both fields are `null` when the directory has no
row for that empno or cannot be reached, and either can be `null` on its own
because a member document may be partial; the table then shows the employee
number alone and a dash for the team.

### `GET /api/activity/users/<user_id>`

**Admin only** (`403 forbidden` otherwise). Returns the personal history shape.
No result is `404 not_found`; a failed OpenSearch query is
`503 activity_query_failed`.

### `POST /api/page-view`

Registered on this same blueprint but deliberately mounted at `/api/page-view`,
not under `/api/activity` — that prefix is an operation prefix
(`_logging/policy.py`), and nesting the beacon there would classify every page
view as `activity_weight=0`. The handler (`routes.py::page_view`) does no
querying itself; it validates `{"path": string}`, resolves it to a feature
slug with `page_to_feature()`, and — if it resolves — calls
`promote_page_view(slug)` so the `after_request` middleware in
`_logging/activity.py` logs a `page_view` row with that slug in `feature`.
Responses are `204` whether or not the path resolved (an unrankable path, e.g.
an ops page or a tab not yet reflected in the URL, is not an error the client
can act on) and `400` only when `path` is missing or blank. There is no office
write path for this route — same as every other `activity` endpoint, writes
happen once, in the shared middleware, not in a provider adapter.

## Who may read what

`/me`, `/summary` and `/fabs` are open to every identified user — they are
aggregates, and a person's own history is theirs to see. The two `/users`
routes enumerate activity per employee, so they are gated with
`_auth.admin.require_admin`, which requires both an admin id **and** a trusted
identity source (a self-declared identity that types an admin's employee
number does not pass). The frontend reads `is_admin` off `/api/activity/me`
and skips the users fetch entirely for non-admins, so the gate is never the
first thing a normal user hits.

## Write path

`back_dev_home/_logging/activity.py` performs the classification and FAB
normalization on every request, and `OpenSearchBulkHandler` stores exactly one
canonical document.

The office adapter's `record_request()` is an **intentional no-op**. Writing
again from the provider adapter would store the same request twice, so no writer
is added there. Only the mock adapter updates process-local state, and it trims
each user's day buckets to the widest read window on every write so a long-lived
process cannot grow without bound.

## Connecting at the office

On the company network, copy the tracked adapter:

```bash
cp back_dev_home/activity/providers/office_example.py \
  back_dev_home/activity/providers/office.py
```

Set the OpenSearch connection and target in `.env`:

```dotenv
SKEWNONO_ACTIVITY_PROVIDER=office
SKEWNONO_LOG_ENV=local
OPENSEARCH_HOST=...
OPENSEARCH_PORT=443
OPENSEARCH_USER=...
OPENSEARCH_PASSWORD=...
```

A production deployment keeps the same cluster settings and only switches to
`SKEWNONO_LOG_ENV=production`.

## Verify

First prepare the alias with `ops_index_mgmt/skewnono_logging.py`, then run the
office provider gate:

```bash
SKEWNONO_ACTIVITY_PROVIDER=office \
SKEWNONO_LOG_ENV=local \
  .venv/bin/python -m pytest back_dev_home/activity -q
```

Then start Flask and check `/api/activity/me`, `/summary`, `/fabs` and `/users`.
Also confirm that with the OpenSearch connection briefly blocked, the response
returns `503 activity_query_failed` rather than leaking a raw cluster error.
