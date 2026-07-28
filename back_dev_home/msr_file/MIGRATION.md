# msr_file — office migration

## Status

- `GET /api/msr-file`, `POST /api/msr-files`: 구현완료 — meas_hist 문서의
  `minio_pkl` 경로에서 후처리 pickle을 읽어 계약 형태로 정규화합니다. 사내
  데이터 검증 전입니다.

## Rules

- FIRST copy the tracked skeleton, then work only in the copy:
  `cp providers/office_example.py providers/office.py`. `office.py` is
  gitignored and lives only at the office, so `git pull` never conflicts on it.
- Edit ONLY `providers/office.py`. Never touch `routes.py`, `data.py`,
  `providers/office_example.py`, `providers/mock.py`, `contracts.py`, or `tests/`.
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
      eqp_ip: str
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

### Invariant: `{row sequences} == {dynamic_fdc keys}`

Office-confirmed 2026-07-27 (`docs/datatables/msr_file_pickle.txt`):
`sequence` is a global running counter over the whole MSR — one number per
measurement row — and `dynamic_fdc` is keyed by that sequence, holding the tool
state captured for it. The two must therefore agree as SETS, not merely as
counts: the frontend's scoped FDC axis (`utils/skewvoirAnalysis/sequence.ts`)
builds `fdcBySeq` — and derives `fdcKeys`, which gates whether any FDC pane
renders at all — from entries keyed by the on-axis sequence set. A payload
whose `dynamic_fdc` keys have the right COUNT but the wrong SET (off-by-one
keying, a re-indexed pipeline, dummy rows keyed differently) would pass a
count-only check silently and then render "FDC 없음" for a measurement that
actually has FDC data.

`build_response` logs a warning when the sets disagree; it does not raise,
because serving flagged data beats serving nothing. The frontend reports the
same mismatch as a badge on the FDC 분석 view (`SequenceModel.integrity`).

A mismatch means the pickle's `df_result_data` and `dynamic_fdc` disagree about
what was measured — investigate the post-processing pipeline, not the adapter.

- Mock behavior: deterministic per-MSR generation seeded from `md5(msr)`, so
  the same MSR always opens to identical detail data. A single per-MSR
  `health` scalar (0 = nominal, 1 = strongly abnormal) biases both the
  per-row `cd_value` drift and the `fixed_fdc`/`dynamic_fdc` telemetry so an
  unhealthy tool shows correlated CD ↔ FDC excursions. `exe_detail_info`
  deliberately omits `site_layout_hash`, `recipe_revision`,
  `coordinate_transform_version` and `sequence_timestamp` — see below.
- Office data source: the meas_hist document found by `msr.keyword` (both
  aliases, `meas_hist_cdsem,meas_hist_hvsem`) carries two MinIO paths —
  `minio_msr` (RAW .MSR text) and `minio_pkl` (post-processed pickle). The
  adapter reads ONLY `minio_pkl`, which is a **key relative to the configured
  `PREFIX`** — not a `"bucket/key"` pair. Its first segment (`hitachi_sem/...`)
  is a folder; the bucket (`BUCKET`) and prefix (`PREFIX`) come from
  `minio_handler/minio_config.py`, the same place the health probe reads them.
  Office-confirmed 2026-07-22: the stored path resolves to
  `user/2067928/hitachi_sem/...`, so passing the bare key to a
  default-constructed `MinioObject()` is correct. Passing that first segment
  as a bucket instead returns `InvalidBucketName` — S3 bucket names cannot
  contain underscores.
  - Trap when writing diagnostics against this client: `MinioObject(prefix=None)`
    does **not** disable the prefix. The constructor reads `None` as "use the
    configured default"; only `prefix=""` or `.use_prefix(None)` clears it.
    A prefixed-vs-raw comparison written with `prefix=None` silently tests the
    same path twice and reports both as present.

  The pickle already holds the
  parsed structure (`df_result_data` + `exe_detail_info` + `alignment` +
  `fixed_fdc` + `dynamic_fdc` + `spm_dict`, see
  `docs/datatables/msr_file_pickle.txt`). MinIO settings come from
  `minio_handler/minio_config.py`, NOT `.env`. Unknown MSR, missing
  `minio_pkl` (e.g. `msr_check: No`), or a non-dict pickle all return `None`
  → 404, same as the mock.
- Normalization gaps handled by `build_response` (pure, pinned at home by
  `tests/test_office_template.py`): spaced pickle columns
  (`"mp_image_name 01"`, `"meas_condition mag"`) → underscore names,
  `object` → `object_type`, `class` → `class_name`, `"None"` strings → real
  `None`, `chip_coordinate` absent office-side → `""`. Gated-key derivations:
  `site_layout_hash` = sha1 of layout geometry + site set (map_offset
  excluded — verify at office it isn't per-run), `recipe_revision` = real
  pickle key if present else `fp-` fingerprint, `coordinate_transform_version`
  = pickle key or pinned `minio-pkl-v1`, `sequence_timestamp` = parent doc
  `start_time`.
- `eqp_ip` is NOT in the pickle — it comes straight off the parent meas_hist
  `_source` (`docs/datatables/meas_hist.txt`), which `_find_parent` already
  fetches whole for `class_name`/`total_images`, so it costs no extra query.
  It is the third leg of the `(eqp_ip, class_name, msr)` address `msr_image`
  serves by, and it rides on this response so a caller holding only an `msr`
  can still build an image URL — a measurement opened from a search hit or a
  shared link is not in the meas_hist list the frontend caches, and reading
  the tool address from that list is what used to blank every image on the
  스큐보아 analysis page. `""` when the MSR has no parent row: an unknown tool
  must read as unknown, never as a fabricated address.
- Notes: office MUST emit the canonical metadata keys that mock forbids
  (`site_layout_hash`, `recipe_revision`, `coordinate_transform_version`,
  `sequence_timestamp`) — they unlock the layout-dependent analyses; see
  `tests/test_contract.py` docstring. These 4 keys live on `exe_detail_info`
  and are declared `NotRequired` in `contracts.py` precisely so that mock
  (absent) and office (present) responses both pass the gate.

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
    .venv/bin/python -m back_dev_home.msr_file.providers.office

The provider key is `get_data_provider("msr_file")` → env var
`SKEWNONO_MSR_FILE_PROVIDER`. The second command is the standalone smoke test:
it finds a recent doc with a `minio_pkl` path, fetches the pickle, and prints
the normalized shape plus a gate check on the 4 canonical metadata keys. The
mock-pin test (`tests/test_contract.py`) asserts mock-only behavior (the
office-gated keys are ABSENT there) and must keep running only in mock mode;
the template normalization itself is pinned by
`tests/test_office_template.py`, which runs in every mode.
