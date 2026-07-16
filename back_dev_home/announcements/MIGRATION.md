# announcements — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

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
    raising.
  - `_is_active(a, now)` filters on the optional `starts_at`/`ends_at`
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
    `Announcement` — `id`, `level`, `title`, `body` are the fields
    actually present in the current single-row fixture
    (`announcements/announcements.json`); `starts_at`/`ends_at` are
    optional and only used for filtering, not required in the output.
  - Empty handling: no active announcements is a valid response —
    `[]` — not an error.
  - Ordering: rows are returned in file order (the same order as
    `announcements.json`); there is no sort applied.
- Office data source: <!-- OFFICE: Redis key or index -->
- Notes: the parity harness pins `GET /api/announcements` as a `200`
  response reflecting the single demo row in
  `announcements/announcements.json`. The contract test in
  `tests/test_contract.py` calls `data.get_announcements()` directly, so
  it always exercises the real `AnnouncementsResponse` shape regardless
  of what `routes.py` does with the result.

## Verify

    SKEWNONO_ANNOUNCEMENTS_PROVIDER=office .venv/bin/pytest back_dev_home/announcements
