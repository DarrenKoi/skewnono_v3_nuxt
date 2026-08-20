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
- Office data source: the meas_hist document for this MSR (both aliases,
  `meas_hist_cdsem,meas_hist_hvsem`) carries two MinIO paths —
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
  `minio_pkl`, or a non-dict pickle all return `None` → 404, same as the mock.
  - The parent lookup goes through `_office_meas_hist.msr_clause`, never a bare
    `msr.keyword` term. `_id` and `msr` are supposed to hold the same value,
    but the `msr` field is absent on 21,474 of 2,250,652 office documents
    (office 확인 2026-08-20, believed to be a loader defect) — including the
    newest, which are the ones a 스큐보아 search surfaces — and there the id
    lives only in the document `_id`. A field-only query returns `None` for those, which the UI
    renders as "this measurement has no data" while its `minio_pkl` sits
    populated in the very document the query failed to find.
- Normalization gaps handled by `build_response` (pure, pinned at home by
  `tests/test_office_template.py`): spaced pickle columns
  (`"mp_image_name 01"`, `"meas_condition mag"`) → underscore names —
  **including every `"mp_image_name NN"` column**: since 2026-08-08 the row
  carries them all as `mp_image_names` (NN order, `_mp_image_names`), because
  HV-SEM shoots one targeting point as several stem-suffixed files
  (`S04_M0004-01MP-U.jpeg` / `-T` / `-M` / `-L`, sometimes `.tif` only) and a
  `_01`-only row structurally hid the rest —
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

## 픽클 보존(retention) — 이 앱은 읽기만 합니다

`minio_pkl` 픽클은 **캐시가 아니라 원천 데이터**입니다. 이 어댑터는
`MinioObject().get_pickle` 로 읽기만 하고 쓰지 않으며, 삭제된 픽클을 raw
`.MSR` 텍스트에서 되만드는 것은 금지되어 있습니다(후처리 파이프라인 중복).
따라서 잘못 지운 픽클의 복구 수단은 상위 파이프라인 재실행뿐입니다.

키 레이아웃은 `user / 2067928/hitachi_sem/{cdsem,hvsem}/{raw_msr,dict_pkl}/
YYYY/MM/DD/` 입니다(user-confirmed 2026-07-28, `docs/datatables/msr_file_pickle.txt`).
pickle 과 raw 원본은 확장자가 아니라 **형제 폴더**로 갈리고, 그 아래가 날짜
파티션이라는 두 가지가 정리 방식을 결정합니다.

`flask_modules` 저장소의 Airflow DAG `minio_purge_old_pickles`(매일 04:05 KST)가
`dict_pkl` 파티션만 **61일** 기준으로 지웁니다. `kinds=("dict_pkl",)` 로 범위를
잡으므로 `raw_msr` 원본은 필터로 걸러지는 것이 아니라 **애초에 순회 대상이
아닙니다**. 또 날짜가 키에 들어 있으므로 오브젝트 전수 조회 없이 파티션 폴더만
훑습니다.

61이라는 값은 meas_hist 의 60일 조회 창(`RETENTION_DAYS`)에서 나온 것으로,
여유가 하루뿐인 데다 그 창은 `now` 가 아니라 **anchor = max(timestamp)**
기준입니다. 적재가 L일 밀리면 실질 여유는 `1 - L`일이 되므로, 적재 지연이
하루라도 상시화되면 DAG 의 `RETENTION_DAYS` 를 반드시 올려야 합니다.

주의 2가지가 있습니다. (1) DAG 는 dry-run 기본값(Airflow Variable
`msr_pickle_purge_dry_run`)으로 배포되어 있으므로, 후보 목록을 확인한 뒤에
Variable 을 끄십시오. (2) 같은 모듈의 일회성 스크립트
(`hitachi_sem_partition_purge.py` 의 `__main__`)는 기본값이 **30일 · 두 kind
전부**입니다. 그대로 실행하면 60일 창이 아직 서비스하는 픽클과 raw 원본까지
지웁니다 — 회수(reclaim)용이지 이 정책이 아닙니다.

이미지 캐시(7일, `2067928/image_cache/`)와는 prefix 가 분리되어 있어 서로
건드리지 않습니다 — `msr_image/MIGRATION.md` 참고.

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
