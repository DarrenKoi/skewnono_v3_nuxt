# Mock → Office 전환 현황

백엔드 기능별 데이터 소스 전환 체크리스트입니다. 각 기능의 전환 절차는
해당 폴더의 `MIGRATION.md`에 있습니다.

## 전환 절차

1. GLM이 `backend/<기능>/MIGRATION.md`를 읽고 `providers/office.py`를 구현합니다.
2. 계약 테스트가 office 모드에서 통과해야 합니다. 저장소 루트에서
   `SKEWNONO_<기능>_PROVIDER=office .venv/bin/pytest backend/<기능>` 형식으로
   실행하며, 이는 각 기능의 `MIGRATION.md` Verify 명령과 동일합니다.
3. Flask를 재시작합니다. `providers/office.py` 파일이 존재하는 것 자체가
   전환 신호이므로, `.env` 수정이나 코드 커밋은 필요하지 않습니다.
4. `GET /api/health/providers` 또는 기동 로그의 provider 표에서 해당 기능이
   `office`로 표시되는지 확인한 뒤, 아래 표의 상태/검증일을 갱신합니다.
   이 엔드포인트는 2026-08-01부터 관리자 전용이므로
   `curl -b "LASTUSER=<관리자 사번>" localhost:5000/api/health/providers`
   형태로 호출합니다. 쿠키 없이 부르면 403이 돌아옵니다. 쿠키를 쓸 수 없는
   상황이라면 기동 로그의 provider 표를 봅니다.

아래 표의 상태/검증일 컬럼은 "실제 사내 데이터로 확인되었는가"를 기록합니다.
`office.py`의 존재 여부(= 무엇이 전환되는가)와는 별개이며, 코드가 이 표를
읽지는 않습니다.

## 상태 값

| 값 | 뜻 |
| --- | --- |
| mock | 아직 office 어댑터를 구현하지 않았습니다. `office_example.py`는 뼈대만 있습니다. |
| 구현완료 | `office_example.py`에 조회 로직을 다 채웠지만 사내 데이터로 돌려보지 않았습니다. 위 절차의 2~3단계가 남았습니다. |
| 구현완료(부분) | 일부 엔드포인트만 office 소스에 연결했고, 나머지는 사내 데이터가 아직 준비되지 않아 mock 응답을 그대로 내보냅니다. 어느 엔드포인트가 mock으로 남아 있는지는 해당 `MIGRATION.md`의 `## Status` 절에 적습니다. |
| office | office 모드로 계약 테스트가 통과했고 화면에서 실데이터를 확인했습니다. 검증일을 함께 적습니다. |
| 보류 | 이번 버전에서 전환하지 않습니다. 화면 자체가 감춰져 있어 office 어댑터가 필요하지 않으며, office 점검 대상에서 제외합니다. |

`구현완료`에서 `office`로 넘어가려면 `office_example.py`를 같은 폴더에
`office.py`로 복사한 뒤(이 파일은 사내 스키마가 들어가므로 gitignore 대상입니다)
계약 테스트를 office 모드로 실행합니다.

msr_file의 office 어댑터는 위 절차 외에 4개의 office-gated 메타데이터 키
(`site_layout_hash`, `recipe_revision`, `coordinate_transform_version`,
`sequence_timestamp`)를 반드시 함께 반환해야 합니다. 자세한 내용은
`msr_file/MIGRATION.md`를 참고합니다.

## 현황

2026-11-01 기준으로 아래 23개 기능 모두 사내 데이터로 연결·검증을 마쳤습니다(user-confirmed 2026-11-01).
sem_list와 storage를 제외한 행의 검증일은 개별 확인일이 아니라 일괄 확인일입니다.

| 기능 | 환경변수 | 계약 | MIGRATION | 상태 | 검증일 |
| --- | --- | --- | --- | --- | --- |
| access_control | SKEWNONO_ACCESS_CONTROL_PROVIDER | access_control/contracts.py | access_control/MIGRATION.md | office | 2026-11-01 |
| activity | SKEWNONO_ACTIVITY_PROVIDER | activity/contracts.py | activity/MIGRATION.md | office | 2026-11-01 |
| admin_logs | SKEWNONO_ADMIN_LOGS_PROVIDER | admin_logs/contracts.py | admin_logs/MIGRATION.md | office | 2026-11-01 |
| afm | SKEWNONO_AFM_PROVIDER | afm/contracts.py | afm/MIGRATION.md | office | 2026-11-01 |
| announcements | SKEWNONO_ANNOUNCEMENTS_PROVIDER | announcements/contracts.py | announcements/MIGRATION.md | office | 2026-11-01 |
| api_tokens | SKEWNONO_API_TOKENS_PROVIDER | api_tokens/contracts.py | api_tokens/MIGRATION.md | office | 2026-11-01 |
| device_statistics | SKEWNONO_DEVICE_STATISTICS_PROVIDER | ebeam/device_statistics/contracts.py | ebeam/device_statistics/MIGRATION.md | office | 2026-11-01 |
| fail_issue | SKEWNONO_FAIL_ISSUE_PROVIDER | ebeam/fail_issue/contracts.py | ebeam/fail_issue/MIGRATION.md | office | 2026-11-01 |
| hardware | SKEWNONO_HARDWARE_PROVIDER | ebeam/hardware/contracts.py | ebeam/hardware/MIGRATION.md | office | 2026-11-01 |
| health | SKEWNONO_HEALTH_PROVIDER | health/contracts.py | health/MIGRATION.md | office | 2026-11-01 |
| lateral_recipe | SKEWNONO_LATERAL_RECIPE_PROVIDER | ebeam/lateral_recipe/contracts.py | ebeam/lateral_recipe/MIGRATION.md | office | 2026-11-01 |
| live_alarm | SKEWNONO_LIVE_ALARM_PROVIDER | ebeam/live_alarm/contracts.py | ebeam/live_alarm/MIGRATION.md | office | 2026-11-01 |
| meas_hist | SKEWNONO_MEAS_HIST_PROVIDER | meas_hist/contracts.py | meas_hist/MIGRATION.md | office | 2026-11-01 |
| msr_file | SKEWNONO_MSR_FILE_PROVIDER | msr_file/contracts.py | msr_file/MIGRATION.md | office | 2026-11-01 |
| msr_image | SKEWNONO_MSR_IMAGE_PROVIDER | msr_image/contracts.py | msr_image/MIGRATION.md | office | 2026-11-01 |
| pm_planning | SKEWNONO_PM_PLANNING_PROVIDER | ebeam/pm_planning/contracts.py | ebeam/pm_planning/MIGRATION.md | office | 2026-11-01 |
| recipe_search | SKEWNONO_RECIPE_SEARCH_PROVIDER | ebeam/recipe_search/contracts.py | ebeam/recipe_search/MIGRATION.md | office | 2026-11-01 |
| recipe_tat | SKEWNONO_RECIPE_TAT_PROVIDER | ebeam/recipe_tat/contracts.py | ebeam/recipe_tat/MIGRATION.md | office | 2026-11-01 |
| sem_list | SKEWNONO_SEM_LIST_PROVIDER | sem_list/contracts.py | sem_list/MIGRATION.md | office | 2026-07-20 |
| short_links | SKEWNONO_SHORT_LINKS_PROVIDER | short_links/contracts.py | short_links/MIGRATION.md | office | 2026-11-01 |
| storage | SKEWNONO_STORAGE_PROVIDER | ebeam/storage/contracts.py | ebeam/storage/MIGRATION.md | office | 2026-07-21 |
| tool_files | SKEWNONO_TOOL_FILES_PROVIDER | ebeam/tool_files/contracts.py | ebeam/tool_files/MIGRATION.md | office | 2026-11-01 |
| tttm | SKEWNONO_TTTM_PROVIDER | ebeam/tttm/contracts.py | ebeam/tttm/MIGRATION.md | office | 2026-11-01 |

(모든 계약/MIGRATION 경로는 `backend/` 기준 상대 경로입니다.)

## 비고

- **chat은 표에 없습니다.** 스레드 저장소가 집과 사무실에서 같은 코드
  (`chat/store.py`)라 `providers/`가 없고, RAG는 `_rag` checkout 기준으로
  따로 결정됩니다. 자세한 내용은 `chat/MIGRATION.md`를 참고합니다.
- **recipe_search의 `/compare`는 2026-11-01에 연결했고 아직 실데이터로
  확인하지 않았습니다.** recipe마다 열람(`get_recipe_open_data`)을 차례로 불러
  만들므로, 비교 결과가 열람 결과와 같습니다. recipe 10개 안쪽을 기준으로 한
  방식이며, 위치를 찾지 못하는 recipe가 하나라도 있으면 요청 전체가 실패합니다.
- **hardware는 탭 단위로 전환합니다.** 디스패처가 `providers/<탭>/office.py`를
  지연 임포트하고, 없는 탭은 같은 폴더의 `mock.py`로 **표시 없이** 폴백합니다.
  어떤 탭이 실데이터인지는 `ls providers/*/office.py` 또는 폴백마다 남는 INFO
  로그로만 확인할 수 있습니다. `office.py`가 있는데 임포트에 실패하는 탭은
  폴백하지 않고 예외를 냅니다.
- `GET /api/health/providers`와 기동 로그의 provider 표는 **무엇이 전환되는지**만
  나타냅니다. 실데이터로 검증했는지 여부는 위 표의 `상태`/`검증일` 열이 기준입니다.
- `office_example.py`가 바뀐 뒤 `git pull`만 하면 사내의 `office.py` 복사본은
  옛 코드로 계속 200을 내보냅니다. 기동 로그의 `STALE office.py: <기능>` 줄을
  확인하고 `python -m scripts.adapters.sync_office_adapters <기능>`으로 다시
  복사합니다.
