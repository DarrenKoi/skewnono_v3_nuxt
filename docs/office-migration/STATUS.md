# Mock → Office 전환 현황

백엔드 기능별 데이터 소스 전환 체크리스트입니다. 각 기능의 전환 절차는
해당 폴더의 `MIGRATION.md`에 있으며, 계약 테스트가 통과한 뒤에만
환경변수를 전환합니다.

## 전환 절차

1. GLM이 `back_dev_home/<기능>/MIGRATION.md`를 읽고 `providers/office.py`를 구현합니다.
2. 계약 테스트가 office 모드에서 통과해야 합니다. 저장소 루트에서
   `SKEWNONO_<기능>_PROVIDER=office .venv/bin/pytest back_dev_home/<기능>` 형식으로
   실행하며, 이는 각 기능의 `MIGRATION.md` Verify 명령과 동일합니다.
3. Flask 실행 환경변수에 `SKEWNONO_<기능>_PROVIDER=office`를 추가하고 재시작한 뒤,
   아래 표의 상태/검증일을 갱신합니다.

## 상태 값

| 값 | 뜻 |
| --- | --- |
| mock | 아직 office 어댑터를 구현하지 않았습니다. `office_example.py`는 뼈대만 있습니다. |
| 구현완료 | `office_example.py`에 조회 로직을 다 채웠지만 사내 데이터로 돌려보지 않았습니다. 위 절차의 2~3단계가 남았습니다. |
| 구현완료(부분) | 일부 엔드포인트만 office 소스에 연결했고, 나머지는 사내 데이터가 아직 준비되지 않아 mock 응답을 그대로 내보냅니다. 어느 엔드포인트가 mock으로 남아 있는지는 해당 `MIGRATION.md`의 `## Status` 절에 적습니다. |
| office | office 모드로 계약 테스트가 통과했고 화면에서 실데이터를 확인했습니다. 검증일을 함께 적습니다. |

`구현완료`에서 `office`로 넘어가려면 `office_example.py`를 같은 폴더에
`office.py`로 복사한 뒤(이 파일은 사내 스키마가 들어가므로 gitignore 대상입니다)
계약 테스트를 office 모드로 실행합니다.

msr_file의 office 어댑터는 위 절차 외에 4개의 office-gated 메타데이터 키
(`site_layout_hash`, `recipe_revision`, `coordinate_transform_version`,
`sequence_timestamp`)를 반드시 함께 반환해야 합니다. 자세한 내용은
`msr_file/MIGRATION.md`를 참고합니다.

## 현황

| 기능 | 환경변수 | 계약 | MIGRATION | 상태 | 검증일 |
| --- | --- | --- | --- | --- | --- |
| activity | SKEWNONO_ACTIVITY_PROVIDER | activity/contracts.py | activity/MIGRATION.md | mock | - |
| admin_logs | SKEWNONO_ADMIN_LOGS_PROVIDER | admin_logs/contracts.py | admin_logs/MIGRATION.md | mock | - |
| announcements | SKEWNONO_ANNOUNCEMENTS_PROVIDER | announcements/contracts.py | announcements/MIGRATION.md | mock | - |
| api_tokens | SKEWNONO_API_TOKENS_PROVIDER | api_tokens/contracts.py | api_tokens/MIGRATION.md | mock | - |
| access_control | SKEWNONO_ACCESS_CONTROL_PROVIDER | access_control/contracts.py | access_control/MIGRATION.md | mock | - |
| health | SKEWNONO_HEALTH_PROVIDER | health/contracts.py | health/MIGRATION.md | 구현완료 | - |
| device_statistics | SKEWNONO_DEVICE_STATISTICS_PROVIDER | ebeam/cdsem/device_statistics/contracts.py | ebeam/cdsem/device_statistics/MIGRATION.md | mock | - |
| pm_planning | SKEWNONO_PM_PLANNING_PROVIDER | ebeam/hitachi/pm_planning/contracts.py | ebeam/hitachi/pm_planning/MIGRATION.md | mock | - |
| recipe_search | SKEWNONO_RECIPE_SEARCH_PROVIDER | ebeam/hitachi/recipe_search/contracts.py | ebeam/hitachi/recipe_search/MIGRATION.md | 구현완료(부분) | - |
| lateral_recipe | SKEWNONO_LATERAL_RECIPE_PROVIDER | ebeam/hitachi/lateral_recipe/contracts.py | ebeam/hitachi/lateral_recipe/MIGRATION.md | 구현완료 | - |
| sem_list | SKEWNONO_SEM_LIST_PROVIDER | sem_list/contracts.py | sem_list/MIGRATION.md | office | 2026-07-20 |
| hardware | SKEWNONO_HARDWARE_PROVIDER | ebeam/hitachi/hardware/contracts.py | ebeam/hitachi/hardware/MIGRATION.md | mock | - |
| skew | SKEWNONO_SKEW_PROVIDER | ebeam/hitachi/skew/contracts.py | ebeam/hitachi/skew/MIGRATION.md | mock | - |
| storage | SKEWNONO_STORAGE_PROVIDER | ebeam/hitachi/storage/contracts.py | ebeam/hitachi/storage/MIGRATION.md | office | 2026-07-21 |
| meas_hist | SKEWNONO_MEAS_HIST_PROVIDER | meas_hist/contracts.py | meas_hist/MIGRATION.md | 구현완료 | - |
| afm | SKEWNONO_AFM_PROVIDER | afm/contracts.py | afm/MIGRATION.md | mock | - |
| recipe_tat | SKEWNONO_RECIPE_TAT_PROVIDER | ebeam/hitachi/recipe_tat/contracts.py | ebeam/hitachi/recipe_tat/MIGRATION.md | 구현완료 | - |
| fail_issue | SKEWNONO_FAIL_ISSUE_PROVIDER | ebeam/hitachi/fail_issue/contracts.py | ebeam/hitachi/fail_issue/MIGRATION.md | mock | - |
| msr_file | SKEWNONO_MSR_FILE_PROVIDER | msr_file/contracts.py | msr_file/MIGRATION.md | 구현완료(부분) | - |

(모든 계약/MIGRATION 경로는 `back_dev_home/` 기준 상대 경로입니다.)
