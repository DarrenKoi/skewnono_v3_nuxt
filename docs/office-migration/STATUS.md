# Mock → Office 전환 현황

백엔드 기능별 데이터 소스 전환 체크리스트입니다. 각 기능의 전환 절차는
해당 폴더의 `MIGRATION.md`에 있습니다.

## 전환 절차

1. GLM이 `back_dev_home/<기능>/MIGRATION.md`를 읽고 `providers/office.py`를 구현합니다.
2. 계약 테스트가 office 모드에서 통과해야 합니다. 저장소 루트에서
   `SKEWNONO_<기능>_PROVIDER=office .venv/bin/pytest back_dev_home/<기능>` 형식으로
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

| 기능 | 환경변수 | 계약 | MIGRATION | 상태 | 검증일 |
| --- | --- | --- | --- | --- | --- |
| activity | SKEWNONO_ACTIVITY_PROVIDER | activity/contracts.py | activity/MIGRATION.md | 구현완료 | - |
| admin_logs | SKEWNONO_ADMIN_LOGS_PROVIDER | admin_logs/contracts.py | admin_logs/MIGRATION.md | 구현완료 | - |
| announcements | SKEWNONO_ANNOUNCEMENTS_PROVIDER | announcements/contracts.py | announcements/MIGRATION.md | 구현완료 | - |
| api_tokens | SKEWNONO_API_TOKENS_PROVIDER | api_tokens/contracts.py | api_tokens/MIGRATION.md | 구현완료 | - |
| access_control | SKEWNONO_ACCESS_CONTROL_PROVIDER | access_control/contracts.py | access_control/MIGRATION.md | 구현완료 | - |
| health | SKEWNONO_HEALTH_PROVIDER | health/contracts.py | health/MIGRATION.md | 구현완료 | - |
| device_statistics | SKEWNONO_DEVICE_STATISTICS_PROVIDER | ebeam/device_statistics/contracts.py | ebeam/device_statistics/MIGRATION.md | mock | - |
| pm_planning | SKEWNONO_PM_PLANNING_PROVIDER | ebeam/pm_planning/contracts.py | ebeam/pm_planning/MIGRATION.md | mock | - |
| recipe_search | SKEWNONO_RECIPE_SEARCH_PROVIDER | ebeam/recipe_search/contracts.py | ebeam/recipe_search/MIGRATION.md | 구현완료(부분) | - |
| lateral_recipe | SKEWNONO_LATERAL_RECIPE_PROVIDER | ebeam/lateral_recipe/contracts.py | ebeam/lateral_recipe/MIGRATION.md | 구현완료 | - |
| sem_list | SKEWNONO_SEM_LIST_PROVIDER | sem_list/contracts.py | sem_list/MIGRATION.md | office | 2026-07-20 |
| hardware | SKEWNONO_HARDWARE_PROVIDER | ebeam/hardware/contracts.py | ebeam/hardware/MIGRATION.md | mock | - |
| tttm | SKEWNONO_TTTM_PROVIDER | ebeam/tttm/contracts.py | ebeam/tttm/MIGRATION.md | 보류 | - |
| storage | SKEWNONO_STORAGE_PROVIDER | ebeam/storage/contracts.py | ebeam/storage/MIGRATION.md | office | 2026-07-21 |
| meas_hist | SKEWNONO_MEAS_HIST_PROVIDER | meas_hist/contracts.py | meas_hist/MIGRATION.md | 구현완료 | - |
| afm | SKEWNONO_AFM_PROVIDER | afm/contracts.py | afm/MIGRATION.md | 보류 | - |
| recipe_tat | SKEWNONO_RECIPE_TAT_PROVIDER | ebeam/recipe_tat/contracts.py | ebeam/recipe_tat/MIGRATION.md | 구현완료 | - |
| fail_issue | SKEWNONO_FAIL_ISSUE_PROVIDER | ebeam/fail_issue/contracts.py | ebeam/fail_issue/MIGRATION.md | 구현완료 | - |
| msr_file | SKEWNONO_MSR_FILE_PROVIDER | msr_file/contracts.py | msr_file/MIGRATION.md | 구현완료(부분) | - |

(모든 계약/MIGRATION 경로는 `back_dev_home/` 기준 상대 경로입니다.)

## 비고

- **afm과 tttm(구 skew)은 이번 버전에서 전환하지 않습니다(보류).** 두 화면은 랜딩
  페이지에서 감춰져 있고 차기 SKEWNONO 버전에서 열 예정이므로, office 어댑터
  구현도 office 연결 점검(`/home-to-office` 감사, `office_example.py` 채우기)도
  대상에서 제외합니다. 표에 행을 남겨 두는 이유는 기능이 사라진 것이 아니라
  뒤로 미뤄졌음을 기록하기 위해서입니다. chat도 같은 이유로 보류 상태이며,
  chat은 아예 행이 없습니다.
- **hardware는 탭 단위로 전환합니다.** `providers/`가 탭별 하위 폴더로 나뉘어
  있고, 디스패처가 `providers/<탭>/office.py`를 지연 임포트합니다. `office.py`가
  아직 없는 탭은 같은 폴더의 `mock.py`로 폴백하므로,
  `SKEWNONO_HARDWARE_PROVIDER=office`를 한 번만 켜 두고 탭을 하나씩 연결하며
  검증할 수 있습니다. 현재 office 어댑터가 있는 탭은 `fdc/` 하나이며, 나머지
  6개 탭은 mock을 그대로 보여 줍니다.
- 폴백은 **응답에 표시되지 않습니다**(mock 표식 없음). 어떤 탭이 실데이터인지는
  `ls providers/*/office.py` 또는 디스패처가 폴백마다 남기는 INFO 로그로만
  확인할 수 있으므로, office 화면을 사내 데이터로 읽기 전에 반드시 확인합니다.
  `office.py`가 있는데 임포트에 실패하는 탭은 폴백하지 않고 예외를 냅니다.
- 표의 hardware 상태는 7개 탭이 모두 연결될 때까지 `mock`으로 둡니다.
- `.env.example`에는 더 이상 기능별 프로바이더 목록이 없습니다. 어떤 기능이
  전환되는지는 `providers/office.py` 파일의 존재 여부가 결정하므로, 목록을
  손으로 맞출 필요가 없어졌습니다. 현재 상태는 `GET /api/health/providers`
  또는 기동 로그의 provider 표에서 확인합니다.
- 그 표는 **무엇이 전환되는지**만 나타냅니다. 실데이터로 검증했는지 여부는
  위 표의 `상태`/`검증일` 열이 유일한 기준입니다.
- **2026-08-01 운영·관리 6개 기능 정비** — activity, admin_logs, announcements,
  api_tokens, access_control, health을 정리하고 권한·장애 처리를 손봤습니다.
  사내 데이터로 돌려본 것은 아니므로 여섯 행의 `상태`는 모두 `구현완료`
  그대로입니다. 다만 이미 `office.py`를 복사해 둔 checkout이 있다면 아래 두
  기능은 **반드시 다시 복사해야 합니다**. 어댑터가 임포트하는 대상이 바뀌어,
  옛 복사본은 폴백하지 않고 app factory 기동 자체를 실패시킵니다.

  | 기능 | 재복사 | 이유 |
  | --- | --- | --- |
  | announcements | 필요 | `_is_active`가 `is_active`로 공개되었습니다 |
  | health | 필요 | probe 본체가 `providers/probe_common.py`로 이동했습니다 |
  | activity | 불필요 | office 껍데기는 그대로이고, 바뀐 `opensearch_reader.py`는 git 추적 대상입니다 |
  | admin_logs | 불필요 | 바뀐 `query.py`가 git 추적 대상입니다 |
  | api_tokens · access_control | 불필요 | `office_example.py`를 건드리지 않았습니다 |

  재복사 명령은 `python -m scripts.sync_office_adapters <기능>`입니다. 기동
  로그의 `STALE office.py:` 줄이 대상 기능을 짚어 주므로, 먼저 로그를 봐도
  됩니다.
