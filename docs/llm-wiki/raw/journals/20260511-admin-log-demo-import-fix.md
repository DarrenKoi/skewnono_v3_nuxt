# Journal — 2026-05-11 admin log demo import fix

> 정제하지 말 것. 거친 채로 빠르게.

## 한 일

- `/api/admin/logs` local demo fallback이 `opensearchpy` 없이도 동작하도록 import 순서를 고쳤다.
- `OPENSEARCH_PASSWORD`가 없고 cloud가 아니면 먼저 fake log rows를 반환하고, 그 뒤에만 `ops_store.OSSearch`를 import한다.
- `curl http://localhost:5000/api/admin/logs`와 `curl http://localhost:3100/api/admin/logs?level=ERROR`가 200을 반환하는지 확인했다.

## 왜 그렇게 했는가

- 이전 구현은 demo fallback 조건문보다 먼저 `from ops_store import OSSearch`를 실행했다.
- local venv에 `opensearchpy`가 없으면 fallback까지 도달하지 못하고 503이 났다.

## 막힌 지점 / 시도와 실패

- 브라우저에서는 500 또는 빈 화면처럼 보였지만 실제 API 응답은 `No module named 'opensearchpy'`를 담은 503이었다.
- Flask test client에서는 전역 Python에 설치된 dependency 때문에 통과했고, 실제 dev server venv에서는 실패했다.

## 다음에 할 것

- cloud에서는 `opensearch-py`를 requirements로 설치하고 real `OPENSEARCH_*` env를 설정해야 한다.
- local demo mode는 계속 `demo` badge로 표시한다.

## 관련

- 코드: `back_dev_home/admin_logs/data.py`
- 코드: `front-dev-home/app/pages/admin/logs.vue`
