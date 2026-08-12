# access_control — office migration

## Status: WRITTEN — activate by copying, no implementation left to do

All six functions are implemented in the tracked template against the office
Redis. The file holds no in-house address or secret, so the copy is verbatim:

```bash
cp providers/office_example.py providers/office.py
```

- `office.py` is gitignored, so `git pull` never conflicts on it. It is also a
  **copy** — if a later `git pull` moves the template, refresh it with
  `python -m scripts.sync_office_adapters access_control`, or the boot log will
  report `STALE office.py: access_control`.
- Requires `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` in
  `back_dev_home/.env`, resolved through `_runtime/office_redis.py`.
- Only edit the copy if the in-house connection needs adjusting. Never touch
  `routes.py`, `data.py`, `providers/mock.py`, `contracts.py`, or `tests/`.

**The mock is NOT broken at the office** — unlike `api_tokens`, whose store is
process memory. The exception store here is an mtime-keyed JSON file, so grants
do propagate across `gunicorn -w N` workers. Switching to office buys two
things: grants become editable from any office machine instead of only by
editing a file on the cloud host, and the denied-attempts list stops being
per-worker (on mock each worker keeps its own in-memory ring buffer, so the
admin page shows only the attempts that happened to hit the worker answering
the request). Neither is a correctness bug, so this switch is discretionary.

## Implemented key layout

```text
skewnono:access_control:exceptions   HASH  <USER_ID> -> granted_at (ISO Z)
skewnono:access_control:denied       ZSET  <USER_ID> scored by epoch seconds
```

This **diverges from this document's original hint**, which suggested a key per
exception plus a SET index. One hash is strictly better at every call site:
`list_exceptions` is a single `HGETALL` instead of `SMEMBERS` + N `HGET`s;
`is_blocked` — which runs on every request from an X-member — is a single
`HEXISTS`; idempotent granting is `HSETNX`, atomic, with no read-before-write
race; and `HDEL`'s 0/1 return *is* the bool `remove_exception` owes its caller.

The ZSET is likewise a better fit than a capped list: `ZADD` on an existing
member updates its score in place, which is exactly the "a repeat denial
refreshes the timestamp and moves the entry to most-recent, it does not
duplicate" rule described under the enforcement path below, and `ZREVRANGE`
gives most-recent-first for free. `ZREMRANGEBYRANK(key, 0, -51)` enforces the
50-entry cap, oldest evicted first.

## Outage behavior — never report infrastructure failure as policy

Every read converts a store failure into the bare `RuntimeError` that
`back_dev_home/__init__.py` maps to a JSON 503, via `unreachable()` in
`_runtime/office_redis.py`.

**Why convert instead of letting the driver exception escape.** The app factory
registers 503 handlers for redis `ConnectionError` and `TimeoutError` **only**. A
`ResponseError` (WRONGTYPE, bad arity) or a bare `OSError` — which redis-py lets
through unwrapped — matches neither and falls through to `InternalServerError`,
answering 500. The body is still JSON (Flask wraps it in an `HTTPException`, which
the factory's handler serves), but 500 reads as "we have a bug" where 503 reads
as "the store is down, retry" — and those send an operator to two different
places. Widening the factory instead would be wrong: `ResponseError`, `DataError`
and `WatchError` usually *are* bugs, and the factory's own comment says
subclasses of the adapter signal types "must stay real 500s". Only the adapter
knows a given call was reaching for the store, so only the adapter can classify.

`unreachable()` also guarantees the raise is *exactly* `RuntimeError` — the
factory checks `type(err) is not RuntimeError` and sends subclasses to a 500, so
a hand-rolled subclass would silently produce the very 500 this avoids.

| Function | On a Redis outage | Why |
| --- | --- | --- |
| `is_blocked` | raises → 503 | `False` would let blocked members in; `True` would tell a **granted** member they are "not allowed to use this service" — a lie that sends someone chasing a policy problem that does not exist. Raising is *also* fail-closed, since the request is not served either way, so it strictly dominates both. |
| `list_exceptions`, `list_denied` | raise → 503 | An admin shown an empty exception table during an outage may conclude the grants were lost and start re-granting. |
| `add_exception`, `remove_exception` | raise `StoreUnavailableError` | `routes.py` catches that exact class for a more specific 503 (`store_unavailable`, "grant NOT saved") than the generic handler gives. |
| `record_denied` | swallowed + logged | Runs only after `is_blocked` already returned True, so the store was readable a moment ago; a failure here must not turn a correct 403 into a 503. |

Only X-prefixed ids reach Redis at all (`is_blocked` short-circuits on the
prefix first), so an outage cannot affect anyone else's requests.

This **diverges from the mock**, whose reads fail safe to an empty store. That
is right for the mock — its failure mode is a corrupt local JSON file, where
carrying on is reasonable — and wrong here, where the failure is a server that
is not answering and there is a status code that says exactly that.

**The `StoreUnavailableError` rule still holds:** it is imported from
`providers.mock`, never redefined. `routes.py` catches
`_STORE_ERRORS` — the module-level `(StoreUnavailableError, OSError)` tuple —
and answers `503 store_unavailable` on POST and DELETE through the shared
`_store_unavailable_503()` builder, so the two handlers cannot drift into
catching different classes or reporting different messages. A raw redis
exception would sail past that tuple. Note also that
`StoreUnavailableError` subclasses `RuntimeError`, and the app factory's
`RuntimeError` handler deliberately rejects subclasses
(`type(err) is not RuntimeError` → 500) — so it *must* keep being caught in
`routes.py`, which it is.

`BLOCKED_PREFIX` and `_now_iso` are imported from `providers/mock.py` rather
than restated: the blocking rule is provider-independent policy, and the
timestamp format must not drift or the frontend would have to branch on
provider to parse it.

## Endpoint: GET /api/admin/access

- Handler: `routes.py` → `access_overview()`. Admin-only
  (`@require_admin`). One combined read — `data.list_exceptions()` +
  `data.list_denied()` + the `BLOCKED_PREFIX` constant — because the admin
  page needs all three at once and separate calls would eat into the
  50-req/5s per-user rate budget.
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
- Office behavior: `list_exceptions` is one `HGETALL` over the exceptions hash;
  `list_denied` is one `ZREVRANGE(0, 49, withscores=True)`, with each score
  rendered back into the mock's ISO-`Z` format rather than stored twice.
- **Deliberate divergence — exception ordering.** The mock returns file
  insertion order. A Redis hash has no order, so rows are sorted by
  `granted_at` then `user_id`, keeping the admin table stable across reloads
  instead of reshuffling. `list_denied` needs no such fix: the ZSET score *is*
  the ordering.

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
  half-loaded view over the real file. The write happens **before** the
  in-memory commit — `_save_locked()` takes the candidate row set as an
  argument — so if the file write fails (`OSError`) the cache was never
  touched and a failed write cannot look committed in memory. No rollback
  step is involved; there is nothing to roll back.
- Office behavior: `HSETNX` on the exceptions hash, which makes idempotency
  **atomic** — a concurrent second grant cannot overwrite the first one's
  `granted_at`, which a read-before-write could. When `HSETNX` reports the
  field already existed, the stored `granted_at` is read back and returned, so
  a repeat grant reports the original time. Then `ZREM` clears any pending
  denied-attempt entry for that id, matching the mock's `_denied.pop`.
  `ValueError` for an empty or non-X id is raised **before** any Redis call.

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
  row exists, the reduced row set is persisted write-through and the
  in-memory delete happens only once that write succeeded — the same
  write-then-commit ordering as `add_exception`, so a write failure
  (`OSError`) leaves the row present in both the file and the cache.
- Office behavior: a single `HDEL`, whose 0/1 return *is* the bool this function
  owes its caller — `HDEL` on a field that is already gone returns 0, not an
  error, so idempotency needs no extra guard. Same rule as `api_tokens`'
  `revoke_token`, reached more cheaply here.

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
- Office behavior — `is_blocked`: the prefix check short-circuits **before** any
  Redis call, so the overwhelming majority of ids cost nothing; an X-prefixed id
  is one `HEXISTS` on the same hash the four admin functions use, so a grant
  written by `add_exception` is visible immediately. The full row is never
  fetched — only its presence matters.
- Office behavior — `record_denied`: `ZADD` on the same ZSET `list_denied`
  reads, followed by `ZREMRANGEBYRANK(key, 0, -51)` to hold the 50-entry cap.
  `ZADD` on an existing member updates its score in place, which gives the
  "refresh the timestamp and move to most-recent, do not duplicate" behavior
  for free. A blank id is ignored, as in the mock. See the outage table above
  for why this one call swallows errors.

## Notes

- The parity harness pins `GET /api/admin/access` as `403 forbidden`
  (parity runs as a non-admin identity) — a legitimate parity value. It
  does not exercise POST/DELETE or the enforcement path. The contract
  test's `list_denied`/`list_exceptions` shape checks plus the
  `add_exception`/`remove_exception` roundtrip are the only coverage of
  this feature's data-layer shapes, and the roundtrip cleans up after
  itself so repeated runs don't leak a synthetic exception row.
- `tests/test_routes.py` covers the HTTP layer the contract gate cannot:
  the `@require_admin` 403 on all three routes, the admin
  grant → overview → delete flow, and a blocked X-member being denied by
  `_auth/middleware.py` and then surfacing in the denied list. It **pins the
  mock provider** (`SKEWNONO_ACCESS_CONTROL_PROVIDER=mock` plus a `tmp_path`
  store file), because it drives the mock-only `reset_for_tests`/store-file
  helpers — an office run of this directory must not route it to Redis. The
  admin gate and the enforcement wiring it asserts are provider-independent.
- `granted_at`/`last_denied_at` are UTC ISO-8601 timestamps with seconds
  precision and a literal `Z` suffix (`"+00:00"` replaced with `"Z"` —
  see `_now_iso()` in `providers/mock.py`, same convention as
  `admin_logs`/`health`). Preserve that format when porting to office so
  frontend date parsing doesn't need to branch on provider.
- `BLOCKED_PREFIX` and `StoreUnavailableError` are re-exported **unswitched**
  from `providers/mock.py` by `data.py` — they are provider-independent
  policy/error type, not part of the seam. `reset_for_tests` and the private
  `_store_path` helper are **not** re-exported: they are mock-only test
  support (dropping in-memory cache state, reporting the mock's own JSON file
  location), never called from `routes.py` and irrelevant to the office
  adapter, so the tests that need them import them from `providers.mock`
  directly rather than borrowing the dispatcher's namespace.

## Verify

At home — the adapter's own suite runs against an injected fake Redis
(`tests/test_office_template.py`), covering the key layout, idempotency, the
50-entry cap and every branch of the outage table without a server:

    .venv/bin/pytest back_dev_home/access_control

At the office, after `cp` and setting `REDIS_*` — this is the run that promotes
the row in `docs/office-migration/STATUS.md` to `office` with a verification
date:

    SKEWNONO_ACCESS_CONTROL_PROVIDER=office .venv/bin/pytest back_dev_home/access_control

Running that at home fails with `RuntimeError: REDIS_HOST is not set` from
`_runtime/office_redis.py`. That is the expected off-network result, not a
defect — it proves the switch resolved to the office adapter.

Then confirm end to end, because the contract gate cannot exercise enforcement:

1. `GET /api/health/providers` reports `access_control` → `office`.
2. As an admin, grant an exception for a test X-id on `/api/admin/access`, then
   sign in as that id and confirm `/api/*` calls succeed. **Repeat the calls** —
   under `gunicorn -w N` a different worker answers each one, and all must agree.
3. Remove the exception and confirm the same id is blocked again with `403
   access_denied` — and that the attempt shows up in the denied list for
   *whichever* worker serves the admin page, which is the per-worker gap on mock
   that this switch closes.
4. Grant the same id twice and confirm `granted_at` does not change.
