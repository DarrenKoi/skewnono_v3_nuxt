# StepOutlierCard ↔ DrillSlideover 중복을 추출할 것인가 — opencode 토론 기록

- 실행일: 2026-08-15
- 스킬: oc-discuss
- 모델: opencode-go/kimi-k3 (tier=heavy)
- 대상: `work/lot-outlier-merge` (spec `.scratch/lot-outlier-merge/spec.md`)
- 라운드: 2 (수렴) · 약 124초 · 세션: `ses_ffe09b457ffeifR4XHXSeP1PlW`

## 배경

`/simplify` 의 reuse·altitude 두 에이전트가 같은 것을 지적했습니다 —
새로 만든 `StepOutlierCard.vue` 가 `DrillSlideover.vue` 로부터
`EXEMPT_BADGE`/`EXEMPT_TITLE` 한국어 문구, 초과 배지 클래스, 그리고 파라미터
행 마크업 약 25줄을 복사해 왔다는 것입니다.

Claude 의 입장은 **추출하지 않는다** 였습니다. 근거는 세 가지였습니다.

1. `exempt` 를 세팅하는 곳은 `deviceDrill.ts` 의 `toOutlierDrill` 하나뿐이고
   (`toViolationDrill` 은 세팅하지 않습니다), 이번 브랜치가
   `toOutlierDrill → DrillSlideover` 경로를 끊었으므로 `DrillSlideover` 의
   `v-if="recipe.exempt"` 배지는 남은 유일한 호출처(`ComplianceTable.vue`)에
   대해 **도달 불가능**해졌습니다. 죽은 코드와 문구를 공유하는 것은 그 가지를
   살아 있는 것처럼 보이게 만듭니다.
2. 스펙 결정 D3 이 `DrillSlideover.vue` 와 `deviceDrill.ts` 를 범위 밖으로
   두었습니다. 이를 건드리면 이 브랜치의 브라우저 확인 목록이 다루지 않는
   measurement-rules 화면이 딸려 들어옵니다.
3. 밑에 깔린 진짜 질문은 리팩터링이 아니라 도메인 질문입니다 — cap 판정이
   CDU/FULL/HALF/MTX job 을 면제해야 하는가. `deviceDrill.ts` 주석은 판정 쪽
   면제를 룰 데이터(`name_override`, `cap: null`)로 표현하며 outlier 기준선과
   **같은 스위치를 쓰지 않는다**고 못박아 두었습니다.

## 모델이 지적한 것

모델의 파일 읽기가 sandbox 에서 거부되어, 1라운드는 Claude 가 제시한 사실
위에서 논증했습니다. 이 사실 자체가 첫 번째 반론의 근거가 되었습니다.

### 반론 1 — 도달 불가능은 어댑터에 대해서만 증명되었다

> "Set in exactly one place — `toOutlierDrill` line 85" only shows no adapter
> *assigns* `exempt`. It says nothing about passthrough. If `toViolationDrill`
> spreads raw records, any `exempt` key in office cap-violation payloads still
> fires `v-if="recipe.exempt"`. Your own constraints make this unfalsifiable
> from home: office DBs are unreachable (…) Cost of being wrong: the branch
> records "dead branch," a later cleanup deletes it, and a live badge silently
> disappears from the measurement-rules page — a page with no harness, so
> regression surfaces only when a human stares at it.

### 반론 2 — 기록한 finding 이 중복의 잘못된 절반이다

> Even granting exempt is dead, only the EXEMPT strings are dead-dead
> duplication. The flagged-badge classes and the ~25-line parameter-row markup
> render for *violations* in DrillSlideover — live for ComplianceTable. So this
> branch creates new live-live duplication, and the one finding you record says
> nothing about it. In a repo whose documented failure mode is exactly "guard
> added to one copy never reaching its sibling," recording the dead-string half
> while omitting the live-markup half documents the less important risk.

### 반론 3 — 범위 규율을 과대 해석했다

> D3 forbids touching DrillSlideover/deviceDrill, but a constants module
> doesn't require touching them — StepOutlierCard could import from a new
> module with DrillSlideover untouched, staging the old file's eventual
> deletion. "Don't edit the old file" ≠ "don't create the shared source of
> truth."

## Claude 의 응답과 모델의 처리

반론 1 은 코드로 반박했습니다. `toViolationDrill` 은 전개(spread) 없이 모든
`DrillRecipe` 를 키 리터럴로 짓고, 입력인 `health` 는 서버 payload 가 아니라
프런트엔드 순수 함수 `evaluateLot` 의 산출물입니다. 즉 `exempt` 는 애초에 선을
넘어오지 않으므로 OFFICE-VERIFY 의 대상이 아닙니다.

반론 3 도 반박했습니다. `StepOutlierCard` 만 import 하는 상수 모듈은 공유
원천이 아니라 소비자가 하나뿐인 간접층입니다. 드리프트가 끝나려면 **양쪽이**
import 해야 하고, 그것이 곧 D3 가 배제한 변경입니다.

모델은 두 반론을 모두 철회했습니다.

> Objection 1 — dropped. Explicit key-literal construction closes the data
> path (…) Unreachability is by construction and home-checkable, exactly as you
> said.
>
> Objection 3 — dropped. You're right that a single-consumer module is
> indirection without drift reduction (…)

## 판정

### Agreed

- 이 브랜치에서 **추출하지 않습니다.** 하네스가 없고 확인이 사람 손이며 범위가
  device-statistics 화면에 묶여 있다는 제약이, 판정 화면을 끌어들이는 변경을
  실제로 금합니다. 서술(outlier)과 규범(cap)이 같은 스위치를 쓰면 안 된다는
  도메인 논거는 끝까지 반박되지 않았습니다.
- `DrillSlideover` 의 `exempt` 가지는 **구성상** 도달 불가능하며, 이는 집에서
  확인 가능한 사실입니다 (office 데이터와 무관).

### I was wrong

- **기록할 finding 을 반쪽만 잡고 있었습니다.** 죽은 것은 `EXEMPT_*` 문구뿐이고,
  초과 배지 클래스와 파라미터 행 마크업 약 25줄은 `ComplianceTable` 경로에서
  **살아서 렌더링됩니다**. 즉 이번 브랜치는 live-live 중복을 새로 만들었고,
  제가 적으려던 finding 은 더 작은 위험을 기록하는 것이었습니다. 이 저장소의
  문서화된 실패 양식(한쪽 사본에 넣은 가드가 형제 사본에 닿지 않음)에 정확히
  해당하므로, 후속 항목은 **live 마크업 중복을 1순위**로, 죽은 `exempt` 가지를
  2순위 관찰로 적습니다.

### Disputed

없습니다. 2라운드에서 수렴했습니다.

모델이 마지막으로 남긴 확인 질문 — "이 브랜치 뒤에도 `toOutlierDrill` 에
호출처가 남아 있는가" — 의 답은 **남아 있다**입니다. `comparison.vue` 의
`selectedLotDrill` 이 모달에 넘길 `DrillDevice` 를 이 어댑터로 만듭니다. 따라서
죽은 것은 어댑터도 `exempt` 필드도 아니고 `DrillSlideover` 의 템플릿 가지
하나뿐이며, 후속 정리도 그 범위로 한정됩니다.

## 후속

`.scratch/lot-outlier-merge/spec.md` 에 후속 작업 절을 추가하고, 위 우선순위
그대로 적었습니다. 이번 브랜치에서는 코드를 바꾸지 않습니다.
