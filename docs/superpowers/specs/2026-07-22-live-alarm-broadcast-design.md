# 라이브 알람 방송 페이지 — 설계

- **Date:** 2026-07-22 (개정 2026-07-23 — writer 배치를 기존 `api_skewnono` 스케줄러로 확정)
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
[api_skewnono 스케줄러]  ──(15초마다, 1분 윈도우)──→  사내 알람 API (팹별 주소)
       │  APScheduler 잡                            ▲
       │  정규화 + 병합 + 15분 초과 제거              팹당 4회/분 고정
       ▼
   [오피스 Redis]  skewnono:live_alarm:{tool_slug}:{fab_name}
       │
       │  GET 1회 (사내 API 호출 없음)
       ▼
[SKEWNONO Flask]  ──(10분으로 최종 절단)──→  브라우저 N개 (각 15초 폴링)
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

### writer 를 어디서 돌릴 것인가

| 방식 | 인스턴스 수 | 배포 독립성 | 관측·복구 | 판단 |
| --- | --- | --- | --- | --- |
| SKEWNONO Flask 데몬 스레드 | 4 (`processes = 4`) | ✗ | 없음 | 채택 불가 |
| SKEWNONO `wsgi.ini` 의 uWSGI mule | 1 | ✗ SKEWNONO 배포마다 끊김 | 직접 구축 | 폴백 (§12) |
| 기존 Flask 스케줄러 서비스의 잡 | 1 | ✓ 별도 서비스 | 기존 인프라 재사용 | **채택** |

데몬 스레드는 `lazy-apps = true` 때문에 워커마다 하나씩 생겨 사내 API 부하가 4배가
되고, 워커가 재활용될 때 조용히 사라집니다. mule 은 프로세스가 정확히 하나라 그
문제는 없지만, SKEWNONO 웹의 배포 주기에 묶입니다. 감시하는 쪽이 감시당하는 쪽의
배포에 흔들려서는 안 됩니다.

현재는 `api_skewnono`(포트 8000)에 등록하지만, **writer 는 특정 스케줄러에 종속되지
않게 작성합니다**(§6). 다른 Flask 스케줄러 서버로 옮기거나 병행 운영할 수 있어야
하며, 이 요구가 §5 의 저장 구조를 결정했습니다.

## 4. 데이터 계약

`back_dev_home/ebeam/hitachi/live_alarm/contracts.py` 에 정의합니다.

**writer 는 이 모듈을 import 하지 않습니다.** writer 는 다른 서비스에서 실행되므로,
두 쪽이 공유하는 것은 Python 코드가 아니라 **Redis 에 담기는 JSON 형태**(§5)입니다.
공유 표면을 필드 이름으로 좁히면 배포 방식이 설계를 구속하지 않습니다.

```python
Kind = Literal["align", "meas"]
FeedStatus = Literal["live", "stale"]

BOARD_WINDOW_SEC = 600      # reader 가 최종적으로 잘라 내보내는 시간 지평
POLL_WINDOW_SEC = 60        # writer 가 사내 API 에 요청하는 윈도우
WRITER_INTERVAL_SEC = 15    # writer 폴링 주기
WRITER_PRUNE_SEC = 900      # writer 가 보관하는 상한 (지평보다 넉넉하게)
STALE_AFTER_SEC = 90        # 이 시간을 넘기면 feed_status = "stale"

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

**시간 지평의 최종 권한은 reader 에게만 있습니다.** writer 는 `WRITER_PRUNE_SEC=900`
으로 넉넉히 자르고, 화면에 나갈 10분은 reader 가 결정합니다. 두 서비스가 이 숫자에
대해 의견이 달라져도 화면은 항상 옳으므로, writer 코드가 복사본으로 관리되더라도
드리프트가 무해합니다.

## 5. Redis 스키마

팹·tool 조합마다 키 두 개를 씁니다.

| 키 | 자료형 | 내용 | TTL |
| --- | --- | --- | --- |
| `skewnono:live_alarm:{tool_slug}:{fab_name}:events` | ZSET | member = `AlarmEvent` 의 canonical JSON, score = `occurred_at` 의 epoch 초 | 24시간 |
| `skewnono:live_alarm:{tool_slug}:{fab_name}:polled_at` | STRING | writer 의 마지막 **성공** 폴링 시각 | 24시간 |

### 왜 ZSET 인가 — 락을 없애기 위해서입니다

writer 는 어느 Flask 스케줄러 서버에도 꽂을 수 있어야 합니다(§6). 그 서버가 분산
락을 제공하는지, 멀티 워커인지 알 수 없으므로 **writer 가 중복 실행돼도 안전해야
합니다.**

JSON 블롭 하나에 보드를 담으면 read-modify-write 가 되어 동시 실행 시 lost update
가 발생하고, 이를 막으려면 호스트가 락을 제공해야 해서 이식성이 깨집니다. ZSET 은
그 문제를 자료구조 수준에서 없앱니다.

| 연산 | 멱등성 |
| --- | --- |
| `ZADD` | 같은 이벤트는 member 문자열이 같아 자동으로 한 번만 남습니다 |
| `ZREMRANGEBYSCORE` | 몇 번 실행해도 결과가 같습니다 |
| `SET polled_at` | 거의 같은 값으로 덮어쓰므로 마지막이 이겨도 무방합니다 |

동시 실행·중복 실행·재시도가 모두 같은 상태로 수렴하므로 **락이 필요 없습니다.**

부수 효과가 더 큽니다. **writer 가 Redis 를 읽지 않아도 됩니다.** 기존 보드를
읽어 병합하는 단계가 사라지므로 writer 에는 병합 함수도 만료 함수도 필요 없습니다.
저장 구조를 복잡하게 만든 것이 아니라 코드를 지운 것입니다.

reader 쪽에서도 10분 절단이 `ZRANGEBYSCORE (now-600) +inf` 의 인자가 되어 파이썬
만료 코드가 사라집니다.

member 를 `id` 가 아닌 canonical JSON(키 정렬, 공백 없음)으로 두는 이유는 키를
하나로 유지하기 위해서입니다. 대신 같은 `id` 인데 부가 필드만 다른 레코드가 두 벌
남을 가능성이 생기므로, **reader 가 읽은 뒤 `id` 로 한 번 더 중복을 제거합니다.**
어차피 reader 가 최종 권한을 갖는 구조이므로 그 자리에서 흡수합니다.

### 네임스페이스와 계약

키를 `api_skewnono:` 가 아닌 `skewnono:live_alarm:` 네임스페이스에 두는 것은
의도된 선택입니다. `api_skewnono:` 는 스케줄러의 살림살이(잡 스토어, 락, 태스크
로그)이고, 이 키는 SKEWNONO 가 소비하는 **애플리케이션 데이터** 입니다. writer 가
어느 스케줄러로 옮겨가도 키 이름은 그대로여야 합니다.

**이 키 구조와 member JSON 형태가 writer 와 reader 사이의 유일한 계약입니다.** 두
서비스는 Python 코드를 공유하지 않으므로, 키 이름 2개와 필드 이름 9개(`AlarmEvent`)
가 합의의 전부입니다.

TTL 24시간은 폐기된 팹의 키가 스스로 정리되게 하되, 하루 안에는 `polled_at` 을
보존해 "언제부터 멈췄는가" 를 진단할 수 있게 하는 값입니다. 두 키 모두 매 성공
폴링마다 `EXPIRE` 를 갱신합니다.

### 어느 Redis 를 쓰는가

**SKEWNONO office 어댑터가 읽는 Redis** 를 그대로 씁니다 —
`back_dev_home/.env` 의 `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` 가 가리키는 곳
입니다. 스케줄러 자신의 Redis(`ApiRedisConfig` 의 잡 스토어 `db=0`, 락 `db=1`)가
아닙니다.

reader 가 읽을 수 있는 Redis 는 그곳뿐이므로, writer 가 다른 인스턴스에 쓰면
reader 에 두 번째 Redis 설정을 추가해야 합니다. 같은 Redis 를 공유하는 데 따르는
위험은 두 가지 장치로 이미 막혀 있습니다.

- **키 네임스페이스** — `skewnono:live_alarm:` 접두사가 기존 `v3_df_*` 키와
  겹치지 않습니다.
- **모든 키에 TTL** — 24시간이 지나면 스스로 사라지므로, writer 가 잘못 돌아도
  Redis 를 무한정 채우지 않습니다.

데이터량은 팹 6개 × 수십 건의 작은 JSON 이라, 이미 저장 중인 parquet DataFrame 에
비하면 무시할 수준입니다.

> **배포 시 확인:** 스케줄러 서버에서 그 Redis 로의 네트워크 접근과 쓰기 권한이
> 열려 있어야 합니다. writer 는 접속 정보를 환경 변수로 받습니다(§6).

## 6. Writer — 이식 가능한 스케줄러 잡

writer 는 **특정 스케줄러 서비스에 종속되지 않습니다.** 어느 Flask + APScheduler
서버에도 파일을 놓고 잡 하나를 등록하면 동작해야 합니다. 그래야 지금은
`api_skewnono` 에 붙이더라도 나중에 다른 스케줄러로 옮기거나 병행 운영할 수
있습니다.

이 요구가 설계를 지배합니다.

### 호스트에 요구하는 것 — 주기 호출 하나뿐

```python
run_once()   # 인자 없음, 반환값 없음, 예외를 밖으로 던지지 않음
```

writer 가 호스트에 기대하는 것은 "15초마다 이 함수를 불러달라" 가 전부입니다.
분산 락도, 잡 스토어도, 앱 컨텍스트도 요구하지 않습니다.

| 흔히 호스트에 의존하는 것 | writer 가 대신 하는 것 |
| --- | --- |
| 분산 락으로 중복 실행 방지 | Redis 연산을 전부 멱등으로 설계 (§5) — 중복 실행이 무해 |
| `app.config` 에서 설정 읽기 | 환경 변수에서 직접 읽음 |
| 프레임워크 로거 | 표준 `logging` 모듈 |
| 앱 컨텍스트 | 필요 없음 |

의존성은 `redis` 와 `requests` 뿐이며, 스케줄러 서버라면 대개 이미 있습니다.

### `api_skewnono` 에 등록하는 경우

```python
"live_alarm_board": {
    "fn": run_once,
    "trigger": IntervalTrigger(seconds=15),
    "lock_ttl": 45,
    "manual_dispatch": True,
},
```

그 플랫폼은 `redis_lock` 을 모든 잡에 강제로 씌우므로 `lock_ttl` 을 **반드시**
덮어써야 합니다. 기본값은 1200초인데, `redis_lock` 은 `finally` 에서 해제하지만
락을 쥔 채 프로세스가 죽으면 키가 TTL 까지 남고 그동안 잡이 매번 skip 됩니다.
워커는 `max-worker-lifetime = 3600` · `reload-on-rss = 1500` · 1시 `restart_uwsgi`
로 자주 재활용되므로 실제로 일어나는 일입니다. 1200초면 화면이 20분간 `stale`
이고, 45초(3주기)면 스스로 회복합니다.

`misfire_grace_time` 도 이 잡에 한해 `10` 으로 낮춥니다. 10초 넘게 밀린 발화는
버리는 편이 낫습니다 — 다음 주기가 5초 뒤입니다.

**다만 정확성이 이 락에 의존하지는 않습니다.** 락은 사내 API 호출을 줄여주는
최적화일 뿐이고, 락이 없는 스케줄러에 얹어도 결과는 같습니다. 그래야 이식 가능
합니다.

### 호스트가 이미 제공하면 재사용하는 것

`api_skewnono` 기준으로, 다음은 플랫폼이 주므로 writer 가 다시 만들지 않습니다.
다른 스케줄러에 옮겨가면 그 서버가 주는 만큼만 쓰면 되고, 없어도 writer 는
동작합니다.

| 성질 | `api_skewnono` 제공 수단 |
| --- | --- |
| 주기 실행 | `IntervalTrigger` (기존 잡이 이미 `seconds=30` 으로 운영 중) |
| 프로세스 재기동 후 복구 | `RedisJobStore` + uWSGI master |
| 실행 이력·오류 관측 | `TaskLogger` → `GET /jobs/logs` |
| 겹침 방지 / 밀린 발화 병합 | `SCHEDULER_JOB_DEFAULTS` 의 `max_instances=1`, `coalesce=True` |
| 단일 인스턴스 | `uwsgi.worker_id() == 1` 역할 선출 |

### 한 주기의 동작

팹마다 독립적으로, 아래를 수행합니다.

1. 사내 알람 API 를 `POLL_WINDOW_SEC=60` 으로 조회합니다. 대상 팹 목록은
   `fab_name → API 주소` 매핑의 키 집합이며, 별도 설정 파일을 두지 않습니다. 팹을
   추가하는 행위와 주소를 등록하는 행위가 같은 한 번의 편집이 되어야 목록과 주소가
   어긋나지 않습니다.
2. 응답을 `AlarmEvent` 로 정규화합니다. `ALID_KIND` 에 없는 알람은 버립니다.
3. 한 파이프라인으로 네 연산을 보냅니다.

```python
pipe.zadd(events_key, {canonical_json(e): epoch(e["occurred_at"]) for e in events})
pipe.zremrangebyscore(events_key, "-inf", now_epoch - WRITER_PRUNE_SEC)
pipe.expire(events_key, 86400)
pipe.set(polled_key, now_text, ex=86400)
pipe.execute()
```

**Redis 를 읽지 않습니다.** 병합은 `ZADD` 가, 만료는 `ZREMRANGEBYSCORE` 가 대신
하므로 writer 에는 병합 함수도 만료 함수도 없습니다.

조회 윈도우 60초가 주기 15초의 4배이므로, 스케줄러 지터나 일시적 실패가 몇 번
발생해도 이벤트를 놓치지 않습니다.

윈도우 안에 알람이 하나도 없을 때 `ZADD` 는 건너뛰되 **`polled_at` 은 갱신합니다.**
"알람이 없었다" 는 폴링 성공이지 실패가 아니며, 이 구분이 §10 의 두 빈 상태를
가릅니다.

### 설정

접속 정보와 튜닝 값은 전부 환경 변수로 받습니다. 호스트 프레임워크의 설정 체계에
의존하지 않아야 이식됩니다.

| 환경 변수 | 용도 |
| --- | --- |
| `LIVE_ALARM_REDIS_HOST` / `_PORT` / `_DB` / `_PASSWORD` | §5 의 Redis (SKEWNONO 가 읽는 것과 동일) |
| `LIVE_ALARM_POLL_WINDOW_SEC` | 기본 60 |
| `LIVE_ALARM_PRUNE_SEC` | 기본 900 |
| `LIVE_ALARM_HTTP_TIMEOUT` | 기본 `3,7` |

### 스레드 풀 예산

`SCHEDULER_EXECUTORS` 는 `ThreadPoolExecutor(max_workers=4)` 이고, 그 상한은
"10~20분짜리 pandas/OpenSearch 잡이 굶지 않게" 두 CPU 환경에서 의도적으로 정해진
값입니다. 따라서 **팹별로 잡을 6개 등록하지 않습니다.** 15초마다 6칸을 요구하면
기존 장기 잡을 밀어냅니다.

잡은 하나만 등록하고, 6개 팹은 **잡 내부의 자체 스레드 풀** 로 병렬 조회합니다.
플랫폼 풀은 항상 1칸만 점유하고, 팹이 늘어도 그대로입니다. HTTP 타임아웃은
`(connect 3, read 7)` 로 두어 팹 수와 무관하게 한 주기가 10초 안에 끝나게 합니다 —
15초 주기에서 다음 발화가 `max_instances=1` 로 skip 되지 않는 선입니다.

### 실패 시 규칙

**사내 API 호출이 실패하면 `polled_at` 을 갱신하지 않습니다. 예외 없습니다.**

이 규칙이 이 설계 전체의 안전성을 지탱합니다. 실패했는데도 시각을 찍으면
하트비트가 거짓말을 하고, 화면은 정상으로 보이면서 실제로는 아무것도 모르는
상태가 됩니다. 실패 시에는 기존 보드를 그대로 두고 로그만 남긴 뒤 다음 주기를
기다립니다.

팹별 예외는 잡 안에서 격리하여, 한 팹의 실패가 다른 팹의 갱신을 막지 않게 합니다.
**`run_once` 는 예외를 밖으로 던지지 않습니다** — 호스트 스케줄러가 무엇이든 잡
하나의 실패로 스케줄러 스레드가 흔들리면 안 되기 때문입니다. 오류는 표준 `logging`
으로 남기고, `TaskLogger` 를 가진 호스트에서는 그 로그가 함께 수집됩니다.

### 코드 배치

writer 는 **SKEWNONO 코드를 하나도 import 하지 않는 자족 모듈** 로 작성합니다.
의존성은 `redis` 와 `requests` 뿐입니다.

원본과 테스트는 SKEWNONO 레포에 둡니다(진실의 원천). 배포 시 그 디렉터리를 스케줄러
서비스에 놓고 잡 하나를 등록합니다. 나중에 두 서비스 사이의 import 경로가 열리면
복사 대신 import 로 바꾸면 되고, 그것은 순수한 개선일 뿐 설계 변경이 아닙니다 —
계약은 어차피 §5 의 Redis 구조이기 때문입니다.

사내 알람 API 주소는 기존 규약대로 gitignore 대상인 `office.py` 안에만 둡니다.
`office_example.py` 를 구현해 두고 오피스에서 `cp office_example.py office.py` 로
활성화합니다.

### 모듈 구성

```text
live_alarm/
├── contracts.py            # 스키마·상수 (SKEWNONO 측)
├── board.py                # 순수 함수: feed_status_for / dedupe_by_id
├── data.py                 # mock|office 디스패처 (안정 층, 수정하지 않음)
├── routes.py               # GET /api/ebeam/<tool_slug>/live-alarm
├── providers/
│   ├── mock.py             # Phase 1 — Redis 없이 즉답
│   └── office_example.py   # ZRANGEBYSCORE + dedupe + feed_status 판정
├── writer/                 # 스케줄러 서비스로 복사되는 자족 모듈
│   ├── job.py              # run_once() — SKEWNONO import 없음
│   ├── normalize.py        # 사내 응답 → AlarmEvent + canonical JSON
│   └── office_example.py   # 사내 알람 API 호출 + fab_name → 주소 매핑
└── tests/
```

`board.py` 에 병합·만료 함수가 없는 것은 Redis 가 그 일을 하기 때문입니다.
`dedupe_by_id` 만 남는데, 이는 §5 에서 설명한 "같은 `id` 인데 부가 필드만 다른
멤버" 를 reader 가 흡수하기 위한 것입니다.

reader 쪽 Redis 접속은 `_runtime/office_redis.py` 의 `redis_client()` 를 재사용하며,
어댑터마다 접속 코드를 다시 만들지 않습니다. writer 는 자족 모듈이므로 자체 클라이언트를
만듭니다 — 이 중복은 서비스 경계를 넘기 위한 의도된 비용입니다.

## 7. SKEWNONO 백엔드 (읽기 전용)

`GET /api/ebeam/<tool_slug>/live-alarm?fab_name=R3`

`office.py` 의 동작은 다음 네 단계가 전부입니다.

```python
now = server_now_epoch()
events = r.zrangebyscore(events_key, now - BOARD_WINDOW_SEC, "+inf")  # 10분 절단
polled_at = r.get(polled_key)
events = board.dedupe_by_id(json.loads(m) for m in events)
status = board.feed_status_for(polled_at, now=now)                    # live | stale
```

**시간 지평의 최종 권한은 reader 에게 있습니다.** writer 가 멈추면 보드가 얼어붙는데,
40분 전 알람을 현재처럼 보여주면 안 되기 때문입니다. reader 가 매 응답마다 10분
경계를 `ZRANGEBYSCORE` 의 하한으로 다시 계산하므로, writer 정지 후 10분 안에 보드가
자연히 비고 화면은 "알람 없음 + 마지막 갱신 34분 전 (지연)" 이라는 정확한 상태가
됩니다. 절단이 질의 인자라서 reader 에는 만료 코드 자체가 없습니다.

writer 의 `WRITER_PRUNE_SEC=900` 은 저장 크기를 묶기 위한 것일 뿐 화면에 영향을 주지
않습니다. 두 서비스가 이 숫자에 대해 의견이 달라져도 안전하도록 의도적으로 분리했습니다.

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
| 스케줄러 워커 재활용 | `RedisJobStore` 에서 잡 복원, 수 초 공백 | 표시 없음 — `STALE_AFTER_SEC=90` 이 흡수 |
| 락이 물린 채 프로세스 사망 | `lock_ttl=45` 만료 후 자동 회복 | 최대 45초간 `stale` |
| writer 중복 실행 (락 없는 호스트) | Redis 연산이 멱등이라 같은 상태로 수렴 | 표시 없음 — 사내 API 호출만 늘어남 |
| 브라우저 폴링 1~2회 실패 | 조용히 재시도 | 변화 없음 |
| 브라우저 폴링 3회 연속 실패 | 재시도 유지 | "연결 불안정" 표시 |
| 미지원 `fab_name` | 404 | 오류 페이지 |

`STALE_AFTER_SEC` 을 60초가 아닌 90초로 잡은 이유가 위 표 5행에 있습니다. 스케줄러
워커는 `max-worker-lifetime = 3600` · `max-requests = 1000` · `reload-on-rss = 1500`
· 1시 `restart_uwsgi` 로 정기적으로 재활용되고, 그때마다 앱 초기화만큼의 공백이
생깁니다. 60초 임계는 배포·재활용마다 거짓 `stale` 을 띄웁니다. 90초는 6주기 연속
실패에 해당하므로 진짜 고장은 여전히 잡아냅니다.

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

- `board.feed_status_for` — 경계값(정확히 90초, 91초), `polled_at = None`
- `board.dedupe_by_id` — 같은 `id` 의 멤버가 둘일 때 하나만 남음
- 정규화 — `ALID_KIND` 매핑, `id` 조립, 미지원 ALID 제외
- `canonical_json` — 필드 순서가 달라도 같은 문자열을 만듦 (ZSET 중복 제거의 전제)
- reader — mock provider 가 `LiveAlarmPayload` 계약을 만족함

**writer** (스케줄러 서비스로 복사되지만 테스트는 SKEWNONO 레포에 둡니다)

- `run_once` 한 주기 — 사내 API 실패 시 `polled_at` 이 갱신되지 않음을 검증합니다.
  이 설계에서 가장 중요한 단일 테스트입니다
- 알람 0건 — `polled_at` 은 **갱신되어야** 합니다 (실패와 구분되는 지점)
- 팹 격리 — 한 팹의 예외가 다른 팹 갱신을 막지 않음을 검증합니다
- `run_once` 가 예외를 밖으로 던지지 않음
- **멱등성** — 같은 응답으로 `run_once` 를 두 번 돌려도 ZSET 크기가 같음. 락 없는
  호스트에 얹을 수 있다는 주장의 근거이므로 반드시 테스트합니다
- 계약 적합성 — writer 가 쓴 멤버를 reader 의 파싱이 그대로 읽어냄을 검증합니다.
  두 서비스가 코드를 공유하지 않으므로, 이 테스트가 드리프트를 잡는 유일한 장치입니다

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

**writer 를 import 로 전환.** 지금은 파일 복사로 스케줄러 서비스에 배치합니다.
두 서비스 사이의 import 경로가 열리면 복사를 import 로 바꿉니다. 계약이 §5 의
Redis 구조이므로 이 전환은 설계 변경이 아니라 배포 방식의 개선입니다.

**폴백 — uWSGI mule.** 어느 Flask 스케줄러에도 잡을 등록할 수 없는 상황이 되면,
SKEWNONO 자체 `wsgi.ini` 에 `mule = ...` 로 writer 를 띄우는 방법이 차선입니다.
프로세스는 정확히 하나가 되고 마스터가 재기동해 주지만, 관측 수단을 직접 만들어야
하고 SKEWNONO 배포마다 감시가 끊깁니다. writer 가 자족 모듈이라 이 전환에 코드
수정은 필요 없습니다 — 호출해 주는 주체만 바뀝니다.

## 13. 확정된 값

| 항목 | 값 |
| --- | --- |
| 보드 시간 지평 (reader 권한) | 10분 |
| writer 보관 상한 | 15분 |
| writer 폴링 주기 | 15초 |
| 사내 API 조회 윈도우 | 1분 |
| 사내 API HTTP 타임아웃 | connect 3초 / read 7초 |
| stale 판정 임계 | 90초 (6주기) |
| `misfire_grace_time` | 10초 |
| `redis_lock` TTL (락을 강제하는 호스트에서만) | 45초 (3주기) |
| 브라우저 폴링 주기 | 15초 |
| Redis | SKEWNONO office 어댑터와 동일 인스턴스·DB |
| Redis TTL | 24시간 (매 성공 폴링마다 갱신) |
| 대상 ALID | `9006` (align), `9100` (meas) |
| 대상 팹 수 | 6 |
| 팹당 사내 API 부하 | 분당 4회 고정 |
| 호스트 스레드 풀 점유 | 잡 1개 = 1칸 (팹 수와 무관) |
| writer 가 호스트에 요구하는 것 | 15초마다 `run_once()` 호출 (락·잡스토어·앱컨텍스트 불필요) |
