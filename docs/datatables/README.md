# 데이터 테이블 스키마 문서

사무실(Phase 2/3) 실데이터 소스의 **구조와 스키마**를 기록하는 폴더입니다. 집에서는
실제 소스에 접근할 수 없으므로, 이 문서들이 office 어댑터(`providers/office.py`)를
작성할 때의 유일한 근거입니다.

**방향 규칙:** 스키마의 진실 원천은 이 문서이고, 어댑터가 문서를 따릅니다. 사무실에서
실제 데이터가 문서와 다르다는 것이 확인되면 **문서를 먼저 고치고** 어댑터를 맞춥니다.
반대로 어댑터를 고치고 문서를 두면 다음 사람이 같은 함정에 다시 빠집니다.

각 문서에는 확인 근거를 함께 적습니다 — `office 확인 YYYY-MM-DD`(사무실 실행으로
검증됨), `user-confirmed`(담당자 확인), `OFFICE-VERIFY`(아직 미검증 가정).

## 파일 → 소스 → 소비 feature

`상태`는 해당 feature의 office 어댑터 연결 여부입니다(2026-07-27 기준).

| 문서 | 사무실 소스 | 소비 feature | 상태 |
| --- | --- | --- | --- |
| `sem_list.txt` | Redis `v3_df_sem_avail` + `v3_df_sem_version` | `sem_list` | 연결 |
| `storage_ppid.txt` | Redis `v3_df_ppid_storage_{cdsem,hvsem}` + `v3_hitachi_sem_ppid_not_avail` | `ebeam/hitachi/storage` | 연결 |
| `meas_hist.txt` | OpenSearch `meas_hist_cdsem` / `meas_hist_hvsem` | `meas_hist`, `recipe_tat`, `fail_issue`, `msr_file`, `lateral_recipe` | 연결 |
| `ebeam_tas_lot_hist.txt` | OpenSearch `ebeam_tas_lot_hist` | `recipe_tat`, `fail_issue` (lot_id↔lot_cd 다리) | 연결 |
| `device_desc.txt` | Redis `device_desc` | `recipe_tat`, `fail_issue`, `device_statistics` | 연결 |
| `r3_device_grp.txt` | Redis `r3_device_grp` | 위와 동일 (R3/R&D) | 연결 |
| `msr_file_pickle.txt` | MinIO — meas_hist 문서의 `minio_pkl` 경로 | `msr_file` | 연결 |
| `msr_image_ftp.txt` | 장비 FTP `/HITACHI/DEVICE/HD/...` | `msr_image` | 연결 |
| `idp_ver.txt` | OpenSearch `cdsem_idp_ver` / `hvsem_idp_ver` | `lateral_recipe` | 연결 |
| `recipe_name_list.txt` | Redis `v3_cdsem_unique_rcp_list` / `v3_hvsem_unique_rcp_list` | `recipe_search` (목록만) | 연결 |
| `live_alarm_board.txt` | 사내 alarm API → Redis ZSET 보드 | `live_alarm` | 연결 |
| `hardware_beam_shape.txt` | OpenSearch `beam_shape_cdsem` | `hardware/bsm` | 연결 |
| `hardware_network_fdc_cdsem.txt` | OpenSearch `network_fdc_cdsem` | `hardware/fdc` | 연결 |
| `hardware_sharpness_monitor_cdsem.txt` | OpenSearch `sharpness_monitor_cdsem` | `hardware/sharpness` | 연결 |
| `hardware_sce_setting.txt` | Redis `sce_info` + MinIO `hitachi_sem/cdsem/sce_info/` | `hardware/sce` | 연결 |
| `hardware_fab_inform_notes.txt` | OpenSearch `fab_inform_notes` | `hardware/bm_pm` (실적) | 연결 |
| `hardware_tool_maintenance_plan.txt` | OpenSearch `tool_maintenance_plan` | `hardware/bm_pm` (계획) | 연결 |
| `hardware_reso_center_data.txt` | OpenSearch `reso_center_cdsem` | `hardware/reso_center` | **미연결** |
| `hardware_mdc_setting.txt` | Redis(fab별 최신) + MinIO(날짜별 이력) | `hardware/mdc` | **미연결** |
| `recipe_idp.txt` | 미정 — IDP 원본 파싱 필요 | `recipe_search` 자세히 보기 | **미연결**(mock) |
| `parameter_info.txt` | 미정 — `recipe_idp` 와 같은 소스로 추정 | `recipe_search` 자세히 보기 | **미연결**(mock) |
| `recipe_params.txt` | 미정 | `device_statistics` | **미연결**(mock) |
| `device_info.txt` | 파생 — `device_desc` 의 요약 view | `device_statistics` | 파생(원천 아님) |
| `hardware.txt` | 데이터 소스 아님 — FDC 파라미터 해설 | `msr_file` mock, 스큐보아 | 참고 |
| `cdsem_mag_pixel_table.txt` | 데이터 소스 아님 — mag/FOV/pixel 계산식 | 프론트 mag-pixel 화면 | 참고 |

`health` feature 는 연결되어 있지만 데이터 테이블을 읽지 않습니다. Redis/OpenSearch/MinIO
세 서버의 생존 여부만 probe 하므로 이 폴더에 해당 문서가 없습니다.

## 아직 사무실 소스가 없는 항목

아래는 화면은 있으나 office 어댑터가 mock 을 그대로 재사용하는 부분입니다. 새 소스를
찾으면 해당 문서부터 채워야 합니다.

- **recipe 자세히 보기** (`recipe_idp.txt`, `parameter_info.txt`) — `recipe_search` 의
  office 어댑터는 recipe **이름 목록**만 Redis 에 연결되어 있고, 열람/비교
  (`get_recipe_open_data` / `get_recipe_compare_data`)는 mock 을 re-export 합니다.
  IDP 원본이 사무실에서 준비되어야 연결할 수 있습니다.
- **hardware/mdc, hardware/reso_center** — 템플릿은 있으나 본문이
  `NotImplementedError` 입니다. `hardware` 를 office 로 켜도 이 두 sub-tab 은 동작하지
  않습니다.

## 파일 이름 규칙

`hardware` feature 는 sub-tab 마다 소스가 따로입니다(bsm, fdc, sharpness, sce,
bm_pm, reso_center, mdc — 8개 문서). 폴더 목록에서 흩어지지 않도록 **`hardware_`
접두사**로 묶습니다. 접두사 없는 `hardware.txt` 는 데이터 소스 문서가 아니라 장비
변곡점 판단에 쓰는 FDC 파라미터 해설이며, 정렬상 그 그룹의 머리에 옵니다.

다른 feature 도 소스가 여러 개로 늘어나면 같은 방식으로 묶습니다.

각 `hardware_*` 문서는 스키마 뒤에 **"어댑터 소비 규약"** 절을 답니다 — 어느 field
를 어떤 조건으로 읽고, 무엇을 일부러 읽지 않으며, 어떤 값을 정규화하는지입니다.
스키마만 있고 이 절이 없으면 사무실에서 같은 함정(예: analyzed text 에 term 걸기,
길이 16이 아닌 배열이 조용히 사라지기)을 매번 다시 밟게 됩니다.

## 표기 규칙

- 컬럼 설명은 `이름 -> 타입: 설명` 한 줄 형식을 씁니다.
- OpenSearch `text` field 의 정확 일치·집계는 반드시 `.keyword` subfield 를 씁니다.
  문서에도 어느 쪽을 쓰는지 명시합니다.
- 시각(timestamp)은 사무실 인덱스 공통으로 **offset 없는 KST wall-clock** 입니다.
  `Z` 접미사가 붙어 저장되는 소스를 발견하면 9시간 어긋나므로 문서에 반드시 적습니다.
- Redis 의 DataFrame 은 parquet 직렬화(`df.to_parquet()`, 값 선두 4바이트 `PAR1`)
  입니다. `_runtime/office_redis.py` 의 `read_dataframe` 이 역직렬화를 담당합니다.
