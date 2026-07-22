# 라이브 알람 방송 페이지 — 설계

- **Date:** 2026-07-22
- **개정 2026-07-23:** writer 배치를 기존 Flask 스케줄러로 확정, 저장을 ZSET 으로 전환,
  외부 설계 리뷰 지적 사항 반영
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
- writer 를 얹기 위한 스케줄러 플랫폼(`flask_modules/api`) 변경을 포함합니다 (§12).

**포함하지 않습니다.**

- 알람 발생·해제 이력의 영구 저장을 하지 않습니다. 보드는 최근 10분만 유지합니다.
- `auto_recipe_creator` 의 자동 보정 진행 상황을 표시하지 않습니다.
- 소리 알림과 브라우저 알림을 사용하지 않습니다 (§9).
- 차트를 그리지 않습니다. 10분 보드는 목록으로 충분합니다.

## 3. 아키텍처

```text
[Flask 스케줄러]  ──(15초마다, 적응형 윈도우)──→  사내 알람 API (팹별 주소)
       │  APScheduler 잡                          ▲
       │  정규화 → ZADD / ZREMRANGEBYSCORE         팹당 4회/분 고정
       ▼
   [오피스 Redis]  skewnono:live_alarm:{tool_slug}:{fab_name}:events  (ZSET)
       │                                          :meta    (STRING)
       │                                          :registry (SET)
       │  ZRANGEBYSCORE 1회 (사내 API 호출 없음)
       ▼
[SKEWNONO Flask]  ──(10분으로 최종 절단)──→  브라우저 N개 (각 15초 ± jitter 폴링)
```

이 구조의 핵심 성질은 **사내 알람 API 가 받는 부하가 시청자 수와 무관하게 고정**
된다는 점입니다. 시청자가 0명이든 200명이든, 새로고침을 몇 번 하든, 팹당 분당
4회입니다.

writer 가 병합·만료까지 끝낸 완성된 보드를 저장하므로, SKEWNONO Flask 는 상태를
갖지 않고 브라우저도 조각을 모을 필요가 없습니다.

### 검토했으나 채택하지 않은 대안

| 대안 | 기각 사유 |
| --- | --- |
| 브라우저가 직접 팬아웃 | 시청자 20명이면 사내 API 에 분당 80회가 영구히 발생합니다. |
| Flask 프로세스 내 TTL 캐시 | `wsgi.ini` 가 `processes = 4` 이므로 상한이 프로세스 수에 비례합니다. |
| Flask 가 Redis 를 read-through 캐시로 사용 | 캐시 미스 시 thundering herd 와 사내 API 호출 지연이 요청 스레드를 점유합니다. |
| SSE 로 서버가 push | `threads = 2 × processes = 4` 이므로 동시 8연결이면 SKEWNONO 전체 API 가 마비됩니다. |
| Nitro 서버 라우트에서 폴링 | Phase 3 은 Flask 가 빌드된 SPA 를 직접 서빙하므로 Nitro 가 존재하지 않습니다. |
| `workflow_3` 모니터에 편승 | 특정 오피스 PC 의 GUI 자동화라 커버리지가 제한되고, 정지 시 거짓 음성이 발생합니다. |

마지막 항목은 향후 재검토 대상입니다 (§14).

### writer 를 어디서 돌릴 것인가

| 방식 | 인스턴스 수 | 배포 독립성 | 관측·복구 | 판단 |
| --- | --- | --- | --- | --- |
| SKEWNONO Flask 데몬 스레드 | 4 (`processes = 4`) | ✗ | 없음 | 채택 불가 |
| SKEWNONO `wsgi.ini` 의 uWSGI mule | 1 | ✗ SKEWNONO 배포마다 끊김 | 직접 구축 | 폴백 (§14) |
| 기존 Flask 스케줄러 서비스의 잡 | 1 | ✓ 별도 서비스 | 기존 인프라 재사용 | **채택** |

데몬 스레드는 `lazy-apps = true` 때문에 워커마다 하나씩 생겨 사내 API 부하가 4배가
되고, 워커가 재활용될 때 조용히 사라집니다. mule 은 프로세스가 정확히 하나라 그
문제는 없지만, SKEWNONO 웹의 배포 주기에 묶입니다. 감시하는 쪽이 감시당하는 쪽의
배포에 흔들려서는 안 됩니다.

**writer 는 특정 스케줄러에 종속되지 않게 작성합니다**(§6). 다른 Flask 스케줄러
서버로 옮기거나 병행 운영할 수 있어야 하며, 이 요구가 §5 의 저장 구조를 결정했습니다.

## 4. 데이터 계약

`back_dev_home/ebeam/hitachi/live_alarm/contracts.py` 에 정의합니다.

**writer 는 이 모듈을 import 하지 않습니다.** writer 는 다른 서비스에서 실행되므로,
두 쪽이 공유하는 것은 Python 코드가 아니라 **Redis 에 담기는 형태**(§5)입니다.

```python
Kind = Literal["align", "meas"]
FeedStatus = Literal["live", "stale", "not_configured"]

BOARD_WINDOW_SEC = 600      # reader 가 최종적으로 잘라 내보내는 시간 지평
POLL_WINDOW_SEC = 60        # 정상 상태에서 writer 가 요청하는 윈도우
WRITER_INTERVAL_SEC = 15    # writer 폴링 주기
WRITER_PRUNE_SEC = 900      # writer 가 보관하는 상한
STALE_AFTER_SEC = 90        # 이 시간을 넘기면 feed_status = "stale"
FUTURE_TOLERANCE_SEC = 300  # 이보다 미래인 이벤트는 버림

assert WRITER_PRUNE_SEC >= BOARD_WINDOW_SEC, (
    "writer 보관 상한이 보드 지평보다 짧으면 reader 가 복원할 수 없는 구간이 생깁니다"
)

ALID_KIND: dict[str, Kind] = {"9006": "align", "9100": "meas"}


class AlarmEvent(TypedDict):
    id: str              # f"{eqp_id}|{alid}|{occurred_at}" — 중복 판정 키
    eqp_id: str
    alid: str
    kind: Kind
    alarm_name: str
    occurred_at: str     # "YYYY-MM-DD HH:MM:SS+09:00" — offset 포함
    occurred_epoch: int  # ZSET score. 파싱·시간대 해석을 한 번만 하기 위한 필드
    recipe_id: str       # "<class>/<recipe>", 없으면 ""
    operation_desc: str
    lot_type_cd: str


class LiveAlarmPayload(TypedDict):
    fab_name: str
    tool_type: ToolType
    feed_status: FeedStatus
    polled_at: str | None    # writer 의 마지막 성공 폴링 시각
    covered_since: str | None  # 이 시각 이후 구간은 빠짐없이 수집되었음
    server_now: str          # 응답 조립 시각. 클라이언트 시계 보정용
    board_window_sec: int
    events: list[AlarmEvent]
```

### 설계 근거

**`kind` 를 백엔드에서 계산합니다.** 프론트엔드가 `9006` 같은 매직 넘버를 알 필요가
없고, 사내에서 ALID 가 바뀌어도 매핑 한 줄만 고치면 됩니다.

**`id` 를 writer 가 조립합니다.** "어떤 필드 조합이 한 이벤트를 유일하게 정하는가"
는 도메인 규칙이므로 UI 코드에 새면 안 됩니다.

**`occurred_epoch` 를 별도 필드로 둡니다.** 시각 문자열을 reader 가 다시 파싱하면
시간대 해석이 두 서비스에 흩어집니다. writer 가 한 번 계산해 담고, reader 는
그대로 씁니다. `occurred_at` 에도 `+09:00` offset 을 명시해 표시용 문자열조차
모호하지 않게 합니다.

**`covered_since` 를 노출합니다.** `polled_at` 만으로는 "마지막 폴링이 성공했다" 는
사실밖에 증명되지 않습니다. 중간에 공백이 있었는지는 별개의 질문이고, §6 의 적응형
backfill 이 그 답을 계산합니다.

**시간 지평의 최종 권한은 reader 에게만 있습니다.** writer 는 `WRITER_PRUNE_SEC`
으로 넉넉히 자르고, 화면에 나갈 10분은 reader 가 결정합니다. 위 `assert` 가 이
관계를 코드로 못박습니다 — 두 값이 독립적으로 조정되더라도 불변식은 깨지지
않습니다.

## 5. Redis 스키마

팹·tool 조합마다 키 두 개를 쓰고, 전체에 레지스트리 키 하나를 둡니다.

| 키 | 자료형 | 내용 | TTL |
| --- | --- | --- | --- |
| `skewnono:live_alarm:{tool_slug}:{fab_name}:events` | ZSET | member = `AlarmEvent` 의 canonical JSON, score = `occurred_epoch` | 24시간 |
| `skewnono:live_alarm:{tool_slug}:{fab_name}:meta` | STRING | JSON — `{"polled_at": ..., "covered_since": ...}` | 24시간 |
| `skewnono:live_alarm:registry` | SET | writer 가 관리하는 `"{tool_slug}:{fab_name}"` 집합 | 24시간 |

### 왜 ZSET 인가 — 락을 없애기 위해서입니다

writer 는 어느 Flask 스케줄러 서버에도 꽂을 수 있어야 합니다(§6). 그 서버가 분산
락을 제공하는지, 멀티 워커인지 알 수 없으므로 **writer 가 중복 실행돼도 안전해야
합니다.**

JSON 블롭 하나에 보드를 담으면 read-modify-write 가 되어 동시 실행 시 lost update
가 발생하고, 이를 막으려면 호스트가 락을 제공해야 해서 이식성이 깨집니다.

| 연산 | 동시 실행 시 |
| --- | --- |
| `ZADD` | 같은 이벤트는 member 문자열이 같아 자동으로 한 번만 남습니다 |
| `ZREMRANGEBYSCORE` | 몇 번 실행해도 결과가 같습니다 |
| `meta` 갱신 | Lua 스크립트로 **단조 증가** 만 허용합니다 (아래) |

부수 효과가 더 큽니다. **writer 가 이벤트를 읽지 않아도 됩니다.** 기존 보드를
읽어 병합하는 단계가 사라지므로 writer 에는 병합 함수도 만료 함수도 필요 없습니다.

reader 쪽에서도 10분 절단이 `ZRANGEBYSCORE` 의 인자가 되어 파이썬 만료 코드가
사라집니다.

### `meta` 는 단조 증가로만 갱신합니다

`SET polled_at` 을 그냥 쓰면 두 writer 가 동시에 돌 때 **느린 쪽이 나중에 도착해
더 최신인 값을 덮어쓸 수 있습니다.** 시각을 되돌리는 쓰기는 하트비트를 거짓말하게
만들므로, 갱신을 Lua 로 감싸 기존 값보다 클 때만 쓰도록 합니다.

```lua
-- KEYS[1]=meta, ARGV[1]=polled_at_epoch, ARGV[2]=covered_since_epoch, ARGV[3]=ttl
local cur = redis.call('get', KEYS[1])
if cur then
  local prev = cjson.decode(cur)
  if prev.polled_at >= tonumber(ARGV[1]) then return 0 end
  -- covered_since 는 뒤로 밀지 않는다: 더 이른 값이 더 넓은 커버리지다
  if prev.covered_since < tonumber(ARGV[2]) then ARGV[2] = prev.covered_since end
end
redis.call('set', KEYS[1], cjson.encode({polled_at=tonumber(ARGV[1]),
                                         covered_since=tonumber(ARGV[2])}), 'EX', ARGV[3])
return 1
```

`ZREMRANGEBYSCORE` 의 파괴성도 같은 맥락에서 문제가 되지만, 절단 기준을 writer 의
로컬 시계가 아니라 **Redis 서버 시계**(아래)로 통일하므로 writer 가 여럿이어도
같은 경계를 계산합니다.

### 시계 권한은 Redis 에 있습니다

writer 와 reader 는 서로 다른 서버에서 돌고, 둘 다 자기 시계로 "지금" 을 계산하면
만료 경계와 stale 판정이 어긋납니다. 두 서비스가 공유하는 유일한 지점이 Redis 이므로
**`TIME` 명령의 반환값을 단일 시계로 삼습니다.**

- writer: 만료 경계, `polled_at`, `covered_since` 전부 Redis 시계 기준
- reader: `ZRANGEBYSCORE` 하한, `feed_status` 판정, `server_now` 전부 Redis 시계 기준

파이프라인에 실어 보내므로 왕복이 늘지 않습니다. 남는 시계는 사내 알람 API 가 찍는
`occurred_at` 하나뿐이고, 그것은 이벤트의 속성이지 인프라의 상태가 아닙니다. 다만
그 시계가 앞서 있을 때 이벤트가 영원히 만료되지 않는 것을 막기 위해,
**writer 는 `occurred_epoch > now + FUTURE_TOLERANCE_SEC` 인 이벤트를 버립니다.**

### 중복 멤버 해소 규칙

member 를 `id` 가 아닌 canonical JSON(키 정렬, 공백 없음, UTF-8)으로 두는 이유는
키를 하나로 유지하기 위해서입니다. 대신 같은 `id` 인데 부가 필드만 다른 레코드가
두 벌 남을 가능성이 생깁니다.

**해소 규칙: reader 가 `id` 로 묶은 뒤, member 문자열이 사전순으로 가장 앞선 것
하나만 남깁니다.** 임의로 보이지만 결정론적이라는 점이 중요합니다 — 어느 reader
프로세스가 응답하든 같은 화면이 나옵니다. 같은 `id` 는 정의상 같은 장비·같은
ALID·같은 시각이므로, 어느 쪽을 골라도 사용자가 보는 사실은 달라지지 않습니다.

### 어느 Redis 를 쓰는가

**SKEWNONO office 어댑터가 읽는 Redis** 를 그대로 씁니다. 스케줄러 자신의
Redis(잡 스토어, 락)가 아닙니다. reader 가 읽을 수 있는 Redis 는 그곳뿐이기
때문입니다.

> **DB 번호 주의:** `_runtime/office_redis.py` 의 `redis_client()` 는 `db` 를
> 전달하지 않으므로 **redis-py 기본값인 db=0** 을 씁니다. `.env` 에 `REDIS_DB` 가
> 있어도 무시됩니다. **writer 도 db=0 에 써야 합니다.** 이 값을 바꾸려면
> `redis_client()` 와 writer 를 함께 고쳐야 합니다.

> **바이트 주의:** 같은 클라이언트가 `decode_responses=False` 이므로 모든 읽기가
> `bytes` 로 돌아옵니다. reader 는 `meta` 와 각 member 를 명시적으로 디코드해야
> 합니다.

키 네임스페이스(`skewnono:live_alarm:`)와 전 키 24시간 TTL 이 공유에 따르는 위험을
막습니다. 데이터량은 팹 6개 × 수십 건의 작은 JSON 이라, 이미 저장 중인 parquet
DataFrame 에 비하면 무시할 수준입니다.

> **배포 시 확인:** 스케줄러 서버에서 그 Redis 로의 네트워크 접근과 쓰기 권한이
> 열려 있어야 합니다.

## 6. Writer — 이식 가능한 스케줄러 잡

writer 는 특정 스케줄러 서비스에 종속되지 않습니다. 어느 Flask + APScheduler
서버에도 파일을 놓고 잡 하나를 등록하면 동작해야 합니다.

### 호스트에 요구하는 것 — 주기 호출 하나뿐

```python
run_once()   # 인자 없음, 설정은 환경 변수, 앱 컨텍스트 불필요
```

| 흔히 호스트에 의존하는 것 | writer 가 대신 하는 것 |
| --- | --- |
| 분산 락으로 중복 실행 방지 | Redis 연산을 멱등·단조로 설계 (§5) |
| `app.config` 에서 설정 읽기 | 환경 변수에서 직접 읽음 |
| 프레임워크 로거 | 표준 `logging` |

의존성은 `redis` 와 `requests` 뿐입니다.

### 한 주기의 동작

팹마다 독립적으로 수행합니다.

1. **조회 윈도우를 결정합니다** (아래 "적응형 backfill").
2. 사내 알람 API 를 그 윈도우로 조회합니다. HTTP 타임아웃 `(connect 3, read 7)`.
3. 응답을 `AlarmEvent` 로 정규화합니다. `ALID_KIND` 에 없는 알람과
   `occurred_epoch > now + 300` 인 이벤트는 버립니다.
4. 한 파이프라인으로 씁니다.

```python
if events:                                  # 빈 mapping 은 redis-py 가 거부한다
    pipe.zadd(events_key, {canonical_json(e): e["occurred_epoch"] for e in events})
pipe.zremrangebyscore(events_key, "-inf", now - WRITER_PRUNE_SEC)
pipe.expire(events_key, 86400)
pipe.evalsha(META_ADVANCE, 1, meta_key, now, covered_since, 86400)
pipe.sadd(registry_key, f"{tool_slug}:{fab_name}")
pipe.expire(registry_key, 86400)
pipe.execute()
```

윈도우 안에 알람이 하나도 없어도 `meta` 는 갱신합니다. **"알람이 없었다" 는 폴링
성공이지 실패가 아니며**, 이 구분이 §10 의 두 빈 상태를 가릅니다.

### 적응형 backfill — 공백이 알람을 삼키지 않게

고정 60초 윈도우는 **공백이 60초를 넘는 순간 알람을 영구히 잃습니다.** `t=0` 에
성공하고 writer 가 `t=75` 에 복구되면, 60초 윈도우는 `t=15..75` 만 덮으므로 `t=10`
의 알람은 아무도 모르게 사라집니다. 그런데 `polled_at=75` 는 신선하므로 화면은
`live` 를 표시합니다 — 잃어버렸다는 사실조차 드러나지 않습니다.

그래서 윈도우를 마지막 성공 시점에서 파생합니다.

```python
gap = now - last_polled_at            # meta 가 없으면 무한대로 취급
window = min(max(gap + SLACK, POLL_WINDOW_SEC), BOARD_WINDOW_SEC)
covered_since = now - window
```

**상한이 `BOARD_WINDOW_SEC` 이라는 점이 이 설계를 단순하게 만듭니다.** 보드는
어차피 10분치만 보여주므로, 공백이 30분이든 3시간이든 600초 조회 한 번이면 보드가
**완전히** 재구성됩니다. 보여줄 것보다 오래된 데이터는 필요가 없으니 "부분 복구"
라는 상태 자체가 존재하지 않고, 별도의 `warming` 표시도 필요 없습니다.

같은 로직이 콜드 스타트도 처리합니다. **`events` 키나 `meta` 키가 없으면**(최초
기동, Redis 재시작, maxmemory 축출) `gap` 을 무한대로 보아 600초를 조회합니다.
`meta` 만 남고 `events` 가 축출된 경우도 `EXISTS` 확인으로 같은 경로를 탑니다 —
그러지 않으면 "빈 보드 + 신선한 하트비트" 라는 가장 나쁜 조합이 나옵니다.

### 실패 시 규칙

**사내 API 호출이 실패하면 `meta` 를 갱신하지 않습니다. 예외 없습니다.** 실패했는데
시각을 찍으면 하트비트가 거짓말을 하고, 화면은 정상으로 보이면서 실제로는 아무것도
모르는 상태가 됩니다.

팹별 예외는 격리하여, 한 팹의 실패가 다른 팹의 갱신을 막지 않게 합니다.

**모든 팹이 실패하면 `run_once` 는 예외를 던집니다.** 부분 실패는 삼키고 로그만
남기지만, 전면 실패는 호스트에 알려야 합니다. 그러지 않으면 `TaskLogger` 같은
호스트 관측 장치가 이 실행을 정상 종료로 기록해, 대시보드는 초록불인데 화면은
`stale` 인 모순이 생깁니다. APScheduler 는 잡의 예외를 잡아 로깅하므로 스케줄러
스레드는 영향받지 않습니다.

### 설정

| 환경 변수 | 기본값 |
| --- | --- |
| `LIVE_ALARM_REDIS_HOST` / `_PORT` / `_PASSWORD` | — (필수) |
| `LIVE_ALARM_REDIS_DB` | `0` (§5 의 DB 번호 주의 참조) |
| `LIVE_ALARM_POLL_WINDOW_SEC` | 60 |
| `LIVE_ALARM_PRUNE_SEC` | 900 |
| `LIVE_ALARM_HTTP_TIMEOUT` | `3,7` |

### 코드 배치

writer 는 **SKEWNONO 코드를 하나도 import 하지 않는 자족 모듈** 입니다. 원본과
테스트는 SKEWNONO 레포에 두고(진실의 원천), 배포 시 그 디렉터리를 스케줄러 서비스에
놓고 잡 하나를 등록합니다. 나중에 import 경로가 열리면 복사를 import 로 바꾸면
되고, 계약은 어차피 §5 의 Redis 구조입니다.

사내 알람 API 주소는 기존 규약대로 gitignore 대상인 `office.py` 안에만 둡니다.

### 모듈 구성

```text
live_alarm/
├── contracts.py            # 스키마·상수·불변식 assert (SKEWNONO 측)
├── board.py                # 순수 함수: feed_status_for / dedupe_by_id / parse_members
├── data.py                 # mock|office 디스패처 (안정 층, 수정하지 않음)
├── routes.py               # GET /api/ebeam/<tool_slug>/live-alarm
├── providers/
│   ├── mock.py             # Phase 1 — Redis 없이 즉답
│   └── office_example.py   # ZRANGEBYSCORE + dedupe + feed_status 판정
├── writer/                 # 스케줄러 서비스로 복사되는 자족 모듈
│   ├── job.py              # run_once() — SKEWNONO import 없음
│   ├── window.py           # 적응형 backfill 계산 (순수 함수)
│   ├── normalize.py        # 사내 응답 → AlarmEvent + canonical JSON
│   └── office_example.py   # 사내 알람 API 호출 + (tool, fab) → 주소 매핑
└── tests/
```

`board.py` 에 병합·만료 함수가 없는 것은 Redis 가 그 일을 하기 때문입니다.

## 7. SKEWNONO 백엔드 (읽기 전용)

`GET /api/ebeam/<tool_slug>/live-alarm?fab_name=R3`

```python
now, _ = r.time()                                       # 단일 시계 (§5)
raw = r.zrangebyscore(events_key, now - BOARD_WINDOW_SEC, now + FUTURE_TOLERANCE_SEC)
meta = r.get(meta_key)                                  # bytes — 디코드 필요
known = r.sismember(registry_key, f"{tool_slug}:{fab_name}")

events = board.dedupe_by_id(board.parse_members(raw))   # 깨진 멤버는 건너뜀
status = board.feed_status_for(meta, known, now=now)
```

**시간 지평의 최종 권한은 reader 에게 있습니다.** writer 가 멈추면 보드가 얼어붙는데,
40분 전 알람을 현재처럼 보여주면 안 되기 때문입니다. 절단이 질의 인자라서 reader 에는
만료 코드 자체가 없습니다.

상한을 `+inf` 가 아니라 `now + FUTURE_TOLERANCE_SEC` 로 두는 이유는, 사내 시계가
크게 앞선 이벤트가 만료되지 않고 영원히 상단에 남는 것을 막기 위해서입니다.

**깨진 멤버 하나가 엔드포인트 전체를 죽이면 안 됩니다.** writer 가 별도 배포이므로
스키마 전환 중에 파싱 불가능한 멤버가 섞일 수 있습니다. `parse_members` 는
해독 실패한 멤버를 경고 로그와 함께 건너뜁니다 — `flask_modules` 의
`read_task_logs` 가 malformed 항목에 대해 쓰는 것과 같은 관대한 정책입니다.

### `feed_status` 판정

| 조건 | 상태 | 의미 |
| --- | --- | --- |
| 레지스트리에 없음 | `not_configured` | 이 팹·tool 은 writer 가 관리하지 않습니다 |
| `meta` 없음 또는 `now - polled_at > 90` | `stale` | 관리 대상인데 갱신이 멈췄습니다 |
| 그 외 | `live` | — |

레지스트리를 두는 이유는 **"설정되지 않음" 과 "죽었음" 이 화면에서 달라야 하기**
때문입니다. 키 부재만으로는 둘을 구분할 수 없습니다. 레지스트리 TTL 24시간이
`STALE_AFTER_SEC` 보다 훨씬 길므로, writer 가 죽어도 레지스트리는 남아 `stale` 로
올바르게 판정됩니다.

`fab_name` 이 미지원이면 404 를 반환합니다. `tool_slug` 는 기존
`resolve_tool_type_from_slug` 를 재사용하므로 CD-SEM 과 HV-SEM URL 이 함께
생성되며, HV-SEM 피드가 사내에 없으면 `not_configured` 가 나옵니다.

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

```ts
const { events, feedStatus, lastPolledAt, newIds, markSeen } = useLiveAlarmFeed(fabName)
```

`useAsyncData` 를 사용하지 않습니다. 그것은 "한 번 가져와 캐시하고 공유" 하는
읽기에 맞는 도구이고, 이 화면은 주기적으로 전체를 교체하는 성격이라 결이 다릅니다.

- **타이머 하나** 가 `15초 ± 3초 jitter` 로 조회하고, 응답으로 목록을 **교체** 합니다.
  jitter 는 여러 브라우저의 요청이 같은 순간에 몰리는 것을 막습니다.
- **시계 보정** — 응답 수신 시 `offset = server_now - Date.now()` 를 저장하고,
  이후 모든 "지금" 을 `Date.now() + offset` 으로 계산합니다.
- **탭 가시성** — `hidden` 이면 타이머를 멈추고, 복귀 시 즉시 1회 조회합니다.
  서버가 완성된 보드를 주므로 복귀에 특별한 처리가 필요 없습니다.
- **신규 판정** — 직전 응답의 `id` 집합과 비교해 새로 등장한 `id` 만 노출합니다.
  뷰어마다 달라야 하는 값이므로 클라이언트에 두는 것이 맞습니다.

### 표시 지연 예산

writer 15초 + 브라우저 15초의 두 단계가 위상이 어긋나면 최악의 경우 알람이 화면에
뜨기까지 **약 30초** 가 걸립니다(중앙값 약 15초). align fail 은 이미 자동화가
대응하고 있고 이 페이지는 인지가 목적이므로 수용합니다. 더 줄이려면 브라우저
주기를 낮추는 쪽이 사내 API 부하를 늘리지 않아 안전합니다.

### 순수 함수 (`app/utils/liveAlarm.ts`)

`diffNewIds(prev, next)`, `formatElapsed(ms)`, `boardCounts(events)`.

### 화면

상단에 피드 상태 바를 둡니다. 피드 상태(정상 / 지연 / 미설정), 마지막 갱신 경과
시간, `Align N건 · 측정 M건` 요약을 표시합니다.

그 아래 최신순 이벤트 목록을 둡니다. 각 행에서 `EQP_ID` 를 가장 크게 표시하고,
종류 배지(Align Fail / 측정 연속 실패)와 경과 시간을 그다음으로, `RECIPE_ID` ·
`OPERATION_DESC` · `LOT_TYPE_CD` 를 보조 정보로 배치합니다. 새로 도착한 행은 잠시
하이라이트합니다.

`RECIPE_ID` 가 있으면 기존 recipe-search 페이지로 가는 링크를 겁니다.

미확인 건수는 `document.title` 에 `(3) 라이브 알람 · R3` 형태로 반영하고, 스크롤
또는 클릭 시 `markSeen()` 으로 초기화합니다.

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
| writer 정지 | `meta` 가 갱신되지 않음 | `stale` 배너 + 마지막 갱신 경과, 목록은 10분 내 자연 소멸 |
| 사내 API 연속 실패 | 위와 동일 | 위와 동일 |
| writer 복구 (공백 60초 초과) | 적응형 backfill 이 공백 구간을 재조회 | 정상 — 누락 없음 |
| `events` 키 축출 / Redis 재시작 | `EXISTS` 실패 → 600초 콜드 스타트 | 한 주기 안에 보드 복원 |
| 전 팹 실패 | `run_once` 가 raise → 호스트가 error 기록 | `stale` |
| 일부 팹 실패 | 격리, 로그만 | 해당 팹만 `stale` |
| Redis 연결 실패 (reader) | 500 | "백엔드 연결 실패", 직전 목록 회색 유지 |
| 깨진 멤버 혼입 | 해당 멤버만 건너뜀 | 나머지 정상 표시 |
| 미등록 팹·tool | 레지스트리 미포함 | `not_configured` — "라이브 알람 미설정" |
| 스케줄러 워커 재활용 | `RedisJobStore` 복원, 수 초 공백 | 표시 없음 — `STALE_AFTER_SEC=90` 이 흡수 |
| writer 중복 실행 | 멱등·단조 연산으로 수렴 | 표시 없음 — 사내 API 호출만 늘어남 |
| 브라우저 폴링 3회 연속 실패 | 재시도 유지 | "연결 불안정" |

`STALE_AFTER_SEC` 이 60초가 아닌 90초인 이유는 워커 재활용 행에 있습니다. 스케줄러
워커는 `max-worker-lifetime` · `max-requests` · `reload-on-rss` · 야간
`restart_uwsgi` 로 정기적으로 재활용되고, 그때마다 앱 초기화만큼의 공백이 생깁니다.
60초 임계는 배포·재활용마다 거짓 `stale` 을 띄웁니다. 90초는 6주기 연속 실패에
해당하므로 진짜 고장은 여전히 잡아냅니다.

### 빈 상태를 반드시 구분합니다

이 화면의 빈 상태에는 서로 완전히 다른 셋이 있습니다.

- "알람 없음" + 마지막 갱신 8초 전 → 팹이 건강합니다.
- "알람 없음" + 마지막 갱신 34분 전 → **아무것도 모르고 있습니다.**
- "알람 없음" + 미설정 → 이 팹은 애초에 감시 대상이 아닙니다.

하트비트가 없으면 앞의 둘이, 레지스트리가 없으면 뒤의 둘이 픽셀 단위로 동일합니다.
따라서 **알람 유무와 무관하게 피드 상태와 마지막 갱신 시각을 항상 표시합니다.**
모니터링 화면에서 "조용하다" 는 신호는 그 자체로 검증되어야 합니다.

## 11. 테스트 전략

시간에 의존하는 로직을 순수 함수로 분리하고 `now` 를 인자로 주입합니다.

**SKEWNONO 측**

- `board.feed_status_for` — 경계값(정확히 90초, 91초), `meta` 없음, 레지스트리 없음
- `board.dedupe_by_id` — 같은 `id` 멤버 둘 → 사전순 우선 하나만, **결정론적**
- `board.parse_members` — 깨진 멤버를 건너뛰고 나머지를 반환, 전부 깨져도 500 없음
- `contracts` 불변식 — `WRITER_PRUNE_SEC < BOARD_WINDOW_SEC` 이면 import 실패
- reader — `bytes` 응답을 올바르게 디코드, mock provider 가 계약을 만족

**writer** (스케줄러로 복사되지만 테스트는 SKEWNONO 레포에 둡니다)

- `window.compute` — 정상 시 60초, 공백 75초면 backfill, 공백 3시간이면 600초 상한,
  `meta` 부재면 600초
- **`events` 키 부재 → 600초** (축출 시나리오. 이게 없으면 "빈 보드 + 신선한
  하트비트" 가 성립합니다)
- 실패 시 `meta` 미갱신 — **이 설계에서 가장 중요한 단일 테스트입니다**
- 알람 0건 — `meta` 는 **갱신되어야** 합니다 (실패와 구분되는 지점)
- 전 팹 실패 → raise / 일부 실패 → raise 하지 않음
- **멱등성** — 같은 응답으로 두 번 돌려도 ZSET 크기가 같음. 락 없는 호스트에 얹을 수
  있다는 주장의 근거이므로 반드시 테스트합니다
- **`meta` 단조성** — 오래된 `polled_at` 으로 갱신을 시도해도 값이 되돌아가지 않음
- 미래 이벤트 거부 — `now + 600` 인 이벤트가 버려짐
- 계약 적합성 — writer 가 쓴 멤버를 reader 의 파싱이 그대로 읽어냄. 두 서비스가
  코드를 공유하지 않으므로, 이 테스트가 드리프트를 잡는 유일한 장치입니다

**프론트엔드**

- `diffNewIds` — 신규 진입, 소멸, 동일 집합
- `formatElapsed` — 경계값과 음수 입력 방어
- `useLiveAlarmFeed` — 교체 동작, 시계 오프셋, 가시성 전환 시 타이머 정지/재개

## 12. 스케줄러 플랫폼 변경 (`flask_modules/api`)

기존 잡의 동작을 바꾸지 않는 범위에서 두 가지가 필요합니다.

### 12.1 잡별 스케줄러 옵션 전달

현재 `schedule.py` 의 `init_jobs()` 는 `add_job()` 에 `id` / `func` / `args` /
`trigger` / `replace_existing` 만 넘깁니다. 따라서 `JOB_FUNCTIONS` 항목에
`misfire_grace_time` 을 적어도 **적용되지 않고**, `SCHEDULER_JOB_DEFAULTS` 의 60초가
그대로 쓰입니다.

`spec` 의 선택 키를 `add_job()` 으로 전달하도록 고칩니다. 기존 항목에는 그 키가
없으므로 동작이 그대로 유지됩니다.

```python
scheduler.add_job(
    id=name, func="api.schedule:run_registered_job", args=[name],
    trigger=spec["trigger"], replace_existing=True,
    **{k: spec[k] for k in ("misfire_grace_time", "executor") if k in spec},
)
```

### 12.2 짧은 잡 전용 executor

`configure_scheduler()` 는 `default` executor 하나(`max_workers=4`)만 두고, 그
상한은 10~20분짜리 pandas/OpenSearch 잡을 염두에 두고 정해진 값입니다. 긴 잡 4개가
겹치면 **15초 잡이 실행 슬롯을 얻지 못하고**, `coalesce` 로 밀린 발화가 버려져
그동안 화면은 `stale` 이 됩니다. 잡 내부의 팹 병렬 처리로는 막을 수 없는, 스케줄러
쪽 굶주림입니다.

짧은 잡 전용 executor 를 추가합니다. 기존 잡은 `executor` 키가 없어 `default` 를
계속 쓰므로 영향이 없습니다.

```python
app.config["SCHEDULER_EXECUTORS"] = {
    "default": ThreadPoolExecutor(max_workers=4),
    "fast": ThreadPoolExecutor(max_workers=1),   # 신규
}
```

### 12.3 등록

```python
"live_alarm_board": {
    "fn": run_once,
    "trigger": IntervalTrigger(seconds=15),
    "executor": "fast",
    "misfire_grace_time": 10,
    "lock_ttl": 45,
    "manual_dispatch": True,
},
```

`lock_ttl` 기본값 1200초를 **반드시** 덮어써야 합니다. `redis_lock` 은 `finally`
에서 해제하지만 락을 쥔 채 프로세스가 죽으면 키가 TTL 까지 남고, 그동안 잡이 매번
skip 됩니다. 워커는 자주 재활용되므로 실제로 일어나는 일이고, 1200초면 화면이
20분간 `stale` 입니다.

**다만 정확성이 이 락에 의존하지는 않습니다.** 락은 사내 API 호출을 줄이는 최적화일
뿐이고, 락이 없는 스케줄러에 얹어도 §5 의 멱등·단조 설계가 결과를 지켜줍니다.

## 13. 리뷰 지적 중 수용하지 않은 것

**"이식성 기계장치가 과설계"** — 수용하지 않습니다. writer 를 다른 Flask 스케줄러
서버에도 붙일 수 있어야 한다는 것은 사용자가 명시한 제약이지, 설계자가 추가한
여유가 아닙니다. 그 제약이 §5 의 저장 구조를 결정했고, 결과적으로 락 의존을
없애면서 writer 코드를 **줄였습니다**.

**같은 초에 발생한 동일 장비·동일 ALID 알람의 `id` 충돌** — 한계로 수용합니다.
사내 알람 API 가 시퀀스 번호를 제공하지 않는 한 구분할 수단이 없고, 같은 장비에서
같은 종류의 알람이 같은 초에 두 번 발생하는 것은 사실상 같은 사건입니다. 시퀀스
필드가 확인되면 `id` 에 추가합니다.

## 14. 향후 과제

**`workflow_3` 모니터 편승.** 그 루프는 이미 사내 알람 API 를 10초마다 폴링하므로,
결과를 같은 Redis 스키마로 써주면 사내 API 호출이 추가로 0이 됩니다. 커버리지가 팹
전체를 포함하는지 확인해야 하고, `meta` 하트비트를 반드시 함께 써야 합니다.

**보드 지평 조정.** `BOARD_WINDOW_SEC` 하나로 결정되며, `contracts.py` 의 assert 가
`WRITER_PRUNE_SEC` 과의 관계를 지켜줍니다.

**타임라인 시각화.** 10분 구간의 이벤트 밀도 스트립. 현재 목록으로 충분하다고
판단하여 제외했습니다.

**writer 를 import 로 전환.** 지금은 파일 복사입니다. import 경로가 열리면 바꾸며,
계약이 §5 의 Redis 구조이므로 설계 변경이 아닙니다.

**폴백 — uWSGI mule.** 어느 스케줄러에도 잡을 등록할 수 없게 되면 SKEWNONO 자체
`wsgi.ini` 의 `mule` 이 차선입니다. writer 가 자족 모듈이라 코드 수정은 필요
없습니다 — 호출해 주는 주체만 바뀝니다.

## 15. 확정된 값

| 항목 | 값 |
| --- | --- |
| 보드 시간 지평 (reader 권한) | 10분 |
| writer 보관 상한 | 15분 (`>= 보드 지평` 을 assert) |
| writer 폴링 주기 | 15초 |
| 사내 API 조회 윈도우 | 정상 60초, 복구 시 `min(공백, 600초)` |
| 사내 API HTTP 타임아웃 | connect 3초 / read 7초 |
| 미래 이벤트 허용 오차 | 300초 (초과 시 폐기) |
| stale 판정 임계 | 90초 (6주기) |
| `misfire_grace_time` | 10초 (§12.1 배선 후 유효) |
| executor | `fast` (전용, `max_workers=1`) |
| `redis_lock` TTL (락 강제 호스트에서만) | 45초 (3주기) |
| 브라우저 폴링 주기 | 15초 ± 3초 jitter |
| 표시 지연 | 중앙값 약 15초 / 최악 약 30초 |
| 시계 권한 | Redis `TIME` (writer·reader 공통) |
| Redis | SKEWNONO office 어댑터와 동일 인스턴스, **db=0** |
| Redis TTL | 24시간 (매 성공 폴링마다 갱신) |
| 대상 ALID | `9006` (align), `9100` (meas) |
| 대상 팹 수 | 6 |
| 팹당 사내 API 부하 | 분당 4회 고정 |
| writer 가 호스트에 요구하는 것 | 15초마다 `run_once()` 호출 |
