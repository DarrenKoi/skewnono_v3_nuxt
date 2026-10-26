# parameter 이미지에 cond.txt 마크 덧그리기 — 접근 방안

- 작성일: 2026-10-26입니다.
- 범위: recipe-search 의 Recipe 열어보기에서 parameter 마다 보이는 이미지 세 slot
  (`img_add1` · `image_add3` · `img_meas1`)입니다. wafer align 이미지(OM/SEM)는
  2026-09-03 에 이미 끝났고, 이 문서는 그 방식을 parameter 이미지로 넓히는 방법을
  다룹니다.
- 상태: 집에서 할 수 있는 조사는 끝났습니다. **사무실 확인 전에는 코드를 바꾸지
  않습니다.** 질문지는 같은 폴더의 `to-office-measurement-box.md` 입니다.
- 선행 문서: `docs/align-crosshair/crosshair_overlay_from_cond.md`(좌표 규약),
  `docs/datatables/hitachi/recipe_idp.txt` 의 `!Cursor_info` 절(schema of record).

## 1. 결론

1. **배관은 이미 깔려 있습니다.** `ParamImage` 응답에는 2026-09-03 부터 `marks`
   field 가 있고, parameter 이미지 확대 창(`ImageLightbox.vue`)은 align 이미지와
   같은 `CondMarks.vue` 로 마크를 덧그립니다. 따라서 남은 일은 "새로 만들기" 가
   아니라 **측정·addressing 이미지에서 숫자가 무엇을 뜻하는지 확인하고, 그 뜻에
   맞게 그리는 방식을 고르는 일**입니다.
2. **막힌 사실은 하나입니다.** `.IMMP` / `.I2MP` / `.IMMS` 의 cond.txt 에
   `!Cursor_info` 줄이 있는지, 있다면 어느 자리에 무엇이 들어 있는지를 아무도 본 적이
   없습니다. 확인된 표본은 모두 align 이미지(`IMAP`)입니다.
3. **지금 상태에는 위험이 하나 있습니다.** 집의 mock 은 모든 parameter 이미지에
   align 식 white box 와 십자선을 넣고 있어서 집에서는 기능이 완성된 것처럼
   보입니다. 사무실에서 그 줄이 없으면 토글이 숨겨질 뿐이라 무해합니다. 그러나 줄이
   있고 `[6..9]` 가 **측정 박스**라면, 화면은 그것을 "white box 중심 → 정렬점
   offset" 으로 그립니다. 그림은 그럴듯하지만 뜻이 틀린, 가장 발견하기 어려운
   종류의 오류입니다.

## 2. align 이미지에서 이미 한 것

### 2-1. 좌표 규약 (user-confirmed 2026-09-03)

| 항목 | 내용 |
| --- | --- |
| 위치 | 이미지 옆 숨김 폴더 `.<image>/cond.txt` |
| key | `!Cursor_info` 또는 `!Cursor_inf` — `cursor_inf` 접두 매칭 |
| `[4],[5]` | 십자선 `(cx, cy)` |
| `[6..9]` | white box `(left, top, right, bottom)` |
| `-1` | 없음. 실패한 align 프레임은 흔히 십자선이 없고, 그 부재가 신호입니다 |
| 좌표계 | `Pixel × 10` oversample 프레임. 이미지 px = 값 / 10 |
| `[0..3]`, `[10..]` | 뜻 모름 — OFFICE-VERIFY. align 표본에서는 `-1` 과 `""` 로 채워져 있었습니다 |

### 2-2. 코드 구성

| 층 | 파일 | 하는 일 |
| --- | --- | --- |
| 파서 | `backend/_core/cond_cursor.py` | **유일한** 파서. 좌표를 이미지 대비 분수(0..1)로 바꿔 `CursorMarks` 로 돌려줍니다 |
| office | `recipe_search/providers/office_example.py` `_image_marks` | reader 의 row 가 아니라 cond.txt **원문 bytes** 에서 뽑습니다. reader 는 `!` key 를 보여 주지 않았습니다(2026-07-30 probe) |
| mock | `recipe_search/providers/mock.py` `_cond_values` | `format_cursor_info` 로 같은 줄을 만들어 넣습니다 |
| contract | `recipe_search/contracts.py` | `ParamImage` · `AlignPoint` · `AlignImage` 가 모두 `marks: CursorMarks \| None` 을 가집니다 |
| 화면 | `components/ebeam/recipeOpen/CondMarks.vue` | SVG 덧그림. viewBox = `Pixel`, `object-fit` 과 같은 `preserveAspectRatio` |
| 토글 | `composables/useCondCrosshair.ts` | 모든 확대 창이 공유하는 표시 여부. 새로고침 후에도 유지되고, `marks` 가 없으면 숨겨집니다 |

브라우저에는 파서가 없습니다. TS 사본이 한 번 생겼다가 지워졌으며 다시 만들지
않습니다. 장비가 숫자 배치를 바꾸면 `cond_cursor.py` 한 곳만 고칩니다.

### 2-3. 그리는 방식

| 마크 | 색 | 뜻 |
| --- | --- | --- |
| 십자선 (화면 전체를 가로지르는 두 선 + 원) | `--sk-ok` | 장비 알고리즘이 정한 점 |
| box 중심 (점) | `--sk-warn` | 엔지니어가 그린 unique-area 의 중심 = 매칭 단서 |
| 이미지 중심 (작은 십자 + 점) | `--sk-accent` | recipe 의 실제 정렬점 |
| box 중심 → 이미지 중심 (점선) | `--sk-accent` | offset. auto_recipe_creator 가 클릭 지점에 더하는 값 |

rcp 이미지는 장비가 정렬점으로 stage 를 옮긴 **뒤에** 캡처한 사진이라 이미지
중심이 곧 정렬점입니다. box 는 사람이 손으로 그린 단서라 중심에서 어긋날 수 있고,
그 어긋남이 offset 입니다.

### 2-4. 쓰는 화면

| 화면 | 컴포넌트 | 비고 |
| --- | --- | --- |
| recipe-search › Recipe 열어보기 › align | `AlignPopup.vue` | OM/SEM 각자의 cond 로 그립니다 |
| live-alarm › ALIGNMENT FAIL › 정렬 기준 이미지 | `live-alarm/AlignImagesModal.vue` | OM/SEM 나란히, `fit="cover"`. 버전은 따지지 않습니다(확정) |
| recipe-search › parameter 이미지 확대 | `recipeOpen/ImageLightbox.vue` | **이번 대상.** 이미 `marks` 를 받고 토글 라벨은 "측정점 십자선 표시" 입니다 |
| recipe 비교 › 이미지 확대 | `recipeCompare/CompareMatrix.vue` → `ImageLightbox` | 같은 확대 창을 씁니다 |

OM 과 SEM 은 배율과 FOV 가 달라 좌표를 서로 옮길 수 없습니다. 각 이미지는 자기
cond 로만 그립니다. parameter 이미지에도 같은 규칙이 적용됩니다.

## 3. parameter 이미지는 무엇이 다른가

같은 cond.txt 어휘를 쓰지만(office 확인 2026-07-30), **찍는 목적이 달라서 같은
숫자 자리가 다른 뜻일 수 있습니다.**

| slot | 파일 | 찍는 단계 | 이미지 중심의 뜻 (가설) | 기대하는 마크 (가설) |
| --- | --- | --- | --- | --- |
| `img_add1` | `IMMP0001.jpeg` | addressing 1 (저배율) | addressing 점 | unique pattern box — align 과 같은 성격 |
| `image_add3` | `I2MP0000.jpeg` | addressing 3 (고배율) | addressing 점 | 위와 같음 |
| `img_meas1` | `IMMS0000.jpeg` | measurement | 측정점(MP) | **측정 커서/박스** (edge 를 찾는 영역). multi-point 면 여러 개일 수 있음 |

모든 칸이 OFFICE-VERIFY 입니다. 그래도 가설을 세워 두는 이유는, 그리는 방식이
**slot 의 역할**에 따라 갈라져야 하기 때문입니다.

- **addressing 이미지**는 align key 와 같은 일을 합니다. 장비가 그 패턴을 찾아
  위치를 맞춥니다. 가설이 맞으면 지금의 그림(box 중심 · 이미지 중심 · offset 점선)을
  그대로 씁니다.
- **측정 이미지**의 box 는 매칭 단서가 아니라 **측정이 일어나는 자리**입니다. 이때
  box 중심 → 이미지 중심 점선은 "정렬 보정량" 이 아니라 "측정 커서가 MP 에서 얼마나
  벗어나 있는가" 를 뜻합니다. 같은 선이라도 라벨과 색이 달라야 하고, 무엇보다 box
  **테두리**가 보여야 합니다. 측정 박스는 중심점보다 범위가 정보이기 때문입니다.
- **HV-SEM** 은 측정 slot 하나가 `-U` / `-T` / `-M` / `-L` 파일 여러 장이고 파일마다
  cond 가 따로 있습니다(user-confirmed 2026-08-08). 응답은 이미 파일 단위로 `marks`
  를 싣고 `(slot, name)` 으로 식별하므로 구조 변경은 필요 없습니다.

### AMP(`PRMS…`) 와의 관계

AMP 파일에는 `Search_Area` · `Inspect_Area` · `Measurement_Point` · `Kind` 가
있습니다. 값 형식은 아직 모릅니다(mock 은 일부러 가짜처럼 보이는 hex 를 넣습니다).
이 값들은 측정 박스의 **크기**나 **개수**일 수 있지만, 이미지 프레임 안의 **위치**를
담고 있다는 근거는 없습니다. 따라서 위치는 cond.txt 에서 읽고, AMP 는 교차 확인용으로만
씁니다. 질문지는 같은 parameter 의 AMP 값도 함께 찍게 해서 둘을 나란히 보게 합니다.

## 4. 사무실 답에 따른 설계 분기

| 경우 | 사무실 관찰 | 백엔드 | 화면 |
| --- | --- | --- | --- |
| A | IMMP/IMMS 에 같은 줄, `[6..9]` 박스 1개 | 변경 없음 | `CondMarks` 에 `role` prop. measure 는 박스 테두리 + 중심, 점선 라벨 변경 |
| B | `[10..]` 에 박스가 여러 개 | `cond_cursor.py` 에 `boxes` 추가, contract `CursorMarks.boxes` | 박스를 반복해 그립니다 |
| C | 다른 `!` key 에 좌표가 있음 | `cond_cursor.py` key 매칭 추가. 출력 모양은 같음 | A 와 같음 |
| D | 줄이 없음 | 덧그릴 위치 정보가 없습니다 — **중단** | 토글은 이미 숨겨집니다. 변경 없음 |
| E | 장비가 jpeg 에 박스를 이미 그려 넣음 | A~C 중 하나와 함께 성립 | 덧그림은 위치 검증 + 중심/offset 읽기 용도가 됩니다 |

어느 경우든 지켜야 할 것은 같습니다.

- 파서는 `cond_cursor.py` 하나입니다. 브라우저는 분수만 받습니다.
- `role` 은 새 field 가 아닙니다. `IMAGE_SLOTS` 의 `role: 'address' | 'measure'` 가
  이미 있고, `ImageLightbox` 의 `data.role` 로 이미 전달되고 있습니다
  (`isMeas` 가 그것을 씁니다). `CondMarks` 에 넘기기만 하면 됩니다.
- align 화면(`AlignPopup` · `AlignImagesModal`)의 그림은 바뀌지 않아야 합니다.
  `role` 의 기본값을 지금 동작으로 둡니다.

경우 D 에서 mock 은 parameter 이미지의 `!Cursor_info` 를 **지워야** 합니다. 지금 값은
"측정 이미지에도 마크가 있다" 를 가르치고 있고, 그것이 거짓으로 판명된 뒤에도
남겨 두면 집에서만 보이는 기능이 됩니다.

## 5. 답이 온 뒤의 구현 순서

1. **회신 기록.** 원문 그대로 + 해석 + 틀렸던 가정 + 적용 내용을 같은 폴더의
   `office-replies.md` 에 남깁니다. 글자 답("3 A")은 그 질문 문장 옆에 적습니다.
2. **두 곳 갱신.** `docs/datatables/hitachi/recipe_idp.txt` 의 `!Cursor_info` 절과
   `recipe_search/providers/mock.py` 의 `_cond_values` 를 같은 변경에서 고칩니다.
   mock 은 지금 모든 이미지에 같은 값을 넣으므로, slot 역할별로 갈라야 합니다
   (`_cond_block` 호출부가 slot 을 알고 있습니다). 어휘 크기를 바꾸면 이후 난수가
   전부 바뀌는 점(`rng.choice` 길이)에 주의합니다.
3. **파서** (경우 B/C 만). `backend/_core/tests/test_cond_cursor.py` 에 사무실 표본
   그대로의 한 줄로 테스트를 먼저 추가하고 red 를 확인한 뒤 고칩니다.
4. **화면.** `CondMarks.vue` 에 `role` prop, `ImageLightbox.vue` 에서 `data.role` 전달,
   토글 라벨을 slot 역할에 맞게 바꿉니다(measure: "측정 박스 표시", address:
   "addressing 마크 표시" 등). 색은 `--sk-*` 토큰만 씁니다. `DESIGN.md` 를 먼저 읽습니다.
5. **office adapter.** param-detail 의 `_image_marks(blob.get(cond))` 가 이미 원문
   bytes 를 읽으므로 경우 A~C 에서는 바뀌지 않습니다. 확인만 합니다.
6. **검증.** 집에서는 mock 으로 브라우저 확인(`browser-verify` 스킬)과
   `.venv/bin/python -m pytest backend/_core backend/ebeam/recipe_search -q` 를 돌립니다.
   사무실에서는 align 때와 같은 방법을 씁니다 — 장비가 jpeg 에 직접 그려 넣은 마크
   위에 덧그림이 **정확히 겹치는지**를 봅니다. 겹치면 좌표 변환이 맞은 것입니다.

## 6. 하지 않을 것

- **썸네일 덧그림.** 지금은 확대 창에서만 그립니다. 썸네일 크기에서는 박스가 몇 px
  이라 읽을 수 없습니다. 요청이 있으면 `fit` prop 으로 바로 붙일 수 있습니다.
- **offset 의 nm 표기.** SEM cond 에는 `Field_Size` 와 `Pixel` 이 있으므로
  px → um 환산은 가능합니다. 다만 화면에 숫자를 하나 더 얹는 일이고 요청된 적이
  없으므로, 엔지니어가 원할 때 추가합니다.
- **TS 파서 재추가.** 2-2 절 참고.

## 7. 아직 모르는 것 (OFFICE-VERIFY)

| # | 질문 | 질문지 |
| --- | --- | --- |
| 1 | IMMP / I2MP / IMMS cond.txt 에 `!Cursor_info` 줄이 있는가 | 1, 2 |
| 2 | 있다면 `-1` 이 아닌 자리는 어디인가 (`[10..]` 포함) | 3 |
| 3 | `!Cursor_info` 외의 `!` key 가 있는가 | 4 |
| 4 | 장비가 jpeg 에 박스/십자선을 직접 그려 넣는가, 몇 개인가 | 5, 6 |
| 5 | `Pixel 1024` 이미지에서도 ×10 인가 | 7 |
| 6 | AMP `Search_Area` · `Inspect_Area` · `Measurement_Point` 의 값 형식 | 8 |
| 7 | HV-SEM `-U` 등 suffix 파일마다 줄이 따로 있는가 | 9 |
