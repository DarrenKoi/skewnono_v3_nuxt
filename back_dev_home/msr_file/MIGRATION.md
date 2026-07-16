# msr_file — office migration

## Rules

- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, or `tests/`.
- Normalize every result to the shapes in `contracts.py` before returning.
- office MUST emit the canonical metadata keys that mock forbids
  (`site_layout_hash`, `recipe_revision`, `coordinate_transform_version`,
  `sequence_timestamp`) — they unlock the layout-dependent analyses; see
  `tests/test_contract.py` docstring.
- Definition of done: the Verify command at the bottom is green.

## Endpoint: GET /api/msr-file

- Handler: `routes.py` → `data.get_msr_file(msr, class_name, total_images)`,
  where `msr` is the required `msr` query param (400 if blank), `class_name`
  is the optional `class_name` query param (`None` if blank), and
  `total_images` is the optional `total_images` query param parsed as an int
  (`None` if not a digit string). Returns 404 if `get_msr_file` returns `None`.
- Contract: `MsrFileResponse` —

  ```python
  class MsrFileResponse(TypedDict):
      msr: str
      class_name: str
      total_images: int
      sequence_count: int
      health: float
      parameters: list[MsrParamSummary]
      fdc_params: list[FdcParamSummary]
      fixed_fdc: dict[str, float]
      dynamic_fdc: dict[str, dict[str, float]]
      exe_detail_info: ExeDetailInfo
      alignment: AlignmentInfo
      spm_dict: SpmDict
      total: int
      rows: list[MsrFileRow]
  ```

- Mock behavior: deterministic per-MSR generation seeded from `md5(msr)`, so
  the same MSR always opens to identical detail data. A single per-MSR
  `health` scalar (0 = nominal, 1 = strongly abnormal) biases both the
  per-row `cd_value` drift and the `fixed_fdc`/`dynamic_fdc` telemetry so an
  unhealthy tool shows correlated CD ↔ FDC excursions. `exe_detail_info`
  deliberately omits `site_layout_hash`, `recipe_revision`,
  `coordinate_transform_version` and `sequence_timestamp` — see below.
- Office data source: <!-- OFFICE: MinIO-parsed msr pickle + canonical layout/coordinate metadata source -->
- Notes: office MUST emit the canonical metadata keys that mock forbids
  (`site_layout_hash`, `recipe_revision`, `coordinate_transform_version`,
  `sequence_timestamp`) — they unlock the layout-dependent analyses; see
  `tests/test_contract.py` docstring. These 4 keys live on `exe_detail_info`
  and are declared `NotRequired` in `contracts.py` precisely so that mock
  (absent) and office (present) responses both pass the gate.

## Endpoint: GET /api/msr-image

- Handler: `routes.py` → `data.get_msr_image(name)`, where `name` is the
  required `name` query param (400 if blank, 400 if longer than 256 chars).
  Returns an `image/svg+xml` response with `Cache-Control: public,
  max-age=3600`.
- Contract: raw SVG string body (no TypedDict — the response is not JSON).
- Mock behavior: a deterministic SVG placeholder generated from `name`, no
  actual image lookup.
- Office data source: <!-- OFFICE: tool FTP image fetch by mp_image filename -->
- Notes: the route + URL contract is identical across phases — only the data
  layer swaps. This route is rate-limit exempt.

## Endpoint: POST /api/msr-files

- Handler: `routes.py` → repeated `data.get_msr_file(msr, class_name,
  total_images)` calls, one per `items[]` entry in the JSON body
  (`{"items": [{"msr": str, "class_name": str|null, "total_images":
  int|null}, ...]}`), capped at `MAX_BULK` (200) items.
- Contract: `{"results": list[MsrFileResponse]}` — found MSRs only, in
  request order; not-found MSRs are silently skipped.
- Mock behavior: same per-MSR generation as `/api/msr-file`, batched to spend
  one rate-limit slot instead of one per MSR.
- Office data source: <!-- OFFICE: same source as /api/msr-file, batched -->
- Notes: same office metadata obligation as `/api/msr-file` applies to every
  item in `results`.

## Verify

    SKEWNONO_MSR_FILE_PROVIDER=office .venv/bin/pytest back_dev_home/msr_file/tests/test_contract_gate.py

The provider key is `get_data_provider("msr_file")` → env var
`SKEWNONO_MSR_FILE_PROVIDER`. The mock-pin test (`tests/test_contract.py`) is
EXCLUDED from this office-mode gate — it asserts mock-only behavior (the
office-gated keys are ABSENT and the office adapter raises
`NotImplementedError`) and must keep running only in mock mode.
