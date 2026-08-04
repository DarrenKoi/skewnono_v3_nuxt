# admin_logs — office migration

## Boundary

`GET /api/admin/logs` behaves as follows, depending on the selected provider:

| Provider | Data source | Uses the network |
| --- | --- | --- |
| `mock` | fixed in-memory demo logs | no |
| `office` | the OpenSearch logging alias selected by `SKEWNONO_LOG_ENV` | yes |

The `mock` provider always returns demo data only, regardless of
`OPENSEARCH_PASSWORD` or the cloud-detection result. The `office` provider does
**not** fall back to mock depending on whether credentials are present; if
configuration or the OpenSearch query fails, the route returns
`503 log_query_failed`.

## Preparing the office adapter

At the office, copy the tracked template:

```bash
cp back_dev_home/admin_logs/providers/office_example.py \
  back_dev_home/admin_logs/providers/office.py
```

`office.py` is gitignored. Do not modify the shared query parser or the response
contract — edit this copy only if the in-house connection needs further
adjustment.

Set the following environment variables:

```dotenv
SKEWNONO_ADMIN_LOGS_PROVIDER=office
SKEWNONO_LOG_ENV=local
```

`SKEWNONO_LOG_ENV` is required and selects the alias:

| Value | Query alias |
| --- | --- |
| `local` | `skewnono_logging_local` |
| `production` | `skewnono_logging` |

OpenSearch connection details are supplied through the `OPENSEARCH_*`
environment variables that `ops_store` reads. The provider contains no branching
on credentials and none on `is_cloud()`.

## Preparing the store

On the company network, review the dry-run output first, then run the command
that actually applies the change:

```bash
.venv/bin/python ops_index_mgmt/skewnono_logging.py \
  --environment all \
  --dry-run
.venv/bin/python ops_index_mgmt/skewnono_logging.py \
  --environment all
```

The second command prepares the policy, template, mappings, initial index and
alias idempotently — but it does modify the shared cluster. Follow
[`docs/back-end/office-data-adapters.md`](../../docs/back-end/office-data-adapters.md)
for the detailed procedure and checklist.

## HTTP contract

The route is protected by `require_admin`. A non-admin gets `403 forbidden`
before the provider is called at all.

Supported query parameters:

- `from`, `to`: a UTC ISO-8601 time range; omitted means the last 24 hours.
  Both values are validated by the shared parser in **both** providers — a
  malformed value is rejected with `400 invalid_log_query` instead of reaching
  OpenSearch (where it would surface as a misleading `503`). A value carrying no
  offset is read as UTC rather than local time (`OFFICE-VERIFY`: assumed to
  match how OpenSearch reads an offset-less date in a range query, unverified
  against the real cluster). Only the mock's filtering depends on that reading;
  the office adapter forwards the caller's string to OpenSearch untouched.
- `page`, `page_size`: default `1` and `50`, maximum page size `200`. If
  `page * page_size` exceeds the OpenSearch result window (10,000), the request
  is rejected with `400 invalid_log_query`.
- `level`, `event`, `method`, `user_id`, `feature`, `path`
- `activity_kind`: narrows the activity classification to one of `entry`,
  `feature`, `page_view`, `background` or `operation`. A `page_view` row is a
  page-open beacon (`POST /api/page-view`); its `feature` field holds the slug
  of the page the user opened, not the beacon's own path.
- `fab_name`: narrows by FAB name. Several may be given comma-separated; they go
  through the same `normalize_fab_name_list` normalization as the writer and are
  matched as a terms query against `fab_name_list`.
- `status_min`, `status_max`
- `q`: free-text search over the field set `FREE_TEXT_FIELDS` in `query.py` —
  the constant is the single definition, so read it there rather than trusting a
  copy of the list here. Both providers cover **the same field set**, but not
  with identical semantics: the office query uses `match_phrase` on the analyzed
  fields (phrase order matters) and case-sensitive `wildcard` on the
  keyword-mapped ones, while the mock lowercases both sides and plain
  substring-matches. Expect the mock to match slightly more liberally.

Invalid numeric or datetime values are converted by the route into
`400 invalid_log_query`.
Configuration errors and OpenSearch query errors are converted into
`503 log_query_failed` with the message `Could not query OpenSearch logs`,
without exposing internal detail.

A successful response follows `LogQueryResponse` in `contracts.py`. In an office
response, `filters` includes the `deployment` and `index_alias` actually queried.
No results is a normal response with `items: []` and `total: 0`, not an error.
`page_count` is the last servable page after clamping to the result window, and
the frontend pagination uses only that value — the 10,000 limit is not
duplicated in the frontend.

## Verify

Verify the deterministic mock contract at home:

```bash
.venv/bin/python -m pytest back_dev_home/admin_logs -q
```

Verify the copied adapter against a real OpenSearch connection at the office:

```bash
SKEWNONO_ADMIN_LOGS_PROVIDER=office \
SKEWNONO_LOG_ENV=local \
.venv/bin/python -m pytest back_dev_home/admin_logs -q
```

If `office.py` is absent, the provider selector fails with a `RuntimeError`
containing the exact copy command. There is no mock fallback in office mode.
