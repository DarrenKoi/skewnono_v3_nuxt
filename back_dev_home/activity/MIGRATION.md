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

`providers/shared.py` holds the three constants both adapters must agree on —
the `Asia/Seoul` calendar zone, the top-features cap of 10, and the 30-day
sparkline window. It exists so the home adapter never imports the office
module: `mock.py` used to take `KST` from `opensearch_reader.py`, which made
every home boot load office-only code. Change a window size there, not in one
adapter.

## What the data means

A request document counts toward activity only if it satisfies all of:

- `event=request`
- `activity_weight=1`
- `activity_kind` is `entry` or `feature`
- it carries an identified person's `user_id`

`entry` is the landing request on `/api/sem-list`. It counts toward active
users, request totals and first/last seen, but **not** toward the top-feature or
FAB-page rankings. Only `feature` documents contribute to feature rankings and
page counts.

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

Returns the signed-in user's request count for this month, active days, feature
ranking, 30-day daily series, and retained-window first/last seen. An unknown
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
`days_active_30d`, `last_seen` and the feature-only `favorite_feature`, sorted
by `(-requests_30d, user_id)`.

### `GET /api/activity/users/<user_id>`

**Admin only** (`403 forbidden` otherwise). Returns the personal history shape.
No result is `404 not_found`; a failed OpenSearch query is
`503 activity_query_failed`.

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
