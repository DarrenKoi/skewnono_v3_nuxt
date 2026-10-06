# AFM 적재 명세의 남은 확인 — Home → Office

- 작성일: 2026-10-06입니다.
- 수신자: 각 AFM 장비에서 파일을 추출·정제하여 적재하는 Office agent입니다.
- 목적: 2026-10-06에 받은 Redis·MinIO 적재 명세로 웹의 읽기 코드를 작성했습니다. 명세에
  없던 부분은 **가정으로 메웠습니다**. 그 가정을 확인하려는 질문서입니다.
- 관계: 앞선 질문서를 **대신하지 않습니다**. 번호는 4차 질문서
  [`to-questionnaire-afm-4.md`](to-questionnaire-afm-4.md)의 Q29에 이어 Q30부터 붙였습니다.
  3차의 Q23(Data 행의 block), Q25(이미지 파일명의 위치 키)와 4차의 Q29 (다)는 이번 질문과
  겹치므로, 여기서 답하시면 그쪽은 따로 답하지 않으셔도 됩니다.
- 회신 기한: 날짜 기한은 없습니다. 3절의 출력만 먼저 보내 주셔도 됩니다.

받은 명세를 정리한 문서는 `docs/datatables/afm/afm_redis.txt`입니다. 잘못 옮긴 곳이 있으면
함께 알려 주십시오.

## 1. 웹이 지금 읽는 방식

질문의 배경입니다. 웹은 **읽기만** 하며 Redis와 MinIO에 쓰지 않습니다.

- **장비 목록**: `afm_d1_tools`의 field `all`을 읽습니다.
- **측정 목록**: `afm_d2_measurements`에서 장비명 field 하나를 읽어 DataFrame 전체를
  목록으로 씁니다. 파일 목록 7종은 객체 key에서 **파일명만** 잘라 화면에 넘기고, 목록이
  비었는지로 "profile 있음 / 이미지 있음"을 판단합니다.
- **측정 상세**: 그 측정의 `data_dir_list`에서 `detail_information.parquet`,
  `detail_summary.parquet`, `detail_points.parquet`를 이름으로 찾아 읽습니다.
- **Profile·이미지**: 화면에서 고른 포인트의 **위치 키**(`0001` 또는
  `0004_X000_Y-002_0002`)가 파일명에 들어 있는 객체를 `profile_dir_list`·`tiff_dir_list`에서
  찾습니다.
- 장비 하나의 DataFrame은 웹 프로세스가 **60초 동안** 들고 있습니다. 적재 직후 최대 1분은
  이전 목록이 보입니다.

## 2. 답하는 방법

질문마다 **Home의 현재 가정**을 적어 두었습니다. 가정이 맞으면 `맞음` 한 단어면
충분합니다. 다르면 실제 값을 적어 주십시오.

```text
Q30: 다름 — 한 행짜리 표, 열 이름 = Info key
Q34: (가) parquet 파일의 metadata / (나) 맞음
Q35: 미정
Q38 (나): 미실측
```

- 아직 모르는 것은 `미정`, 해당 사례를 보지 못한 것은 `미실측`으로 구분해 주십시오.
- 추정은 추정이라고 표시해 주십시오.
- **이름과 값은 한 글자씩 그대로** 옮겨 주십시오. 대소문자·공백·밑줄·괄호·단위 표기가
  그대로 웹의 키가 됩니다.

## 3. 출력 한 번으로 답할 수 있는 질문

Q30~Q33과 Q37은 실제 DataFrame의 열을 보면 바로 답이 나옵니다. 아래를 장비마다 측정 한
건씩 실행한 **출력을 그대로** 붙여 주시면, 그 질문들은 따로 답하지 않으셔도 됩니다.
`r`과 `get_object`는 쓰고 계신 Redis 연결과 MinIO 읽기 함수로 바꿔 주십시오.

```python
import io
import pandas as pd

def show(label, raw):
    df = pd.read_parquet(io.BytesIO(raw))
    print(f"--- {label}: {df.shape}")
    print(df.dtypes.to_string())
    print(df.head(3).to_string())

show("afm_d1_tools", r.hget("afm_d1_tools", "all"))

for tool in ("MAP608", "MAPC01", "5EAP1501"):
    raw = r.hget("afm_d2_measurements", tool)
    show(f"afm_d2_measurements[{tool}]", raw)
    row = pd.read_parquet(io.BytesIO(raw)).iloc[0]
    for kind in ("data", "profile", "tiff", "align", "tip", "capture", "raw"):
        print(kind, list(row[f"{kind}_dir_list"])[:3])
    for key in row["data_dir_list"]:
        show(key, get_object(key))
```

값이 사내 정보라 그대로 옮기기 어려우면 `df.head(3)` 줄은 빼고 열 이름과 dtype만 보내
주셔도 됩니다. block이 둘 이상인 측정(예: method가 `Profile_LEFT_UL` + `Profile_RIGHT_UL`)
한 건이 섞여 있으면 Q31·Q32에 특히 도움이 됩니다.

## 4. 먼저 답해 주시면 좋은 질문

가정이 틀리면 화면이 **오류 없이 비거나 틀린 값을 보여 주는** 곳입니다.

| 번호 | 한 줄 요약 | 틀리면 생기는 일 |
| --- | --- | --- |
| Q32 | points의 `Point No`·`Site ID` 열 이름 | 포인트 목록이 비어 Profile·이미지를 고를 수 없습니다 |
| Q33 | 파일명 안의 위치 키 | 포인트를 골라도 Profile·이미지가 "없음"으로 보입니다 |
| Q39 | `filename` 열이 측정마다 유일한지 | 측정 상세가 다른 측정을 엽니다 |
| Q34 | Profile 단위가 실린 곳 | 축에 단위가 빠지고, 1D profile이 히트맵으로 그려집니다 |
| Q35 | 원본 TIFF의 위치 | 원본 TIFF 다운로드 버튼이 나오지 않습니다 |

## 5. 질문

### 5.1 측정 상세 — parquet 3종

#### Q30. `detail_information.parquet`의 모양

- 질문: Info 섹션을 어떤 표로 적재하셨습니까.
- 가정: **열이 둘**(key, value)이고 Info의 한 줄이 한 행입니다. 열이 둘이 아니면 **한
  행짜리 넓은 표**(열 이름 = Info key)로 읽습니다.
- 함께 확인하고 싶은 것: 빈 값(`Carrier ID` 등)이 null인지 빈 문자열인지, 값이 모두
  문자열인지.
- 쓰임: 측정 상세의 정보 표와 LOT·시작 시각 표시에 씁니다.
- 답 형식: `맞음` 또는 열 이름과 dtype(3절의 출력으로 대신할 수 있습니다).

#### Q31. `detail_summary.parquet`의 모양

- 질문: Summary 섹션을 어떤 표로 적재하셨습니까.
- 가정: 한 행이 "block 하나의 통계 하나"입니다. `Site` 열에 method 명
  (`Profile_LEFT_UL`), `ITEM` 열에 `MEAN`/`STDEV`/`MIN`/`MAX`/`RANGE`, 나머지는 단위가 붙은
  측정 컬럼(`Left_H (nm)`)입니다.
- 함께 확인하고 싶은 것: Summary가 없는 측정은 객체가 **없는지**, 0행짜리 객체가
  **있는지**.
- 쓰임: 포인트 값과 block 평균의 차이를 보여 줍니다. `Site`·`ITEM` 두 이름이 다르면 그
  비교가 통째로 사라집니다.
- 답 형식: `맞음` 또는 열 이름과 dtype.

#### Q32. `detail_points.parquet`의 모양

- 질문: Data 섹션을 어떤 표로 적재하셨습니까.
- 가정: 측정 point 하나가 한 행이고, raw CSV의 열 이름을 그대로 둡니다. 웹은 그 가운데
  **`Point No`**(정수)와 **`Site ID`**(없는 recipe는 열이 없거나 null)로 위치 키를
  만듭니다 — `0001`, Site ID가 있으면 `0004_X000_Y-002_0002`.
- 함께 확인하고 싶은 것:
  - 두 열의 **정확한 철자**(`Point No` / `Point_No` / `PointNo`, `Site ID` / `Site_ID`).
  - block이 여럿인 측정에서 행이 **어느 block의 것인지**를 담은 열이 있습니까(3차 Q23).
    없다면 block 순서대로 이어 붙어 있습니까.
  - `Method ID`(또는 `Method_ID`)의 dtype — 숫자와 문자열이 섞이는 열입니다.
  - `Valid`와 `<측정명>_Valid` 열의 dtype과 FALSE의 표기.
- 쓰임: 포인트 목록, Site 지도, 포인트별 측정값입니다.
- 답 형식: `맞음` 또는 열 이름과 dtype. block이 둘인 측정 한 건이면 가장 좋습니다.

### 5.2 Profile과 이미지

#### Q33. 파일명 안의 위치 키

- 질문: `profile_<원본이름>.parquet`와 이미지 `<파일명>.webp`의 이름에서, 그 파일이 어느
  포인트의 것인지를 어떻게 알 수 있습니까(3차 Q25).
- 가정: 이름에 **`_<위치 키>_Height`** 가 들어 있습니다. raw profile 이름이
  `..._0001_Height.txt`, `..._0004_X000_Y-002_0002_Height.txt`였던 그대로입니다.

  ```text
  profile_#260709#033958#RL1C_L1_XDEC_5MM_LINE#01#NA#NA#RL1C078.01_0001_Height.parquet
  #260709#033958#RL1C_L1_XDEC_5MM_LINE#01#NA#NA#RL1C078.01_0001_Height.webp
  ```

- 함께 확인하고 싶은 것: align·tip·capture 이미지의 이름 규칙과, 그 이미지들이 포인트마다
  있는지 측정마다 하나인지.
- 쓰임: 포인트를 고르면 그 Profile과 Result 이미지를 엽니다.
- 답 형식: 종류별(profile, tiff, align, tip, capture) **실제 객체 key 한 건씩**.

#### Q34. Profile의 단위가 실린 곳

- 질문: `XUnit`·`YUnit`·`ZUnit`·`DataSize`·`SurfaceSize`는 어디에 실려 있습니까.
  - (가) parquet **파일의 metadata**(schema metadata)입니까, MinIO **객체의 user
    metadata**(`x-amz-meta-*`)입니까.
  - (나) key의 철자가 위 다섯 그대로입니까.
- 가정: (가) 웹은 parquet 파일의 metadata를 먼저 보고, 없으면 객체의 user metadata를
  읽습니다. (나) 맞습니다(대소문자는 구분하지 않고 읽습니다).
- 함께 확인하고 싶은 것: 열 이름이 `X`·`Y`·`Z`인지, `SurfaceSize`의 값 형식 한 건.
- 쓰임: 축 단위 표시와, `DataSize`가 한 줄(`1024 x 1`)일 때 선 그래프로 그리는 판단입니다.
- 답 형식: `(가) parquet 파일의 metadata / (나) 맞음`처럼 적어 주십시오.

#### Q35. 원본 TIFF의 위치

- 질문: 사용자가 내려받을 **원본 TIFF**는 어디에 있습니까.
- 가정: 모릅니다. `raw_dir_list`는 csv/txt라고 받았으므로, 웹은 그 목록에 webp와 이름이
  같고 확장자가 `.tif`/`.tiff`인 key가 있을 때만 다운로드를 제공합니다. **지금 명세대로면
  다운로드 버튼이 나오지 않습니다.**
- 쓰임: Result 이미지의 "원본 TIFF 다운로드"와 측정 한 건의 TIFF 묶음(zip)입니다.
- 답 형식: `raw_dir_list에 포함` / `별도 — <key 규칙과 실제 key 한 건>` / `적재하지 않음` /
  `미정`. 확장자(`.tif`/`.tiff`)와 파일 하나의 대략적인 크기도 알려 주십시오.

### 5.3 측정 목록 (`afm_d2_measurements`)

#### Q36. `time`과 null

- 질문:
  - (가) `time`은 4자리(`HHMM`)입니까, 6자리(`HHMMSS`)입니까. 명세에는 `HHMM`으로, 측정키의
    예에는 `070028`로 적혀 있었습니다.
  - (나) MAP608의 `time`은 파일명의 **첫 시각**(세션 시작)입니까, **끝 시각**(측정
    시작)입니까.
  - (다) `formatted_date`·`time`·`point_count`가 null이 되는 것은 각각 어떤 경우입니까.
- 가정: (가) 미정입니다. 화면은 4~6자리를 모두 읽습니다. (나) 미정입니다. (다) `time`은
  파일명의 그 자리가 `NA`일 때, `formatted_date`는 날짜를 읽지 못했을 때, `point_count`는
  data CSV가 없을 때라고 보았습니다.
- 쓰임: 목록의 측정 시각 표시와 정렬(날짜·시각 내림차순), 기간 필터입니다. 날짜가 null인
  행은 "오늘 / 3일 / 7일"에서 빠지고 "전체"에만 보입니다.
- 답 형식: (가) `4자리` / `6자리`, (나) `첫 시각` / `끝 시각`, (다) 경우별 한 줄.

#### Q37. 명세에 없던 열

- 질문: "주요 열" 외에 어떤 열이 더 있습니까. 특히 아래 둘이 있습니까.
  - 측정 구분(`measured_info` — 측정키의 여섯 번째 필드에 해당하는 값)
  - 장비 id(`tool_id` — `afm_d1_tools`의 `id`와 같은 값)
- 가정: 둘 다 없습니다. 웹은 측정 구분을 비워 두고, 장비 id는 장비명을 소문자로 바꿔
  씁니다.
- 함께 확인하고 싶은 것: `slot_number`의 dtype과 값의 꼴(`01`인지 `5NNN0336.01`인지 —
  4차 Q29), `date`·`time`이 문자열인지(정수면 앞의 0이 사라집니다).
- 답 형식: 전체 열 이름과 dtype(3절의 출력으로 대신할 수 있습니다).

#### Q38. 파일 목록의 경계 사례

- (가) 질문: Info만 있고 data CSV가 없는 측정(MAPC01의 일부 recipe)은 `data_dir_list`가
  **비어 있습니까**, `detail_information.parquet` **하나만** 들어 있습니까.
  - 가정: 미정입니다. 웹은 목록이 비어 있지 않으면 "측정 데이터 있음"으로 표시하므로,
    하나만 들어 있는 경우에는 표시가 틀립니다.
- (나) 질문: Redis의 목록에는 있는데 MinIO에 객체가 없는 경우가 생길 수 있습니까(적재
  도중, 삭제 도중).
  - 가정: 생길 수 있다고 보고, 그때는 오류가 아니라 "없음"으로 보여 줍니다.
- 답 형식: (가) `비어 있음` / `information 하나` / 그 밖, (나) `있음` / `없음` / `미실측`.

#### Q39. `filename` 열

- 질문:
  - (가) `filename`은 어느 파일의 이름입니까 — 앵커 CSV의 **원래 파일명 전체**
    (`#260709#...#RL1C078.01_Info.csv`)입니까. MAPC01은 `_Info.csv`입니까, data CSV입니까.
  - (나) 한 장비 안에서 `filename`이 **측정마다 유일**합니까. `unique_key`는 유일합니까.
- 가정: (가) 앵커 CSV의 원래 파일명 전체이고, MAPC01은 `_Info.csv`입니다. (나) 둘 다
  유일합니다.
- 쓰임: 웹은 `filename`을 측정 상세의 **주소(URL)** 로 씁니다. 유일하지 않으면 주소 하나가
  두 측정을 가리켜, 먼저 찾은 쪽이 열립니다. `filename`이 유일하지 않고 `unique_key`만
  유일하다면 주소를 `unique_key`로 바꾸겠습니다.
- 답 형식: (가) 장비별 실제 값 한 건, (나) `둘 다 유일` / `unique_key만 유일` / 그 밖.

### 5.4 장비 목록과 나머지 key

#### Q40. `afm_d1_tools`

- 질문:
  - (가) `id`의 실제 값은 어떤 꼴입니까(`map608` / `MAP608` / 숫자).
  - (나) `alias`에는 무엇이 들어 있습니까. 비어 있는 장비가 있습니까.
  - (다) `fab`은 언제, 어떤 값으로 채워질 예정입니까. `afm_d2_measurements`의 `fab` 열도
    지금은 비어 있습니까.
- 가정: (가) 장비명의 소문자입니다. (나) 화면에 보일 이름이고, 비어 있으면 장비명을
  씁니다. (다) 미정입니다. 화면은 지금 MAPC01=R3, 5EAP1501=M15, MAP608=PKG(추정)로
  묶어 보여 줍니다.
- 답 형식: (가)(나)는 실제 세 행을 그대로, (다)는 `미정` 또는 계획.

#### Q41. 나머지 key 둘

- 질문: 사용하는 key가 4개라고 하셨는데 명세는 위 둘만 받았습니다. `afm_tool_recipes`
  (JSON 문자열)와 나머지 하나는 무엇을 담고, 웹이 읽어야 하는 것입니까.
- 가정: 웹의 현재 화면은 둘 다 읽지 않습니다.
- 쓰임: `afm_tool_recipes`가 장비별 recipe 목록이라면 측정 검색의 Recipe 필터를 목록
  전체를 읽지 않고 채울 수 있습니다.
- 답 형식: key마다 이름, hash field, 값의 모양 한 건, 갱신 주기.

### 5.5 운영

#### Q42. 갱신과 보존

- 질문:
  - (가) 장비 하나의 field는 얼마나 자주 다시 쓰입니까.
  - (나) 장비 하나의 DataFrame은 지금 몇 행, 몇 MB쯤입니까.
  - (다) 오래된 측정을 지우는 계획(3개월 안이 검토 중이었습니다)이 정해졌습니까. 지울 때
    Redis 행과 MinIO 객체 가운데 어느 쪽을 먼저 지웁니까.
- 가정: (가)(나) 미정입니다. 웹은 60초 동안 이전 값을 보여 줄 수 있고, 한 번 읽을 때 그
  장비의 전체 목록을 받습니다. (다) 미정입니다.
- 쓰임: (나)가 크면 측정 상세를 열 때마다 전체 목록을 읽는 방식을 바꿔야 합니다(4차 Q29
  (다)). (다)는 삭제된 측정의 주소를 열었을 때 "보존 기간 경과"로 안내하는 데 씁니다.
- 답 형식: (가) 주기, (나) 장비별 행 수와 크기, (다) `미정` 또는 계획.

## 6. 회신 방법

- 회신은 [`office-data-findings.md`](office-data-findings.md)에 이어 붙입니다. 이 저장소에
  쓸 수 없으면 2절의 형식과 3절의 출력을 전달해 주시면 Home이 옮겨 적습니다.
- 비밀번호·토큰 등 자격 증명 값은 적지 않습니다.
