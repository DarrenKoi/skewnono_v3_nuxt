# AFM 팁 열 추가 요청 — Home → Office

- 작성일: 2026-10-06입니다.
- 수신자: Office agent입니다. AFM 측정 데이터를 Redis·MinIO에 적재하는 작업과 사무실에서
  SKEWNONO를 실행·확인하는 작업을 모두 맡고 있으므로, 1~5절은 적재 작업에 대한 요청이고
  6~7절은 적재 후 SKEWNONO에서 확인할 것입니다.
- 목적: AFM 담당 엔지니어가 팁 불량 모니터링 현황을 보고 싶다고 요청했습니다. 이를 위한
  화면(`/afm/<장비>/tips`)은 이미 만들어져 있고, **측정 목록 `afm_d2_measurements`에 열
  9개가 추가되면** 사무실에서도 동작합니다. 그 열의 추가를 요청합니다.
- 회신 기한: 날짜 기한은 없습니다. 5절의 항목을 적재 후 알려 주십시오.

## 1. 배경

팁 모니터링 화면은 한 장비의 **모든 측정**을 팁 종류(`Tip ID`)별로 묶어, 같은 종류
측정의 평균 ± 3σ를 벗어난 측정을 짚습니다. 보는 항목은 Tip Width, Approach Count,
Mileage, 완료되지 않은 포인트 수, Valid=FALSE 포인트 수입니다.

이 값들은 지금 측정마다 따로 있는 `detail_information.parquet`과
`detail_points.parquet`에만 있습니다. 화면이 열릴 때 측정 수만큼 MinIO를 읽을 수는
없으므로, 측정 한 건당 한 줄로 요약한 값이 목록에 있어야 합니다.

별도 key를 만들지 않고 기존 목록에 열을 더하는 이유는 다음과 같습니다.

- 추가하는 값이 모두 "측정 한 건당 값 하나"라서 목록의 행 단위와 같습니다.
- 한 DataFrame에 함께 쓰이므로 목록과 팁 값이 서로 다른 회차의 것이 될 수 없습니다.
- 목록을 만들 때 이미 Info를 읽고 있습니다(`slot_number`가 Info의 `Sample Location`에서
  옵니다).

## 2. 추가할 열

대상은 Redis hash `afm_d2_measurements`의 모든 field(장비별 DataFrame)입니다. 기존 열과
직렬화 방식(parquet)은 그대로 둡니다. 열 이름은 SKEWNONO가 제안한 것입니다. 다른 이름을
쓰시면 실제 이름을 알려 주십시오.

| 열 | 형 | 내용 |
| --- | --- | --- |
| `tip_id` | text | Info의 `Tip ID` 값 그대로 |
| `tip_cassette_id` | text | Info의 `Tip Cassette ID` 값 그대로 |
| `tip_port_no` | text | Info의 `Tip Port No` 값 그대로 |
| `tip_slot_no` | text | Info의 `Tip Slot No` 값 그대로 |
| `tip_width` | text 또는 float | Info의 `Tip Width` 값 |
| `approach_count_mean` | float | data 전체 행의 `Approach Count` 평균 |
| `mileage_mean` | float | data 전체 행의 `Mileage` 평균 |
| `not_completed_count` | int | `State`가 `COMPLETED`가 아닌 data 행의 수 |
| `invalid_count` | int | `State`가 `COMPLETED`이고 `Valid`가 FALSE인 data 행의 수 |

## 3. 계산 규칙

- **Info 값은 가공하지 않습니다.** 앞의 네 열은 Info에 적힌 문자열 그대로입니다. Info에 그
  key가 없거나 값이 비어 있으면 null입니다.
- **`tip_width`는 어느 형이든 받습니다.** Info의 문자열을 그대로 넣어도 되고(`NaN`이나
  단위가 붙은 값 포함), 숫자로 바꿔 넣어도 됩니다. SKEWNONO가 앞의 숫자만 읽고 `NaN`은
  "측정 없음"으로 다룹니다. 편한 쪽으로 정하시고 어느 쪽인지만 알려 주십시오.
- **뒤의 네 열은 그 측정의 data 행 전체에서 계산합니다.** 블록(`Site`)을 가리지 않고 한
  측정의 모든 행을 대상으로 합니다.
- **평균은 숫자로 읽히는 값만 씁니다.** `Approach Count`나 `Mileage`가 비어 있거나 숫자가
  아닌 행은 평균에서 뺍니다. 숫자인 행이 하나도 없으면 null입니다.
- **`Valid`는 FALSE라고 적힌 행만 셉니다.** 비어 있는 `Valid`는 세지 않습니다. 대소문자는
  가리지 않습니다(`FALSE`, `False`, `false`).
- **data 행이 없는 측정은 뒤의 네 열이 모두 null입니다.** info CSV만 있는 측정이 여기에
  해당합니다. 0이 아니라 null이어야 "포인트가 모두 정상"과 구분됩니다.
- **이미 적재된 측정도 채워 주십시오.** 과거 측정에 값이 없으면 팁 이력이 열 추가
  시점부터만 보입니다. 소급이 어렵다면 어느 날짜부터 채워지는지 알려 주십시오.

## 4. 바뀌지 않는 것

- 기존 열, 행의 순서, `unique_key`·`filename`의 값은 그대로입니다.
- MinIO의 `detail_*.parquet`은 그대로 둡니다. 상세 화면이 계속 읽습니다.
- 새 Redis key는 만들지 않습니다.

## 5. 적재 후 알려 주실 것

1. 실제 열 이름과 `tip_width`의 형(text인지 float인지)입니다.
2. 과거 측정을 소급해 채웠는지, 아니라면 채워지기 시작한 날짜입니다.
3. 측정 목록의 보존 기간입니다. 오래된 측정을 목록에서 지운다면 며칠치를 두는지
   알려 주십시오. 팁 이력을 그보다 길게 볼 수 없기 때문입니다.
4. `Tip ID` 값의 실제 예시 몇 개입니다(장비별로 종류가 몇 가지인지 포함).
5. `Tip Width`에 단위가 붙어 오는지, 붙는다면 어떤 단위인지입니다.
6. `State`에 `COMPLETED`·`FAILED`·`STOPPED` 외의 값이 있는지입니다.
7. `Mileage`의 단위와, 팁을 교체하면 값이 초기화되는지입니다.

## 6. 적재 후 SKEWNONO에서 확인할 것

열이 적재된 뒤, 사무실 PC에서 아래 순서로 확인해 주십시오.

### 6.1 열이 실제로 들어왔는지

저장소 루트에서 실행합니다. 장비 세 대(`MAP608`, `MAPC01`, `5EAP1501`) 모두 확인합니다.

```python
from backend._runtime.office_redis import read_dataframe, redis_client

COLUMNS = [
    "tip_id", "tip_cassette_id", "tip_port_no", "tip_slot_no", "tip_width",
    "approach_count_mean", "mileage_mean", "not_completed_count", "invalid_count",
]
for tool in ("MAP608", "MAPC01", "5EAP1501"):
    df = read_dataframe(redis_client().hget("afm_d2_measurements", tool), f"afm_d2_measurements[{tool}]")
    present = [c for c in COLUMNS if c in df.columns]
    print(tool, len(df), "rows · missing:", sorted(set(COLUMNS) - set(present)))
    print(df[present].dtypes.to_string())
    print(df[present].isna().sum().to_string())
    print(df["tip_id"].value_counts(dropna=False).head(10).to_string())
```

기록할 것은 장비별 행 수, 빠진 열, 각 열의 dtype, 열별 null 건수, `Tip ID` 종류입니다.

### 6.2 목록과 상세가 같은 값을 말하는지

장비마다 측정 3건 이상을 골라(data 행이 있는 것 2건, info만 있는 것 1건), 목록의 9개
값과 그 측정의 `detail_information.parquet`·`detail_points.parquet`에서 3절의 규칙으로
직접 계산한 값을 비교해 주십시오. 특히 다음을 확인합니다.

- `Tip Width`가 `NaN`인 측정에서 목록의 `tip_width`가 무엇으로 들어오는지입니다.
- 블록이 둘 이상인 측정에서 건수가 한 블록이 아니라 전체 행 기준인지입니다.
- info만 있는 측정에서 뒤의 네 열이 0이 아니라 null인지입니다.

### 6.3 adapter를 새로 복사했는지

`office.py`는 복사본이라 `git pull`만으로는 바뀌지 않습니다.

1. `main`을 `6d625a80` 이후로 받습니다.
2. Flask를 띄우고 boot log에 `STALE office.py: afm`이 나오는지 봅니다.
3. 나오면 `python -m scripts.adapters.sync_office_adapters afm`으로 다시 복사합니다.
4. 열 이름을 2절과 다르게 정했다면 복사 전에 알려 주십시오.
   `backend/afm/providers/office_example.py`의 `_row`를 home에서 먼저 고쳐야 합니다.

### 6.4 테스트와 화면

1. `SKEWNONO_AFM_PROVIDER=office .venv\Scripts\python -m pytest backend/afm -q`를 실행하고
   통과·skip·실패 건수를 알려 주십시오.
2. `GET /api/health/providers`에서 `afm`이 `office`로 나오는지 확인합니다.
3. `GET /api/afm/files?tool=MAP608` 응답의 첫 행에 9개 key가 있고 값이 null이 아닌지
   확인합니다.
4. 브라우저에서 장비 세 대의 `/afm/<장비>/tips`를 엽니다. 확인할 것은 다음과 같습니다.
   - "팁 값이 있는 측정이 없습니다"가 아니라 팁 종류별 구역이 나오는지입니다.
   - 상단의 "없는 측정 N건"이 6.1의 `tip_id` null 건수와 같은지입니다.
   - 차트 x축의 날짜가 실제 측정 날짜와 맞는지입니다. `MAP608`은 목록의 `time`이 세션
     시작 시각이라 같은 세션의 측정이 한 시각에 겹쳐 보이는 것이 정상입니다.
   - 화면이 열리는 데 걸리는 시간과 브라우저 console의 오류 유무입니다.
5. 측정 목록·상세·시계열 비교 화면이 전과 같이 동작하는지 한 번씩 열어 봅니다.

## 7. 회신에 담을 것

- 5절의 일곱 항목에 대한 답입니다.
- 6.1의 출력 전체입니다.
- 6.2에서 어긋난 측정이 있었다면 그 `unique_key`와 양쪽 값입니다.
- 6.4의 pytest 건수와 화면에서 본 것입니다.

회신을 받으면 home에서 `docs/datatables/afm/afm_redis.txt`와
`backend/afm/providers/mock.py`의 `OFFICE-VERIFY` 표기를 `office 확인 <날짜>`로 바꾸고,
mock의 값 생김새를 실제에 맞춥니다.
