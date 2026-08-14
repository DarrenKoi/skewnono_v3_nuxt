# 02 — 면제 문구와 파라미터 행을 두 컴포넌트가 함께 쓰게 한다

Status: open
Spec: [`../spec.md`](../spec.md) · 결정: D2
Blocked by: 01

`StepOutlierCard.vue` 가 `DrillSlideover.vue` 에서 복사해 온 세 덩어리를
단일 원천으로 모읍니다.

| 덩어리 | StepOutlierCard | DrillSlideover | 상태 |
| --- | --- | --- | --- |
| `EXEMPT_BADGE` / `EXEMPT_TITLE` | `:125-129` | `:109-111` | 아직 동일 |
| 초과 배지 클래스 | `:49-52` | `:59-62` | **이미 갈라짐** |
| 파라미터 행 (~18줄) | `:89-105` | `:68-87` | **이미 갈라짐** |

세 번째 덩어리는 `<table>` 을 쓰지 않은 이유를 적은 **주석까지** 복사돼
있습니다 (`StepOutlierCard:86-88`, `DrillSlideover:66-67`).

**Files:**

- Create: 면제 문구 상수 모듈 (`front-dev-home/app/utils/` — 값 import 없는
  문자열이라 컴포넌트 밖에 두는 편이 `node --test` 로 확인 가능합니다)
- Create: 파라미터 행 컴포넌트 (`components/ebeam/devstat/` — 두 화면이
  공유하므로 어느 한 화면의 폴더가 아닌 곳이 맞지만, 이 저장소에 공용 폴더
  관례가 없으므로 **작업 시작 전에 위치를 정하고 여기에 적을 것**)
- Edit: `components/cdsem/comparison/StepOutlierCard.vue`
- Edit: `components/ebeam/devstat/DrillSlideover.vue`

**규칙 (D2):**

**양쪽이 import 해야 공유입니다.** 소비자가 하나뿐인 모듈은 드리프트를 줄이지
못하는 간접층입니다 — `oc-discuss` 에서 이미 확인된 결론이므로
(`docs/opencode/2026-08-15-lot-outlier-merge-duplication-discuss.md`),
`DrillSlideover` 를 건드리지 않고 끝내는 형태는 이 티켓의 답이 아닙니다.

**갈라진 두 곳을 합칠 때 어느 쪽으로 맞추는가:**

`StepOutlierCard` 쪽입니다. 토큰(`--sk-bad-*`)과 유틸리티 클래스
(`.sk-field-name` / `.sk-field-value`)를 쓰는 쪽이 `DESIGN.md` 를 따르고 있고,
`DrillSlideover` 의 raw `rose-*` 가 고쳐야 할 대상입니다. 단, 크기는 다릅니다 —
슬라이드오버는 뷰포트의 80% 라 `sk-badge-lg` 를 쓰고 카드는 아닙니다. **크기는
props 로 남기고 색만 통일합니다.**

**완료 조건:**

- 두 파일 어디에도 `rose-` 가 없습니다.
- `EXEMPT_TITLE` 문자열이 저장소에 한 번만 등장합니다
  (`grep -rn "CDU 계열" front-dev-home/app` 결과 1건).
- `npm test` · `npm run typecheck` · `npm run lint` 통과.
- measurement-rules 슬라이드오버 확인은 티켓 05.
