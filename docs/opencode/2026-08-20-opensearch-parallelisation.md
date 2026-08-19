# OpenSearch 읽기 병렬화 — msearch 대 ThreadPool 논쟁

- 일자: 2026-08-20
- 스킬: `oc-discuss`
- 모델: `glm-5.3` (variant `high`, tier `heavy`), 세션 `ses_fe4479266ffeP7jmAyiu37HGJB`
- 라운드: 2회 (88초 + 56초 = 144초)
- 발단: "OpenSearch / MinIO 를 async·병렬로 가져오도록 세팅돼 있는가"

## 배경 조사 결과

`back_dev_home/ebeam/_office_search.py` 가 모든 e-beam office 어댑터의 단일
접근 계층이며, 노출하는 진입점은 `aggregate()` 와 `fetch_hits()` 두 개입니다.
둘 다 동기 blocking 호출이고 `msearch` 도 async 클라이언트도 쓰지 않습니다.
저장소 전체에서 실제로 팬아웃하는 경로는 `msr_image` 의 FTP 다운로더
(6 커넥션, 스트리밍 진행률) 하나뿐입니다.

## Claude 의 최초 입장

1. `msearch` 는 보류한다 — 확실한 이득은 HTTP 왕복·TLS 오버헤드뿐이고
   sub-request 동시성은 클러스터의 `max_concurrent_searches` 가 정한다.
2. `device_statistics` 의 `_idp_parameters` 청크 루프는 병목이 아니다.
   `_IDP_CHUNK = 500` 에 device 당 레시피 100~200개이므로 평시 1회로 끝난다.
3. `msearch` 의 진짜 위험은 에러 시맨틱이다 — HTTP 200 안에 per-response
   `{"error":…, "status":404}` 가 담기므로 `NotFoundError` → `LookupError`
   매핑이 조용히 멈추고, `timed_out` · `_shards.failed` · `aggregations`
   검증을 응답마다 재적용해야 한다.
4. 대신 (a) 계측 먼저, (b) 항상 2회이고 독립인 `bm_pm` 만 ThreadPool,
   (c) health 프로브 병렬화.

## Agreed

- 진단(1·2·3번)은 코드 대조로 양측이 확인했습니다. 모델도 `_IDP_CHUNK = 500`,
  per-response 검증, `NotFoundError` 매핑을 직접 열람해 동의했습니다.
- **결론: 계측만 출하하고 그 외에는 아무것도 하지 않습니다.** 살아남는
  병렬화 대상이 없습니다.
- `office.py` gitignore 우려는 실질 위험이 아닙니다 —
  `scripts/sync_office_adapters.py` 와 부팅 로그의 `STALE office.py` 경고가
  이미 절차로 존재합니다. 모델이 확인 후 철회했습니다.
- pyarrow mimalloc 흉터는 제안된 두 경로에 닿지 않습니다. OpenSearch 경로는
  JSON 만 다루고 `probe_common.py` 에는 pandas·parquet·`read_dataframe` 가
  없습니다. 다만 **Redis DataFrame 읽기(`sem_list` 2키 로드 등)의 병렬화는
  이 사유로 영구히 배제**하기로 양측이 합의했습니다.
- A/B 를 하게 된다면 `ttl_cache` 의 900초 TTL 때문에 나중에 도는 경로가 warm
  cache 를 타므로, 순차 실행이 아니라 교차 실행해야 합니다.

## Disputed

없습니다. 모델이 3·5번을 철회하고 2번 press 를 원칙적으로 수용했으며,
Claude 가 1·2·4번을 인정하여 2라운드에서 수렴했습니다.

## I was wrong

**(4) 우선순위 판단 — 전면 인정.** 모델의 지적:

> bm_pm's own docstring documents an UNVERIFIED stored-clock convention *and* a
> live 9-hour anchor bug. You'd be parallelising queries whose windows are
> known-suspect, on a diagnostic-adjacent tab, while the module's correctness
> items wait for the same scarce office trip.

확인 결과 사실이었습니다.
`ebeam/hardware/providers/bm_pm/office_example.py` 의 모듈 docstring 은
(i) 두 인덱스가 offset 없는 KST 를 저장하는지 **미검증**이며 `Z` 접미사가
있으면 모든 윈도가 9시간 밀린다는 것과, (ii) 프론트가
`new Date().toISOString()` 을 보내고 라우트가 `Z` 만 떼는 탓에 anchor 가 실제로
UTC wall clock 으로 도착해 **"최근 약 9시간의 maintenance 가 사라져 보이는"**
살아 있는 버그를 명시하고 있습니다. 지금 틀린 데이터를 보여주는 탭의 쿼리를,
동일한 희소 자원인 사무실 방문을 써서 병렬화하는 것은 방어할 수 없습니다.
bm_pm 을 대상에서 철회했습니다.

**(1) 반-msearch 논거의 대칭성 — 부분 인정.** 모델의 지적:

> Your own argument against msearch refutes ThreadPoolExecutor equally. […]
> You've argued the payoff is capped and then committed untestable code to
> capture it anyway.

이득의 상한이 양쪽 동일하다는 점은 맞습니다. Claude 는 비용 축의 비대칭
(ThreadPool 은 기존 `aggregate()` 를 그대로 호출하므로 에러 시맨틱 표면을
전혀 건드리지 않음)으로 반박했고 모델도 이 부분은 인정했지만, "상한이 있는
이득 + 검증 불가한 비용" 이면 (a) 만 남는다는 결론은 유효합니다.

**(2) "측정 먼저" 의 순서 모순 — 대체로 인정.** 모델의 지적:

> The next office trip is the only execution window. If timing logging and the
> ThreadPoolExecutor change ship together, the measurement can never gate the
> change.

Claude 는 env 플래그 + 어느 경로가 돌았는지 기록하는 로깅이면 한 번의 방문으로
A/B 가 되어 "측정이 저작이 아니라 채택을 게이트한다"고 press 했고, 모델은 원칙적
으로 수용했습니다. 다만 대상이 사라졌으므로 실익이 없습니다.

**최초 답변의 오류 하나 더.** Claude 는 첫 턴에서 `_idp_parameters` 청크 루프를
"이득 가장 큰 최우선 병목"이라고 단정했습니다. 코드 모양(`for … range(0, len,
CHUNK)`)만 보고 N회 왕복이라 읽은 것으로, 정의부 주석("보통 1회로 끝나지만…
질의가 무한정 커지지 않게 잘라 둡니다")을 읽지 않은 결과입니다. 청킹 루프는
**분할이 목적**인 것과 **상한 방어가 목적**인 것이 있고, 구분은 코드 모양이
아니라 주석과 실제 데이터 분포에만 있습니다.

## 따라 나오는 것

- 유일한 산출물은 `_office_search.py` 의 요청별 소요시간 계측입니다. 집에서
  안전하고, 아직 작성되지 않은 어댑터를 포함한 모든 어댑터가 혜택을 받으며,
  다음 사무실 방문을 "측정 불가능한 변경 배포" 에서 "두 번째 변경이 필요한지
  판정할 데이터 획득" 으로 바꿉니다.
- health 프로브 병렬화는 경제성에서 탈락했습니다. 각 프로브가 의도적으로
  저렴하고(PING, `latest(size=1)`, 8-entry list), 유일한 진짜 장점인 전면
  장애 시 타임아웃 3회 누적은 실패 row 가 이미 elapsed 를 기록하므로 계측이
  먼저 그 상황의 발생 여부를 알려줍니다.
- Redis DataFrame 읽기 병렬화는 pyarrow mimalloc 사유로 영구 배제합니다.
