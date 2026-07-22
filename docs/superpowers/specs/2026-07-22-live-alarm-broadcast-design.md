# 라이브 알람 방송 페이지 — 설계

- **Date:** 2026-07-22
- **Feature:** `back_dev_home/ebeam/hitachi/live_alarm`
- **Status:** 설계 확정, 미구현

## 1. 문제

`auto_recipe_creator` 의 align fail 자동 대응 시스템은 사내 알람 API 를 폴링하여
`ALID=9006`(Align Fail)을 감지하고 자동 보정을 시작합니다. 그러나 이 감지 사실은
자동화 프로세스 내부에만 머물러 있어, 계측 엔지니어는 "지금 어느 장비의 정렬이
깨졌는가" 를 알 방법이 없습니다.

SKEWNONO 에 상시 열어두는 라이브 페이지를 만들어, align fail 과 측정 연속 실패를
발생 직후 화면으로 보여줍니다.

기존 `fail_issue` 기능과는 성격이 다릅니다. `fail_issue` 는 날짜 구간을 받아
집계·순위를 내는 **사후 분석** 이고, 이 페이지는 최근 10분을 계속 갱신하는
**실시간 상황판** 입니다. 두 기능은 데이터 소스도 다릅니다.

## 2. 범위

**포함합니다.**

- Align Fail (`ALID=9006`) 과 측정 연속 실패 (`ALID=9100`) 두 종류만 다룹니다.
- 팹 단위 페이지입니다. 사내 알람 API 주소가 팹마다 다르기 때문입니다.
- CD-SEM 과 HV-SEM 양쪽 URL 을 같은 라우트 패턴으로 생성합니다.
- 사내 알람 API 를 폴링하여 Redis 에 기록하는 writer 를 포함합니다.

**포함하지 않습니다.**

- 알람 발생·해제 이력의 영구 저장을 하지 않습니다. 보드는 최근 10분만 유지합니다.
- `auto_recipe_creator` 의 자동 보정 진행 상황을 표시하지 않습니다.
- 소리 알림과 브라우저 알림을 사용하지 않습니다 (§9 참조).
- 차트를 그리지 않습니다. 10분 보드는 목록으로 충분합니다.

## 3. 아키텍처

```text
[스케줄러 서버]  ──(15초마다, 1분 윈도우)──→  사내 알람 API (팹별 주소)
       │                                       ▲
       │  정규화 + 병합 + 10분 초과 제거          팹당 4회/분 고정
       ▼
   [오피스 Redis]  skewnono:live_alarm:{tool_slug}:{fab_name}
       │
       │  GET 1회 (사내 API 호출 없음)
       ▼
[SKEWNONO Flask]  ──→  브라우저 N개 (각 15초 폴링)
```

이 구조의 핵심 성질은 **사내 알람 API 가 받는 부하가 시청자 수와 무관하게 고정**
된다는 점입니다. 시청자가 0명이든 200명이든, 새로고침을 몇 번 하든, 팹당 분당
4회입니다. 그리고 사내 API 가 받는 질의는 **1분 윈도우 단 한 종류** 뿐입니다.

writer 가 병합·만료까지 끝낸 완성된 보드를 저장하므로, SKEWNONO Flask 는 상태를
갖지 않고 브라우저도 조각을 모을 필요가 없습니다. 병합을 브라우저 20개가 각자
하는 대신 writer 가 한 번만 수행합니다.

### 검토했으나 채택하지 않은 대안

| 대안 | 기각 사유 |
| --- | --- |
| 브라우저가 직접 팬아웃 | 시청자 20명이면 사내 API 에 분당 80회가 영구히 발생합니다. |
| Flask 프로세스 내 TTL 캐시 | `wsgi.ini` 가 `processes = 4` 이므로 상한이 프로세스 수에 비례합니다. |
| Flask 가 Redis 를 read-through 캐시로 사용 | 캐시 미스 시 thundering herd 와 사내 API 호출 지연이 요청 스레드를 점유합니다. |
| SSE 로 서버가 push | `threads = 2 × processes = 4` 이므로 동시 8연결이면 SKEWNONO 전체 API 가 마비됩니다. |
| Nitro 서버 라우트에서 폴링 | Phase 3 은 Flask 가 빌드된 SPA 를 직접 서빙하므로 Nitro 가 존재하지 않습니다. |
| `workflow_3` 모니터에 편승 | 특정 오피스 PC 의 GUI 자동화라 커버리지가 제한되고, 정지 시 거짓 음성이 발생합니다. |

마지막 항목은 향후 재검토 대상입니다 (§12).

## 4. 데이터 계약

`back_dev_home/ebeam/hitachi/live_alarm/contracts.py` 에 정의하며, writer 와 reader
가 함께 import 합니다. 스키마가 한 곳에만 존재해야 한쪽만 고쳐서 깨지는 사고를
막을 수 있습니다.

```python
Kind = Literal["align", "meas"]
FeedStatus = Literal["live", "stale"]

BOARD_WINDOW_SEC = 600      # 보드가 유지하는 시간 지평
POLL_WINDOW_SEC = 60        # writer 가 사내 API 에 요청하는 윈도우
WRITER_INTERVAL_SEC = 15    # writer 폴링 주기
STALE_AFTER_SEC = 60        # 이 시간을 넘기면 feed_status = "stale"

ALID_KIND: dict[str, Kind] = {"9006": "align", "9100": "meas"}


class AlarmEvent(TypedDict):
    id: str              # f"{eqp_id}|{alid}|{occurred_at}" — 중복 판정 키
    eqp_id: str
    alid: str
    kind: Kind
    alarm_name: str
    occurred_at: str     # "YYYY-MM-DD HH:MM:SS" (KST)
    recipe_id: str       # "<class>/<recipe>", 없으면 ""
    operation_desc: str
    lot_type_cd: str


class LiveAlarmPayload(TypedDict):
    fab_name: str
    tool_type: ToolType
    feed_status: FeedStatus
    polled_at: str | None    # writer 의 마지막 성공 폴링 시각. 보드가 없으면 None
    server_now: str          # 응답 조립 시각. 클라이언트 시계 보정용
    board_window_sec: int
    events: list[AlarmEvent]
```

### 설계 근거

**`kind` 를 백엔드에서 계산합니다.** 프론트엔드가 `9006` 같은 매직 넘버를 알 필요가
없고, 사내에서 ALID 가 바뀌어도 백엔드 매핑 한 줄만 고치면 됩니다.

**`id` 를 백엔드에서 조립합니다.** "어떤 필드 조합이 한 이벤트를 유일하게 정하는가"
는 도메인 규칙이므로, UI 코드에 새면 안 됩니다.

**`server_now` 는 캐시하지 않고 응답 조립 시점에 매번 새로 찍습니다.** 이 값이 얼어
붙으면 클라이언트의 경과 시간 계산이 통째로 어긋납니다.

## 5. Redis 스키마

| 항목 | 값 |
| --- | --- |
| 키 | `skewnono:live_alarm:{tool_slug}:{fab_name}` |
| 값 | JSON — `{"polled_at": "YYYY-MM-DD HH:MM:SS", "events": [AlarmEvent, ...]}` |
| TTL | 24시간 |
| writer | 팹·tool 조합당 정확히 1개 |

값을 키 하나에 JSON 블롭으로 저장합니다. 10분간 발생하는 align/meas fail 은 많아야
수십 건이므로 통째로 읽고 쓰는 편이 단순하고, writer 가 조합당 하나뿐이라 경합이
없습니다. 한 팹에서 10분에 수백 건이 발생하는 상황이 확인되면 ZSET 으로 바꾸며,
그 변경은 writer 와 office 어댑터 안에서만 일어납니다.

TTL 24시간은 폐기된 팹의 키가 스스로 정리되게 하되, 하루 안에는 `polled_at` 을
보존해 "언제부터 멈췄는가" 를 진단할 수 있게 하는 값입니다.

## 6. Writer

`python -m back_dev_home.ebeam.hitachi.live_alarm.writer.run` 으로 실행하며,
SKEWNONO 가 아닌 별도 스케줄러 서버에서 상주 실행합니다.

한 주기의 동작 순서입니다.

1. 대상 팹 각각에 대해 사내 알람 API 를 `POLL_WINDOW_SEC=60` 으로 조회합니다.
   대상 팹 목록은 `writer/office.py` 의 `fab_name → API 주소` 매핑의 키 집합이며,
   별도 설정 파일을 두지 않습니다. 팹을 추가하는 행위와 주소를 등록하는 행위가
   같은 한 번의 편집이 되어야 목록과 주소가 어긋나지 않습니다.
2. 응답을 `AlarmEvent` 로 정규화합니다. `ALID_KIND` 에 없는 알람은 버립니다.
3. Redis 에서 기존 보드를 읽어 `id` 기준으로 병합합니다.
4. `occurred_at` 이 `BOARD_WINDOW_SEC=600` 을 넘긴 이벤트를 제거합니다.
5. 병합된 보드와 **이번 폴링 시각** 을 `polled_at` 으로 함께 씁니다.

`WRITER_INTERVAL_SEC=15` 이고 조회 윈도우가 60초이므로 4배의 겹침이 있습니다.
스케줄러 지터나 일시적 실패가 몇 번 발생해도 이벤트를 놓치지 않습니다.

### 실패 시 규칙

**사내 API 호출이 실패하면 `polled_at` 을 갱신하지 않습니다. 예외 없습니다.**

이 규칙이 이 설계 전체의 안전성을 지탱합니다. 실패했는데도 시각을 찍으면
하트비트가 거짓말을 하고, 화면은 정상으로 보이면서 실제로는 아무것도 모르는
상태가 됩니다. 실패 시에는 기존 보드를 그대로 두고 로그만 남긴 뒤 다음 주기를
기다립니다.

한 팹의 실패가 다른 팹의 갱신을 막아서는 안 되므로, 팹별로 독립적으로 처리하고
예외를 팹 단위에서 격리합니다.

### 모듈 구성

```text
live_alarm/
├── contracts.py            # 스키마·상수 (writer/reader 공용)
├── board.py                # 순수 함수: merge_events / prune_events / feed_status_for
├── data.py                 # mock|office 디스패처 (안정 층, 수정하지 않음)
├── routes.py               # GET /api/ebeam/<tool_slug>/live-alarm
├── providers/
│   ├── mock.py             # Phase 1 — Redis 없이 즉답
│   └── office_example.py   # Redis GET + prune + feed_status 판정
├── writer/
│   ├── run.py              # 주기 루프
│   ├── mock_source.py      # 로컬에서 루프를 돌려보기 위한 알람 소스
│   └── office_example.py   # 사내 알람 API 호출 + fab_name → 주소 매핑
└── tests/
```

사내 알람 API 주소는 기존 규약대로 gitignore 대상인 `office.py` 안에만 존재합니다.
`office_example.py` 를 구현해 두고 오피스에서 `cp office_example.py office.py` 로
활성화합니다. Redis 접속은 `_runtime/office_redis.py` 의 `redis_client()` 를
재사용하며, 어댑터마다 접속 코드를 다시 만들지 않습니다.

## 7. SKEWNONO 백엔드 (읽기 전용)

`GET /api/ebeam/<tool_slug>/live-alarm?fab_name=R3`

`office.py` 의 동작은 다음 세 단계가 전부입니다.

1. Redis 에서 해당 팹의 보드를 읽습니다.
2. `board.prune_events(events, now=server_now)` 로 10분 지평을 다시 적용합니다.
3. `board.feed_status_for(polled_at, now=server_now)` 로 `live` / `stale` 을 판정합니다.

**reader 도 writer 와 동일한 만료 규칙을 적용합니다.** writer 가 멈추면 보드가
얼어붙는데, 40분 전 알람을 현재처럼 보여주면 안 되기 때문입니다. reader 가 함께
만료시키면 writer 정지 후 10분 안에 보드가 자연히 비고, 화면은 "알람 없음 +
마지막 갱신 34분 전 (지연)" 이라는 정확한 상태를 표시합니다. 두 곳이 같은
`board.py` 순수 함수를 호출하므로 규칙이 갈라지지 않습니다.

`fab_name` 이 미지원이면 404 를 반환합니다. `tool_slug` 는 기존
`resolve_tool_type_from_slug` 를 재사용하므로 CD-SEM 과 HV-SEM URL 이 함께
생성되며, HV-SEM 피드가 사내에 없으면 `office.py` 가 빈 보드를 반환하고 화면은
그대로 "알람 없음" 을 그립니다.

## 8. 프론트엔드

### 라우트와 등록

| 대상 | 변경 |
| --- | --- |
| `app/pages/ebeam/cd-sem/[fab]/live-alarm.vue` | 신규 |
| `app/pages/ebeam/hv-sem/[fab]/live-alarm.vue` | 신규 |
| `app/utils/features.ts` | `FEATURE_SLUGS` 에 `'live-alarm'` 추가 |
| `app/components/nav/FeatureTabs.vue` | 팹 탭 항목 추가 |

`live-alarm` 은 팹에 종속되므로 `FABLESS_FEATURES` 에 넣지 않습니다.

### `composables/useLiveAlarmFeed.ts`

이 페이지의 데이터 로직 전부를 이 composable 이 소유합니다. 공개 인터페이스는
좁게 유지합니다.

```ts
const { events, feedStatus, lastPolledAt, newIds, markSeen } = useLiveAlarmFeed(fabName)
```

`useAsyncData` 를 사용하지 않습니다. 그것은 "한 번 가져와 캐시하고 공유" 하는
읽기에 맞는 도구이고, 이 화면은 15초마다 전체를 교체하는 성격이라 결이 다릅니다.
`usePersistedState` 도 사용하지 않습니다. 알람 데이터는 메모리에만 둡니다.

동작 규칙입니다.

- **타이머 하나** 가 15초마다 조회하고, 응답으로 목록을 **교체** 합니다. 병합·중복
  제거·만료는 서버가 이미 끝냈으므로 클라이언트는 하지 않습니다.
- **시계 보정** — 응답 수신 시 `offset = server_now - Date.now()` 를 저장하고,
  이후 모든 "지금" 을 `Date.now() + offset` 으로 계산합니다. 팹 PC 시계가
  어긋나 있어도 경과 시간이 음수로 표시되거나 이벤트가 일찍 사라지지 않습니다.
- **탭 가시성** — Page Visibility API 로 `hidden` 이면 타이머를 멈추고, 복귀
  시 즉시 1회 조회합니다. 서버가 완성된 보드를 주므로 복귀 시 특별한 처리가
  필요 없습니다.
- **신규 판정** — 직전 응답의 `id` 집합과 비교해 새로 등장한 `id` 만
  `newIds` 로 노출합니다. 이 값은 뷰어마다 달라야 하는 값이므로 클라이언트에
  두는 것이 맞습니다.

### 순수 함수 (`app/utils/liveAlarm.ts`)

`diffNewIds(prev, next)`, `formatElapsed(ms)`, `boardCounts(events)` 를 분리해
시간 의존 로직을 결정론적으로 테스트할 수 있게 합니다.

### 화면

상단에 피드 상태 바를 둡니다. 피드 상태(정상 / 지연), 마지막 갱신 경과 시간,
`Align N건 · 측정 M건` 요약을 표시합니다.

그 아래 최신순 이벤트 목록을 둡니다. 각 행에서 `EQP_ID` 를 가장 크게 표시하고,
종류 배지(Align Fail / 측정 연속 실패)와 경과 시간을 그다음으로, `RECIPE_ID` ·
`OPERATION_DESC` · `LOT_TYPE_CD` 를 보조 정보로 배치합니다. `newIds` 에 포함된
행은 잠시 하이라이트합니다.

`RECIPE_ID` 가 있으면 기존 recipe-search 페이지로 가는 링크를 겁니다. 알람을
확인한 뒤 해당 레시피를 살펴보는 것이 자연스러운 다음 행동이기 때문입니다.

미확인 건수는 `document.title` 에 `(3) 라이브 알람 · R3` 형태로 반영합니다.
사용자가 페이지를 스크롤하거나 클릭하면 `markSeen()` 이 호출되어 초기화됩니다.

## 9. 알림 방식

시각 강조와 `document.title` 만 사용합니다.

**브라우저 알림(Notification API)은 사용할 수 없습니다.** 이 API 는 secure
context(https, 또는 localhost)에서만 노출되는데, 프로덕션은
`http://sknn.skhynix.com` 평문 HTTP 입니다. 개발 PC 의 `localhost:3000` 에서는
동작하다가 사내 배포에서만 조용히 죽으므로, 아예 도입하지 않습니다.

소리 알림은 기술적으로 가능하지만(secure context 제약을 받지 않음) 공유 사무실
환경을 고려하여 채택하지 않습니다.

## 10. 실패 모드

| 상황 | 시스템 동작 | 화면 표시 |
| --- | --- | --- |
| writer 정지 | `polled_at` 이 갱신되지 않음 | `stale` 배너 + 마지막 갱신 경과 시간, 목록은 10분 내 자연 소멸 |
| 사내 API 연속 실패 | writer 가 보드를 유지하고 `polled_at` 미갱신 | 위와 동일 |
| Redis 연결 실패 | reader 가 500 반환 | "백엔드 연결 실패" 배너, 직전 목록을 회색으로 유지 |
| 보드 키 부재 | `polled_at = None`, `events = []` | `stale` + "피드 미가동" |
| 브라우저 폴링 1~2회 실패 | 조용히 재시도 | 변화 없음 |
| 브라우저 폴링 3회 연속 실패 | 재시도 유지 | "연결 불안정" 표시 |
| 미지원 `fab_name` | 404 | 오류 페이지 |

### 빈 상태를 반드시 구분합니다

이 화면의 빈 상태에는 서로 완전히 다른 두 가지가 있습니다.

- "최근 10분간 알람 없음" + 마지막 갱신 8초 전 → 팹이 건강한 상태입니다.
- "최근 10분간 알람 없음" + 마지막 갱신 34분 전 → 아무것도 모르고 있는 상태입니다.

하트비트가 없으면 이 둘은 픽셀 단위로 동일합니다. 따라서 **알람 유무와 무관하게
마지막 갱신 시각을 항상 표시합니다.** 모니터링 화면에서 "조용하다" 는 신호는 그
자체로 검증되어야 합니다.

## 11. 테스트 전략

시간에 의존하는 로직을 순수 함수로 분리하고 `now` 를 인자로 주입합니다. 이렇게
하지 않으면 테스트가 `sleep` 에 의존하거나 조용히 flaky 해집니다.

**백엔드**

- `board.merge_events` — 중복 `id` 병합, 지연 보고된 과거 이벤트 수용
- `board.prune_events` — 경계값(정확히 600초, 601초)
- `board.feed_status_for` — 경계값(정확히 60초, 61초), `polled_at = None`
- 정규화 — `ALID_KIND` 매핑, `id` 조립, 미지원 ALID 제외
- writer 한 주기 — 사내 API 실패 시 `polled_at` 이 갱신되지 않음을 검증합니다
- writer 팹 격리 — 한 팹의 예외가 다른 팹 갱신을 막지 않음을 검증합니다
- reader — mock provider 가 `LiveAlarmPayload` 계약을 만족함

**프론트엔드**

- `diffNewIds` — 신규 진입, 소멸, 동일 집합
- `formatElapsed` — 경계값과 음수 입력 방어
- `useLiveAlarmFeed` — 교체 동작, 시계 오프셋 적용, 가시성 전환 시 타이머 정지/재개

## 12. 향후 과제

**`workflow_3` 모니터 편승.** 그 루프는 이미 사내 알람 API 를 10초마다 폴링하고
있으므로, 결과를 같은 Redis 스키마로 써주면 사내 API 호출이 추가로 0이 됩니다.
채택하려면 커버리지가 팹 전체를 포함하는지 확인해야 하고, `polled_at` 하트비트를
반드시 함께 써야 합니다. 이 변경은 writer 교체만으로 이루어지며 contracts,
reader, 프론트엔드는 영향받지 않습니다.

**보드 지평 조정.** `BOARD_WINDOW_SEC` 상수 하나로 결정되므로, 15분이나 30분이
필요해지면 그 값만 바꿉니다.

**타임라인 시각화.** 10분 구간의 이벤트 밀도를 보여주는 작은 스트립을 추가할 수
있으나, 현재 목록만으로 충분하다고 판단하여 제외했습니다.

## 13. 확정된 값

| 항목 | 값 |
| --- | --- |
| 보드 시간 지평 | 10분 |
| writer 폴링 주기 | 15초 |
| 사내 API 조회 윈도우 | 1분 |
| stale 판정 임계 | 60초 (4주기) |
| 브라우저 폴링 주기 | 15초 |
| Redis TTL | 24시간 |
| 대상 ALID | `9006` (align), `9100` (meas) |
| 팹당 사내 API 부하 | 분당 4회 고정 |
