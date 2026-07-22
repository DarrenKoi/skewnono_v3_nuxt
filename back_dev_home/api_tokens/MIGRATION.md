# api_tokens — office migration

## Rules

- FIRST copy the tracked skeleton, then work only in the copy:
  `cp providers/office_example.py providers/office.py`. `office.py` is
  gitignored and lives only at the office, so `git pull` never conflicts on it.
- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/office_example.py`, `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.
- Implement **all five** functions here, not just the three CRUD ones:
  `create_token`, `list_tokens`, `revoke_token`, `find_by_plaintext`,
  `touch_last_used`. See "Auth path" below — the last two must read/write
  the SAME office store as the first three, or bearer-token auth breaks.

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
- Office data source: <!-- OFFICE: key pattern — e.g. a Redis SET/hash per
  owner (`api_tokens:owner:<owner_user_id>` → set of token ids, plus
  `api_tokens:token:<token_id>` → hash with label/created_at/last_used_at)
  so list/get/revoke can all key off `token_id` without a full scan -->

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
- Office data source: <!-- OFFICE: same Redis key pattern as above — write
  the token hash (never the plaintext) into `api_tokens:token:<token_id>`
  and index it by owner; the one-time plaintext is generated in-process
  and only returned, never persisted -->

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
- Office data source: <!-- OFFICE: DEL on a Redis key that is already gone
  returns 0, not an error — make sure the office adapter maps "0 keys
  deleted" to `False`, not an exception, to preserve idempotency -->

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
- Office data source: <!-- OFFICE: same `api_tokens:token:<token_id>` /
  hash-lookup key pattern as the CRUD functions above — find_by_plaintext
  needs a hash → token_id reverse index (mirrors the mock's `_by_hash`
  dict) so it doesn't have to scan every token to match a hash -->

## Notes

- The parity harness pins `GET /api/account/api-tokens` as
  `200 {"tokens": []}` (empty store, fresh process) — a legitimate parity
  value. It does not exercise POST/DELETE (the harness only issues GET
  requests). The contract test's roundtrip (create → assert shape →
  revoke) is the only coverage of those two endpoints' data-layer shapes,
  and it cleans up after itself so repeated runs don't leak tokens.
- `created_at`/`last_used_at` are ISO-8601 UTC timestamps
  (`timespec="seconds"`, no `Z` suffix — unlike `admin_logs`/`health`,
  this feature does not append a literal `Z`). Preserve that format (or
  document a deliberate change) when porting to office so frontend date
  parsing doesn't need to branch on provider.

## Verify

    SKEWNONO_API_TOKENS_PROVIDER=office .venv/bin/pytest back_dev_home/api_tokens
