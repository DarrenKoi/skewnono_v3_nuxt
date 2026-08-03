# announcements — office migration

## Status: WRITTEN — activate by copying, no implementation left to do

`get_announcements` is implemented in the tracked template against one Redis
key. The file holds no in-house address or secret, so the copy is verbatim:

```bash
cp providers/office_example.py providers/office.py
```

- `office.py` is gitignored, so `git pull` never conflicts on it. It is also a
  **copy** — refresh it with `python -m scripts.sync_office_adapters
  announcements` if a later `git pull` moves the template, or the boot log will
  report `STALE office.py: announcements`.
- **A copy made before the `_is_active` → `is_active` rename must be
  refreshed.** The import is module-level, so a pre-rename copy fails the app
  factory at boot rather than degrading — loud on purpose, and the refresh
  command above is the fix.
- Requires `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` in
  `back_dev_home/.env`, resolved through `_runtime/office_redis.py`.
- Only edit the copy if the in-house connection needs adjusting. Never touch
  `routes.py`, `data.py`, `providers/mock.py`, `contracts.py`, or `tests/`.

## Why Redis and not the JSON file

The mock reads `announcements/announcements.json` from disk, and that is not
broken at the office — it re-reads on mtime change, so it is even
multi-worker-safe. It is the *operational* story that fails: in Phase 3 the app
lives at `/project/workSpace/` on a cloud host, so editing that file means shell
access on the box — and the announcement most worth posting is the one about the
box being unwell. A Redis value can be set from any machine on the internal
network, takes effect on the next request for every worker, and needs no
redeploy. Publishing a banner becomes:

```bash
redis-cli -h "$REDIS_HOST" -a "$REDIS_PASSWORD" SET skewnono:announcements \
  '[{"id":"2026-07-30-maint","level":"warning","title":"정기 점검",
     "body":"07-31 02:00~04:00 조회가 지연될 수 있습니다."}]'
```

Because this switch buys operability rather than correctness, it is
discretionary — staying on mock at the office is legitimate if editing the file
on the host is acceptable.

## Implemented key layout

```text
skewnono:announcements   STRING  a JSON array of Announcement rows
```

**No cache, deliberately.** The mock caches on file mtime; a Redis `GET` per
page load is cheap enough that caching would only add a window where an operator
has published a notice and the app is still serving the old one. Announcements
are posted precisely when something is going wrong, so staleness is the
expensive failure here.

## Every failure degrades to "no banners", never to an error

`routes.py` is `jsonify(get_announcements())` with no try/except, and the SPA
calls this endpoint on **every page load** — so a raise here is a 500 on every
page. All of the following resolve to `[]` with a warning in the log:

| Condition | Result |
| --- | --- |
| Key unset, or value empty | `[]` — the normal "nothing posted" state |
| Truncated / invalid JSON | `[]` |
| A JSON object where an array belongs | `[]` |
| A non-dict row inside the array | that row skipped, the rest served |
| Redis unreachable | `[]` |
| `REDIS_*` not configured | `[]` |

That last row is the one place this adapter deliberately differs from
`access_control`, which lets a missing `REDIS_HOST` become a 503: enforcement
failing loudly is correct, a decorative banner breaking every page is not.

The deviation is expressed by **which client accessor is called** —
`redis_client_or_none()` here versus `redis_client()` there — so it is visible
at the call site rather than buried in an `except RuntimeError`. That also means
only a genuine outage (`STORE_ERRORS`) is swallowed on the read; a `RuntimeError`
from a real defect still surfaces.

The non-dict-row tolerance is **shared, not office-only hardening**: both
providers read hand-edited data, so `mock._load` applies the same skip — and the
same warning — to `announcements.json`. A bare string row is dropped there too,
never an `AttributeError`.

`is_active` is imported from `providers/mock.py` rather than restated (it is
public there precisely because the office adapter shares it, and it uses that
module's private `_parse_bound` internally). The active-window semantics —
either bound optional, an unparseable bound treated as absent, and a naive
stamp read as KST so operators can type `2026-05-07T18:00:00` without an
offset — must not drift between providers, since the same operator writes both.

## Endpoint: GET /api/announcements

- Handler: `routes.py` → `data.get_announcements()`, returned directly as
  the JSON body via `jsonify(...)` (the response is a bare JSON array, not
  an object wrapper). The route has no auth decorator and no
  try/except — any exception (including office's `NotImplementedError`)
  propagates as a plain 500 from Flask.
- Contract: `AnnouncementsResponse` (row shape `Announcement`) —

  ```python
  class Announcement(TypedDict, total=False):
      id: str
      level: Literal["info", "warning", "critical"]
      title: str
      body: str
      starts_at: str
      ends_at: str
      dismissible: bool


  AnnouncementsResponse = list[Announcement]
  ```

- Mock behavior: `get_announcements()` reads the whole feature from a
  single JSON file, `announcements/announcements.json` (a bare JSON
  array of `Announcement` rows), and returns only the rows that are
  currently active:
  - The file is read through `_load()`, which caches the parsed list
    keyed on the file's `mtime` (`Path.stat().st_mtime`) — editing
    `announcements.json` on disk and calling again picks up the change
    without a process restart; a missing file returns `[]` rather than
    raising, and a non-dict row (e.g. a bare string from a bad hand edit)
    is skipped rather than raising.
  - `is_active(a, now)` filters on the optional `starts_at`/`ends_at`
    bounds: an announcement is excluded if `now < starts_at` or
    `now > ends_at`; either bound may be omitted (unbounded on that
    side), and a bound that fails to parse (`_parse_bound` returns
    `None` for non-strings, empty strings, or values `datetime.fromisoformat`
    rejects) is treated as absent rather than as a failure.
  - Naive timestamps (no UTC offset in the JSON, e.g.
    `"2026-05-07T18:00:00"`) are interpreted as KST (`UTC+9`,
    `_DEFAULT_TZ`) before comparison against `now` (which is UTC-aware)
    — this lets operators author `announcements.json` in local time
    without remembering to add an offset; comparing a naive value
    against an aware one directly would raise `TypeError` and 500 the
    route, which is exactly what this normalization avoids.
  - `now` is evaluated once per call (`datetime.now(timezone.utc)`), not
    cached — every request re-checks the active window.
  - Row shape passthrough: rows are returned exactly as parsed from JSON
    (no field renaming or reshaping) as long as they match
    `Announcement` — `id`, `level`, `title`, `body` are the required
    fields; `starts_at`/`ends_at` are optional and only used for
    filtering, not required in the output.
  - Empty handling: no active announcements is a valid response —
    `[]` — not an error, and it is the shipped default:
    `announcements/announcements.json` holds `[]` until an operator posts
    a notice, so the banner is absent rather than showing filler.
  - Ordering: rows are returned in file order (the same order as
    `announcements.json`); there is no sort applied.
- Office behavior: one `GET skewnono:announcements`, parsed as a JSON array,
  then filtered through the mock's own `is_active` so the active-window rules
  are identical by construction. Row order is preserved (no sort), rows pass
  through unreshaped, and every failure path yields `[]` — see the degradation
  table above.
- Notes: `tests/test_routes.py` pins `GET /api/announcements` as a `200`
  carrying the contract shape, and asserts nothing about the row count —
  the shipped file is empty and operators add rows to it, so both `[]` and
  a live banner are correct. The contract test in
  `tests/test_contract.py` calls `data.get_announcements()` directly, so
  it always exercises the real `AnnouncementsResponse` shape regardless
  of what `routes.py` does with the result.

## Verify

At home — the adapter's own suite runs against an injected fake Redis
(`tests/test_office_template.py`), covering the active-window rules (including
the KST-naive convention) and every row of the degradation table.
`tests/test_routes.py` adds the HTTP hop: `GET /api/announcements` is a `200`
carrying the contract shape under either provider, and — fenced to mock, since
it drives the JSON file — a non-dict row is skipped rather than 500-ing.

    .venv/bin/pytest back_dev_home/announcements

At the office, after `cp` and setting `REDIS_*`:

    SKEWNONO_ANNOUNCEMENTS_PROVIDER=office .venv/bin/pytest back_dev_home/announcements

Unlike every other office gate, **this one also passes at home**, because
"unconfigured" is this adapter's documented degradation rather than a failure:
`get_announcements()` returns `[]`, which satisfies `AnnouncementsResponse`. A
green run off-network therefore proves the contract shape but says nothing about
the connection — so the office checks below are the real verification, not the
gate. Then:

1. `GET /api/health/providers` reports `announcements` → `office`.
2. `SET skewnono:announcements` to a one-row array; reload any page and confirm
   the banner appears without a redeploy.
3. `SET` it to `[]` and confirm the banner disappears on the next load — proving
   there is no cache in the way.
4. `SET` it to deliberate garbage (`not json`) and confirm pages still render
   with no banner, and a warning is logged. This is the important one: it is the
   difference between a bad paste being a non-event and a bad paste taking the
   SPA down.
