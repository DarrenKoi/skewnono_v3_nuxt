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
  slot — see `docs/datatables/afm/afm_raw_files.txt`), and a recipe name may
  hold spaces and parentheses (`RQQA_PFH_MONF (1)`). Three per-tool facts shape
  the rows: `MAP608`'s leading time is the session start, so several rows
  share one `date`/`time`; `MAPC01` names its lot in the Info section rather
  than the file name, and re-measures one sample several times a day so only
  `time` tells those rows apart (a measurement is `date#time#recipe#slot`);
  `5EAP1501`'s name ends with the tool's original file name. **Which files exist is decided by the recipe**
  (the `RECIPES` table), never by the tool or the row: a recipe with no data
  CSV has `has_data == False` and `data_dir_list == ["no files"]`, and the
  same goes for profile and images. Absence is a normal state, not an error.
  `point_count` is recipe configuration too, and ranges from 1 to 36.
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
  unit-suffixed keys named by the recipe (`"Left_H (nm)"`, `"Dishing_H (nm)"`,
  `"Ra (nm)"`, `"1_Minimum (nm)"`…`"51_Minimum (nm)"`, …) alongside stable
  `Site`/`ITEM` keys — hence the loose `dict[str, Any]` typing rather than a
  fully-keyed TypedDict. Two axes, not one: a summary row's `Site` is the
  **method** name of its block (one file can hold several, e.g.
  `Profile_LEFT_UL` + `Profile_RIGHT_UL`), while a data row's `Site ID`
  (`0002_X002_Y-001`) is the **position** and is what `available_points`
  the profile file name carries. `available_points` lists the **position
  keys**: the 4-digit point number (`0001`), or on a recipe that records
  `Site ID` the Site ID followed by the point number
  (`0004_X000_Y-002_0002`) — the same text the point's profile and image
  files are named after. `State` is one of `COMPLETED` / `FAILED` /
  `STOPPED`. `Method_ID` is a number on some recipes and a string on others
  and is the same in every block of a file, so **blocks are matched by
  position, never by `Method_ID`**; a stopped measurement leaves its later
  block with rows that have no measurement columns and no summary. Either table can be empty on its
  own: a recipe with no data CSV empties both, and real files were also seen
  with no Summary, or with a Data section that has no table.
- Office data source: <!-- OFFICE: AFM measurement detail / summary export API -->
- Notes: `get_afm_file_detail` is `@lru_cache`d in mock — pure function of
  `(filename, tool_name)`; office does not need to replicate caching but
  should keep the same argument shape.

## Endpoint family: GET /api/afm/files/&lt;filename&gt;/profile/&lt;point&gt;, GET /api/afm-files/profile/&lt;filename&gt;/&lt;point&gt;

- Handler: `routes.py` → `data.get_profile_points(filename, point, tool_name,
  site_info)` (`filename`/`point` URL-decoded; `tool_name` from `?tool=`;
  `site_info` built from `?site_id=`/`?site_x=`/`?site_y=`/`?point_no=` query
  args — `point_no` parsed to `int` or `None`)
- Contract: `list[AfmProfilePoint]`, plus `AfmProfileMeta | None` from
  `data.get_profile_meta(filename, point, tool_name)`, which the route sends
  as `meta` —

  ```python
  class AfmProfilePoint(TypedDict):
      x: float
      y: float
      z: float


  class AfmProfileMeta(TypedDict):
      x_unit: str
      y_unit: str
      z_unit: str
      data_size: str
      surface_size: str
  ```

- Mock behavior: generates synthetic height samples per
  `(filename, point, site_info)` on the tool's real grid shape — 512×64 on
  `MAP608`, a mix of 1D lines (1024×1 … 16384×1) and 2D grids on `MAPC01`,
  in the units that file declares (`um`/`nm`/`pm`/`Pixel`, varying per file
  on `MAPC01`). A 1D line has `y == 0` throughout.
  Returns `None` if the file isn't found or the measurement's recipe writes
  no profile (and every `5EAP1501` row), which the route turns into a `404`
  that the page shows as an empty state. Any `point`
  string is otherwise accepted — the mock does not validate it against
  `available_points`.
- Office data source: <!-- OFFICE: AFM profile/height-map export API -->
- Notes: route wraps the list in `{success, data, meta, count, tool, message}`.
  The loaded profile is an X/Y/Z parquet whose object metadata carries
  `XUnit`, `YUnit`, `ZUnit`, `DataSize` and `SurfaceSize`; map those five onto
  `AfmProfileMeta` and lower-case the columns to `x`/`y`/`z`. Units are kept
  per file and never unified, so do not convert them — the page prints
  whatever unit arrives, and draws a profile as a line instead of a heat map
  when `data_size` declares one row (`"1024 x 1"`), falling back to "`y` never
  varies" only if `data_size` is missing. A `Pixel` axis has no known length; pass it through.

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
