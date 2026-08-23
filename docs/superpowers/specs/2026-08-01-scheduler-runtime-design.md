# 스케줄러 런타임 설계

## 1. 배경

백엔드에 주기 작업을 붙일 자리가 필요합니다. 당장 필요한 작업은 세 가지입니다 —
image_cache 의 오래된 객체 삭제, device-statistics 주차 스냅샷 사전 계산, 그리고
그 스냅샷의 보존 기간 관리입니다.

문제는 "스케줄러가 없다"가 아닙니다. **이미 하나 있고, 운영 환경에서 조용히
잘못 동작하고 있습니다.**

`back_dev_home/msr_image/scheduler.py` 는 `create_app()` 안에서
`BackgroundScheduler(daemon=True)` 를 띄웁니다. 그런데 `wsgi.ini` 는
`processes = 4` 와 `lazy-apps = true` 로 동작하므로, **네 개의 uWSGI 워커가 각자
`create_app()` 을 호출하고 각자 스케줄러 스레드를 만듭니다.** 매일 새벽 3시에
네 프로세스가 동시에 같은 MinIO prefix 를 향해 `purge_now()` 를 부릅니다.

삭제 자체는 멱등이므로 데이터가 깨지지는 않습니다. 실제 비용은 두 가지입니다 —
불필요한 4배의 삭제 트래픽, 그리고 **그 작업이 돌았는지 확인할 방법이 어디에도
없다는 점**입니다.

`flask_modules/api/` 는 사내 환경에서 정확히 이 문제를 풀기 위해 만들어진
코드입니다. 워커 1 선출(`__init__.py`), TTL 갱신이 붙은 Redis 분산 락
(`extension.py`), 실행 기록을 남기는 `TaskLogger` 를 갖고 있습니다. 이 문서는
그 패턴을 이 저장소로 옮기는 설계를 기술합니다.

한편 device-statistics 주차 스냅샷은 **설계가 이미 끝나 있습니다.**
`docs/datatables/hitachi/device_statistics_weekly_trend.txt` 가 payload 구조와 MinIO
key 규칙을 확정했고, `providers/office_example.py:966` 에
`write_weekly_snapshot()` 이 구현되어 있습니다. 그 문서의 마지막 줄이 남긴 숙제가
**"스케줄러 자체는 아직 없습니다"** 입니다. 즉 이 작업에 필요한 것은 설계가 아니라
런타임입니다.

## 2. 목표와 비목표

### 목표

- 여러 uWSGI 워커 중 **정확히 한 프로세스만** 작업을 실행하도록 만듭니다.
- 실행 기록(시작·종료·실패·건너뜀·유실)을 남기고 조회 가능하게 만듭니다.
- 작업 세 개를 등록합니다 — image_cache 삭제, 주차 스냅샷 적재, 스냅샷 sweep.
- **집(Phase 1)에서 런타임 전체가 동작하도록** 만듭니다. Redis·MinIO 가 없는
  환경에서도 스케줄러가 뜨고 작업이 mock provider 를 향해 실제로 실행됩니다.
- `wsgi.ini` 를 **수정하지 않고** 위를 모두 달성합니다(§ 4 참조).

### 비목표

- **대시보드를 만들지 않습니다.** `flask_modules/api/templates/index.html` 에
  해당하는 Jinja 화면은 옮기지 않습니다. 이 저장소의 프런트엔드는 Nuxt SPA 이며,
  서버 렌더 템플릿 한 장을 위해 새 표면을 여는 값이 되지 않습니다.
- **수동 실행 엔드포인트(`/jobs/run_job`)를 만들지 않습니다.** 토큰 인증이 딸린
  POST 표면을 여는 셈인데, 이 저장소의 신원 모델은 `LASTUSER` 쿠키 하나입니다.
  두 번째 인증 체계를 들이는 비용이 얻는 것보다 큽니다.
- heartbeat / next_runs 키를 만들지 않습니다. 워커가 넷뿐이고 조회 표면이
  `/api/health/jobs` 하나이므로, 실행 기록만으로 "돌고 있는가"에 답할 수
  있습니다.
- 작업 본문의 비즈니스 로직을 바꾸지 않습니다. `purge_now()` 도
  `write_weekly_snapshot()` 도 동작은 그대로입니다.

## 3. 아키텍처

### 3.1 위치

```text
back_dev_home/_scheduler/
  __init__.py       start_scheduler(app)  ← 앱 팩토리의 유일한 진입점
  config.py         SchedulerConfig — 환경변수 기반
  election.py       is_scheduler_worker()
  runlog.py         RunLog 두 구현(메모리 / Redis)
  locks.py          job_lock() 두 구현(no-op / Redis)
  registry.py       JOB_REGISTRY + 래핑 + 등록
  tasks/
    image_cache.py         purge_image_cache()
    device_statistics.py   write_weekly_snapshot() · sweep_weekly_snapshots()
  tests/
```

선출 · 실행기록 · 락을 `runtime.py` 한 파일에 몰지 않고 셋으로 나눕니다. 각각
독립적으로 테스트되고 서로를 부르지 않으므로, 한 파일에 두면 세 관심사가 한
파일의 크기만큼 얽힙니다.

**밑줄 접두 폴더입니다.** 앱 팩토리의 `rglob("routes.py")` 자동 등록이 `_` 로
시작하는 경로를 건너뛰므로, `_runtime/` · `_logging/` 과 같은 공용 배관으로
취급됩니다.

feature 폴더(`scheduler/`)로 두지 않는 이유는 스케줄러가 feature 가 아니기
때문입니다 — 대응하는 Nuxt 탭이 없고, `contracts.py` 로 표현할 반환 타입이 없으며,
`providers/` 분기가 의미를 갖지 않습니다(여기서의 home/office 차이는 데이터
출처가 아니라 **백엔드**입니다).

`_runtime/` 에 합치지 않는 이유는 그 폴더가 현재 **provider 선택** 한 가지를
답하고 있기 때문입니다 — `site.py` · `data_provider.py` · `office_registry.py` 가
모두 "어느 어댑터가 응답하는가"에 대한 답입니다. 스케줄러는 자체 생명주기를 갖는
다른 관심사이며, 합치면 `_runtime/` 이 두 가지가 됩니다.

작업 **본문**은 `_scheduler/tasks/` 에 두되 feature 를 얇게 호출하는 형태로
유지합니다. `flask_modules/api/tasks/` 와 같은 구조입니다. 실제 로직은 여전히
feature 안에 남습니다 — `tasks/image_cache.py` 는 `msr_image/cache.py` 를 부를 뿐
삭제 로직을 갖지 않습니다.

### 3.2 합성 순서

각 작업은 **`redis_lock(task_logger.wrap(fn))`** 로 감쌉니다. 순서가
중요합니다 — 반대로 감으면 동시 실행에 막힌 실행이 `start` / `skip` / `end` 세
줄을 남깁니다. 이 순서에서는 `skip` 한 줄만 남습니다.

### 3.3 두 개의 백엔드

home/office 차이는 런타임 내부의 분기가 아니라 **하나의 인터페이스 뒤에 놓인 두
백엔드**로 표현합니다.

| 관심사 | 집 (`get_mode() == "mock"`) | 사무실 |
| --- | --- | --- |
| 선출 | 항상 이 프로세스 | `uwsgi.worker_id() == 1` |
| jobstore | APScheduler 기본(메모리) | APScheduler 기본(메모리) — § 3.4 |
| 락 | no-op, 항상 획득 | `redis.lock.Lock` + TTL 갱신 데몬 |
| 실행 기록 | 메모리 ring buffer + `logging` | Redis 리스트(`LPUSH` + `LTRIM`) |

**선출 판단은 `get_mode()` 로 하고 `is_cloud()` 로 하지 않습니다.** Phase 2 는
사무실 localhost 에서 도는데 그곳의 파일시스템은 집과 구분되지 않습니다. 같은
함정이 이미 한 번 데모 사용자 유출을 만들었고(`__init__.py:250-257` 의 주석),
같은 가드를 씁니다.

**선출은 세 단계입니다. 두 번째 단계가 집에서 이미 깨져 있습니다.**

```python
def is_scheduler_worker() -> bool:
    # 1. uWSGI: 워커 1 만.
    try:
        import uwsgi
        return uwsgi.worker_id() == 1
    except ImportError:
        pass
    # 2. Werkzeug 리로더: 감시자 부모가 아니라 앱 자식만.
    if _reloader_parent():
        return False
    # 3. 그 외(단일 프로세스, pytest): 이 프로세스.
    return True
```

2단계가 필요한 이유입니다. `index.py:26` 이 `debug=not cloud` 이므로 집에서는
Werkzeug 리로더가 켜집니다. 리로더는 모듈을 **두 프로세스**에서 실행합니다 —
파일을 감시하는 부모와 실제 앱을 띄우는 자식입니다. 둘 다 `create_app()` 을
부르고 둘 다 uWSGI 가 아니므로, 1·3단계만 있으면 **한 대의 개발 머신에서
스케줄러가 둘** 뜹니다.

이것은 앞으로 생길 문제가 아니라 **이미 그런 상태입니다.**
`msr_image/scheduler.py` 의 기존 가드는 `"msr_image_scheduler" in
app.extensions` 인데, 이는 app 객체 하나 안에서만 유효하며 프로세스 경계를 볼
수 없습니다. 실무상 무해했을 뿐(삭제는 멱등이고 집 캐시는 작습니다) "정확히
하나"라는 성질은 집에서 성립한 적이 없습니다.

부모와 자식을 가르는 것은 `WERKZEUG_RUN_MAIN` 입니다 — 리로더가 **자식에게만**
넣어 주는 환경변수입니다. 따라서 "리로더 부모"는 `app.debug` 가 참이면서
`WERKZEUG_RUN_MAIN` 이 없는 경우로 정확히 식별됩니다. uWSGI·클라우드에서는
`debug` 가 거짓이므로 이 판정에 걸리지 않고 1단계로 갑니다.

### 3.4 `RedisJobStore` 는 쓰지 않습니다

`flask_modules` 는 `RedisJobStore` 를 쓰지만 여기서는 쓰지 않습니다
(user-confirmed 2026-08-01).

이 저장소의 작업은 `JOB_REGISTRY` 에 **코드로 선언**되어 부팅마다 다시
등록되고, 세 트리거가 모두 cron 입니다. cron 은 절대 벽시계 기준이므로 재시작
후 새 스케줄러가 계산하는 다음 발화 시각이 곧 정답입니다. 즉 스케줄 자체를
Redis 에 보존해서 얻는 것이 거의 없습니다.

반대로 치르는 비용은 작지 않습니다. `RedisJobStore` 는 작업을 pickle 하는데,
`functools.wraps` 로 감싼 클로저를 pickle 하면 래퍼의 `__qualname__` 이 원래
함수를 가리키므로 **복원된 작업이 락과 로거를 통째로 우회**합니다.
`flask_modules` 가 `func="api.schedule:run_registered_job"` 라는 문자열 경로
간접층을 두는 이유가 이것이며, 거기에 더해 레지스트리에서 지운 작업이 Redis 에
남아 계속 발화하는 문제를 막는 orphan 수거까지 필요해집니다. 그 위험은 전부
**집에서 재현할 수 없는 부분**에 몰려 있습니다.

포기하는 것은 하나입니다 — 프로세스가 03:10 에 죽어 있었다면 그 실행은 유실로
**탐지되지 않고** 그냥 건너뛰어집니다. 다음 발화는 정상입니다.

락은 그대로 Redis 를 씁니다. jobstore 와 락은 다른 문제를 풀며, 여러 워커가
동시에 같은 작업을 실행하는 것을 막는 쪽은 락입니다.

### 3.5 사무실 백엔드에서 그대로 가져오는 두 줄

`extension.py` 에서 사소해 보이지만 반드시 유지해야 하는 부분입니다.

- **`Lock(..., thread_local=False)`** — TTL 갱신 워치독은 락을 획득한 스레드가
  **아닌** 스레드에서 `extend()` 를 부릅니다. redis-py 의 기본값은 획득 토큰을
  `threading.local()` 에 넣으므로, 워치독은 토큰을 찾지 못하고 매 tick 마다
  예외를 던집니다.
- **`lock.extend(ttl, replace_ttl=True)`** — `replace_ttl` 이 없으면 `extend` 는
  남은 TTL 에 **더합니다**. 갱신할 때마다 만료가 뒤로 밀리므로, 강제 종료된
  프로세스가 `ttl` 을 한참 넘겨 락을 고아로 남깁니다. TTL 이 존재하는 이유
  자체를 뒤집는 동작입니다.

## 4. uWSGI — 수정하지 않습니다

`scripts/deploy/pack.py:244` 와 `docs/deployment.md` § 3 이 확인해 주듯
**`wsgi.ini` 는 배포 번들에서 의도적으로 제외됩니다.** 클라우드 호스트의
`/project/workSpace/wsgi.ini` 에 영구 보관되며 오버레이가 덮어쓰지 않습니다.
따라서 `wsgi.ini` 수정이 필요한 설계는 배포 한 번이 아니라 **클라우드 호스트에서의
수동 편집**을 요구하며, 집에서는 그 결과를 확인할 방법이 없습니다.

다행히 현재 파일이 필요한 것을 이미 모두 갖고 있습니다.

| 설정 | 스케줄러가 이것에 의존하는 이유 |
| --- | --- |
| `enable-threads = true` | `BackgroundScheduler` 는 요청 스레드 밖에서 돕니다. 없으면 uWSGI 가 요청 처리 외 스레딩을 초기화하지 않아 스케줄러가 조용히 tick 하지 않습니다. |
| `lazy-apps = true` | **핵심 의존입니다.** 각 워커가 스스로 `create_app()` 을 부르므로 `uwsgi.worker_id()` 가 의미를 갖고, 스케줄러 스레드가 fork **이후에** 생성됩니다. preforking(`lazy-apps = false`)이면 앱이 마스터에서 한 번 만들어지는데 스레드는 `fork()` 를 넘어가지 못하므로, 스케줄러가 **어느 프로세스에도 존재하지 않게** 됩니다. |
| `master = true`, `processes = 4` | `worker_id()` 에 1..4 의 안정적인 값을 부여합니다. 선출이 읽는 값입니다. |
| `die-on-term = true` | TERM 이 워커까지 도달하므로 `atexit` 종료 훅이 실제로 실행됩니다. |

문제처럼 보이지만 아닌 것 두 가지를 기록해 둡니다.

**`harakiri = 60` 은 20분짜리 작업을 죽이지 않습니다.** uWSGI 는 harakiri 타이머를
**요청** 단위로 요청 핸들러 진입 시 걸고 응답 시 해제합니다. 스케줄러 스레드 풀에서
도는 작업은 타이머를 걸지 않습니다. 같은 워커에서 요청이 멈추는 경우에만 프로세스가
죽습니다.

**`max-requests = 1000` 의 워커 재활용이 유일한 실제 상호작용입니다.** 요청 1000건
후 워커 1 이 재생성되며 스케줄러 스레드도 함께 사라집니다. uWSGI 는 worker-id
슬롯을 재사용하므로 새 프로세스가 다시 선출되어 스케줄러를 복구하고, 공백은 앱
부팅 시간만큼입니다. 다만 이 재활용이 **종료 경쟁**을 드러냅니다 —
`flask_modules/api/__init__.py:75` 가 `shutdown(wait=False)` **앞에**
`scheduler.pause()` 를 부르는 이유가 이것입니다. pause 가 없으면 트리거 루프가
tick 도중일 때 ThreadPoolExecutor 가 철거되어 `cannot schedule new futures after
shutdown` 이 산발적으로 발생합니다. `max-requests` 가 켜져 있으므로 재활용은 이
환경에서 드문 일이 아니라 일상입니다. 설정 변경이 아니라 **이 종료 순서를 그대로
가져오는 것**이 해법입니다.

교과서적 대안인 uWSGI **mule**(요청을 받지 않는 전용 프로세스, `max-requests` 와
harakiri 로부터 구조적으로 자유로움)은 채택하지 않습니다. 위에서 말한 클라우드
호스트 `wsgi.ini` 수동 편집이 필요하고, Phase 1/2 의 `python index.py` 에는 mule 이
없으므로 워커 선출 경로를 어차피 만들어야 하며, 그러면 두 경로를 유지하게 됩니다.

로컬 `wsgi.ini` 에 주석을 달아도 클라우드의 사본에는 닿지 않으므로, `lazy-apps` 와
`enable-threads` 가 핵심 의존이라는 사실은 **`docs/deployment.md` 에 기록합니다.**
CLAUDE.md 가 `ARROW_DEFAULT_MEMORY_POOL` 에 하는 것과 같은 취급입니다.

## 5. 작업 레지스트리

```python
JOB_REGISTRY = {
    "image_cache_purge": {
        "fn": purge_image_cache,
        "trigger": CronTrigger(hour=3, minute=10),
        "lock_ttl": 600,
    },
    "weekly_snapshot_write": {
        "fn": write_weekly_snapshot,
        "trigger": CronTrigger(day_of_week="mon", hour=1, minute=0),
        "lock_ttl": 600,
        "misfire_grace_time": 21600,
    },
    "weekly_snapshot_sweep": {
        "fn": sweep_weekly_snapshots,
        "trigger": CronTrigger(day_of_week="mon", hour=2, minute=30),
        "lock_ttl": 600,
        "misfire_grace_time": 3600,
    },
}
```

**01시~08시는 한가한 시간대입니다(user-confirmed 2026-08-01).** 그 시간대에서는
자원 경합을 걱정하지 않고 작업을 돌릴 수 있습니다. 위 세 작업은 모두 그 창
안(01:00 · 02:30 · 03:10)에 있으며, 앞으로 작업을 추가할 때도 이 창 안에서 빈 분을
고르는 것을 기본으로 합니다.

`schedule.py` 의 레지스트리 주석이 정리한 네 가지 손잡이를 따릅니다.

**분(minute)은 손으로 배치하며 어떤 두 작업도 같은 순간을 공유하지 않습니다.**
cron 은 정확한 순간에 발화하므로 `minute=0` 으로 적힌 두 작업은 "비슷한 시각"이
아니라 **함께** 시작합니다. 세 작업을 서로 다른 시(hour)의 `:10` · `:00` · `:30`
에 둡니다.

**`lock_ttl` 은 주기가 아니라 전부 600 입니다.** 일간·주간 작업이므로 다음 발화가
최소 24시간 뒤이고, 24시간 미만의 어떤 TTL 도 실행을 건너뛰게 만들지 않습니다.
반면 값이 작으면 OOM 으로 죽은 워커가 남긴 고아 락이 10분 만에 풀립니다.
"주간 작업이니 TTL 도 주간"이라는 추론이 이 손잡이를 가장 자주 틀리게 만듭니다.

**주간 작업의 `misfire_grace_time` 은 넉넉해야 합니다.** APScheduler 의 기본값
60초는 작업이 워커 스레드에 **도달한 시점**에 검사되므로 큐 대기까지 포함합니다.
스냅샷 적재가 창을 놓치면 다음 재시도는 **다음 주 월요일**입니다. 6시간의 유예는
비용이 없고 일주일을 아낍니다.

**sweep 은 write 보다 90분 뒤이며 절대 앞서지 않습니다.** 먼저 쓸면 write 와
경쟁하여 가장 새 스냅샷이 도착하는 같은 시간에 8번째 오래된 것을 지울 수 있고,
화면이 잠깐 7주만 그리게 됩니다. 또한 write 가 실패한 주에는 삭제가 일어나지
않습니다.

`SCHEDULER_TIMEZONE = "Asia/Seoul"` 이므로 `hour=1` 은 서울 새벽 1시이며, 주차
key 의 월요일도 같은 시간대의 ISO 월요일입니다. payload 의 `generated_at` 이
`+09:00` 으로 찍히는 것(datatable 문서)과 일관됩니다.

## 6. 주차 스냅샷의 home/office 분기

### 6.1 `data.py` 에 두 함수를 추가합니다

```python
def write_weekly_snapshot(date_key: str | None = None) -> str:
    return _provider().write_weekly_snapshot(date_key)

def sweep_weekly_snapshots(keep_weeks: int = 12) -> int:
    return _provider().sweep_weekly_snapshots(keep_weeks)
```

CLAUDE.md 의 *"Do not edit `data.py`"* 와 `device_statistics/MIGRATION.md` 의
*"Never touch `data.py`"* 는 **사무실 어댑터 구현자를 향한 지침**입니다 — 사무실
방문에서 바뀌는 파일은 `office.py` 뿐이어야 한다는 뜻입니다. 설계 시점에 새로
dispatch 되는 기능을 추가하는 것은 다른 행위이며, 그렇게 하지 않으면 스케줄러가
`providers.office` 를 직접 import 하게 되어 dispatcher 가 존재하는 이유인 그 swap
을 하드코딩하게 됩니다. 두 문서가 서로 모순되지 않도록 **같은 변경에서
`MIGRATION.md` 를 갱신합니다.**

이 해석은 확인되었습니다 — 필요하면 `data.py` 를 건드려도 된다(user-confirmed
2026-08-01). 다만 범위는 **함수 두 개를 dispatcher 에 추가하는 것**뿐이며,
`_provider()` 의 선택 로직은 그대로입니다.

### 6.2 mock 은 디스크에 씁니다

`providers/mock.py` 가 두 함수를 갖습니다. 사무실 어댑터의 분해를 그대로
재사용하여(payload 생성 → 쓰기) home 과 office 가 바이트 호환 JSON 을 만듭니다.

```text
집:      var/weekly_trend/2026-08-03.json
사무실:  {MinIO 기본 prefix}/device_statistics/weekly_trend/2026-08-03.json
```

집 쪽 경로는 `SKEWNONO_WEEKLY_TREND_DIR` 로 재정의합니다. `msr_image` 의
`IMAGE_CACHE_DIR` 과 같은 규칙이며, 기본값도 같은 `var/` 아래입니다.

**읽기 경로는 의도적으로 갈라집니다 — mock 은 스냅샷을 읽지 않습니다.**

사무실 어댑터는 과거 주차를 스냅샷에서 읽고, 스냅샷이 없는 과거 주차는
**응답에서 키 자체를 뺍니다**(datatable 문서의 읽기 규칙 3). 사무실에서는
옳습니다. 집에 그 규칙을 그대로 옮기면 파괴적입니다 — 새로 받은 체크아웃에는
스냅샷이 하나도 없으므로 `recipe-trend` 가 8개 대신 **1개 날짜만** 돌려주고,
트렌드 차트는 월요일이 여덟 번 실제로 지나갈 때까지 비어 있게 됩니다.

따라서 `providers/statistics.py` 의 `get_weekly_trend_data` 는 **지금처럼 모든
주차를 라이브로 계산합니다.** 결정론적 seed(`_seed_for(lot_cd, point_index)`)
덕분에 같은 날짜는 항상 같은 값이므로, 집에서 트렌드 화면은 오늘과 똑같이
동작합니다.

집에서 `write_weekly_snapshot()` 이 하는 일은 **payload 를 만들어 파일로
남기는 것까지**이며, 그 파일을 다시 읽어 화면에 그리지는 않습니다. 검증도
거기까지입니다(§ 8 의 왕복 테스트). 이 분기는 mock 의 docstring 에 적어 두어
나중에 "사무실과 다르니 맞추자"는 수정이 화면을 비우지 않도록 합니다.

`msr_image` 의 `DiskCache` / `MinioImageCache` 분기와 같은 형태이므로, 새로 만드는
패턴이 아니라 따를 선례가 있습니다.

### 6.3 sweep 은 `last_modified` 가 아니라 **key 의 날짜**로 지웁니다

`MinioImageCache.purge` 를 의도적으로 그대로 베끼지 않는 유일한 지점입니다.

`image_cache` 가 `last_modified` 로 지우는 이유는 객체가 연속적으로 도착하고
그 쓰기 시각이 곧 나이이기 때문입니다. 스냅샷은 다릅니다 — **key 가 곧 주차**입니다.
놓친 주를 메우려고 `write_weekly_snapshot("2026-06-01")` 을 다시 부르면 그 객체의
`last_modified` 는 오늘이 됩니다. `last_modified` 기준 sweep 은 그 오래된 백필을
남기고 정상적인 최근 것을 지웁니다. key 에서 파싱한 ISO 날짜로 거르면 정확하고,
key 목록만 보고도 sweep 의 판단을 감사할 수 있습니다.

보존 기본값은 **12주**입니다. 화면은 8주(기본 `points`)를 보므로 `points` 를 나중에
올릴 여유를 두면서도 상한이 있습니다. 이 값은 **나중에 바뀔 것을 전제로**
합니다(user-confirmed 2026-08-01) — 첫 적재 후 실제 객체 크기를 보고 조정합니다.
따라서 코드에 상수로 박지 않고 `SKEWNONO_WEEKLY_TREND_KEEP_WEEKS` 환경변수로
재정의합니다. 조정에 배포가 필요하지 않아야 합니다.

sweep 은 `_is_missing_object()` 를 재사용하며 **`AccessDenied` 를 "지울 것 없음"
으로 삼키지 않습니다.** 사무실 자격증명은 허용된 prefix 밖에서 `NotFound` 가 아니라
`AccessDenied` 를 돌려주므로, 그것을 삼키면 경로 오타가 "성공"을 보고하면서 영원히
아무것도 하지 않는 sweep 이 됩니다. 예외를 올립니다.

## 7. 관측과 오류 처리

### 7.1 엔드포인트 하나

**`GET /api/health/jobs`** — 새 blueprint 가 아니라 기존 `health/` feature 에
추가합니다. 최근 실행 기록을 돌려줍니다.

```text
{ts, job, event, duration_ms, error?}
event ∈ start | end | error | skip | missed
```

기본 200건, `?limit=` 로 조정하되 보관 상한인 500건을 넘지 않습니다. 보관 상한은
저장 계층이 정의합니다 — 사무실은 `LTRIM` 으로 500건을, 집은 같은 크기의 메모리
ring buffer 로 유지합니다. 작업이 셋이고 하루 몇 건씩 쌓이므로 500건은 두 달치
이상입니다.

사무실은 Redis 리스트를, 집은 ring buffer 를 읽으므로 양쪽 phase 에서 같은 모양의
답을 돌려줍니다. `/health/providers` 와 같은 신원 게이트 뒤에 둡니다.

### 7.2 오류 처리

작업이 예외를 던져도 스케줄러 스레드가 죽어서는 안 됩니다.

- `TaskLogger.wrap` 은 `repr(exc)` 와 함께 `error` 를 기록하고 **다시
  던집니다.** APScheduler 가 executor 에서 잡으며 다음 발화는 정상 진행됩니다.
- 락 해제는 `finally` 에서 이루어지며 `RedisError` 를 삼킵니다. 여기서 예외가
  올라가면 작업 자신의 예외를 **대체**하여 진짜 원인을 가립니다.
- 로거의 Redis 실패는 기록 후 삼킵니다. 관측이 관측 대상을 깨뜨려서는 안 됩니다.
- `EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES` 리스너는 대시보드가 없어도
  유지합니다. 없으면 유실된 발화가 **어떤 기록도 남기지 않고**, 유일한 흔적이
  uWSGI 로그 한 줄인데 사무실에서 그것을 읽고 있지 않을 수 있습니다.

## 8. 테스트

전부 집에서 돕니다.

| 테스트 | 확인하는 것 |
| --- | --- |
| 레지스트리 슬로팅 | 어떤 두 작업도 같은 발화 순간을 공유하지 않으며, 모든 항목이 `lock_ttl` 과 `fn` 을 가짐 |
| 선출 — uWSGI | `worker_id() == 1` 만 선출, 나머지 셋은 스케줄러를 만들지 않음 |
| 선출 — 리로더 | `debug=True` + `WERKZEUG_RUN_MAIN` 없음(감시자 부모) → 미선출, 있음(앱 자식) → 선출. 집 개발 서버에서 스케줄러가 정확히 하나임을 보장 |
| 선출 — 단일 프로세스 | uWSGI 도 리로더도 아니면(pytest, `debug=False` 실행) 선출 |
| 락 | 두 번째 동시 호출이 건너뛰고 `skip` 기록을 **정확히 한 줄** 남김(`start`/`skip`/`end` 아님) |
| 멱등성 | `create_app()` 두 번에 스케줄러 하나, `app.testing` 이면 시작하지 않음(현재 가드 승계) |
| 스냅샷 왕복 | `write_weekly_snapshot()` 이 남긴 파일을 다시 읽어 payload 가 `build` 결과와 일치함(§ 6.2 — 화면 읽기 경로는 타지 않음) |
| 트렌드 화면 불변 | 스냅샷이 하나도 없는 상태에서 `get_weekly_trend_data()` 가 여전히 8개 날짜를 돌려줌 — mock 에 사무실 읽기 규칙이 새어 들어오면 실패 |
| sweep | 정확히 `keep_weeks` 만 남기고 key 날짜로 지우며, 백필된 오래된 주도 삭제됨 |
| 이전 | `msr_image/tests/test_scheduler.py` 가 새 task 모듈을 향하도록 변경 |

Redis 기반 락과 jobstore 는 집에서 실제 서버를 상대로 검증할 수 없는 유일한
부분이며 가짜(fake)로 대체합니다. mock 의 값 도메인이 사무실보다 좁다는 알려진
맹점이 있으므로, **검증되지 않았다는 사실 자체를 § 10 에 남깁니다.**

## 9. 변경 목록

| 변경 | 파일 |
| --- | --- |
| 새 스케줄러 런타임 | `_scheduler/` (새 폴더, 모듈 6개 + 테스트) |
| 스케줄러 기동 | `back_dev_home/__init__.py:287-288` → `start_scheduler(app)` |
| purge 작업 이전 | `msr_image/scheduler.py` **삭제**, 본문 → `_scheduler/tasks/image_cache.py` |
| 스냅샷·sweep dispatch | `device_statistics/data.py`, `providers/mock.py`, `providers/office_example.py` |
| 실행 기록 엔드포인트 | `health/routes.py`, `health/contracts.py` |
| 문서 | `docs/deployment.md`(핵심 uWSGI 설정), `device_statistics/MIGRATION.md`, `docs/datatables/hitachi/device_statistics_weekly_trend.txt`(보존 정책 구현됨으로 갱신) |

## 10. OFFICE-VERIFY

집에서 확인할 수 없어 사무실에서 확인해야 하는 항목입니다.

- **워커 선출이 실제 uWSGI 4워커에서 동작하는가.** `uwsgi.worker_id()` 경로는 집의
  `python index.py` 에서 한 번도 실행되지 않습니다. `/api/health/jobs` 가 작업당
  하루 한 줄만 보이면 성공이고, 네 줄이 보이면 선출이 실패한 것입니다.
- **락 TTL 갱신이 장시간 작업에서 유지되는가.** 스냅샷 적재가 `lock_ttl` 600초를
  넘길 경우 워치독이 갱신하는지 — 갱신에 실패하면 락이 조용히 보호를 멈춥니다.
- **첫 스냅샷 객체의 실제 크기**(datatable 문서의 기존 항목). 예상보다 크면 적재
  단위를 fab 별로 쪼개는 것을 검토합니다.
- **sweep 의 `AccessDenied` 경로.** prefix 를 일부러 틀리게 주었을 때 성공이 아니라
  예외가 나는지.
- **워커 재활용(`max-requests = 1000`) 시 `cannot schedule new futures` 로그가
  나오지 않는지.** pause-then-shutdown 이 실제로 그 경쟁을 막는지 확인합니다.
