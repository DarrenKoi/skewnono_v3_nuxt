# live_alarm — 오피스 전환 절차

swap surface 는 **하나**입니다. `providers/office.py` 를 만들면 이 기능이
office 모드로 전환됩니다. 별도의 스케줄러 서비스나 writer 배포는 필요하지
않습니다.

## 1. office_utils 에 알람 조회 함수를 둡니다

`office_utils/live_alarm.py` 에 아래 한 함수를 둡니다. SKEWNONO 는 이 함수
하나만 호출합니다.

```python
def get_ebeam_metrology_alarms(fac_id: str) -> pd.DataFrame:
    """한 fac_id 의 알람 rows 를 ALID 구분 없이 모두 돌려줍니다."""
```

**ALID 로 미리 거르지 마십시오.** 무엇을 화면에 올릴지는
`contracts.ALID_KIND` 가 정합니다. 여기서 걸러 보내면 관심 코드가 하나 늘 때
office 쪽 코드를 다시 배포해야 합니다.

| ALID | kind | AL_TEXT |
| --- | --- | --- |
| `9006` | align | ALIGNMENT FAIL |
| `9007` | meas | FAILURE IN DETECTION OF PATTERN |
| `9035` | meas | FAILURE IN AUTO MEASUREMENT |

셋 다 HITACHI 전용 코드이고, CD-SEM 과 HV-SEM 이 같은 코드를 씁니다. AMAT
장비의 측정 실패 코드는 아직 확인되지 않았습니다.

예전 이름 `get_cdsem_alarms()` 에서 두 가지가 바뀌었습니다 — `fac_id` 인자가
생겼고, 대상이 CD-SEM 이 아니라 e-beam metrology 전체(CD-SEM + HV-SEM)입니다.

반환 컬럼은 전부 대문자이고, `UTC9` 만 `datetime64[us]`, `RAWID` 만 `int`,
나머지는 전부 `str` 입니다. 전체 목록과 dtype 은
[`docs/datatables/live_alarm_board.txt`](../../../../docs/datatables/live_alarm_board.txt)
에 있습니다. 여기 적힌 것보다 컬럼이 많아도 무해합니다 — `normalize.py` 는
이름으로 찾아 읽습니다.

| 컬럼 | 필수 | 의미 |
| --- | --- | --- |
| `EQP_ID` | 예 | 장비 ID. 이 값으로 sem_list 에서 fab 을 찾습니다 |
| `ALID` | 예 | 알람 코드. 위 표 참조 |
| `UTC9` | 예 | 발생 시각(KST). `TIMESTAMP` 로 대체 가능 |
| `RAWID` | 아니오 | row 고유 키. 있으면 중복 제거 키로 씁니다 |
| `AL_TEXT` | 아니오 | 알람 설명. 화면 문구가 됩니다 |
| `AL_TYPE` | 아니오 | `inform` / `warning` |
| `AL_CODE` | 아니오 | 용도 미확인 |
| `LOT_ID`, `CASSETTE_ID` | 아니오 | lot / FOUP |
| `RECIPE_ID`, `PPID` | 아니오 | 같은 recipe 의 두 표기 |
| `OPERATION_DESC`, `STEP_ID` | 아니오 | step 명 / process ID |
| `LOT_TYPE_CD` | 아니오 | lot 종류 코드 |
| `MESEVENTNAME`, `EQ_STAT` | 아니오 | `waferload`·`endrun` / `proc`·`wait` |
| `ALARM_MODELNAME` | 아니오 | 장비 model 명 |
| `TIMESTAMP` | 아니오 | `UTC9` 가 없을 때의 대체 값 |

선택 컬럼이 비어 있으면 `NaN` 이어도 됩니다. `normalize.py` 가 `NaN`/`NaT`/
`None` 을 빈 문자열로 바꿔 화면에 `nan` 이라는 글자가 찍히지 않게 합니다.

### timeout 은 이 함수 안에서 걸어야 합니다

**`get_ebeam_metrology_alarms` 는 반드시 자체 timeout 을 걸어야 하며, 그 값은
`LOCK_TTL_SEC`(20초)보다 짧아야 합니다.** SKEWNONO 는 이 호출에 timeout 을 걸지 않습니다 —
조회 수단(HTTP/DB/MES 클라이언트)을 office 쪽만 알기 때문입니다.

20초를 넘기면 락이 만료되어 **다음 요청이 두 번째 조회를 시작합니다.** 느린
사내 API 앞에서 호출이 겹치는 것이 이 설계가 막으려던 바로 그 상황이므로,
timeout 은 선택이 아닙니다. 권장값은 connect 3초 / read 7초입니다(예전 writer
가 쓰던 `LIVE_ALARM_HTTP_TIMEOUT=3,7` 과 같은 값).

```python
response = requests.get(url, params=..., timeout=(3, 7))
```

조회가 실패하면 예외를 그대로 올립니다. 빈 DataFrame 을 돌려주면 "조회 성공,
알람 없음" 으로 기록되어 `fetched_at` 이 갱신되고, 화면은 피드가 죽은 줄
모르게 됩니다.

### 인자는 fac_id 입니다

`fac_id` 는 fab 을 묶은 **상위 단위**(`M16`, `R3`)이고, 화면 URL 이 나르는
`fab_name` 은 그보다 세분화된 값(`M16A`, `M16B`, `R3`, `R4`)입니다.

| 키 | 값 예시 |
| --- | --- |
| `fab_name` | `M16A`, `M16B`, `M16C`, `R3`, `R4` |
| `fac_id` | `M16`, `R3` (`R3`+`R4` → `R3`, `M16A/B/C` → `M16`) |

**`R3` 는 두 값이 같아지는 유일한 값입니다.** 그래서 `R3` 만으로 시험하면 이
구분이 드러나지 않습니다. `M16` 이 들어오는 순간 `fab_name` 을 그대로 넘기면
빈 결과가 돌아오고, 화면에는 "조용한 fab" 으로 보입니다.

`fab_name → fac_id` 변환표는 코드에 없습니다. `sem_list` row 가 두 컬럼을 모두
갖고 있어 roster 에서 읽습니다. fab 이 늘어도 코드를 고칠 필요가 없습니다.

## 2. reader 활성화

```bash
cd back_dev_home/ebeam/live_alarm/providers
cp office_example.py office.py
```

`office.py` 파일이 존재한다는 사실 자체가 이 기능을 office 모드로
전환합니다. 별도의 환경 변수 설정은 필요하지 않습니다.

**이미 `office.py` 를 복사해 둔 배포라면, 다중 FAB 병합(2026-08-07)이
`office_example.py` 를 바꿨으므로 재복사가 필요합니다** — 5절 참고. 부팅
로그의 `STALE office.py: live_alarm` 표시나
`python -m scripts.sync_office_adapters live_alarm` 로 확인·갱신합니다.

## 3. 동작 확인

```bash
curl 'http://localhost:5000/api/health/providers' | grep live_alarm
curl 'http://localhost:5000/api/cdsem/live-alarm?fab_name=M16A'
redis-cli --scan --pattern 'skewnono:live_alarm:*'
```

응답의 `feed_status` 값을 확인합니다.

| 값 | 의미 | 조치 |
| --- | --- | --- |
| `live` | 마지막 성공 조회가 90초 이내입니다 | 없음 |
| `stale` | 마지막 성공 조회가 오래됐습니다 | Flask 로그에서 `live_alarm refresh failed` 를 확인합니다 |
| `not_configured` | sem_list 에 이 fab 의 해당 tool 이 없습니다 | roster 를 확인합니다 |

`unmatched_count` 가 0 이 아니면, 알람은 왔는데 그 `EQP_ID` 가 sem_list 에
없다는 뜻입니다. 방화벽 미개방 장비일 가능성이 높습니다. 이 값은 화면에도
한 줄로 표시되므로, roster 구멍이 조용히 묻히지 않습니다.

## 4. 부하 확인

사내 alarm API 호출은 **fac_id 당 20초에 한 번**이 상한입니다. 보는 사람이
몇 명이든, 얼마나 자주 새로고침하든 이 상한은 변하지 않습니다. 아무도
페이지를 열지 않으면 호출은 0 입니다.

호출이 이보다 잦다면 `CACHE_TTL_SEC` 이 아니라 락을 의심합니다. Redis 가 여러
대로 분리돼 있으면 `SET NX` 가 인스턴스마다 따로 걸려 상한이 인스턴스 수만큼
늘어납니다.

**다중 FAB 을 선택해도 이 fac_id 당 상한 자체는 바뀌지 않습니다.** 늘어나는
것은 선택한 서로 다른 fac 의 **개수(K)** 뿐입니다 — 자세한 내용은 5절.

## 5. 다중 FAB 병합 (multi-fab phase B, 2026-08-07)

`get_board(tool_type, fab_names)` — 인자가 단일 `fab_name` 에서 리스트로
바뀌었습니다. 이 절이 설명하는 병합 로직은 `office_example.py` 안에 있으므로,
2절의 재복사 안내를 따르십시오.

### fac 중복 제거

선택한 FAB 목록은 먼저 `fac_id_for(fab, tool_type)` 로 fac_id 로 바뀌고,
그 결과에서 **중복이 제거된** fac 집합만 실제로 조회합니다(`dict.fromkeys`).
`M16A`/`M16B`/`M16C` 는 fac_id 를 공유하므로 셋을 동시에 선택해도 조회는
1회입니다. 4절의 fac_id 당 20초 상한은 그대로이고, 곱해지는 것은 선택한
서로 다른 fac 의 개수(K) 뿐입니다 — `R3`+`M16B` 를 함께 선택하면 fac 이
둘(`R3`, `M16`)이므로 호출도 2배, `M16A`+`M16B`+`M16C` 만 선택하면 fac 이
하나이므로 1배(중복 제거 전과 같음)입니다.

### `AlarmEvent.fab_name` — reader 가 그때그때 붙이는 값

`fab_name` 은 office feed 에도, Redis ZSET 에 저장되는 이벤트 member 에도
**없습니다**. `office_utils.get_ebeam_metrology_alarms` 가 돌려주는 컬럼도,
ZSET 에 쓰는 직렬화도 이 필드를 모릅니다 — 1절의 계약은 그대로입니다.
board 를 조립할 때마다 roster 의 `placement_of(eqp_id)` 로 다시 계산해
붙이므로, 이미 저장된 이벤트라도 fab 소속은 항상 조회 시점의 roster 를
따릅니다. `eqp_id` 가 어느 fab 에도 속하지 않으면(roster 에 아직 없는
장비) `unmatched_count` 에 더해지고 이벤트는 버려집니다.

### `merged_meta` — worst-of

여러 fac 를 병합할 때 `board.merged_meta()` 가 `feed_status` 판단에 쓸
메타를 하나로 합칩니다. 규칙은 worst-of 입니다 — 선택된 fac 중 **하나라도**
한 번도 조회에 성공한 적이 없으면(그 fac 의 메타에 `fetched_at` 이 없으면)
전체를 `None` 으로 돌려 `feed_status` 를 `stale` 로 만들고, 전부 성공
이력이 있으면 그중 **가장 오래된** `fetched_at` 을 보고합니다. 신선한 fac
뒤에 오래된 fac 이 숨어 화면이 "다 최신"으로 보이는 일을 막기 위함입니다.

### `not_configured_fabs` — 부분 미구성

선택한 FAB 중 이 tool_type 의 장비를 가진 fac 이 하나도 없는 FAB 은
`not_configured_fabs` 에 담기고, 나머지 구성된 FAB 만으로 보드가 정상
렌더링됩니다. 선택한 FAB **전부**가 미구성일 때만 `feed_status` 가
`not_configured` 가 됩니다 — 하나라도 구성돼 있으면 보드는 그 FAB 의
데이터로 정상 표시되고, 미구성 FAB 은 화면 하단 한 줄에 이름만 남습니다.

## 주의

- 캐시 키는 `fac_id` 단위입니다. `M16A`/`M16B`/`M16C` 가 하나의 항목을
  공유하고, `R3`/`R4` 도 하나를 공유합니다.
- 조회에 실패하면 `fetched_at` 을 갱신하지 않습니다. 데이터가 오지 않았는데
  최신인 것처럼 보이는 상태를 만들지 않기 위한 것이므로, 편의를 위해서라도
  실패 경로에서 타임스탬프를 찍지 않습니다.
- 조회에 실패하면 락을 풀지 않고 TTL 로 만료시킵니다. 이것이 재시도 backoff
  입니다. 실패 직후 모든 요청이 다시 사내 API 를 때리는 일을 막습니다.
- fab 귀속은 `EQP_ID` 를 파싱해서 정하지 않습니다. 반드시 `sem_list` roster
  에서 찾습니다 — `_tool_specs.py` 에 이 구분을 어겼을 때 장비 8대가 화면에서
  조용히 사라진 사례가 적혀 있습니다.
