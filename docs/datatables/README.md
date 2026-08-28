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

`상태`는 해당 feature의 office 어댑터 연결 여부입니다.

| 문서 | 사무실 소스 | 소비 feature | 상태 |
| --- | --- | --- | --- |
| `hitachi/members.txt` | Redis hash `members` | `_auth` (사용자 이름·소속, `GET /api/me`) | 구현완료(스키마 user-confirmed, 실행 검증 대기) |
| `hitachi/sem_list.txt` | Redis `v3_df_sem_avail` + `v3_df_sem_version` | `sem_list` | 연결 |
| `hitachi/storage_ppid.txt` | Redis `v3_df_ppid_storage_{cdsem,hvsem}` + `v3_hitachi_sem_ppid_not_avail` | `ebeam/storage` | 연결 |
| `hitachi/meas_hist.txt` | OpenSearch `meas_hist_cdsem` / `meas_hist_hvsem` | `meas_hist`, `recipe_tat`, `fail_issue`, `msr_file`, `lateral_recipe`, `ebeam/tttm`, `ebeam/pm_planning`(CD 모니터링 recipe 포함) | 연결 |
| `hitachi/ebeam_tas_lot_hist.txt` | OpenSearch `ebeam_tas_lot_hist` | `recipe_tat`, `fail_issue` (lot_id↔lot_cd 다리), `device_statistics`(M fab 공정 스텝) | 연결(device_statistics 제외) |
| `hitachi/device_desc.txt` | Redis `device_desc` | `recipe_tat`, `fail_issue`, `device_statistics` | 연결 |
| `hitachi/r3_device_grp.txt` | Redis `r3_device_grp` | 위와 동일 (R3/R&D) | 연결 |
| `hitachi/planstep_r3.txt` | OpenSearch `sknn-planstep-r3` | `device_statistics` (R3 공정 스텝; M fab 은 `ebeam_tas_lot_hist`) | 구현완료(사무실 검증 대기) |
| `hitachi/msr_file_pickle.txt` | MinIO — meas_hist 문서의 `minio_pkl` 경로 | `msr_file`, `ebeam/tttm`, `ebeam/pm_planning` | 연결 |
| `hitachi/msr_image_ftp.txt` | 장비 FTP `/HITACHI/DEVICE/HD/...` | `msr_image` | 연결 |
| `hitachi/idp_ver.txt` | OpenSearch `cdsem_idp_ver` / `hvsem_idp_ver` | `lateral_recipe`, `device_statistics`(파라미터 개수 — `parameters` blob) | 연결(lateral_recipe만) |
| `hitachi/recipe_name_list.txt` | Redis `v3_{cdsem,hvsem}_unique_rcp_list` + `v3_{cdsem,hvsem}_rcp_loc_{fab}` + `v3_{cdsem,hvsem}_tools_in_rcp_{fab}` | `recipe_search` | 연결 |
| `hitachi/live_alarm_board.txt` | 사내 alarm API → Redis ZSET 보드 | `live_alarm` | 연결 |
| `hitachi/hardware_beam_shape.txt` | OpenSearch `beam_shape_cdsem` | `hardware/bsm` | 연결 |
| `hitachi/hardware_network_fdc_cdsem.txt` | OpenSearch `network_fdc_cdsem` | `hardware/fdc` | 연결 |
| `hitachi/hardware_sharpness_monitor_cdsem.txt` | OpenSearch `sharpness_monitor_cdsem` | `hardware/sharpness` | 연결 |
| `hitachi/hardware_sce_setting.txt` | Redis `sce_info` + MinIO `hitachi_sem/cdsem/sce_info/` | `hardware/sce` | 연결 |
| `hitachi/hardware_bm_pm.txt` | OpenSearch `fab_inform_notes`(실적) + `tool_maintenance_plan`(계획) | `hardware/bm_pm` | 연결 |
| `hitachi/hardware_reso_center_data.txt` | OpenSearch `reso_center_cdsem` | `hardware/reso_center` | 연결 |
| `hitachi/hardware_mdc_setting.txt` | Redis `mdc_setting` + MinIO `hitachi_sem/cdsem/mdc_setting/` | `hardware/mdc`, `ebeam/tttm`, `ebeam/pm_planning` | 연결 |
| `hitachi/skewnono_logging.txt` | OpenSearch `skewnono_logging{,_local}` (자체 생성) | `activity`, `admin_logs` | 연결(alias office 확인 2026-07-28) |
| `hitachi/skewnono_chat_logging.txt` | OpenSearch `skewnono_chat_logging{,_local}` (자체 생성) | `chat` (대화 turn 기록) | 연결(alias 생성 user-confirmed 2026-08-04) |
| `hitachi/chat_rag_contract.txt` | 사내 RAG 저장소(in-process, `chat/_rag/`) + MinIO figure 저장소 | `chat` (근거 검색·질의 rewrite·follow-ups) | 구현완료(사무실 검증 대기) — office 어댑터 template 완성 2026-08-28 |
| `chat/chat_office_adapter_handoff.txt` | RAG 측 agent 의 handoff 편지(2026-08-27) — 공개 API 셋과 seam 채우기 지시 | `chat` | 참고 문서(원문 보존, 오탈자 포함) |
| `hitachi/recipe_idp.txt` | 장비 FTP `/HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}.idp` → `office_utils.read_idp_info` | `recipe_search` 자세히 보기 | 연결 |
| `hitachi/parameter_info.txt` | 미정 — IDP 파서가 돌려주지 않음(`amp_info`) | `recipe_search` 자세히 보기 | **미연결**(mock) |
| `hitachi/recipe_params.txt` | `sknn-planstep-r3`(recipe 목록) + `cdsem_idp_ver`(파라미터) — `planstep_r3.txt` 참고 | `device_statistics` | 구현완료(사무실 검증 대기) |
| `hitachi/device_statistics_weekly_trend.txt` | MinIO `device_statistics/weekly_trend/YYYY-MM-DD.json` (자체 생성) | `device_statistics` (recipe-trend) | 어댑터 구현완료, **적재 스케줄러 미구현** |
| `hitachi/device_info.txt` | 파생 — `device_desc` / `r3_device_grp` 의 요약 view | `device_statistics` | 파생(원천 아님) |
| `hitachi/hardware.txt` | 데이터 소스 아님 — FDC 파라미터 해설 | `msr_file` mock, 스큐보아 | 참고 |
| `hitachi/cdsem_mag_pixel_table.txt` | 데이터 소스 아님 — mag/FOV/pixel 계산식 | 프론트 mag-pixel 화면 | 참고 |

`health` feature 는 연결되어 있지만 데이터 테이블을 읽지 않습니다. Redis/OpenSearch/MinIO
세 서버의 생존 여부만 probe 하므로 이 폴더에 해당 문서가 없습니다.

## 아직 사무실 소스가 없는 항목

아래는 화면은 있으나 office 어댑터가 mock 을 그대로 재사용하는 부분입니다. 새 소스를
찾으면 해당 문서부터 채워야 합니다.

- **측정 방향(X/Y)** — `tttm` 과 `pm_planning` 의 계약이 요구하는 axis 를 담은
  컬럼이 pickle 에도 meas_hist 에도 없습니다. 방향은 parameter **이름**에
  들어 있으나 이름 짓는 방식이 recipe·fab 마다 매우 다양하므로
  (user-confirmed 2026-08-18), `SKEWNONO_AXIS_PARAM_MAP`(glob 지원)으로
  채웁니다. 못 채우면 그 행을 **버립니다** — 기본값을 넣지 않습니다.
  자세한 내용은 `hitachi/msr_file_pickle.txt` 의 해당 절.
- **CD 스펙 창과 BSM 합격 밴드** — `pm_planning` 의 mock 이 쓰는
  `spec_range_mock` 의 숫자는 지어낸 값입니다. office 어댑터는 장비 그룹의
  중앙값 ±1 %(팹이 밝힌 action limit)와 장비 그룹 상대 MAD 이상치 검정으로
  **대신하며**, 따라서 `cd_in_spec` 의 뜻이 "기록된 스펙 안"이 아니라
  "형제 장비들과 일치"입니다. 실제 스펙이 나오면 이 항목부터 채우십시오.
- **recipe 비교** (`hitachi/recipe_idp.txt`, `hitachi/parameter_info.txt`) — `recipe_search` 의
  office 어댑터는 recipe **이름 목록**과 **열람**(`get_recipe_open_data`)까지
  연결되었습니다 — Redis 레지스트리(`v3_*_rcp_loc_*` / `v3_*_tools_in_rcp_*`)를
  먼저 찾고, 없으면 measurement history 로 넘어가 장비 FTP 의 `.idp` 파일을
  받아 `office_utils.read_idp_info.combined_idp_info()` 로 파싱합니다. 다만
  **비교**(`get_recipe_compare_data`)는 여전히 mock 을 re-export 합니다 —
  열람에서 파생되는 관계를 유지하려면 tool 당 FTP 세션 1개로 최대 200개 recipe 의
  `.idp` 를 배치 조회하는 구현이 필요하기 때문입니다. `align_images` 와
  `amp_info` 두 항목은 이 파서가 돌려주지 않아 열람이 연결된 지금도 **여전히
  소스가 없습니다**. 자세한 내용은 `hitachi/recipe_idp.txt`.

## 파일 이름 규칙

`hardware` feature 는 sub-tab 마다 소스가 따로입니다(bsm, fdc, sharpness, sce,
bm_pm, reso_center, mdc — 8개 문서). 폴더 목록에서 흩어지지 않도록 **`hardware_`
접두사**로 묶습니다. 접두사 없는 `hitachi/hardware.txt` 는 데이터 소스 문서가 아니라 장비
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
  사무실 데이터가 한국 시간 기준으로 생성되기 때문입니다(user-confirmed 2026-08-20).
  `Z` 접미사가 붙어 저장되는 소스를 발견하면 9시간 어긋나므로 문서에 반드시 적습니다.
  예외가 하나 있습니다 — `skewnono_logging` 은 우리가 직접 쓰는 인덱스라 offset 을
  포함한 UTC 로 저장합니다. 사무실이 만든 데이터가 아니므로 규약 밖입니다.
- Redis 의 DataFrame 은 parquet 직렬화(`df.to_parquet()`, 값 선두 4바이트 `PAR1`)
  입니다. `_runtime/office_redis.py` 의 `read_dataframe` 이 역직렬화를 담당합니다.

## Vendor subdirectory convention

이 폴더는 한 사무실에 여러 장비 vendor 가 섞여 운영됨에 따라 vendor 별로
분리되어 있습니다. 현재 `hitachi/` 만 채워져 있고, `veritysem/` 과 `provision/` 은
다음 추가 대상의 stub 입니다. 새 vendor 를 이 폴더에 추가할 때는
`.claude/skills/add-vendor/SKILL.md` 의 절차를 따릅니다.
