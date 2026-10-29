# 측정 박스 — 사무실 회신 기록

사무실 회신을 원문 그대로 남기고, 집이 어떻게 해석했는지, 어떤 가정이 틀렸는지,
무엇을 고쳤는지를 함께 적습니다. 사무실 데이터는 집에서 볼 수 없으므로, 이 기록이
무엇을 묻고 무엇을 들었는지 알려 주는 유일한 근거입니다.

| 회신 | 날짜 | 답한 질문지 |
| --- | --- | --- |
| 1차 | 2026-10-29 | `to-office-meas-marks.md` |

`to-office-measurement-box.md`(2026-10-26)에는 따로 회신이 오지 않았습니다. 그 대신
사무실이 `office_utils` 에 `meas_marks` · `recipe_marks` 를 만들어 보냈고, 측정
박스는 cond.txt 가 아니라 AMP 로 계산하는 것으로 정해졌습니다.

## 1차 회신 (2026-10-29)

### 원문

```text
1: A - 단, pixel은 '1024,1024' 문자열이 아니라 [1024, 1024] 리스트 (ViewBox 00 pw ph)
2: A - 세 함수 모두 cond의 pixel 문자열 그대로 받음
3: A - utf-8
4: A - 못 찾으면 None, 예외 없음
5: ? - 테스트 중. 결과 확인 후 알려주겠음.
6: C (자리 같음. 나누는 값은 Pixelx10 이 아니라 5120 고정)
7: A
8: B (Single, Radia=Kind, Dense Line, Space=Object, Ellipse, Formula=Measurement; Formula는 None)
9: A
10:
11:
12:
10-12 실배포 검증 필요.
```

### 질문별 해석

| # | 질문 | 답 | 해석 |
| --- | --- | --- | --- |
| 1 | `marks_from_amp` 의 반환값이 dict 이고 `pixel` · `bars` · `circles` 로 꺼내는가 | A | 맞습니다. 단, 반환값의 `pixel` 은 list `[1024, 1024]` 이고 그대로 viewBox `0 0 pw ph` 가 됩니다 |
| 2 | 세 함수에 cond `Pixel` 문자열을 그대로 넘기는가 | A | 맞습니다. 입력은 문자열 `'1024,1024'`, 출력은 list 입니다 |
| 3 | ENMP 텍스트를 utf-8 로 디코딩하는가 | A | 맞습니다 |
| 4 | 원점 함수는 못 찾으면 None 을 돌려주는가 | A | 맞습니다. 예외는 던지지 않습니다 |
| 5 | HV-SEM 의 VIMMS blob 이 suffix 파일마다 따로 있는가 | ? | 사무실에서 확인 중입니다. 집은 `IMMS0001-U` 를 요청하는 지금 방식을 유지합니다 |
| 6 | addressing 박스 "7-10" 이 집의 [6..9] 와 같고 프레임도 ×10 인가 | C | 자리는 같습니다. **나누는 값은 `Pixel × 10` 이 아니라 5120 고정**입니다 |
| 7 | 반지름은 폭 기준, bar 의 `cy` · `h` 는 높이 기준인가 | A | 맞습니다 |
| 8 | 분기 값이 모두 AMP `Kind` 에 있는가 | B | 세 field 에 나뉘어 있습니다. Kind: Single, Radial. Object: Dense Line, Space. Measurement: Ellipse, Formula. Formula 는 None 입니다 (원문의 `Radia` 는 Radial 로 읽었습니다) |
| 9 | 표의 한 행의 `img_meas1` · `img_meas2` 가 그 region 의 파일인가 | A | 맞습니다. region 을 따로 넘기지 않아도 됩니다 |
| 10–12 | 배포 후 눈 확인 | 빈칸 | 실제 배포 후 검증할 예정입니다 |

### 틀렸던 가정

- **`!Cursor_info` 의 프레임.** 2026-09-03 부터 집의 파서는 좌표를 `Pixel × 10` 으로
  나눴습니다. 실제로는 Pixel 과 무관하게 5120 으로 나눕니다. 지금까지의 표본이 모두
  512-px align 이미지여서 두 값이 같았고, 그래서 드러나지 않았습니다. 1024-px
  이미지에서는 십자선과 박스가 **절반 크기로, 왼쪽 위로 쏠려** 그려졌을 것입니다.
  이 파서는 align · live-alarm · parameter 이미지가 함께 쓰므로 세 화면 모두에
  해당합니다. auto_recipe_creator 의 `NATIVE_SIZE = 5120` 상수가 처음부터 이 값이었습니다.
- **분기 field.** mock 은 모든 분기 값을 `Kind` 에 넣고 있었습니다.

### 적용한 것

- `backend/_core/cond_cursor.py` 가 5120 고정 프레임으로 나누도록 고쳤습니다.
  1024-px 테스트를 먼저 추가해 red 를 확인한 뒤 고쳤습니다.
- recipe_search mock 이 cond 의 `!Cursor_info` 를 5120 프레임으로 만들도록 고쳤습니다.
  msr_image mock 은 512-px 만 만들므로 바꾸지 않았습니다.
- recipe_search mock 의 AMP 블록이 분기 값을 해당 field(Kind / Object / Measurement)에
  넣도록 고쳤습니다. Single 은 mock 의 Object 가 항상 Space 이므로 two-box 로 그립니다.
- `docs/datatables/hitachi/recipe_idp.txt` 의 `!Cursor_info` 절과 "측정 박스" 절,
  `approach.md`, `docs/align-crosshair/crosshair_overlay_from_cond.md` 를 갱신했습니다.
- office adapter 는 바꿀 것이 없었습니다. 1–4 번 답이 지금 코드의 가정과 같습니다.

### 남은 것 (OFFICE-VERIFY)

- 5번: HV-SEM suffix 파일의 VIMMS blob 이름.
- 정사각형이 아닌 이미지에서도 두 축 모두 5120 으로 나누는지.
- 10–12번: 실제 배포 후 덧그림이 장비 박스와 겹치는지, 원점 표시, 서버 로그.
