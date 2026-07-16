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
| health | SKEWNONO_HEALTH_PROVIDER | health/contracts.py | health/MIGRATION.md | mock | - |
| device_statistics | SKEWNONO_DEVICE_STATISTICS_PROVIDER | ebeam/cdsem/device_statistics/contracts.py | ebeam/cdsem/device_statistics/MIGRATION.md | mock | - |
| pm_planning | SKEWNONO_PM_PLANNING_PROVIDER | ebeam/hitachi/pm_planning/contracts.py | ebeam/hitachi/pm_planning/MIGRATION.md | mock | - |
| recipe_search | SKEWNONO_RECIPE_SEARCH_PROVIDER | ebeam/hitachi/recipe_search/contracts.py | ebeam/hitachi/recipe_search/MIGRATION.md | mock | - |
| lateral_recipe | SKEWNONO_LATERAL_RECIPE_PROVIDER | ebeam/lateral_recipe/contracts.py | ebeam/lateral_recipe/MIGRATION.md | mock | - |
| sem_list | SKEWNONO_SEM_LIST_PROVIDER | sem_list/contracts.py | sem_list/MIGRATION.md | mock | - |
| hardware | SKEWNONO_HARDWARE_PROVIDER | ebeam/hitachi/hardware/contracts.py | ebeam/hitachi/hardware/MIGRATION.md | mock | - |
| skew | SKEWNONO_SKEW_PROVIDER | ebeam/hitachi/skew/contracts.py | ebeam/hitachi/skew/MIGRATION.md | mock | - |
| storage | SKEWNONO_STORAGE_PROVIDER | ebeam/hitachi/storage/contracts.py | ebeam/hitachi/storage/MIGRATION.md | mock | - |
| meas_hist | SKEWNONO_MEAS_HIST_PROVIDER | meas_hist/contracts.py | meas_hist/MIGRATION.md | mock | - |
| afm | SKEWNONO_AFM_PROVIDER | afm/contracts.py | afm/MIGRATION.md | mock | - |
| recipe_tat | SKEWNONO_RECIPE_TAT_PROVIDER | ebeam/hitachi/recipe_tat/contracts.py | ebeam/hitachi/recipe_tat/MIGRATION.md | mock | - |
| fail_issue | SKEWNONO_FAIL_ISSUE_PROVIDER | ebeam/hitachi/fail_issue/contracts.py | ebeam/hitachi/fail_issue/MIGRATION.md | mock | - |
| msr_file | SKEWNONO_MSR_FILE_PROVIDER | msr_file/contracts.py | msr_file/MIGRATION.md | mock | - |

(모든 계약/MIGRATION 경로는 `back_dev_home/` 기준 상대 경로입니다.)
