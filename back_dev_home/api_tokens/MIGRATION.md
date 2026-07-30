# api_tokens — office migration

## Status: WRITTEN — activate by copying, no implementation left to do

All five functions are implemented in the tracked template against the office
Redis. There is no in-house address or secret in the file, so the copy is
verbatim (same as `activity` and `admin_logs`):

```bash
cp providers/office_example.py providers/office.py
```

- `office.py` is gitignored, so `git pull` never conflicts on it. It is also a
  **copy** — if a later `git pull` moves the template, refresh it with
  `python -m scripts.sync_office_adapters api_tokens`, or the boot log will
  report `STALE office.py: api_tokens`.
- Requires `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` in
  `back_dev_home/.env` — resolved through `_runtime/office_redis.py`, the same
  client `sem_list` and `storage` already read through.
- Only edit the copy if the in-house connection needs adjusting. Never touch
  `routes.py`, `data.py`, `providers/mock.py`, `contracts.py`, or `tests/`.

**Why this feature cannot stay on mock at the office.** `providers/mock.py`
holds its tokens in two module-level dicts. Under `gunicorn -w N` the worker
that serves `POST /api/account/api-tokens` and the worker that later
authenticates `Authorization: Bearer skn_...` are different processes, so
`find_by_plaintext` misses a token that exists perfectly well in a sibling
worker and bearer auth fails nondeterministically — and every restart drops
every token. Leaving `api_tokens` on mock at the office is a defect, not a safe
default. (`access_control` and `announcements` do not share this problem: their
mocks are mtime-keyed JSON files, which do propagate across workers.)

## Implemented key layout

```text
skewnono:api_tokens:token:<token_id>   HASH  id owner_user_id label
                                             hash created_at last_used_at
skewnono:api_tokens:owner:<owner_id>   SET   token ids owned by this member
skewnono:api_tokens:hash:<sha256>      STR   token_id
```

Three decisions worth knowing before you change anything here:

- **No TTL on any key.** `msr_image/redis_jobs.py` — the only other writer
  against this Redis — expires everything it writes, because a job is
  transient. A token is a durable credential; a TTL here would log a member out
  with no trace. Do not copy the TTL idiom over.
- **`last_used_at` is stored as `""` when absent, never as `None`.** Redis hash
  fields are strings, so writing `None` directly round-trips as the literal
  string `"None"` and the frontend renders a token as having been used at
  "None". The adapter maps `"" → None` on read.
- **The `hash:` reverse index is not optional.** `find_by_plaintext` runs on the
  hot path of every bearer request; without the index it would need a full
  keyspace scan. It mirrors the mock's `_by_hash` dict.

The adapter imports `_PREFIX`, `_hash`, `_now`, `_TOUCH_DEBOUNCE`,
`_public_view` and `_TokenRow` from `providers/mock.py` rather than restating
them. That is deliberate: the token prefix and hash algorithm must not drift
between providers, and reusing `_TokenRow` is what guarantees the attribute
access `_auth/middleware.py` performs (`row.owner_user_id`, `row.id`) keeps
working. See "Auth path" below.

## Endpoint: GET /api/account/api-tokens

- Handler: `routes.py` → `list_api_tokens()` → `data.list_tokens(g.user_id)`,
  wrapped as `{"tokens": [...]}`. No admin/label validation on this path;
  `g.user_id` is set upstream by the identity middleware.
- Contract: `TokenListResponse` (row shape `TokenRow`) —

  ```python
  class TokenRow(TypedDict):
      id: str
      label: str
      created_at: str
      last_used_at: str | None


  TokenListResponse = list[TokenRow]
  ```

- Mock behavior: `list_tokens(owner_user_id)` filters the in-memory
  `_tokens` store to rows whose `owner_user_id` matches the caller and maps
  each to `_public_view` (`id`, `label`, `created_at`, `last_used_at`).
  Order is insertion order of the underlying dict (not explicitly sorted).
  An owner with no tokens gets `[]` — that is a valid response, not an
  error.
- Office behavior: reads `skewnono:api_tokens:owner:<owner_user_id>` (SET of
  token ids), then one `HGETALL` per id. A token id in the owner index whose
  row is gone is **skipped**, not returned as a half-populated row — a row
  missing its `id` field would otherwise authenticate as owner `""`.
- **Deliberate divergence — ordering.** The mock returns its dict's insertion
  order. A Redis SET has no order at all, so the office adapter sorts by
  `created_at`, then `id` to break same-second ties. Without a sort the
  response would reshuffle on every request. Oldest-first either way, so the
  frontend needs no change.

## Endpoint: POST /api/account/api-tokens

- Handler: `routes.py` → `create_api_token()`. Before calling `data.py`:
  - Rejects the request with `403 forbidden` if `g.api_token_id` is set —
    a caller authenticated via an existing API token cannot mint another
    one (prevents a leaked token from self-propagating).
  - Reads `label` from the JSON body, strips it, and returns
    `400 invalid_request` if it is empty or longer than 80 characters.
  - Calls `data.create_token(g.user_id, label)`, which returns
    `(view, plaintext)` — **a tuple, not a dict** (this is the real,
    verbatim signature from the old mock; do not change it, `routes.py`
    destructures it positionally). `routes.py` then reassembles the wire
    response itself: `{"token": view, "plaintext": plaintext}, 201`.
- Contract: `CreateTokenResponse` (this is the *wire/response* shape that
  `routes.py` builds from the tuple `data.create_token` returns — the
  contract does not describe the raw Python return value) —

  ```python
  class CreateTokenResponse(TypedDict):
      token: TokenRow
      plaintext: str
  ```

  The secret (`plaintext`) is returned exactly once, as a **sibling** key
  of `token`, not embedded inside the row. Because of that, `TokenRow`
  needed no `NotRequired` field for the secret — the row shape returned by
  `list_tokens` and the row nested inside `create_token`'s response are
  identical (`_public_view` is used for both in the mock).
- Mock behavior: `create_token(owner_user_id, label)` generates a
  `skn_`-prefixed random token (`secrets.token_urlsafe(32)`), stores only
  its SHA-256 hash (never the plaintext) keyed by a 12-hex-char id
  (`uuid.uuid4().hex[:12]`), and returns the public view plus the one-time
  plaintext. An empty/whitespace-only label is coerced to `"untitled"`
  (this happens in the mock itself, after `routes.py`'s own empty-label
  400 check — reachable only if the label was non-empty but became empty
  after `.strip()` inside the mock, which can't currently happen since
  `routes.py` already stripped and 400'd on empty; still, don't remove the
  mock's own fallback when porting behavior to office).
- Office behavior: writes the row hash, adds the id to the owner SET, and sets
  the `hash:<sha256>` → `token_id` reverse index — three writes, no TTL. Only
  the SHA-256 reaches Redis; the plaintext exists in process memory just long
  enough to be returned once (`test_plaintext_is_never_persisted` asserts it
  appears nowhere in the store). Blank labels coerce to `"untitled"`, matching
  the mock.

## Endpoint: DELETE /api/account/api-tokens/\<token_id\>

- Handler: `routes.py` → `revoke_api_token(token_id)`. Same
  `g.api_token_id` forbid-check as POST. Calls
  `data.revoke_token(g.user_id, token_id)` → `bool`; `False` becomes
  `404 not_found`, `True` becomes `{"revoked": token_id}`.
- Contract: plain `bool` — no TypedDict needed, `assert_matches` handles
  scalar `bool` directly.
- Mock behavior: `revoke_token(owner_user_id, token_id)` looks the row up
  by `token_id`; returns `False` if the row does not exist **or** exists
  but belongs to a different owner (an owner can never revoke someone
  else's token, and the response gives no hint which case it was). If
  found and owned, it removes the row from both `_tokens` and the
  `_by_hash` reverse index and returns `True`.
- **Revoke must be idempotent.** Calling revoke twice on the same
  `token_id` must not error: the first call removes the row and returns
  `True` (`200`); every subsequent call finds no row and returns `False`
  (`404`) — never raises, never leaves a partial/duplicate entry. The
  contract gate's roundtrip test (`tests/test_contract.py`) relies on
  exactly this: it creates a token then revokes it once and asserts
  `True`; office must preserve that a **second** revoke of the same id
  (not exercised by the gate test, but by real client retries) returns
  `False` cleanly rather than throwing on a missing Redis key.
- Office behavior: reads the row first, so ownership is checked before anything
  is deleted; a mismatched owner returns `False` having written nothing. On a
  match it deletes the reverse index, removes the id from the owner SET, then
  deletes the row. Idempotency falls out of the read-first order — a second
  revoke finds no row and returns `False` without touching Redis further, so a
  `DEL` against an already-gone key never surfaces. Revoking the owner's last
  token leaves **no** keys behind: Redis drops a SET once its final member is
  removed (`test_revoke_token_removes_row_owner_index_and_hash_index`).

## Auth path: find_by_plaintext / touch_last_used

These are not HTTP endpoints — they are called by
`back_dev_home/_auth/middleware.py:4`
(`from ..api_tokens.data import find_by_plaintext, touch_last_used`) on
**every** `/api/*` request that carries an
`Authorization: Bearer skn_...` header (`_try_api_token` in that file),
not just at token creation time. `data.py` dispatches both through the
same `_provider()` switch as the three CRUD functions above — **this
office adapter must implement both against the SAME Redis store it uses
for create_token/list_tokens/revoke_token.** If only the CRUD three are
wired to office while these two stay pointed at the mock's in-memory
store, a token created via office `create_token` becomes unfindable by
`find_by_plaintext`, and bearer-token auth silently breaks for every
office-created token the moment `api_tokens` resolves to office — this is
not a hypothetical, it is the exact bug this section exists
to prevent.

- `find_by_plaintext(plaintext) -> _TokenRow | None`: hashes the plaintext
  (SHA-256) and looks it up by hash, never by the plaintext itself (the
  store never contains a plaintext token to begin with). Returns `None`
  if the prefix doesn't match (`skn_`) or the hash isn't found.
  **Return-shape contract:** `back_dev_home/_auth/middleware.py` does
  `g.user_id = row.owner_user_id` and `g.api_token_id = row.id` — i.e. it
  reads **attributes**, not dict keys. The mock's return type is its
  private `providers/mock._TokenRow` dataclass with fields `id`,
  `owner_user_id`, `label`, `hash`, `created_at`, `last_used_at`. The
  office implementation does not have to reuse that exact class, but
  whatever it returns MUST expose at least `.id` and `.owner_user_id` as
  attributes (a small dataclass/namedtuple is the simplest match — do not
  return a plain dict, `row.id` would raise `AttributeError`).
- `touch_last_used(token_id) -> None`: updates `last_used_at` on the
  resolved row. Called once per authenticated bearer request, right after
  `find_by_plaintext` succeeds — i.e. on the hot path of every API call a
  token makes, not just once at creation. The mock debounces the actual
  write to once per 60s per token (`_TOUCH_DEBOUNCE`) to avoid a write per
  request; preserve that debounce (or an equivalent) in office so this
  doesn't become a write-per-request against Redis.
- Office behavior — `find_by_plaintext`: the wrong-prefix check short-circuits
  **before** any Redis call, so a malformed Authorization header costs no round
  trip on a path that runs for every request. A correct prefix reads
  `hash:<sha256>` → `token_id`, then the row. If the index outlives its row the
  result is `None`, which the middleware turns into `401 invalid_token` — never
  a partially-populated row.
- Office behavior — `touch_last_used`: reads only the `last_used_at` field
  (`HGET`, not `HGETALL`) and returns early inside the 60s window, so the steady
  state for a busy token is one cheap read per request and one write per minute.
  A `last_used_at` that fails to parse is overwritten rather than allowed to
  wedge the token permanently. An unknown `token_id` is a no-op — it must not
  create a key, or a bogus id would leave a row with no `id` field behind
  (`test_touch_last_used_on_an_unknown_token_is_a_noop`).

## Notes

- The parity harness pins `GET /api/account/api-tokens` as
  `200 {"tokens": []}` (empty store, fresh process) — a legitimate parity
  value. It does not exercise POST/DELETE (the harness only issues GET
  requests). The contract test's roundtrip (create → assert shape →
  revoke) is the only coverage of those two endpoints' data-layer shapes,
  and it cleans up after itself so repeated runs don't leak tokens.
- `created_at`/`last_used_at` are ISO-8601 UTC timestamps
  (`timespec="seconds"`, no `Z` suffix — unlike `admin_logs`/`health`,
  this feature does not append a literal `Z`). The office adapter preserves the
  format by importing the mock's `_now`, so it cannot drift.

## Verify

At home — the adapter's own suite runs against an injected fake Redis
(`tests/test_office_template.py`), so it is fully covered without a server:

    .venv/bin/pytest back_dev_home/api_tokens

At the office, after `cp` and setting `REDIS_*` — this is the run that has
never happened yet, and the one that promotes the row in
`docs/office-migration/STATUS.md` from `구현완료` to `office` with a 검증일:

    SKEWNONO_API_TOKENS_PROVIDER=office .venv/bin/pytest back_dev_home/api_tokens

Running that at home fails with `RuntimeError: REDIS_HOST is not set` from
`_runtime/office_redis.py`. That is the expected off-network result, not a
defect — it proves the switch resolves to the office adapter and that the
adapter reached for its client.

Then confirm end to end, since the contract gate cannot prove the multi-worker
fix that motivated this adapter:

1. `GET /api/health/providers` reports `api_tokens` → `office`.
2. Mint a token in the UI, then call any `/api/*` endpoint with
   `Authorization: Bearer skn_...` **repeatedly** — under `gunicorn -w N` a
   different worker answers each time, and every one must accept it. That is
   precisely what the mock could not do.
3. Restart the backend and reuse the same token: it must still authenticate.
