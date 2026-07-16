# access_control — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.
- Implement **all six** functions here, not just the four admin-CRUD ones:
  `is_blocked`, `list_exceptions`, `add_exception`, `remove_exception`,
  `record_denied`, `list_denied`. See "Enforcement path" below —
  `is_blocked`/`record_denied` must read/write the SAME office store as
  the other four, or member blocking silently breaks.
- **StoreUnavailableError rule:** when the office Redis store is
  unreachable, `add_exception`/`remove_exception` MUST raise
  `StoreUnavailableError` — imported from `providers.mock`
  (`from back_dev_home.access_control.providers.mock import
  StoreUnavailableError`), never redefined or replaced with a different
  exception type. `routes.py` already has
  `except (StoreUnavailableError, OSError):` → `503 store_unavailable`
  wired for both POST and DELETE; if office raises anything else (a raw
  Redis client exception, for example), that handler will not catch it
  and the request will 500 instead of the intended 503. Catch the
  Redis-specific error inside `providers/office.py` and re-raise it as
  `StoreUnavailableError(...)`.

## Endpoint: GET /api/admin/access

- Handler: `routes.py` → `access_overview()`. Admin-only
  (`@require_admin`). One combined read — `data.list_exceptions()` +
  `data.list_denied()` + the `BLOCKED_PREFIX` constant — because the admin
  page needs all three at once and separate calls would eat into the
  20-req/5s per-user rate budget.
- Contract: `AccessOverviewResponse` (the wire shape `routes.py` builds;
  `contracts.py` also models the two list rows and the rule block
  separately since the contract test checks `list_exceptions`/
  `list_denied` directly, not the wrapped GET response) —

  ```python
  class RuleInfo(TypedDict):
      blocked_prefix: str

  class ExceptionRow(TypedDict):
      user_id: str
      granted_at: str

  class DeniedRow(TypedDict):
      user_id: str
      last_denied_at: str

  ExceptionListResponse = list[ExceptionRow]
  DeniedListResponse = list[DeniedRow]

  class AccessOverviewResponse(TypedDict):
      rule: RuleInfo
      exceptions: ExceptionListResponse
      denied: DeniedListResponse
  ```

- Mock behavior: `list_exceptions()` returns every granted row from the
  write-through JSON exception store (see "Enforcement path" below for the
  store's fail-safe read semantics) in file/insertion order — no explicit
  sort. `list_denied()` returns the in-memory ring buffer of the last 50
  distinct denied member ids, **most-recent-first** (`reversed(...)`), one
  entry per id (a second denial for an already-tracked id updates its
  timestamp and moves it to the end — it does not duplicate the entry).
  `BLOCKED_PREFIX` is `"X"` — provider-independent policy, re-exported
  unswitched from `providers/mock.py` (see `data.py`'s module docstring).
- Office data source: <!-- OFFICE: key pattern — e.g. a Redis hash per
  exception (`access_control:exception:<user_id>` → `{granted_at}`) plus a
  Redis SET or sorted-set index of all granted ids for `list_exceptions`
  to enumerate, and a Redis list/sorted-set capped at 50
  (`access_control:denied` — a ZSET keyed by timestamp is the natural fit
  for the "most-recent-first, dedup by id" semantics) for `list_denied` -->

## Endpoint: POST /api/admin/access/exceptions

- Handler: `routes.py` → `access_add_exception()`. Admin-only. Reads
  `user_id` from the JSON body (missing key coerces to `""` via
  `body.get("user_id", "")`). Calls `data.add_exception(user_id)`.
  - `ValueError` (empty id, or an id not starting with `X`/`x`) →
    `400 invalid_member_id`.
  - `StoreUnavailableError` or `OSError` → `503 store_unavailable` (grant
    NOT saved — see the StoreUnavailableError rule above).
  - Success → the returned row, `201`.
- Contract: `ExceptionRow` (see above). `add_exception` returns this shape
  directly — `routes.py` does not reassemble it.
- Mock behavior: `add_exception(user_id)` normalizes to
  `user_id.strip().upper()`. Rejects empty ids and ids not starting with
  `BLOCKED_PREFIX` (`X`) with `ValueError` — **only ids the blocking rule
  would actually block are grantable**; granting an exception for a
  non-X id is a caller error, not a no-op. If the normalized id is already
  granted, the existing row (with its original `granted_at`) is returned
  unchanged — **add_exception is idempotent**, it does not bump
  `granted_at` on a repeat grant. Otherwise a new row
  `{"user_id": normalized, "granted_at": <now, ISO-8601 UTC, "Z" suffix>}`
  is created, persisted write-through to the JSON file, and any pending
  denied-attempt entry for that id is cleared (`_denied.pop(normalized,
  None)`) — a fresh grant clears the "attempted and was blocked" history
  for that id. If the store is unreadable (fail-safe), the grant is
  refused with `StoreUnavailableError` rather than persisting a
  half-loaded view over the real file. If the file write itself fails
  (`OSError`), the in-memory row is rolled back before the exception
  propagates, so a failed write never looks committed in memory.
- Office data source: <!-- OFFICE: write the exception hash keyed by
  normalized `user_id`; idempotency means a write to an already-existing
  key must NOT refresh `granted_at` — read-before-write (or a Redis
  `HSETNX`-style conditional set on the `granted_at` field only) to
  preserve the original grant time -->

## Endpoint: DELETE /api/admin/access/exceptions/\<user_id\>

- Handler: `routes.py` → `access_remove_exception(user_id)`. Admin-only.
  Calls `data.remove_exception(user_id)` → `bool`.
  - `StoreUnavailableError`/`OSError` → `503 store_unavailable` (removal
    NOT saved).
  - `False` → `404 not_found`.
  - `True` → `{"removed": user_id.strip().upper()}`, `200`.
- Contract: plain `bool` — no TypedDict needed, `assert_matches` handles
  scalar `bool` directly (same pattern as `api_tokens`' `revoke_token`).
- Mock behavior: `remove_exception(user_id)` normalizes the id, returns
  `False` if no exception row exists for it (no-op, not an error) —
  **removal must be idempotent**: calling it twice on the same id returns
  `True` once, then `False` on every subsequent call, never raising. If a
  row exists, it is deleted from the in-memory store and persisted
  write-through; on a write failure (`OSError`) the row is restored in
  memory before the exception propagates (mirrors `add_exception`'s
  rollback-on-write-failure behavior).
- Office data source: <!-- OFFICE: DEL on a Redis key that is already gone
  returns 0, not an error — map "0 keys deleted" to `False`, not an
  exception, to preserve idempotency (same rule as `api_tokens`'
  `revoke_token`) -->

## Enforcement path: is_blocked / record_denied

These are not HTTP endpoints exposed by `access_control/routes.py` — they
are called by `back_dev_home/_auth/middleware.py:41`
(`_deny_if_blocked()`, invoked from `install_identity_middleware`'s
`before_request` hook) on **every** authenticated request, not just admin
requests. `data.py` dispatches both through the same `_provider()` switch
as the four admin-CRUD functions above — **this office adapter must
implement both against the SAME Redis store it uses for
list_exceptions/add_exception/remove_exception.** If only the four
admin-CRUD functions are wired to office while `is_blocked`/
`record_denied` stay pointed at the mock's in-memory store, a grant
written via office `add_exception` becomes invisible to office
`is_blocked` — a member the admin just unblocked in the office UI would
still get `403 access_denied` on every `/api/*` call, and conversely a
member removed from the office exception list would keep passing through
a stale mock-side `is_blocked` check. This is not a hypothetical, it is
the exact class of bug the `api_tokens` migration hit with
`find_by_plaintext`/`touch_last_used`.

- `is_blocked(user_id) -> bool`: normalizes to `.strip().upper()`. Returns
  `False` immediately (short-circuits) for any id not starting with
  `BLOCKED_PREFIX` (`X`) — the overwhelming majority of ids never touch
  the exception store at all. For an X-prefixed id, returns `True` unless
  the normalized id is present in the exception store. **Admin bypass is
  not part of this function** — `_deny_if_blocked()` checks
  `is_admin(user_id)` separately, after `is_blocked`, as a short-circuit
  order optimization (non-X ids skip both the exception-store read and
  the admin allowlist check).
- `record_denied(user_id) -> None`: called only when `is_blocked` returned
  `True` and the request path starts with `/api/*` (SPA HTML routes are
  never recorded, so the frontend can still render the access-denied
  screen for blocked members). Normalizes the id, upserts it into the
  denied ring buffer with the current timestamp, and moves it to the
  most-recently-denied position — a repeat denial updates the timestamp
  in place rather than adding a duplicate entry, and the buffer is capped
  at 50 entries (oldest evicted first).
- Office data source: <!-- OFFICE: is_blocked should key off the same
  exception-hash pattern as list_exceptions/add_exception/remove_exception
  above (a Redis `EXISTS`/`HEXISTS` check on the normalized user_id is
  enough — no need to fetch the full row); record_denied should key off
  the same denied-attempts store as list_denied -->

## Notes

- The parity harness pins `GET /api/admin/access` as `403 forbidden`
  (parity runs as a non-admin identity) — a legitimate parity value. It
  does not exercise POST/DELETE or the enforcement path. The contract
  test's `list_denied`/`list_exceptions` shape checks plus the
  `add_exception`/`remove_exception` roundtrip are the only coverage of
  this feature's data-layer shapes, and the roundtrip cleans up after
  itself so repeated runs don't leak a synthetic exception row.
- `granted_at`/`last_denied_at` are UTC ISO-8601 timestamps with seconds
  precision and a literal `Z` suffix (`"+00:00"` replaced with `"Z"` —
  see `_now_iso()` in `providers/mock.py`, same convention as
  `admin_logs`/`health`). Preserve that format when porting to office so
  frontend date parsing doesn't need to branch on provider.
- `BLOCKED_PREFIX` and `StoreUnavailableError` are re-exported **unswitched**
  from `providers/mock.py` by `data.py` — they are provider-independent
  policy/error type, not part of the seam. `reset_for_tests` and the
  private `_store_path` helper are also re-exported unswitched, but for a
  different reason: they are mock-only test support (dropping in-memory
  cache state, and reporting the mock's own JSON file location) consumed
  by the legacy `tests/test_access_control.py` at the repo root — they are
  never called from `routes.py` and are irrelevant to the office adapter.

## Verify

    SKEWNONO_ACCESS_CONTROL_PROVIDER=office .venv/bin/pytest back_dev_home/access_control
