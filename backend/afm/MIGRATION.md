# afm — office migration

## Rules

- FIRST copy the tracked skeleton, then work only in the copy:
  `cp providers/office_example.py providers/office.py`. `office.py` is
  gitignored and lives only at the office, so `git pull` never conflicts on it.
- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/office_example.py`, `providers/mock.py`, `contracts.py`, or `tests/`.
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
  (`MAP608`, `MAPC01`, `5EAP1501`), each with a lowercase `id`, the tool name
  as both `name` and `label`, and the tool's fab. `MAPC01`=R3 and
  `5EAP1501`=M15 are office-confirmed (2026-10-02); `MAP608`=PKG is still
  `OFFICE-VERIFY`. The raw files carry no fab field, so the mapping has to
  come from a table keyed on the tool id.
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
  `TOOL_CONFIGS` table (fixed row count per tool). `filename` follows each
  tool's own raw file-name field order (`#`-separated, `NA` for an empty
  slot — see `docs/datatables/afm/afm_raw_files.txt`), so `MAPC01` rows have
  `lot_id == "NA"`, `has_data == False` and `data_dir_list == ["no files"]`,
  and every `5EAP1501` row has `has_profile == False`.
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
  unit-suffixed keys named by the recipe (e.g. `"Pad_1_H (nm)"` on
  `MAP608`, `"1_Minimum (nm)"`…`"51_Minimum (nm)"` on `5EAP1501`)
  alongside stable `Site`/`ITEM` keys — hence the loose `dict[str, Any]`
  typing rather than a fully-keyed TypedDict. `MAPC01` has no data CSV, so
  its `summary` and `data` are empty lists while `information` is filled.
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

- Mock behavior: generates synthetic height samples per
  `(filename, point, site_info)` on the tool's real grid shape — 512×64 on
  `MAP608`, a mix of 1D lines (1024×1 … 16384×1) and 2D grids on `MAPC01`.
  Returns `None` if the file isn't found or the measurement has no profile
  (every `5EAP1501` row), which the route turns into a `404`. Any `point`
  string is otherwise accepted — the mock does not validate it against
  `available_points`.
- Office data source: <!-- OFFICE: AFM profile/height-map export API -->
- Notes: route wraps the list in `{success, data, count, tool, message}`.
  The raw profile txt states its X/Y/Z units in the header and they differ
  per file (um / nm / pm / Pixel); `AfmProfilePoint` has no unit field yet.

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

## Verify

    SKEWNONO_AFM_PROVIDER=office .venv/bin/pytest backend/afm
