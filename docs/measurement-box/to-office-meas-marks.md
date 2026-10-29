# 측정 박스 연결 확인 — Home → Office (2026-10-29)

- 작성일: 2026-10-29입니다.
- 수신자: office_utils 의 `meas_marks` · `recipe_marks` 를 작성한 Office agent입니다.
- 목적: 집에서 `meas_marks` 를 recipe-search 의 param-detail 응답에 연결했습니다.
  아직 실제 데이터로 실행해 보지는 않았습니다. 집이 함수 인자와 반환값을 **가정한
  자리**가 7곳 있습니다. 실행 전에 그 가정이 맞는지 확인하려는 요청입니다.
- 답하는 방법: 대부분의 질문은 글자 하나로 답합니다. **A 는 "집의 가정이 맞음"**,
  **B 는 "다름"**(이때는 한 줄로 실제 값이나 형식을 적어 주십시오), **`?` 는
  "모름"** 입니다. 마지막에 빈 답안지가 있습니다.

## 1. 집이 구현한 방식

`fetch_recipe_marks` 대신 **직접 체인**을 썼습니다. param-detail 은 이미 한 번의
FTP 방문으로 PRMS(AMP) · ENMP · 이미지별 cond.txt 바이트를 모두 받아 둡니다. 그래서
같은 방문에 VIMMS blob 하나만 더 받고, 이미지 **파일마다** 아래 순서로 호출합니다.

```python
condition = read_meas_image_condition(cond_bytes)
pixel = condition.get("Pixel")                          # 리더가 준 값 그대로
field_um = float(str(condition.get("Field_Size")).split()[0])  # '4.499 um, 4.499 um' -> 4.499

offset, origin = None, "center"
if enmp_bytes:
    offset = msr_info_offset(enmp_bytes.decode("utf-8", errors="replace"), pixel)
    origin = "msr" if offset is not None else origin
if offset is None and vimms_blob_bytes:                 # blob = 측정 이미지 stem, 예: IMMS0002
    offset = vimms_mp_offset(vimms_blob_bytes, pixel)
    origin = "vimms" if offset is not None else origin

marks = marks_from_amp(read_amp_info(amp_bytes), pixel, field_um=field_um, mp_offset=offset)
```

- 측정 이미지(`img_meas1`)에만 호출합니다. addressing 이미지에는 호출하지 않습니다.
- 위 과정 중 어디서든 예외가 나거나 `marks_from_amp` 가 None 을 돌려주면 "덧그림
  없음" 으로 처리합니다. 호스트에 `meas_marks` 가 없을 때도 같습니다.
- `list_parameters` 와 region 인자는 쓰지 않습니다. 화면의 parameter 표 한 행이
  이미 (Parameter, Region) 단위이고, 그 행의 `img_meas1` · `img_meas2` 값이 곧 그
  region 의 IMMS · PRMS 파일을 가리킨다고 보았습니다.
- 화면에서 그리는 방식은 다음과 같습니다.
  - bar 는 `x = (cx - w/2) × 폭`, `y = (cy - h/2) × 높이`, 너비 `w × 폭`, 높이
    `h × 높이` 인 사각형입니다.
  - circle 은 `(cx × 폭, cy × 높이)` 를 중심으로 반지름 `r_in × 폭` 인 원이고,
    `r_out > 0` 이면 반지름 `r_out × 폭` 인 원을 하나 더 그립니다.
  - viewBox 는 반환값의 `pixel` 입니다.

## 2. 질문

### 질문 1. 반환값의 형식

`marks_from_amp` 의 반환값을 **dict** 로 보고 `m["pixel"]`, `m["bars"]`,
`m["circles"]` 로 꺼냅니다. bars · circles 가 비어 있으면 key 가 없거나 빈 list 라고
가정했습니다.

- A: dict 이고, 위 세 key 로 꺼내면 됩니다.
- B: dataclass 등 다른 형식입니다. (형식을 한 줄로 적어 주십시오)

### 질문 2. `pixel` 인자의 형식

`read_meas_image_condition` 이 돌려준 `Pixel` 값(`'1024,1024'` 같은 문자열)을
**가공하지 않고** `marks_from_amp`, `msr_info_offset`, `vimms_mp_offset` 에 넘깁니다.

- A: 세 함수 모두 이 문자열을 그대로 받습니다.
- B: 다른 형식이 필요합니다. (예: `(1024, 1024)` 튜플, 또는 첫 숫자 하나)

### 질문 3. `msr_info_offset` 에 넘기는 ENMP 텍스트

ENMP 파일 바이트를 **utf-8 로 디코딩**하고, 깨지는 글자는 치환해서 넘깁니다.

- A: utf-8 로 디코딩하면 됩니다.
- B: 다른 인코딩이 필요하거나, 텍스트가 아니라 바이트를 받습니다. (한 줄로 적어 주십시오)

### 질문 4. 원점 함수가 실패를 알리는 방식

`msr_info_offset` 과 `vimms_mp_offset` 은 원점을 찾지 못하면 **None 을 돌려준다**고
가정했습니다. None 일 때만 다음 단계로 넘어갑니다.

- A: 못 찾으면 None 을 돌려줍니다.
- B: 예외를 던지거나 `(0, 0)` 같은 값을 돌려줍니다. (어느 쪽인지 적어 주십시오)

### 질문 5. HV-SEM 의 VIMMS blob 이름

CD-SEM 은 `IMMS0002.jpeg` 의 blob 이 `IMMS0002` 입니다. HV-SEM 은 측정 slot 하나가
`IMMS0001-U.jpeg` / `-T` / `-M` / `-L` 처럼 여러 파일입니다. 집은 확장자만 떼어
`IMMS0001-U` 를 blob 으로 요청합니다.

- A: HV-SEM 도 파일마다 `IMMS0001-U` 같은 blob 이 따로 있습니다.
- B: suffix 파일들이 blob 하나(`IMMS0001`)를 함께 씁니다.
- C: HV-SEM 에는 VIMMS blob 이 없습니다.

### 질문 6. addressing 박스 (`cond_address_box`)

집은 cond.txt 의 `!Cursor_info` 를 이미 한 곳에서 파싱하고 있어서, `cond_address_box`
를 따로 호출하지 않고 그 결과를 씁니다. 집의 파서는 **0부터 세어 [6],[7],[8],[9]**
를 박스 (left, top, right, bottom)로 읽고, 모든 값을 `Pixel × 10` 으로 나눕니다.

- A: "7-10" 은 1부터 센 자리이고 집의 [6..9] 와 같습니다. 10배 프레임도 같습니다.
- B: 0부터 센 [7..10] 입니다. (집의 파서가 한 칸 어긋나 있는 것입니다)
- C: 자리는 같지만 프레임이 다릅니다. (나누는 값을 적어 주십시오)

### 질문 7. 원 반지름과 bar 크기의 기준

이미지는 대개 정사각형(`1024,1024`)이지만, 정사각형이 아닐 때를 대비해 기준을 정해야
합니다. 집은 **원 반지름은 폭 기준**, **bar 의 `cx`·`w` 는 폭 기준, `cy`·`h` 는
높이 기준**으로 그립니다.

- A: 집의 기준과 같습니다.
- B: 모든 값이 폭 기준입니다. (`cy` 와 `h` 도 폭에 곱함)
- C: 그 밖의 기준입니다. (한 줄로 적어 주십시오)

### 질문 8. 분기를 정하는 AMP field

Ellipse · Radial · Single · Dense Line · Multi_Point 분기 값이 AMP 의 **`Kind`**
field 에 들어 있다고 가정했습니다. Formula 는 `Measurement` field 의 값이라고 알고
있습니다. 이 가정은 집의 mock 에만 쓰이고, 실제 계산은 `meas_marks` 가 합니다.

- A: 다섯 분기 값 모두 `Kind` 에 들어 있습니다.
- B: 일부는 다른 field 에 들어 있습니다. (예: `Ellipse` 는 `Object`)

### 질문 9. region 과 파일

화면의 parameter 표 한 행의 `img_meas1`(IMMS) · `img_meas2`(PRMS) 값이, 그 행
region 의 측정 이미지와 AMP 파일이라고 보았습니다. 즉, `fetch_recipe_marks` 가
region 으로 고르는 파일과 같다고 가정했습니다.

- A: 같습니다. region 을 따로 넘길 필요가 없습니다.
- B: `fetch_recipe_marks` 는 region 으로 다른 파일을 고릅니다. (규칙을 한 줄로 적어 주십시오)

## 3. 실행 후 눈으로 확인할 것

배포한 뒤 recipe-search 에서 recipe 를 열고, parameter 를 하나 고른 다음 Measure 1
이미지를 확대합니다.

1. 테라코타색(주황빛 빨강) 박스나 원이 장비가 jpeg 에 직접 그려 넣은 박스 위에 **정확히
   겹치는지** 봅니다. 겹치면 좌표 변환이 맞은 것입니다.
2. 확대 창 왼쪽 아래의 `원점 ENMP / VIMMS / 중앙` 표시가 무엇인지 봅니다. `중앙` 이
   자주 보이면 원점을 찾는 단계가 실패하고 있다는 뜻입니다.
3. 서버 로그에 `measurement box failed` 나 `meas_marks missing` 경고가 있는지
   봅니다.

| # | 확인 | 답 |
| --- | --- | --- |
| 10 | 덧그림이 장비 박스와 겹치는가 (A 겹침 / B 어긋남 / C 장비 박스 없음) | |
| 11 | 원점 표시 (A 대부분 ENMP / B VIMMS 가 많음 / C 중앙이 많음) | |
| 12 | 서버 로그 경고 (A 없음 / B 있음 — 한 줄 첨부) | |

## 4. 답안지

```text
1:
2:
3:
4:
5:
6:
7:
8:
9:
10:
11:
12:
```
