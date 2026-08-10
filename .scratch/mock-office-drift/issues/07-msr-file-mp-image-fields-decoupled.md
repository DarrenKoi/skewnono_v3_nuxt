# msr_file 의 mp_image_name_01 / no_of_mp_image 가 mp_image_names 와 따로 논다

Type: bug
Status: needs-triage
검증: 에이전트 보고(미확인) — 착수 전 원본 대조 필요

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
