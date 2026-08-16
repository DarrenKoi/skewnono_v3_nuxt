# TTTM CD 한계 — 요구사항 (대화에서 확정)

이 문서는 별도 스펙 없이 대화로 진행된 작업의 요구사항을 사후에 기록한 것입니다.
아래 인용은 사용자가 실제로 쓴 문장 그대로이며, 구현을 보고 역으로 지어낸 것이
아닙니다. 날짜는 모두 2026-08-16 입니다.

## R1 — 관리 한계는 median 기준 ±0.15 nm 이다

> "in the fab, we manage the tools running inside +-0.15nm from median. If a
> tool bigger than that, should go through the PM/BM."

- 장비 1대를 fleet consensus(중앙값)와 비교하는 규칙입니다.
- 벗어나면 PM/BM 대상입니다.

## R2 — 한계는 패턴 크기에 따라 커져야 한다

> "생각해보니 이 ceiling 은 어떤 wafer를 사용하냐에 따라 달라질 것 같아. 패턴이
> 크면 ceiling 한계도 같이 커질거고, pattern이 작으면 그만큼 ceiling도 작아지는게
> 맞아."

- 고정된 nm 값이 아니라 CD에 비례해야 합니다.

## R3 — 0.15 nm 은 15 nm 모니터 wafer 에서의 값이다

> "모니터 wafer는 15nm에서 +-0.15를 기준으로 함."

- 따라서 비율은 CD의 1% 입니다 (0.15 / 15 = 0.01).
- 페이지는 범용이어야 합니다: "0.15nm가 기준은 맞지만, 나의 page는 좀 더
  범용적으로 쓰이길 원함."

## R4 — recipe 별 독립, 결합에는 지수를 쓴다

> "single recipe is prefereable. But when multiple recipes are compared, each
> recipe should be indepandent. we might need some index to combine the results
> from each recipe. we can use median value from cd data from msr and use that
> to get the % of CD limit. right?"

- CD 중앙값은 **MSR 의 CD 데이터**에서 옵니다.
- recipe(및 셀)마다 독립적으로 평가하고, 결합할 때 지수를 씁니다.

## R5 — tolerance 상한 0.20 nm 은 유지한다

> "0.20 ceiling is reasonable."

- `tolerance_range.max` 를 0.30 으로 올리자는 조사 문서의 권고는 기각되었습니다.

## R6 — 지수를 실제로 사용할 것

> "use the index."

- 지수를 유틸리티로만 두지 말고 N배화 판정·정렬에 실제로 반영해야 합니다.

## R7 — 0.20 은 절대값이 아니라 모니터 wafer 기준값이다 (2026-08-16 확정)

oc-review 의 Spec 축이 R2 와 R5 의 충돌을 지적했습니다. knob 을 CD 비례로 바꾸면
CD 68 nm 셀에서 knob max 0.20 nm 가 실효 0.907 nm 가 되므로, 0.20 을 절대 상한으로
읽으면 지켜지지 않는 셈이었습니다. 두 해석을 사용자에게 제시하고 답을 받았습니다.

> "0.20 is a monitor wafer figure, let it scale"

- **확정:** 0.20 nm 자체가 15 nm 모니터 wafer 에서의 값이며, 다른 CD 에서는 같은
  비율로 커집니다. 셀별 실효 허용치를 0.20 에서 자르지 **않습니다**.
- 따라서 R5 와 R2 는 충돌하지 않습니다. R5 는 **눈금의 최대값**을 고정하고,
  R2 는 **그 눈금이 각 CD 에서 뜻하는 nm** 을 비례시킵니다. 두 문장이 같은 대상을
  가리킨다고 읽은 것이 혼선의 원인이었습니다 — 대화에서 "ceiling" 이 관리 한계와
  knob 상한 양쪽에 쓰였기 때문입니다.
- 구현은 이미 이 해석이었으므로 동작 변경은 없고, 계약·문서·mock 설명만
  갱신했습니다.

## 범위 밖 (명시적으로 유예)

- office adapter 구현. `providers/office_example.py` 는 여전히 stub 입니다.
- 여러 recipe 를 동시에 불러오는 UI. 현재 picker 는 단일 recipe 입니다.
