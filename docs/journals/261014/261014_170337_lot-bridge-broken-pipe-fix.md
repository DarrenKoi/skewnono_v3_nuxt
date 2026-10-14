# lot bridge 전량 조회 timeout으로 인한 uWSGI Broken pipe 수정

- 일시: 2026-10-14 17:03 KST
- 상태: 완료 (사무실 배포 후 데이터 정상 로딩 확인)
- 스킬: `diagnosing-bugs` (mattpocock)

## 1. 요약

- 사무실 배포 후 `uwsgi_response_writev_headers_and_body_do(): Broken pipe` 가
  `/api/cdsem/recipe-tat/ranking` 과 `/_nuxt/` 정적 파일에서 함께 나고, 여러
  페이지에서 데이터가 보이지 않았습니다.
- 원인은 `_lot_bridge` 가 `ebeam_tas_lot_hist` 60일치 문서 전량을 내려받는
  조회가 timeout 을 넘긴 것으로 판단했습니다. composite aggregation 으로 바꿔
  `00ad1ae0` 로 push 했고, 사무실 배포 후 정상 로딩을 확인했습니다.

## 2. 진행 사항

- 최근 3일 커밋 중 용의자 두 개를 검토했습니다.
  - `fb9f3ee9`/`a10f5852`/`550e126f` 의 activity middleware 에러 바디 읽기:
    `status >= 400` 에서만 실행되고 예외도 잡혀 있어 느려질 원인이 아니라고
    판단해 기각했습니다.
  - `68cb7066` (2026-10-13) 의 `ops_store._search_all_hits` scroll →
    search_after 교체: 한 페이지 1000건, `_source` 전체, 정렬
    `[시간 desc, _id asc]`, `track_total_hits=False` 입니다.
- `backend` 전체에서 `range_dataframe_all` 을 부르는 곳은
  `backend/ebeam/_office_meas_hist.py::_lot_bridge` 한 곳뿐이었습니다. 이
  bridge 를 recipe_tat ranking(`try_bridge`), `/devices`, fail_issue,
  meas_hist 가 모두 거칩니다.
- 사무실 확인(2026-10-13)은 "전량이 들어오는가"였고 "얼마나 걸리는가"가
  아니었습니다. scroll 이 문서를 빠뜨리던 동안에는 받는 양이 적어 빨랐고,
  고친 뒤 전량이 오면서 timeout 을 넘긴 것으로 추론했습니다.
- 집에서는 사무실 OpenSearch 에 접근할 수 없어 증상을 재현하는 feedback
  loop 를 만들 수 없었습니다. 대신 경로 분석으로 가설을 세우고, 문서
  다운로드 금지를 단언하는 회귀 테스트로 red→green 을 확인했습니다.
- 작업 중 사용자가 `/_nuxt/` 에서도 Broken pipe 가 난다고 알려왔습니다.
  3단계 배포에서는 같은 uWSGI 워커(`processes=4`, `threads=4`)가 정적 파일까지
  서빙하므로, 워커 포화라는 같은 원인의 증거로 해석했습니다.
- 사무실 배포 결과 정상 로딩이 확인되었습니다. 빈 bridge 는 LookupError 를
  내도록 했으므로, 정상 동작 자체가 `lot_id.keyword` 매핑 확인이 됩니다.

## 3. 수정 내용

- 수정 `backend/ebeam/_office_meas_hist.py`: `_lot_bridge` 가
  `search().range_dataframe_all()` 대신
  `composite_buckets(_LOT_HIST_INDEX, [("lot_id", "lot_id.keyword"),
  ("lot_cd", "lot_cd.keyword")], {}, {"range": {"event_tm": {"gte":
  "now-60d"}}})` 로 unique 쌍만 받습니다. 쌍이 0개면 `LookupError` 를 냅니다.
- 수정 `backend/ebeam/tests/test_office_meas_hist.py`: 회귀 테스트 2개를
  추가했습니다. 하나는 `search` 를 막아 문서 다운로드가 일어나지 않음을
  단언하고, 다른 하나는 빈 bridge 가 크게 실패하는지 확인합니다.
- 수정 `docs/datatables/hitachi/ebeam_tas_lot_hist.txt`: 조회 방법 1번을
  composite 방식으로 바꾸고, 변경 이유와 `office 확인 2026-10-14` 를 적었습니다.
- 커밋: `00ad1ae0` (수정), `c329ccdc` (OFFICE-VERIFY → 확인 표시).
  전체 테스트 3967 passed, 13 skipped, ruff 통과.

## 4. 결정 사항과 근거

- **composite aggregation 채택:** bridge 는 (lot_id, lot_cd) 쌍만 필요합니다.
  기존 `composite_buckets` 헬퍼를 재사용했고, device_statistics 가 이미 같은
  index 에서 `lot_cd.keyword` 로 집계하는 선례가 있었습니다. `_id` 정렬도
  없고, scroll·`lte: now` 함정도 해당하지 않습니다.
- **기각한 대안:**
  - `_source` 필터만 추가: 전송량은 줄지만 왕복 횟수(문서 수/1000)는 그대로라
    기각했습니다.
  - `68cb7066` 되돌리기: scroll 의 문서 누락이 되살아나므로 기각했습니다.
- **빈 bridge 검사 추가:** 매핑에 없는 `.keyword` 필드로 composite 를 돌리면
  에러 없이 0건이 돌아와 화면이 "데이터 없음"으로 조용히 비게 됩니다.
  그래서 크게 실패하도록 했습니다.
- **`ttl_cache` lock 은 추가하지 않음:** 사용자가 질문했습니다. lock 을 걸면
  동시 조회가 최대 16개에서 4개(프로세스당 1개)로 줄지만, 나머지 스레드는
  lock 을 기다리며 그대로 묶이므로 워커 포화는 풀리지 않습니다. 조회가 짧아진
  지금은 필요 없다고 봤습니다. 다시 느려지면 lock 이 아니라
  stale-while-revalidate(만료돼도 이전 값을 돌려주고 한 스레드만 갱신)를
  검토합니다.
- **알려진 차이:** 한 lot_id 가 여러 lot_cd 와 짝지어진 경우, 이전에는 정렬
  순서상 마지막 행이, 지금은 composite 키 순서상 마지막 버킷이 이깁니다.
  드문 경우라 그대로 두었습니다.

## 5. 배운 것 / 주의점

- 데이터 누락을 고치는 변경은 받는 양을 늘려 조회를 느리게 만들 수 있습니다.
  사무실 검증에서 행 수뿐 아니라 걸리는 시간도 함께 확인해야 합니다.
- `/_nuxt/` 정적 파일의 Broken pipe 는 정적 파일 문제가 아니라 uWSGI 워커
  포화의 신호입니다.
- "시간이 지나면 해결되는" 현상은 대개 스레드 교체가 아니라 `ttl_cache`
  (900초)가 채워진 결과입니다. 그래서 15분마다 갱신 요청이 다시 느린 조회를
  떠안고, 캐시가 프로세스별이라 4개 프로세스가 각자 겪습니다.
  `harakiri=720` 과 `max-requests=1000` 은 워커를 재시작하면서 캐시도 함께
  비웁니다.
- `range_dataframe_all` 경로는 `os_timing` 에 기록되지 않습니다
  (`aggregate()`/`fetch_hits` 만 기록). 그래서 request row 의
  `opensearch_query_count` 로는 이번 문제가 보이지 않았을 것입니다.

## 6. 다음 단계

- 배포 후 15분 이상 지나 캐시 갱신 시점에도 바로 뜨는지 사용자 확인 대기.
- 그 밖의 미결 작업은 `.remember/open-jobs.md` 를 따릅니다.

## 7. 메모리 업데이트

- `project_completeness_fix_exposes_latency.md` 를 추가하고 `MEMORY.md` 에
  색인을 달았습니다. 누락을 고친 변경이 timeout 을 드러낸 경위와,
  `/_nuxt/` Broken pipe 를 워커 포화로 읽어야 한다는 내용입니다.
