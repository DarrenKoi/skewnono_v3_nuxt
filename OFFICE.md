# Office 검증 메모

## 확인된 구조

- Home 환경은 `back_dev_home/meas_hist/data.py`의 메모리 mock을 사용하며 OpenSearch에 연결하지 않습니다.
- Office/production 환경도 `/api/meas-hist/search` 계약을 유지하고 데이터 계층만 OpenSearch 구현으로 교체합니다.
- OpenSearch 연결은 저장소의 `ops_store`와 `OPENSEARCH_*` 환경 변수를 사용합니다. 비밀번호와 인증서는 이 문서에 기록하지 않습니다.
- CD-SEM health check가 현재 참조하는 색인은 `meas_hist_cdsem`입니다. 실제 검색 alias는 office에서 다시 확인해야 합니다.

## Skewvoir fallback 준비 조건

1. 실제 meas_hist index template에 `search_all` 필드를 `wildcard` 타입으로 추가합니다.
2. ingest 시 `back_dev_home.meas_hist.opensearch_query.build_search_all_value()` 결과를 `search_all`에 저장합니다.
3. 기존 보존 기간 문서는 매핑 추가만으로 값이 채워지지 않으므로 재색인 또는 backfill합니다.
4. `search_meas_hist()`의 office 구현에서 구조화 필터는 기존 keyword 필드에 적용하고, 반복 `q` 값은 `build_q_fallback_clause()`로 bool query에 추가합니다.
5. 아래 office-local 테스트가 통과한 뒤 provider를 office 구현으로 전환합니다.

```powershell
$env:TEST_STAGE = "local"
$env:TEST_OPENSEARCH_INDEX = "meas_hist_cdsem"
$env:TEST_MEAS_HIST_Q = "ECXDX"
python -m unittest tests.test_meas_hist_search_local
```

`OPENSEARCH_HOST`, `OPENSEARCH_USER`, `OPENSEARCH_PASSWORD` 등 연결 환경 변수는 별도로 설정해야 합니다.

## 미확인 사항

- HV-SEM 실제 검색 alias는 확인되지 않았습니다.
- 실제 meas_hist mapping에서 각 source field의 이름과 타입이 home 계약과 동일한지 확인이 필요합니다.
- Office 클러스터의 `search.allow_expensive_queries` 설정은 확인되지 않았습니다. 전용 `wildcard` 필드를 사용하더라도 실데이터 latency와 slow log를 확인해야 합니다.
