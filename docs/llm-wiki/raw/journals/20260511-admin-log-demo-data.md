# Journal — 2026-05-11 admin log demo data

> 정제하지 말 것. 거친 채로 빠르게.

## 한 일

- local 환경에서 `OPENSEARCH_PASSWORD`가 없으면 `/api/admin/logs`가 fake log rows를 반환하게 했다.
- demo rows는 `INFO`, `WARNING`, `ERROR`, `request`, `request_exception`을 섞어서 `/admin/logs` 화면의 filter와 detail panel을 확인할 수 있게 했다.
- cloud 환경에서는 fake data로 fallback하지 않고 계속 real OpenSearch 설정을 요구한다.
- `/admin/logs` subtitle 옆에 demo badge를 표시해서 fake data인지 알 수 있게 했다.

## 왜 그렇게 했는가

- local 개발자는 OpenSearch 없이도 admin log table UI를 확인해야 한다.
- 운영 환경에서 credential 누락을 fake data로 숨기면 안 되므로 `is_cloud()`가 true일 때는 기존처럼 실패하게 두었다.

## 막힌 지점 / 시도와 실패

- 처음 구현은 `OPENSEARCH_PASSWORD`가 없으면 503을 반환해서 화면에 row가 없었다.
- local fallback은 backend에 두었다. frontend mock으로 만들면 API filter, paging, error behavior를 같이 검증할 수 없다.

## 다음에 할 것

- cloud에서 실제 `skewnono_logging` 문서가 들어오면 demo badge가 사라지고 real rows가 보이는지 확인한다.
- 필요하면 demo row fixture를 별도 파일로 빼지만 지금은 작아서 backend helper 안에 유지한다.

## 관련

- 코드: `back_dev_home/admin_logs/data.py`
- 코드: `front-dev-home/app/pages/admin/logs.vue`
