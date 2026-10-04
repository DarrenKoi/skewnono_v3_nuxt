# Recipe Status 사전 집계 요청 — Home → Office

- 작성일: 2026-10-04입니다.
- 수신자: 사무실에서 SKEWNONO용 데이터를 만드는 scheduler를 관리하는 Office agent입니다.
- 목적: `/recipe-status` 화면이 여는 데 약 10초가 걸립니다. 화면이 열릴 때마다 같은
  집계를 다시 계산하기 때문입니다. 원본이 한 시간에 한 번만 바뀌므로, **한 시간에 한 번
  미리 집계한 표를 Redis에 올려 두는 scheduled task**를 만들어 주시기를 요청합니다.
- 회신 기한: 날짜 기한은 없습니다. 6절의 항목을 task 등록 후 알려 주십시오.

## 1. 배경

`/recipe-status` 화면은 `meas_hist_cdsem`, `meas_hist_hvsem` 두 alias를 읽습니다. 문서 한
건이 측정 실행 한 건입니다. 화면은 원본 행을 쓰지 않고 합계와 건수만 씁니다(레시피별
TAT 순위, 일별 추이, align/meas fail 순위, 디바이스별·장비별 표).

지금은 사용자가 화면을 열 때마다 SKEWNONO가 OpenSearch에 집계를 여러 번 요청합니다.
레시피와 lot 전체를 1000개씩 끊어 걷기 때문에 왕복 횟수가 많습니다.

요청하는 것은 **화면의 최종 결과가 아니라, 그 결과를 만들 수 있는 가장 잘게 나눈
합계표**입니다. 순위·비율·평균은 SKEWNONO가 이 표에서 계산합니다. 이렇게 나누는 이유는
다음과 같습니다.

- fab 선택, 날짜 범위, 디바이스 선택이 바뀌어도 같은 표 하나로 답할 수 있습니다.
- 계산식이 SKEWNONO 한 곳에만 있으므로 두 저장소의 숫자가 어긋날 일이 없습니다.
- Office 쪽 작업은 필터 없는 group-by 한 번입니다.

## 2. 만들 Redis key

세 개입니다. key 이름은 기존 `v3_df_sem_list`의 규칙을 따랐습니다. 사무실 규칙과 다르면
바꾸시고 실제 이름을 알려 주십시오.

| Key | 값의 형태 | 내용 |
| --- | --- | --- |
| `v3_df_recipe_status_cdsem` | pandas DataFrame, `df.to_parquet()` | `meas_hist_cdsem`의 합계표 |
| `v3_df_recipe_status_hvsem` | pandas DataFrame, `df.to_parquet()` | `meas_hist_hvsem`의 합계표 |
| `v3_recipe_status_meta` | JSON 문자열 | 생성 시각과 범위(4절) |

- 직렬화는 `v3_df_sem_list`와 같은 parquet입니다(값의 첫 4바이트가 `PAR1`).
- 세 key는 **한 transaction으로** 씁니다(redis-py의 `pipeline(transaction=True)`).
  표와 meta가 서로 다른 회차의 것이면 SKEWNONO가 범위를 잘못 판단합니다.
- TTL은 **3시간**으로 걸어 주십시오. task가 멈추면 key가 사라지고, SKEWNONO는 지금처럼
  OpenSearch를 직접 읽습니다. 오래된 숫자를 계속 보여 주는 것보다 안전합니다.

## 3. 합계표의 정의

### 3.1 대상 범위

- 대상 문서: 해당 alias의 문서 중 `timestamp`가 **최근 45일** 안에 있는 것 전부입니다.
  다른 필터는 걸지 않습니다.
- "최근 45일"의 끝은 벽시계가 아니라 **두 alias를 합친 `timestamp`의 최댓값이 속한
  날짜**입니다. 시작은 그 날짜에서 44일 전의 00:00입니다.
- 45는 상수로 빼 두십시오. 표의 크기를 보고 늘리거나 줄일 수 있습니다.

### 3.2 행의 단위 (group-by key)

아래 8개 column의 조합 하나가 한 행입니다.

| Column | Type | 원본 필드 | 비고 |
| --- | --- | --- | --- |
| `date` | string | `timestamp` | `yyyy-MM-dd`. 아래 주의 참고 |
| `fab_name` | string | `fab_name` | 저장된 값 그대로 |
| `eqp_id` | string | `eqp_id` | 저장된 값 그대로. 대소문자를 바꾸지 않습니다 |
| `eqp_model_cd` | string | `eqp_model_cd` | 저장된 값 그대로 |
| `full_name` | string | `full_name` | `class_name/recipe_name` 조합 |
| `class_name` | string | `class_name` | |
| `recipe_name` | string | `recipe_name` | |
| `lot_id` | string | `lot_id` | `lot_cd`가 아닙니다 |

주의할 점은 두 가지입니다.

- **`date`는 시간대를 변환하지 않습니다.** `timestamp`는 KST 시각이 UTC 표시를 달고
  저장되어 있습니다. 저장된 값의 날짜 부분(앞 10글자)을 그대로 씁니다. KST로 다시
  변환하면 날짜가 9시간만큼 밀려 일별 추이가 조용히 틀립니다.
- **key column이 비어 있는 문서도 버리지 않습니다.** 값이 없으면 빈 문자열 `""`로 채워
  행에 포함합니다. pandas의 `groupby`는 기본값이 null 행을 버리므로, 먼저 `fillna("")`를
  하거나 `dropna=False`를 주어야 합니다.

### 3.3 값 column

| Column | Type | 정의 |
| --- | --- | --- |
| `exec_count` | int64 | 그 조합의 문서 수 |
| `meastime_sum` | int64 | `meastime`의 합(초). 필드가 없는 문서는 0으로 더합니다 |
| `meastime_count` | int64 | `meastime` 필드가 **있는** 문서 수 |
| `align_fail_count` | int64 | `align_fail == "Fail"`인 문서 수 |
| `align_na_count` | int64 | `align_fail == "NA"`인 문서 수 |
| `meas_fail_count` | int64 | `fail_ratio > 15.0`인 문서 수 |
| `fail_ratio_sum` | float64 | `fail_ratio`의 합. 필드가 없는 문서는 0으로 더합니다 |

- `exec_count`와 `meastime_count`는 다른 값입니다. `meastime`은 `msr_check`가 `"Yes"`인
  문서에만 있습니다. 실행 건수는 문서 수이고, 평균 측정 시간의 분모만 `meastime_count`
  입니다. 하나로 합치지 마십시오.
- `fail_ratio`는 0~100의 퍼센트입니다. 기준은 **15.0 초과**(`>`, 이상이 아님)입니다.
  `fail_ratio`가 없는 문서는 fail로 세지 않습니다. 15.0은 상수로 빼 두십시오.
- `align_fail`의 값은 `"Pass"`, `"Fail"`, `"NA"` 셋입니다. 대소문자를 그대로 비교합니다.
- 값 column에는 NaN이 없어야 합니다. 전부 0 이상의 숫자입니다.

### 3.4 참고 구현

의미를 고정하기 위한 스케치입니다. OpenSearch에서 읽는 부분은 사무실의 기존 방법을
쓰십시오. `df`는 3.1의 범위를 읽은 원본 행이고, 필요한 필드는 3.2의 원본 필드와
`meastime`, `align_fail`, `fail_ratio`입니다.

```python
KEYS = ["date", "fab_name", "eqp_id", "eqp_model_cd",
        "full_name", "class_name", "recipe_name", "lot_id"]
MEAS_FAIL_THRESHOLD = 15.0

df["date"] = df["timestamp"].astype(str).str[:10]   # 시간대 변환 없음
df[KEYS] = df[KEYS].fillna("").astype(str)

df["exec_count"] = 1
df["meastime_count"] = df["meastime"].notna().astype("int64")
df["meastime_sum"] = df["meastime"].fillna(0).astype("int64")
df["align_fail_count"] = (df["align_fail"] == "Fail").astype("int64")
df["align_na_count"] = (df["align_fail"] == "NA").astype("int64")
df["meas_fail_count"] = (df["fail_ratio"] > MEAS_FAIL_THRESHOLD).astype("int64")
df["fail_ratio_sum"] = df["fail_ratio"].fillna(0.0).astype("float64")

VALUES = ["exec_count", "meastime_sum", "meastime_count", "align_fail_count",
          "align_na_count", "meas_fail_count", "fail_ratio_sum"]
cube = df.groupby(KEYS, as_index=False, dropna=False)[VALUES].sum()
```

`timestamp`를 datetime으로 읽었다면 `astype(str).str[:10]` 대신
`dt.strftime("%Y-%m-%d")`를 쓰되, 그 전에 `tz_convert`를 하지 않습니다.

## 4. meta key

`v3_recipe_status_meta`의 값은 아래 JSON입니다.

```json
{
  "built_at": "2026-10-05T09:12:40",
  "window_start": "2026-08-22",
  "window_end": "2026-10-05",
  "meas_fail_threshold": 15.0,
  "docs": {"cdsem": 412345, "hvsem": 98765},
  "rows": {"cdsem": 51234, "hvsem": 12345}
}
```

| Field | 뜻 |
| --- | --- |
| `built_at` | 집계를 마친 시각. 사무실 벽시계(KST), 시간대 표시 없이 적습니다 |
| `window_start`, `window_end` | 3.1의 범위. 양 끝 날짜를 포함합니다 |
| `meas_fail_threshold` | 3.3에서 쓴 기준값 |
| `docs` | alias별로 범위 안에서 읽은 원본 문서 수 |
| `rows` | alias별 합계표의 행 수 |

SKEWNONO는 요청받은 날짜 범위가 `window_start`~`window_end` 안에 있을 때만 이 표를 쓰고,
벗어나면 지금처럼 OpenSearch를 직접 읽습니다. 예시의 숫자는 형식을 보이기 위한 것입니다.

## 5. 실행 주기와 검증

- 주기: **매시 한 번**, `meas_hist` 적재가 끝난 직후입니다. 적재가 끝나기 전에 돌면 한
  시간 내내 직전 회차의 숫자가 보입니다.
- 실패 시: 기존 key를 지우지 말고 그대로 둡니다. TTL이 정리합니다.
- 등록 전에 아래 두 가지가 맞는지 확인해 주십시오. 둘 다 alias별로 봅니다.
  - `cube["exec_count"].sum()`이 범위 안의 원본 문서 수(`docs`)와 **정확히** 같습니다.
    다르면 null key 행이 버려진 것입니다.
  - `cube["date"].min()`, `cube["date"].max()`가 `window_start`, `window_end`와 같습니다.

## 6. 회신해 주실 것

가정이 맞으면 `맞음` 한 단어면 충분합니다. 이름과 값은 한 글자씩 그대로 옮겨 주십시오.

| 번호 | 항목 | 답 형식 |
| --- | --- | --- |
| R1 | 실제 key 이름 세 개 | `맞음` 또는 실제 이름 |
| R2 | task가 도는 분(예: 매시 12분)과 `meas_hist` 적재가 끝나는 분 | 숫자 두 개 |
| R3 | 한 회차의 실행 시간 | 초 |
| R4 | alias별 `docs`, `rows`, parquet 값의 바이트 수 | 숫자 |
| R5 | key column별로 `""`가 된 문서 수 | column 이름과 건수. 없으면 `없음` |
| R6 | 5절의 검증 두 가지 결과 | `일치` 또는 차이 |
| R7 | `meastime`이 없는 문서 수, `fail_ratio`가 없는 문서 수 | 숫자 두 개 |

R4의 크기가 수십 MB를 넘으면 `lot_id`를 뺀 표와 넣은 표로 나누는 방안을 Home이 다시
제안합니다. 지금은 나누지 말고 한 표로 만들어 크기만 알려 주십시오.

## 7. 추가 요청 (선택)

우선순위는 위 합계표보다 낮습니다. 여유가 있을 때 같은 task에 넣어 주십시오.

SKEWNONO는 `lot_id`를 `lot_cd`로 바꾸기 위해 `ebeam_tas_lot_hist`의 최근 60일
(`event_tm` 기준)을 15분마다, uWSGI worker마다 따로 읽습니다. 이 표도 Redis에 있으면 그
읽기가 사라집니다.

| Key | 값의 형태 | 내용 |
| --- | --- | --- |
| `v3_df_lot_bridge` | pandas DataFrame, `df.to_parquet()` | column `lot_id`, `lot_cd` 두 개 |

- 대상: `ebeam_tas_lot_hist`에서 `event_tm`이 최근 60일 안인 문서입니다.
- `lot_id`와 `lot_cd`가 둘 다 비어 있지 않은 쌍만 남기고 중복을 제거합니다.
- 한 `lot_id`에 `lot_cd`가 둘 이상 나오는 경우가 있으면 지우지 말고 그대로 두시고,
  그런 `lot_id`가 몇 건인지 알려 주십시오.
- 주기와 TTL은 합계표와 같습니다.

## 8. 회신 방법

- 6절의 형식으로 전달해 주시면 Home이 `docs/datatables/`에 옮겨 적습니다.
- 비밀번호·토큰 등 자격 증명 값은 적지 않습니다.
