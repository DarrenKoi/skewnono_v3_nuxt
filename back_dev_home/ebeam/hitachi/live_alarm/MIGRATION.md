# live_alarm — 오피스 전환 절차

이 기능은 다른 기능과 달리 **swap surface 가 둘** 입니다.

| 위치 | 역할 | 실행 주체 |
| --- | --- | --- |
| `providers/office.py` | Redis 를 읽어 화면에 내보냅니다 | SKEWNONO Flask |
| `writer/office.py` | 사내 알람 API 를 폴링해 Redis 에 씁니다 | 스케줄러 서비스 |

writer 가 먼저 돌아야 reader 가 보여줄 것이 생깁니다. 아래 순서대로 진행합니다.

## 1. 스케줄러 플랫폼 사전 조건

`flask_modules/api` 에 다음 두 가지가 이미 반영되어 있어야 합니다.

- `extension.py` 의 `SCHEDULER_EXECUTORS` 에 `fast` executor (단일 스레드 전용
  레인)
- `schedule.py` 의 `init_jobs` 가 job 별 `misfire_grace_time` / `executor` 를
  선택적으로 전달하는 로직

두 가지 모두 이미 배포되어 있는 것으로 확인되었으므로, 이 절차에서 스케줄러
플랫폼 자체를 수정할 필요는 없습니다. 없는 상태에서 등록하면 15초 주기 job 이
긴 job 에 밀려 4-worker 스레드풀에서 굶고, `misfire_grace_time` 은 기본값
60초가 적용됩니다.

## 2. writer 배치

1. `back_dev_home/ebeam/hitachi/live_alarm/writer/` 디렉터리 전체를 스케줄러
   서비스로 복사합니다. `job.py` 는 이미 `from .normalize import ...` /
   `from .window import compute_window` 같은 상대 경로 import 만 사용하므로,
   복사 후 import 를 다시 손볼 필요가 없습니다.
2. `cp office_example.py office.py` 후 `ALARM_API` 에 팹별 실제 주소를
   채웁니다. **이 맵의 키 집합이 곧 감시 대상 팹 목록입니다** — 팹을
   추가하는 일과 주소를 등록하는 일이 같은 한 줄의 편집이라, 목록과 주소가
   따로 어긋날 일이 없습니다.
3. 환경 변수 `LIVE_ALARM_REDIS_*` 를 설정합니다. **`LIVE_ALARM_REDIS_DB` 는
   반드시 0 이어야 합니다** — `office_redis.py` 가 `db` 인자를 전혀 넘기지
   않아 reader 가 항상 0 번 db 에 있기 때문입니다.
4. `JOB_FUNCTIONS` 에 다음과 같이 등록합니다.

   ```python
   "live_alarm_board": {
       "fn": run_once,
       "trigger": IntervalTrigger(seconds=15),
       "executor": "fast",
       "misfire_grace_time": 10,
       "lock_ttl": 45,          # 기본값 1200 을 반드시 덮어씁니다
       "manual_dispatch": True,
   },
   ```

   `lock_ttl` 기본값 1200초를 그대로 두면, 락을 쥔 워커가 재활용되는 순간부터
   20분 동안 이 job 이 계속 skip 되고 화면은 그동안 내내 `stale` 로 보입니다.

## 3. writer 동작 확인

```bash
redis-cli -n 0 --scan --pattern 'skewnono:live_alarm:*'
redis-cli -n 0 SMEMBERS skewnono:live_alarm:registry
redis-cli -n 0 GET skewnono:live_alarm:cd-sem:R3:meta
```

`meta` 의 `polled_at` 값이 약 15초 간격으로 계속 올라가면 정상입니다. 올라가지
않으면 스케줄러의 `/jobs/logs` 에서 `live_alarm_board` 의 `error` 레코드를
확인합니다. `registry` 셋에 등록한 `tool_slug:fab_name` 조합이 모두 보이는지도
함께 확인합니다.

## 4. reader 활성화

```bash
cd back_dev_home/ebeam/hitachi/live_alarm/providers
cp office_example.py office.py
```

`office.py` 파일이 존재한다는 사실 자체가 이 기능을 office 모드로 전환합니다.
별도의 환경 변수 설정은 필요하지 않습니다 (`_runtime/office_registry.py` 가
파일 존재 여부만 확인합니다).

## 5. 검증

```bash
SKEWNONO_LIVE_ALARM_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/live_alarm
curl 'http://localhost:5000/api/health/providers' | grep live_alarm
curl 'http://localhost:5000/api/cdsem/live-alarm?fab_name=R3'
```

응답의 `feed_status` 값을 확인합니다.

| 값 | 의미 | 조치 |
| --- | --- | --- |
| `live` | 정상 수신 중입니다 | 없음 |
| `stale` | 레지스트리에는 있으나 갱신이 멈췄습니다 | writer job 로그를 확인합니다 |
| `not_configured` | 이 팹이 `ALARM_API` 에 등록되어 있지 않습니다 | 주소 맵에 추가합니다 |

## 주의

- writer 는 절대 `back_dev_home` 를 import 하지 않습니다. 이식성이 이 기능의
  핵심 설계 제약이므로, 편의를 위해서라도 import 를 추가하지 않습니다.
- writer 와 reader 는 Python 코드를 공유하지 않습니다. 유일한 예외는 reader
  가 `writer.job` 에서 키 레이아웃(`keys()`, `REGISTRY_KEY`)만 가져오는
  것뿐입니다. 그 외에 사람이 직접 맞춰야 하는 마지막 약속은 `AlarmEvent`
  멤버 스키마이며, `test_written_members_are_readable_by_the_reader` 가 이를
  지킵니다. writer 를 수정할 때마다 이 테스트를 반드시 다시 실행합니다.
