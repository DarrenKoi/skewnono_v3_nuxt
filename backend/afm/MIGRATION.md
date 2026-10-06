# afm — office migration

## Rules

- FIRST copy the tracked skeleton, then work only in the copy:
  `cp providers/office_example.py providers/office.py`. `office.py` is
  gitignored and lives only at the office, so `git pull` never conflicts on it.
- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/office_example.py`, `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- Definition of done: the Verify command at the bottom is green.

## Status — template follows the office's own answers, not yet run there (2026-10-06)

`providers/office_example.py` is a full adapter over the loaded shape in
[`docs/datatables/afm/afm_redis.txt`](../../docs/datatables/afm/afm_redis.txt):
Redis hashes `afm_d1_tools` (field `all`) and `afm_d2_measurements` (field =
tool name), plus the MinIO objects under `2067928/afm/<TOOL>/<측정키>/`. It only
reads; nothing here writes to MinIO or Redis.

First run at the office, before the `cp`:

    python -m backend.afm.providers.office_example

It prints one measurement per tool — the row, its file lists, and the typed
detail rows. The column layouts and value conventions come from the office's
sixth reply (`docs/afm/office-data-findings.md`); what is still an assumption is
the short `OFFICE-VERIFY` list at the top of the file. `backend/afm/tests/test_office_template.py`
runs the same code at home against a fake hash and a fake object store.

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
- Office data source: Redis hash `afm_d1_tools`, field `all` — columns
  `id, name, fab, alias`. `id` is stored upper-case and returned lower-case (the
  page's tool slug). `fab` is an empty string for now and `alias` holds `R3` /
  `M15` (null for `MAP608`), so the adapter returns `fab or alias`
  (`OFFICE-VERIFY` that alias means the fab).
- Notes: the route wraps this directly in a bare JSON array (no envelope).

## Endpoint family: GET /api/afm/files, GET /api/afm-files

- Handler: `routes.py` → `data.list_afm_files(tool_name)` (`tool_name` from
  `?tool=` query arg, normalized via `data.normalize_tool`, default
  `"MAP608"` when absent/blank)
- Contract: `list[AfmMeasurementRow]` (existing TypedDict, unchanged — see
  `contracts.py`. The seven `*_dir_list` keys — data, profile, tiff, align,
  tip, capture, raw — hold file **names**, and `[]` when there are none; there
  is no `["no files"]` sentinel. `formatted_date`, `time` and `point_count` can
  be `null`.)
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
  CSV has `has_data == False` and `data_dir_list == []`, and the
  same goes for profile and images. Absence is a normal state, not an error.
  `point_count` is recipe configuration too, and ranges from 1 to 36.
- Office data source: Redis hash `afm_d2_measurements`, field = tool name — one
  parquet DataFrame holding that tool's whole history. The lists there are full
  MinIO keys; the adapter returns their basenames, turns a `NA` time into
  `null`, and sorts newest first. `has_data` is true only when
  `detail_points.parquet` is listed (an info-only measurement still lists its
  information object), and `has_image` only when a webp is (`tiff_dir_list`
  holds the original TIFFs too). `measured_info` is always null at the office
  and `tool_id` does not exist; the adapter returns `""` and the lower-cased
  tool name.
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
      information: dict[str, str | None]
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
- Office data source: the measurement's `data_dir_list` —
  `detail_information.parquet` (columns `name`, `value`),
  `detail_summary.parquet` (0 rows and no columns when there is no Summary) and
  `detail_points.parquet`. **Every value is loaded as text**; the adapter's
  `_cell` turns unit-bearing columns, `Point No` and `Site X` / `Site Y` into
  numbers and the `Valid` columns into booleans, and an unmeasured cell (`" "`)
  or unset `_Valid` (`""`) into `null`. Each data row keeps `Site`, the method
  name of its block — the page splits blocks on it and must never infer them
  from row order. The adapter adds `measurement_point` (Site ID + 4-digit
  `Point No`) and, when there are no points, reads `available_points` off the
  profile and image names.
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
      z: float | None


  class AfmProfileMeta(TypedDict):
      x_unit: str
      y_unit: str
      z_unit: str
      data_size: str
      surface_size: str
  ```

- Mock behavior: generates synthetic height samples per
  `(filename, point, site_info)` on the tool's real grid shape — 512×64 on
  `MAP608`, a mix of 1D lines (1024×1 … 16384×1) and 2048×256 grids on `MAPC01`,
  in the units that file declares (`um`/`nm`/`pm`/`Pixel`, varying per file
  on `MAPC01`). A 1D line has `y == 0` throughout.
  Returns `None` if the file isn't found or the measurement's recipe writes
  no profile (and every `5EAP1501` row), which the route turns into a `404`
  that the page shows as an empty state. Any `point`
  string is otherwise accepted — the mock does not validate it against
  `available_points`.
- Office data source: the `profile_<raw name>.parquet` in `profile_dir_list`
  whose name carries `_<point>_Height`. Units are the MinIO object's user
  metadata (`x-amz-meta-xunit` …, stored lower-case), read with a stat.
- Notes: route wraps the list in `{success, data, meta, count, total, tool, message}`.
  The provider returns the **whole file**; the route thins it with
  `profile_sampling.thin_profile` to at most 65,536 samples (a 2048×256 scan
  is 524,288, which hangs the page) and reports the file's own size as
  `total`. Do not thin, level or fill in the adapter: `z` is the stored value,
  and a NaN travels as `None`.
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
- Contract: `str | bytes` — a `str` is a self-contained SVG document and is
  served as `image/svg+xml`; `bytes` are a stored webp and are served as
  `image/webp`. The mock returns the first, the office the second.
- Mock behavior: renders a synthetic gradient/scatter SVG seeded from
  `(tool_name, filename, point)`; returns `None` if the file isn't found.
  `/image` 404s as `{success: false, error, message, tool}`; `/image-file`
  404s as the plain text `"Image file not found"`.
- Office data source: the webp in `tiff_dir_list` whose name carries
  `_<point>_Height` (naming is `OFFICE-VERIFY`). The gallery routes
  (`.../images/<type>` and `.../images/<type>/<name>`) read `align` / `tip` /
  `capture` / `tiff` lists the same way, by name.
- Notes: the `/image` JSON response's `url` field is built by the route
  layer from the request's own filename/point/tool (not from the provider
  return value) — office only needs to return the SVG string; the route
  wiring is unaffected.

## Endpoint family: GET /api/afm/files/&lt;filename&gt;/tiff/&lt;name&gt;

- Handler: `routes.py` → `data.get_tiff_original(filename, name, tool_name)`
  (`filename`/`name` URL-decoded; `tool_name` from `?tool=`). `name` is an
  entry of the measurement's `tiff_dir_list` — the **display** image name, not
  the stored key.
- Contract: `AfmOriginalFile | None` —

  ```python
  class AfmOriginalFile(TypedDict):
      filename: str
      content_type: str
      data: bytes
  ```

- Mock behavior: returns a fabricated 256×256 8-bit grayscale TIFF, seeded
  from `(tool_name, filename, name)`, named after the listed image with its
  extension swapped to `.tiff`. Returns `None` when the measurement is unknown
  or `name` is not in its `tiff_dir_list`, which the route turns into a plain
  `404`. `list_analysis_images(..., "tiff", ...)` lists the webps only and adds an
  `original_url` key pointing at this route to each one whose TIFF sits beside it
  in `tiff_dir_list` (none on `5EAP1501`); the other three image types carry no
  such key, and the page shows the 원본 TIFF 다운로드 button only where the key
  is present.
- Office data source: the measurement's `tiff_dir_list`, which holds the
  originals beside their webp conversions (none on `5EAP1501` so far). The
  adapter pairs them by name — the webp's own with a `.tif` / `.tiff` extension
  (`OFFICE-VERIFY`) — and an image without a pair carries no `original_url`.
- Notes: read the object with `minio_handler.MinioObject().get(key)` (lazy
  import, raw bytes) and return its **key basename** as `filename` — the route
  sends it as the download name, so do not compose one. Return `None` for an
  object that is not there. Emit `original_url` from `list_analysis_images`
  only for images whose original actually exists; that key is the page's only
  signal. The route sends `content_type` verbatim (`image/tiff`).
- `GET /api/afm/files/<filename>/tiff.zip` (all originals of one measurement
  in one zip) is composed in `routes.py` from `list_analysis_images` and
  `get_tiff_original`, so it needs **no extra office function**. An image whose
  original returns `None` is left out of the archive; none at all is a `404`.
  The zip is built in memory, so tell us if office TIFFs are tens of MB each.

## Verify

    SKEWNONO_AFM_PROVIDER=office .venv/bin/python -m pytest backend/afm
