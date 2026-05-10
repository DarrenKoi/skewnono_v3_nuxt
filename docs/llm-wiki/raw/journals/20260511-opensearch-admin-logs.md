# Journal — 2026-05-11 OpenSearch admin logs

> 정제하지 말 것. 거친 채로 빠르게.

## 한 일

- `skewnono_logging` alias에 쓰는 production logging 경로를 보강했다.
- request log에 `feature`, `activity_weight`, `request_path`, `query_string`, `error_code`, `error_name` 필드를 추가했다.
- HTTP status 기준으로 2xx/3xx는 `INFO`, 4xx는 `WARNING`, 5xx는 `ERROR`로 기록하게 했다.
- Flask unhandled exception을 `request_exception` 이벤트로 남기고 stack trace를 `exception.stack`에 담게 했다.
- `/api/admin/logs` backend API를 추가해서 `skewnono_logging`을 시간, level, event, status, user, feature, method, path, text query로 조회하게 했다.
- `/admin/logs` Nuxt page를 추가했다. navigation에는 연결하지 않고 URL을 직접 입력해서 들어가는 운영자용 화면이다.
- `ops_index_mgmt/skewnono_logging.py` dry-run 결과에 새 mapping field와 existing alias mapping update request가 나오게 했다.
- `opensearch-py>=2,<3`를 backend requirements에 추가했다.

## 왜 그렇게 했는가

- request 성공/실패와 function failure를 같은 `skewnono_logging` index에서 보게 하면 운영 화면 query가 단순하다.
- 별도 error index는 volume이 확인된 뒤에 나눠도 되므로 v1에서는 `level`, `event`, `status`, `feature` filter로 충분하다.
- log shipping은 request path를 막으면 안 되므로 기존 queue + background bulk 구조를 유지했다.
- `/api/admin/logs`와 `/api/activity/*` 조회는 activity score에 포함하지 않도록 했다. 로그 확인 행동이 leaderboard 점수를 올리면 운영자가 볼 때 데이터가 흐려진다.

## 막힌 지점 / 시도와 실패

- `back_dev_home` route auto-discovery는 `routes.py` 파일 자체가 아니라 package module의 `bp` export를 기대했다. 그래서 `back_dev_home/admin_logs/__init__.py`에서 `bp`를 re-export했다.
- local 환경에는 OpenSearch가 없어서 `/api/admin/logs` smoke test는 503이 맞다. 처음에는 localhost:443 연결을 시도하면서 오래 기다렸고, 이후 `OPENSEARCH_PASSWORD`가 없으면 빠르게 실패하도록 바꿨다.
- 전체 frontend lint는 기존 AFM/recipe statistics 파일의 unrelated lint error 때문에 실패했다. 새 파일만 대상으로 한 eslint와 Nuxt typecheck는 통과했다.

## 다음에 할 것

- cloud 환경에서 `OPENSEARCH_HOST`, `OPENSEARCH_USER`, `OPENSEARCH_PASSWORD`를 설정한 뒤 `python -m ops_index_mgmt.skewnono_logging --dry-run`과 실제 setup을 실행한다.
- 운영 cluster에서 `/api/admin/logs?level=ERROR`가 5xx와 `request_exception` 문서를 보여주는지 확인한다.
- activity leaderboard를 OpenSearch aggregate index로 전환하는 작업은 별도 task로 남긴다.

## 관련

- 코드: `back_dev_home/_logging/activity.py`
- 코드: `back_dev_home/_logging/opensearch_handler.py`
- 코드: `back_dev_home/admin_logs/routes.py`
- 코드: `back_dev_home/admin_logs/data.py`
- 코드: `front-dev-home/app/pages/admin/logs.vue`
- 코드: `ops_index_mgmt/skewnono_logging.py`
