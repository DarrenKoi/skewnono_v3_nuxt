# msr_file 의 mp_image_name_01 / no_of_mp_image 가 mp_image_names 와 따로 논다

Type: bug
Status: done
검증: **확인함** (원본 대조 완료 2026-08-10)

## 결정 (2026-08-10) — 목록에서 파생합니다

빈 `mp_image_name 01` 은 **관측된 적이 없으나 예외 상황으로 가능**하다고 봅니다
(OFFICE-VERIFY — `user-confirmed` 가 아닙니다). 관측되지 않았다는 이유로
방치하면, 실제로 발생했을 때 화면이 이미지를 들고 있으면서 "대표 이미지 없음"
을 보여 주고 개수까지 목록 길이와 어긋납니다.

## 고친 것

세 필드를 `_mp_image_names()` 한 목록에서 파생시켜 어긋날 수 없게 했습니다:

- `mp_image_names` — 채워진 NN 컬럼 전부, NN 순
- `mp_image_name_01` — 그 목록의 첫 원소 (없으면 "")
- `no_of_mp_image` — `len(mp_image_names)`

원시 값을 조용히 버리지는 않습니다. `build_response` 가 원시 컬럼과 파생값이
달랐던 **행 수를 응답당 한 줄**로 WARNING 에 남깁니다 — 행마다 찍으면 큰 MSR
에서 로그가 잠기므로 집계합니다. 실제로 관측되면 그 로그가 OFFICE-VERIFY 를
해소할 근거가 됩니다.

## 테스트

빈 01 행, 정상 행, 로그 발생/미발생 4건. 파생을 되돌리면 실패합니다.

## 원래 서술 (참고)

## 배경

HV-SEM 은 한 측정점에 여러 이미지(`-U`/`-T`/`-M`/`-L`)를 남깁니다. 응답에는
세 가지가 함께 나갑니다 — `mp_image_name_01`(대표 1장), `no_of_mp_image`(개수),
`mp_image_names`(전체 목록).

## 갈리는 지점

- **mock** — `providers/mock.py`: 셋 다 **하나의 리스트에서 파생**합니다.
  구조적으로 어긋날 수 없습니다.
- **office** — `providers/office_example.py`: 앞의 둘은 **각자의 원시 컬럼**을
  읽고, `mp_image_names` 만 `_mp_image_names()` 가 만듭니다. 후자는 빈 값을
  버리고 NN 순으로 재정렬합니다.

## 결과

`mp_image_name 01` 이 비어 있고 `02`~`04` 만 채워진 HV-SEM 행에서 사무실은

- `mp_image_name_01 == ""` 를 3개짜리 목록 옆에 함께 내보내고,
- `no_of_mp_image` 가 `len(mp_image_names)` 와 **어긋날 수 있습니다.**

집에서는 구조적으로 불가능한 상태입니다.

## 필요한 판단

- `mp_image_name_01` 은 **원시 컬럼 그대로**인가, **목록의 첫 원소**인가?
  (빈 01 이 실물에 존재하는지가 `OFFICE-VERIFY`)
- `no_of_mp_image` 는 **원시 개수**인가 **실제 목록 길이**인가? 둘이 다를 수
  있다면 어느 쪽이 화면의 근거인가?

## 착수 시

가장 단순한 해법은 office 도 셋을 `_mp_image_names()` 결과에서 파생시키는
것입니다. 다만 그러면 원시 컬럼이 담고 있는 정보(예: "01 이 비어 있다"는 사실
자체)가 사라지므로, 그것이 진단에 필요한지 먼저 정해야 합니다.

관련 메모: HV-SEM 다중 이미지의 성질은 이미 확인된 사실입니다 — slot/row 는
이미지 고유 키가 될 수 없습니다.
