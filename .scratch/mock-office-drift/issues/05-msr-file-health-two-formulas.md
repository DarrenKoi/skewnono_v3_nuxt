# msr_file 의 health 가 두 개의 무관한 공식이다

Type: question
Status: needs-triage
검증: **확인함** (원본 대조)

## 갈리는 지점

계약 필드 `health` 하나에 서로 다른 정의가 둘 있습니다.

- **mock** — `providers/mock.py`: `round(((sha % 1000) / 1000) ** 2, 3)`.
  독립 시드에서 나오며, **FDC 드리프트를 만들어 내는 입력**입니다.
- **office** — `providers/office_example.py`:
  `round(min(1.0, max(drift_sigma) / 3.5), 3)`. 드리프트의 **출력**입니다.

방향이 반대입니다 — mock 은 health → drift, office 는 drift → health.

## 이것이 의도적일 가능성

office 쪽 주석은 이 차이를 의도한 것으로 적고 있습니다. mock 은 실제 드리프트를
알 수 없으니 health 를 먼저 뽑아 거기서 드리프트를 만드는 것이 자연스럽습니다.

다만 **눈금이 맞지 않습니다**: mock 의 health 0.5 는 office 공식으로 환산하면
약 3.33σ 에 해당하고, office 는 그 드리프트에 0.95 를 줍니다. 즉 같은 숫자가
집과 사무실에서 다른 심각도를 뜻합니다.

## 곁가지 — 상수 복제

office 의 `3.5` 는 `_fdc_status` 의 bad 임계값을 **손으로 베낀 값**입니다.
임계값을 조정하면 health 가 조용히 어긋납니다. 이건 판단 없이 고칠 수 있습니다
(09번에 넣지 않고 여기 둔 이유는 05 결정과 같은 파일이라 함께 만지는 편이
낫기 때문입니다).

## 필요한 판단

- `health` 는 **무엇을 뜻하는 숫자인가?** 눈금이 두 provider 에서 같아야
  하는가, 아니면 "집에서는 그럴듯한 값이면 충분"한가?
- 같아야 한다면 mock 의 health 생성 후 그 값으로 드리프트를 만들고, **다시
  office 와 같은 공식으로 health 를 재계산**하는 형태가 맞습니다.
- 상수 `3.5` 는 어느 결정이든 `_fdc_status` 에서 import 해야 합니다.

## 참고

`drift_sigma` 자체는 이미 `FdcSpec.drift_sigma()` 로 단일화했습니다
(커밋 `2ecc5fbf`). `health` 도 같은 처방이 가능한 자리입니다.
