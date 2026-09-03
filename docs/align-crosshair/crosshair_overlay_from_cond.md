# cond.txt crosshair 를 OM/SEM align 이미지 위에 그리기

align 이미지 옆에 딸린 `cond.txt` 에서 crosshair(측정/align point) 좌표를 뽑아
같은 이미지 위에 십자선으로 겹쳐 그리는 절차. 좌표계 변환이 전부이고 나머지는
`cv2.line` 두 줄이다.

## 1. cond.txt 는 어디 있나

이미지 파일마다 **같은 폴더 안에 점(`.`) 접두 숨김 폴더**가 하나씩 있고 그 안에
`cond.txt` 가 들어 있다. 파일명은 확장자까지 그대로 쓴다.

```text
<image>.jpeg   →   .<image>.jpeg/cond.txt
```

align_images 트리 기준 실제 위치:

```text
align_images/<eqp_id>/<class>/<recipe>/
├─ align_img_from_rcp/            # recipe 등록 align key (Scope 있음)
│   ├─ IMAP0001.jpeg              #   OM
│   ├─ .IMAP0001.jpeg/cond.txt
│   ├─ IMAP0002.jpeg              #   SEM
│   └─ .IMAP0002.jpeg/cond.txt
└─ align_img_from_msr/            # 측정 궤적 (S=성공, E=실패). Scope 없음
    ├─ S0001.jpeg
    ├─ .S0001.jpeg/cond.txt
    └─ ...
```

consensus 캐시(`<cache_root>/<class>/<recipe>/events/<event_id>/S*.jpeg`)도 같은
규약이다 — `.<파일명>/cond.txt`.

경로 계산은 손으로 하지 말고 `align/cond_file.py` 를 쓴다:

```python
from poc.workflow_3.align.cond_file import cond_path_for, load_cond

cond_path_for("…/IMAP0001.jpeg")   # → …/.IMAP0001.jpeg/cond.txt
cond = load_cond("…/IMAP0001.jpeg")  # 없으면 None
```

## 2. cond.txt 에서 무엇을 뽑나

한 줄 형식은 `key<공백/탭>값,값,...` 이다. crosshair 를 그리는 데 필요한 키는 셋:

| 키 | 뽑는 것 | 용도 |
|---|---|---|
| `Pixel` | `(width, height)` — 예 `512,512` | 좌표 스케일 기준 |
| `Scope` | `OM` / `OMDF` / `SEM` 토큰 | modality 구분 (rcp 만 존재) |
| `!Cursor_info` | 콤마 구분 숫자열 | crosshair + white box 좌표 |

`!Cursor_info` 값 배열의 **0-base 인덱스**:

| 인덱스 | 의미 |
|---|---|
| `[4], [5]` | **crosshair (cx, cy)** — 이 둘이 `-1` 이 아니면 crosshair 존재 |
| `[6], [7], [8], [9]` | white box `(left, top, right, bottom)` — `[8],[9]` 가 `-1` 이 아니면 존재 |

`-1` 은 "없음" 이다. 그리기 전에 반드시 확인할 것 — E(실패) 이미지에는 crosshair 가
아예 없는 경우가 흔하고, 그 부재 자체가 신호다.

키 이름은 실데이터에서 `!Cursor_inf` / `!Cursor_info` 로 흔들리므로 파서는
`cursor_inf` **접두 매칭**을 한다. 직접 파싱하지 말고 `parse_cond()` 를 쓸 것.

### msr 은 Scope 가 없다

`align_img_from_msr/` 의 cond 에는 `Scope` 가 없다. modality 는 키·배율로 추론한다
(`cond_file.msr_modality`):

- `Accelerating_voltage` 키 있음 → **SEM** (확정)
- `!OM_Brightness` 키 있음 → **OM** (확정)
- 둘 다 없으면 `Magnification` 보조: `< 200` → OM, `> 500` → SEM, 사이는 모호(None)

rcp 는 `Scope` 가 있으므로 `CondInfo.is_om` / `.is_sem` 을 쓴다.

## 3. 좌표 변환 — 여기가 유일한 함정

`!Cursor_info` 의 좌표는 이미지 px 가 **아니다**. `Pixel` 의 **10배 oversample
프레임**(`clean_align_image.OVERSAMPLE = 10`) 기준이다.

```text
이미지 px = cursor 좌표 / 10
```

즉 `Pixel 512,512` 이면 cursor 프레임은 5120x5120 이고, `(2097, 2561)` 은 512-px
이미지 위에서 `(209.7, 256.1)` 이다. (`workflow_2/draw_crosshair_from_numbers.py` 의
`NATIVE_SIZE = 5120` 상수가 이것과 같은 값이다 — 512 x 10.)

**로드한 이미지가 `Pixel` 과 다른 크기면** 고정 /10 은 계통 오차가 된다(리사이즈 저장 등).
그럴 때는 나누기 전에 `cond_for_image()` 로 축별 보정한 사본을 먼저 얻는다. 멱등이라
여러 번 불러도 이중 보정되지 않는다:

```python
from poc.workflow_3.align.cond_file import load_cond, cond_for_image

img  = cv2.imread(path)
cond = cond_for_image(load_cond(path), img.shape[:2])   # Pixel != 실제 크기면 경고 + 보정
```

## 4. 그리기

crosshair 는 **점 하나**다. 십자 두 선은 FOV 전체를 가로지르므로 교차점만 있으면
선 길이는 화면 전체로 암시된다(white box 처럼 숫자 4개가 필요하지 않다).

```python
import cv2
from poc.workflow_3.align.cond_file import load_cond, cond_for_image
from poc.workflow_3.align.clean_align_image import cursor_to_image

img  = cv2.imread(image_path)
h, w = img.shape[:2]
cond = cond_for_image(load_cond(image_path), (h, w))

if cond and cond.crosshair_xy:
    cx, cy = cursor_to_image(cond.crosshair_xy)      # /10
    cxi, cyi = round(cx), round(cy)
    t = max(1, w // 400)
    cv2.line(img, (cxi, 0), (cxi, h - 1), (0, 255, 0), t, cv2.LINE_AA)  # 세로
    cv2.line(img, (0, cyi), (w - 1, cyi), (0, 255, 0), t, cv2.LINE_AA)  # 가로
    cv2.circle(img, (cxi, cyi), max(3, w // 80), (0, 255, 0), t, cv2.LINE_AA)

if cond and cond.box_ltrb:                            # 겸사 white box
    l, top = cursor_to_image(cond.box_ltrb[:2])
    r, b   = cursor_to_image(cond.box_ltrb[2:])
    cv2.rectangle(img, (round(l), round(top)), (round(r), round(b)), (255, 255, 0), 1)
```

프레임 중심 대비 오프셋 `(cx - w/2, cy - h/2)` 이 곧 align target 의 편차이므로,
중심 마커를 같이 찍어두면 눈으로 바로 읽힌다.

### 좌표계 확인 방법

**S(성공) msr 이미지 위에 그린다.** S 에는 도구가 이미 crosshair 를 그려 두었으므로,
우리가 그린 십자가 그 위에 정확히 겹치면 변환이 맞은 것이다. E 이미지에는 crosshair 가
없으니 검증에 못 쓴다.

## 5. OM / SEM 을 함께 볼 때

같은 recipe 의 OM(`IMAP0001`)과 SEM(`IMAP0002`)은 **배율이 다르고 FOV 가 다르므로
좌표를 서로 옮길 수 없다.** 나란히(side-by-side) 배치해서 각각 자기 cond 로 그리는 것이
유일하게 맞는 조합 방식이다. 각 패널 캡션에 `Scope` / `Pixel` / `Magnification` 을
찍어두면 어느 쪽이 어느 modality 인지 헷갈리지 않는다.

성질 차이도 같이 기억할 것 — OM key 는 프레임의 10~20% 를 차지하고, SEM 은 zoom-in 되어
key 가 프레임의 80~100% 를 채운다. 그래서 SEM 패널에서는 crosshair 가 거의 중앙에
찍히고 눈으로 오프셋을 읽기 어렵다(숫자를 같이 찍는 이유).

## 6. 그리기 vs 지우기 — 반대 작업이 이미 있다

같은 좌표를 **지우는** 쪽 구현이 `align/clean_align_image.py` 다. crosshair 는 CV
matcher 의 distractor 라 매칭 전에 `cv2.inpaint(TELEA)` 로 지운다. white box 도 rcp 에
그려 넣은 주석이라 테두리만 지운다(안쪽은 실제 내용이므로 절대 채우지 않는다).

정리하면 **시각화(사람용) = 그린다 / 매칭 입력(CV용) = 지운다.** 같은 파서·같은 좌표
변환을 쓰되 목적이 반대다. 시각화 코드를 매칭 경로에 끼워 넣지 말 것.

## 참고 코드

- `poc/workflow_3/align/cond_file.py` — 파서, 경로 계산, 스케일 보정, modality 추론
- `poc/workflow_3/align/clean_align_image.py` — `OVERSAMPLE`, `cursor_to_image()`, 지우기
- `poc/workflow_2/draw_crosshair_from_numbers.py` — 숫자 2개로 단일 이미지에 그리는 최소 예제
- `poc/workflow_3/align/diagnostics/crosshair_detect.py` — 이미지에서 crosshair 를 *찾는* 쪽(cond 없이)
