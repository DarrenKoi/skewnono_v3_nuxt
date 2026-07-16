# afm — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Endpoint family: GET /api/afm/tools

- Handler: `routes.py` → `data.get_tools()`
- Contract: `list[AfmToolRow]` —

  ```python
  class AfmToolRow(TypedDict):
      id: str
      name: str
      label: str
      fab: str
  ```

- Mock behavior: returns one row per configured tool
  (`MAP608`, `MAPC01`, `5MAPT01`), each with a lowercase `id`, the tool name
  as both `name` and `label`, and the tool's fab.
- Office data source: <!-- OFFICE: AFM tool/asset registry query -->
- Notes: the route wraps this directly in a bare JSON array (no envelope).

## Endpoint family: GET /api/afm/files, GET /api/afm-files

- Handler: `routes.py` → `data.list_afm_files(tool_name)` (`tool_name` from
  `?tool=` query arg, normalized via `data.normalize_tool`, default
  `"MAP608"` when absent/blank)
- Contract: `list[AfmMeasurementRow]` (existing TypedDict, unchanged — see
  `contracts.py`; notably has many keys including duplicate snake_case /
  camelCase `has_*`/`has*` boolean pairs kept for frontend compatibility, and
  `profile_dir_list`/`data_dir_list`/`tiff_dir_list`/`align_dir_list`/
  `tip_dir_list` each holding either real file names or the literal
  `["no files"]` sentinel when that dir has no files for the row.)
- Mock behavior: deterministically generates rows per tool from a static
  `TOOL_CONFIGS` table (fixed row count per tool); `filename`/`unique_key`
  encode date, recipe, lot, time, and slot.
- Office data source: <!-- OFFICE: AFM measurement file index / listing API -->
- Notes: route wraps the list in
  `{success, data, total, tool, message}`. `total` and `message` are derived
  from `len(rows)` at the route layer — office only needs to return the
  contract-shaped list; the envelope keeps working automatically.

## Endpoint family: GET /api/afm/files/&lt;filename&gt;, GET /api/afm-files/detail/&lt;filename&gt;

- Handler: `routes.py` → `data.get_afm_file_detail(filename, tool_name)`
  (`filename` URL-decoded via `unquote`; `tool_name` from `?tool=`)
- Contract: `AfmFileDetail` —

  ```python
  class AfmFileDetail(TypedDict):
      filename: str
      tool: str
      pickle_filename: str
      information: dict[str, str]
      summary: list[dict[str, Any]]
  ```

  (mock also returns `data: list[dict[str, Any]]` — raw per-point
  measurement rows — and `available_points: list[str]` — the site codes
  valid for the `point` argument to `/profile` and `/image`; these extra
  keys are consumed by the frontend and by this feature's own contract
  tests but are not required by the contract policy, which allows extra
  keys.)
- Mock behavior: looks the row up via `_find_measurement` (matches on
  filename with `.csv`/`.pkl` stripped); returns `None` if no row matches,
  which the route turns into a `404` with
  `{success: false, error, message, tool}`. `summary` rows have
  unit-suffixed dynamic keys (e.g. `"Left_H (nm)"`, `"Right_H (nm)"`,
  `"Ref_H (nm)"`) alongside stable `Site`/`ITEM` keys — hence the loose
  `dict[str, Any]` typing rather than a fully-keyed TypedDict.
- Office data source: <!-- OFFICE: AFM measurement detail / summary export API -->
- Notes: `get_afm_file_detail` is `@lru_cache`d in mock — pure function of
  `(filename, tool_name)`; office does not need to replicate caching but
  should keep the same argument shape.

## Endpoint family: GET /api/afm/files/&lt;filename&gt;/profile/&lt;point&gt;, GET /api/afm-files/profile/&lt;filename&gt;/&lt;point&gt;

- Handler: `routes.py` → `data.get_profile_points(filename, point, tool_name,
  site_info)` (`filename`/`point` URL-decoded; `tool_name` from `?tool=`;
  `site_info` built from `?site_id=`/`?site_x=`/`?site_y=`/`?point_no=` query
  args — `point_no` parsed to `int` or `None`)
- Contract: `list[AfmProfilePoint]` —

  ```python
  class AfmProfilePoint(TypedDict):
      x: float
      y: float
      z: float
  ```

- Mock behavior: generates a fixed 20×20 grid (400 points) of synthetic
  height-map samples per `(filename, point, site_info)`; returns `None` if
  the file isn't found (any `point` string is otherwise accepted — the mock
  does not validate it against `available_points`), which the route turns
  into a `404`.
- Office data source: <!-- OFFICE: AFM profile/height-map export API -->
- Notes: route wraps the list in `{success, data, count, tool, message}`.

## Endpoint family: GET /api/afm/files/&lt;filename&gt;/image/&lt;point&gt;, GET /api/afm-files/image/&lt;filename&gt;/&lt;point&gt;, and GET .../image-file/&lt;point&gt; variants

- Handler: `routes.py` → `data.get_profile_image_svg(filename, point,
  tool_name)`, called from two route pairs: `/image/...` (returns JSON
  metadata + a URL pointing at the `/image-file/...` variant) and
  `/image-file/...` (returns the raw SVG body with
  `mimetype="image/svg+xml"`)
- Contract: plain `str` (assert with `isinstance`, not a TypedDict) — a
  self-contained inline SVG document.
- Mock behavior: renders a synthetic gradient/scatter SVG seeded from
  `(tool_name, filename, point)`; returns `None` if the file isn't found.
  `/image` 404s as `{success: false, error, message, tool}`; `/image-file`
  404s as the plain text `"Image file not found"`.
- Office data source: <!-- OFFICE: AFM rendered image / thumbnail export API -->
- Notes: the `/image` JSON response's `url` field is built by the route
  layer from the request's own filename/point/tool (not from the provider
  return value) — office only needs to return the SVG string; the route
  wiring is unaffected.

## Endpoint family: GET /api/afm/activities, GET /api/afm/activities/me

- Handler: `routes.py` → `data.list_user_activities(user, limit)`.
  `/activities` takes `user` from `?user=` (may be `None`) and `limit` from
  `?limit=` (default `100`); `/activities/me` always passes the
  `LASTUSER`/`LAST_USER` cookie value (or `"anonymous"`) as `user` and a
  fixed `limit=50`.
- Contract: `list[AfmUserActivity]` —

  ```python
  class AfmUserActivity(TypedDict):
      timestamp: str
      user: str
      action: str
      tool: str
      filename: str
      summary_count: int
      detail_count: int
  ```

- Mock behavior: derives activity rows from `list_afm_files("MAP608")`
  (hard-coded to the `MAP608` tool regardless of any tool filter),
  clamping to `min(max(limit, 0), 20)` rows; when no explicit `user` is
  passed, cycles through 4 synthetic `engineer0N` actors. `timestamp` is
  UTC ISO-8601 with a literal `Z` suffix.
- Office data source: <!-- OFFICE: AFM usage/audit log query, filtered by user -->
- Notes: `/activities` wraps in `{success, data, count, message}`;
  `/activities/me` additionally echoes `user` in the envelope.

## Endpoint family: GET /api/afm/current-user

- Handler: `routes.py` → reads the `LASTUSER`/`LAST_USER` cookie directly
  (no `data.py` seam involved); returns `{success, user, message}` with
  `user` defaulting to `"anonymous"`.
- Contract: none — this endpoint does not go through `data.py`, so there is
  nothing for the office provider to implement here.
- Office data source: n/a.

## Endpoint family: GET /api/afm/analytics

- Handler: `routes.py` → `data.get_user_analytics(days)` (`days` from
  `?days=`, default `7`)
- Contract: `AfmUserAnalytics` —

  ```python
  class AfmDailyStat(TypedDict):
      date: str
      unique_users: int
      total_sessions: int
      total_actions: int
      avg_actions_per_session: float

  class AfmAnalyticsSummary(TypedDict):
      period_days: int
      total_unique_users: int
      avg_daily_users: float
      avg_daily_sessions: float

  class AfmUserAnalytics(TypedDict):
      daily_stats: list[AfmDailyStat]
      summary: AfmAnalyticsSummary
  ```

- Mock behavior: clamps `days` to `[1, 30]`; generates one synthetic
  `daily_stats` entry per day with deterministically increasing session/
  action counts; `summary.total_unique_users` is a **fixed constant (`6`)**
  independent of `days` or the actual `daily_stats` contents — office should
  not assume it equals a sum/max over `daily_stats[].unique_users`.
- Office data source: <!-- OFFICE: AFM usage analytics aggregation (daily active users/sessions) -->
- Notes: route wraps in `{success, data, message}`.

## Verify

    SKEWNONO_AFM_PROVIDER=office .venv/bin/pytest back_dev_home/afm
