# admin_logs — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/admin/logs

- Handler: `routes.py` → `data.query_logs(request.args)`. The route sits
  behind the `require_admin` decorator (`back_dev_home/_auth/admin.py`) —
  a non-admin `g.user_id` gets a `403 forbidden` before `data.query_logs`
  is ever called, so the provider itself does not need to re-check admin
  status. The route also translates a `ValueError` raised while parsing
  query params into a `400 invalid_log_query` response, and any other
  exception into a `503 log_query_failed` response — both happen at the
  route layer, not inside the provider.
- Contract: `LogQueryResponse` (with row shape `LogItem`) —

  ```python
  class LogItem(TypedDict, total=False):
      id: str
      index: str
      timestamp: str | None
      level: str | None
      event: str | None
      logger: str | None
      user_id: str | None
      method: str | None
      path: str | None
      status: int | None
      latency_ms: int | None
      feature: str | None
      message: str | None
      exception: dict[str, Any] | None
      raw: dict[str, Any]


  class LogQueryResponse(TypedDict):
      generated_at: str
      page: int
      page_size: int
      total: int
      filters: dict[str, Any]
      items: list[LogItem]
  ```

- Mock behavior: `query_logs(params)` first builds a normalized query +
  filter dict from the raw `Mapping` of query-string params
  (`_build_query`), then dispatches on data source:
  - If `OPENSEARCH_PASSWORD` is unset and the process is not cloud
    (`is_cloud()` false — always true in home/dev), it serves from a
    fixed, in-memory 5-row demo dataset (`_demo_source`) filtered in
    Python (`_matches_demo`) rather than querying OpenSearch at all.
  - If `OPENSEARCH_PASSWORD` is unset and the process IS cloud, it raises
    `RuntimeError("OPENSEARCH_PASSWORD is not configured")` — this is a
    genuine misconfiguration, not a valid response shape.
  - Otherwise it queries the real `ops_store.OSSearch` index
    (`INDEX_ALIAS = "skewnono_logging"`) via `search_raw`, sorted
    `@timestamp` descending, and maps hits through `_item_from_hit`.
  - Time range: `from`/`to` default to the trailing 24 hours
    (`now - 24h` .. `now`) when neither is supplied by the caller;
    supplying only one of the two still yields a partial default (each
    side is defaulted independently, they're read as a pair only when
    both are present).
  - Pagination: `page` defaults to `1`, clamped to a minimum of `1`.
    `page_size` defaults to `50` (`DEFAULT_PAGE_SIZE`), clamped to
    `[1, 200]` (`MAX_PAGE_SIZE`). Unparsable integers raise `ValueError`
    (caught by `routes.py` and turned into the 400 response).
  - Filters accepted: `level` (comma-separated, upper-cased, OR'd via
    `terms`), `event`, `method` (upper-cased), `user_id`, `feature`,
    `path` (substring/wildcard match, case-sensitive in the OpenSearch
    query but case-insensitive in demo mode via `.lower()`),
    `status_min`/`status_max` (inclusive range), and `q` (free-text —
    OR'd across `message`, `exception.message`, `exception.stack`,
    `error_name`, and wildcard `path`/`user_id` in the real query; in demo
    mode it's a case-insensitive substring check over a concatenation of
    `message`, `path`, `user_id`, `error_name`, and every value in
    `exception` if present).
  - Sort order: real OpenSearch query requests `@timestamp` descending
    server-side; the demo dataset is defined newest-first already and is
    not re-sorted after filtering, so it stays newest-first as long as
    `_demo_source` itself is authored in that order.
  - Row shape: `_item_from_hit` maps an OpenSearch hit to `LogItem` —
    `id` from `_id`, `index` from `_index`, and the rest read from
    `_source` (`@timestamp` → `timestamp`, `path` falls back to
    `request_path` if `path` is absent, `raw` is the full untouched
    `_source` dict for callers that need fields not in the narrow
    `LogItem` shape). Demo-mode hits are synthesized with the same
    `_id`/`_index`/`_source` envelope (`_id: "demo-<n>"`,
    `_index: "skewnono_logging-demo"`) so `_item_from_hit` handles both
    paths identically.
  - Empty handling: no rows matching the filters is a valid response —
    `items: []`, `total: 0` — not an error.
  - `generated_at` is stamped at request time, UTC ISO-8601 with seconds
    precision and a literal `Z` suffix (`_iso_z`), and is volatile
    (scrubbed by the parity harness — office does not need to match it
    byte-for-byte).
  - `filters` in the response is the same normalized filter dict used to
    build the query (echoes back the effective `from`/`to`/`level`/etc.,
    plus `demo_mode: true` when the demo path was used) — it reflects
    defaults actually applied, not just what the caller passed in.
- Office data source: <!-- OFFICE: confirm the `skewnono_logging` OpenSearch
  index alias and `ops_store.OSSearch` connection are already live for this
  feature (the mock's OpenSearch branch is real code, not a stub — it may
  already be office-ready once `OPENSEARCH_PASSWORD` is configured) -->
- Notes: the parity harness pins `GET /api/admin/logs` as a `403` response
  (no admin cookie in the harness client), which is a legitimate parity
  value per the harness's own policy — non-200 responses are still valid
  pins. The contract test in `tests/test_contract.py` calls
  `data.query_logs({})` directly (bypassing `require_admin`, since that
  check lives in `routes.py`), so it always exercises the real
  `LogQueryResponse` shape regardless of the harness's admin-gating.

## Verify

    SKEWNONO_ADMIN_LOGS_PROVIDER=office .venv/bin/pytest back_dev_home/admin_logs
