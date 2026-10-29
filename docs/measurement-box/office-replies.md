# 측정 박스 — 사무실 회신 기록

사무실 회신을 원문 그대로 남기고, 집이 어떻게 해석했는지, 어떤 가정이 틀렸는지,
무엇을 고쳤는지를 함께 적습니다. 사무실 데이터는 집에서 볼 수 없으므로, 이 기록이
무엇을 묻고 무엇을 들었는지 알려 주는 유일한 근거입니다.

| 회신 | 날짜 | 답한 질문지 |
| --- | --- | --- |
| 1차 | 2026-10-29 | `to-office-meas-marks.md` |
| 2차 | 2026-10-29 | `to-office-meas-marks.md` 5번 + HV-SEM 실행 결과 |
| 3차 | 2026-10-29 | 2차의 HV-SEM 원 검증 결과 |
| 4차 | 2026-10-29 | 3차의 남은 질문 (Inner/Outer_Diameter) |
| 5차 | 2026-10-29 | 4차의 남은 질문 (`Target` 형식) |
| 6차 | 2026-10-29 | 사무실 local(Windows) 실행 확인 |

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

- 5번: HV-SEM suffix 파일의 VIMMS blob 이름. → 2차 회신에서 B 로 확정했습니다.
- 정사각형이 아닌 이미지에서도 두 축 모두 5120 으로 나누는지.
- 10–12번: 실제 배포 후 덧그림이 장비 박스와 겹치는지, 원점 표시, 서버 로그.

## 2차 회신 (2026-10-29)

### 원문

```text
HV-SEM 확인 결과 CD-SEM 체인 그대로 동작.
체인 무수정 동작 - msr_info_offset -> vimms_mp_offset -> marks_from_amp이 HV-SEm AMP/ENMP/cond 에서 그대로 돈다. blob type 87. blob-msr=(13,-6)까지 CD-SEM과 동일
레터 질문 5 = B 확정: Slot stem (IMMS0001)이 blob 하나이고 -U/-T/-M/-L 4장이 공유. cond는 파일마다 (.IMMS0001-U.jpeg/cond.txt). 4장 모두 pixel 512, 512로 marks 도 동일
HV-SEM 신유형 발견: Kind=Single + Object=Inner_Diameter/Outer_Diameter (원 지름 측정)이 CD-SEM에 없던 조합. 현재 코드는 일반 two-box 경로로 bar를 그려 17/7/3개 marks를 냈다. circle이 맞는지는 직접 검증 필요 -> 확인 중.
버그 1건 (probe 위치) : .idp는 raw 폴더가 아니라 idw 폴더 (data/<idw>/<recipe>.idp)에 있다. raw 내 경로 RETR은 서버 기분에 따라 되다가 550으로 막히는 굴러가는 독장이라 home agent는 _list_raw_dirs 체인이 raw내 .idp를 내려받는다면 같은 내용이다.
```

### 해석

| 항목 | 해석 |
| --- | --- |
| HV-SEM 체인 | 직접 체인이 HV-SEM 의 AMP · ENMP · cond 에서 고치지 않고 그대로 동작합니다. blob type 87, blob 과 msr 원점의 차이 (13, -6) 도 CD-SEM 과 같습니다 |
| 질문 5 | **B** — blob 은 slot stem `IMMS0001` 하나이고 `-U/-T/-M/-L` 네 파일이 함께 씁니다. cond 는 파일마다 있고, 표본에서는 네 장 모두 `Pixel 512,512`, marks 도 같았습니다 |
| 신유형 | `Kind=Single` + `Object=Inner_Diameter` / `Outer_Diameter`(구멍 지름 측정)는 HV-SEM 에만 있습니다. 지금 모듈은 two-box 로 bar 17 / 7 / 3 개를 냅니다. 원이 맞는지는 사무실에서 확인 중입니다 |
| `.idp` 위치 | `.idp` 는 raw 폴더가 아니라 idw 폴더(`data/<idw>/<recipe>.idp`)에 있습니다. raw 폴더 안의 경로로 RETR 하면 되다가 550 으로 막히기도 합니다. 집 코드가 raw 폴더에서 `.idp` 를 받는다면 같은 문제가 있다는 경고입니다 |

### 틀렸던 가정

- **blob 이름.** 집은 파일마다 확장자만 떼어 `IMMS0001-U` 를 blob 으로 요청했습니다.
  HV-SEM 에서는 그런 파일이 없어서, ENMP 원점을 찾지 못한 parameter 는 VIMMS 를
  건너뛰고 바로 중앙 원점으로 떨어졌을 것입니다.

### 적용한 것

- office adapter 가 blob 이름을 slot 값(`img_meas1`)의 stem 으로 정하도록
  고쳤습니다. parameter 하나에 blob 을 한 번만 요청하고 suffix 파일 네 장이 함께
  씁니다. HV-SEM 형태의 listing 으로 테스트를 먼저 추가해 red 를 확인했습니다.
- mock 이 측정 박스를 파일이 아니라 parameter 기준으로 만들도록 고쳤습니다. 이제
  suffix 파일들이 같은 박스를 받습니다.
- `Inner_Diameter` / `Outer_Diameter` 를 datatables 와 mock 주석에 기록했습니다.
  어떻게 그려야 하는지 모르므로 mock 은 아직 이 조합을 만들지 않습니다.
- `.idp` 위치는 **집 코드에 해당하지 않습니다.** office adapter 는 `.idp` 를
  `data/<idw>/<idp>.idp`(idw 폴더)에서 받고, 저장소의 probe 도 같은 경로를 씁니다.
  `_list_raw_dirs` 는 raw 폴더를 listing 만 하고, 그중 이미지 확장자 파일만 계획에
  넣으므로 raw 폴더 안의 `.idp` 를 받지 않습니다.

### 남은 것 (OFFICE-VERIFY)

- `Inner_Diameter` / `Outer_Diameter` 를 원으로 그려야 하는지. 모듈이 바뀌면 집은
  바꿀 것이 없습니다. 화면은 `circles` 를 이미 그립니다.
- 10–12번: 실제 배포 후 확인할 항목.

## 3차 회신 (2026-10-29)

### 원문

```text
원인 : marks_from_amp의 Ellipse 서클 분기가 mp_offset(msr 원점)을 무시했습니다. HV-SEM Radial 계열 (Measurement="Ellipse")은 ENMP msr_info 원점이 커서에 더해져야 홀 중심이 되는데, 그것이 빠져 서클이 msr 오프셋 만큼 어긋나 있었습니다. -> meas_marks.py 코드 수정 완료.
```

### 해석

- 2차에서 확인 중이던 HV-SEM 원 검증의 결과입니다. `marks_from_amp` 의 Ellipse
  원 분기가 `mp_offset` 을 더하지 않아, 원이 msr 원점 offset 만큼 어긋나 있었습니다.
  사무실이 `meas_marks.py` 를 고쳤습니다.
- 원의 중심은 커서 + ENMP msr_info 원점입니다. bar 분기와 같은 규칙입니다.
- HV-SEM 의 Radial 계열 측정은 `Measurement="Ellipse"` 로 들어옵니다.

### 집에 미치는 영향

- **코드 변경은 없습니다.** 원점은 집이 `mp_offset` 으로 넘기고, 더하는 일은 모듈이
  합니다. 화면은 받은 `circles` 를 그대로 그립니다.
- mock 은 처음부터 원 중심에 원점을 더해 그리고 있어서 고칠 것이 없었습니다.
- **배포:** 고친 `meas_marks.py` 가 호스트의 office_utils 에 올라가야 합니다.
  office_utils 는 SKEWNONO 번들과 따로 배포됩니다.

### 남은 것 (OFFICE-VERIFY)

- 2차의 `Kind=Single` + `Object=Inner_Diameter` / `Outer_Diameter` 가 이번 Radial
  계열(`Measurement="Ellipse"`)과 같은 parameter 인지. → 4차 회신에서 같은 것으로
  확정했습니다.
- 10–12번: 실제 배포 후 확인할 항목.

## 4차 회신 (2026-10-29)

### 원문

```text
네 같은 것입니다. 전부 실측으로 확인.
그 Bars 17/7/3은 bars 가 아니라 전부 Ellipse 분기가 그린 circles 였습니다. 갯수가 Target과 정확히 일치합니다.
Kind = Single + Object / Inner/Outer_Diameter는 HV-SEM이 Radial 계열을 표기하는 방식입니다. CD-SEM은 Kind=Radial로 오지만 HV-SEM은 Kind 에 Single을 넣고 원 측정을 Measurement=Ellipse로만 표시합니다. 그래서 marks_from_amp은 Measurement=="Ellipse" 분기(어제 제가 고른 곳)에서 정확히 잡습니다.
```

### 해석

- 3차의 남은 질문에 대한 답입니다. 2차의 `Kind=Single` + `Object=Inner_Diameter` /
  `Outer_Diameter` parameter 와 3차의 Radial 계열(`Measurement="Ellipse"`)은 **같은
  것**입니다. 실측으로 확인했습니다.
- **2차의 "bar 17 / 7 / 3 개" 는 잘못 본 것이었습니다.** 처음부터 Ellipse 분기가
  그린 원이었고, 원의 개수가 AMP `Target` 과 정확히 같습니다.
- HV-SEM 은 홀 측정을 `Kind=Single` + 지름 Object + `Measurement=Ellipse` 로
  적습니다. CD-SEM 은 `Kind=Radial` 입니다. 그래서 `marks_from_amp` 는 Kind 가
  아니라 `Measurement=="Ellipse"` 로 분기하고, 그 분기가 Kind 보다 먼저입니다.

### 틀렸던 가정

- 2차 해석은 "지금 모듈이 two-box 로 bar 를 낸다" 였습니다. 실제로는 처음부터
  원이었습니다. 어긋나 보였던 원인은 3차에서 고친 원점 누락이었습니다.
- mock 의 Ellipse parameter 는 `Kind=Multi_Point`, `Object=Space` 로 남아 있었고
  원도 하나만 그렸습니다. 실제 HV-SEM 의 조합이 아니었습니다.

### 적용한 것

- mock 의 Ellipse parameter 가 HV-SEM 조합을 그대로 갖도록 고쳤습니다:
  `Kind=Single`, `Object=Inner_Diameter` 또는 `Outer_Diameter`,
  `Measurement=Ellipse`. 원은 사무실 표본 개수(1 / 3 / 7 / 17)만큼 홀 배열로 그리고,
  `Target` 에 그 개수를 넣습니다. 원 개수와 `Target` 이 같은지 테스트로 확인합니다.
- datatables 에 HV-SEM 표기, Ellipse 우선순위, 원 개수 = `Target` 을 기록했습니다.
- office adapter 와 화면은 바꿀 것이 없었습니다.

### 남은 것 (OFFICE-VERIFY)

- `Target` 이 개수를 정수 문자열로 담는지 (mock 은 그렇게 가정합니다). → 5차
  회신에서 맞다고 확정했습니다.
- 10–12번: 실제 배포 후 확인할 항목.

## 5차 회신 (2026-10-29)

### 원문

```text
Target는 정수 문자열 맞음
```

### 해석과 적용

- AMP `Target` 은 target 개수를 담은 정수 문자열(`'7'` 등)입니다. 4차에서 mock 이
  가정한 형식과 같습니다.
- datatables 의 OFFICE-VERIFY 를 확인으로 바꿨습니다.
- mock 은 지금까지 `Target` 을 형식을 모르는 값(가짜 hex)으로 채웠습니다. 이제
  Ellipse 가 아닌 parameter 도 정수 문자열(1–3)을 냅니다. Ellipse 가 아닌 parameter
  에서 값의 범위는 지어낸 것입니다(OFFICE-VERIFY). `Target` 은 AMP field 의 마지막
  자리라서, 바꿔도 다른 field 의 난수는 달라지지 않습니다.

### 남은 것 (OFFICE-VERIFY)

- 10–12번: 실제 배포 후 확인할 항목.

## 6차 회신 (2026-10-29)

### 원문

```text
office local (windows)에서 몇개 확인하니 일단 작동 잘 됨 확인.
```

### 해석

- 사무실 local(Windows, Phase 2)에서 recipe 몇 개로 측정 박스가 잘 그려지는 것을
  확인했습니다. 집에서 보낸 코드(`office.py` 재복사)와 사무실의 `meas_marks.py` 가
  함께 실제 데이터에서 처음 동작한 기록입니다.
- 10–12번(덧그림이 장비 박스와 겹치는지, 원점 표시, 서버 로그)을 항목별로 답한
  것은 아니므로 각각 확정하지 않았습니다.

### 남은 것

- cloud(Phase 3) 배포와 그곳의 office_utils 에 `meas_marks.py` 올리기.
- 10–12번을 항목별로 확인하기. 특히 `원점 중앙` 표시가 자주 보이는지는 원점
  체인이 실제로 얼마나 실패하는지 알려 줍니다.
