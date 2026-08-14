# 나쁨(빨강)을 하나의 토큰 계열로 모으기 — `--sk-bad` 스윕

Status: open (드리프트 수정 완료 — 티켓 04 조사만 남음)
작성일: 2026-08-15
브라우저 확인: 2026-08-15 (device-statistics + measurement-rules, 라이트·다크,
hover 실측, 콘솔 오류·경고 0건)
발단: `.scratch/lot-outlier-merge/spec.md` 의 후속 작업 1·3순위
토론 기록: `docs/opencode/2026-08-15-lot-outlier-merge-duplication-discuss.md`

## 확인된 것 (2026-08-15)

브라우저에서 computed style 로 실측한 값입니다 — 클래스 문자열이 아니라 실제
렌더링 결과입니다.

| 확인 | 라이트 | 다크 |
| --- | --- | --- |
| 표 배지 / 모달 배지 (같은 계열인가) | `soft` + `bad` 양쪽 동일 | 동일 |
| 표 배지 hover | `oklch(0.89 0.07 30)` = 토큰 | `oklch(0.38 0.08 28)` = 토큰 |
| 슬라이드오버 위반 배지 | `soft` + `bad`, 26px 유지 | 동일 |
| 슬라이드오버 flagged 카드 tint | `--sk-bad-tint` | 동일 |
| 파라미터 행 크기 (모달 13/14 · 슬라이드오버 15/16) | 유지 | 유지 |

부수 효과로 고쳐진 것: 모달의 `분석 제외` 배지가 이제 Spoqa(sans) 로 그려집니다.
`StepOutlierCard` 사본에 `font-sans` 가 빠져 있어 한글이 JetBrains Mono 로 나오고
있었습니다 — 공유 컴포넌트가 `DrillSlideover` 쪽 값을 가져오면서 함께 풀렸습니다.

`DrillSlideover` 의 `분석 제외` 배지는 화면에 나타나지 않았습니다. 토론 기록이
"구성상 도달 불가능" 이라고 적은 그 가지이며, 이번 확인이 그것을 재확인했습니다.

## 배경

`lot-outlier-merge` 브랜치가 device-statistics 의 초과 표시를 `--sk-bad` 계열로
옮겼습니다 (커밋 `1d58ef86`). 그런데 그 표시의 **형제 사본**은 옮겨지지 않아,
지금 `main` 에는 같은 뜻의 빨강이 두 종류로 렌더링됩니다.

| 화면 | 컴포넌트 | 초과/위반 색 |
| --- | --- | --- |
| device-statistics Lot 요약 모달 | `StepOutlierCard.vue` | `--sk-bad` / `-soft` / `-border` |
| measurement-rules cap 위반 슬라이드오버 | `DrillSlideover.vue` | `bg-rose-100 text-rose-700 dark:bg-rose-950/50 …` |
| device-statistics Lot 표의 배지 | `LotTable.vue:200,346` | `bg-rose-100 … hover:bg-rose-200 …` |

두 번째·세 번째 행이 원래 있던 것이고 첫 번째 행만 새로 토큰화됐습니다. 즉 이번
드리프트는 "언젠가 벌어질 위험" 이 아니라 **한 브랜치 안에서 커밋 두 개 사이에
이미 벌어진 사실**입니다.

`DESIGN.md` 는 이 상황을 미리 금지해 두었습니다 — 색은 `--sk-*` 토큰에서만 오고
(`CLAUDE.md`), `Bad` 는 `--sk-bad` 계열이며 raw `rose-*` 는 **메시지 줄의 에러
텍스트 하나**에만 허용됩니다 (`DESIGN.md:58,62`).

## 진짜 원인은 색이 아니라 사본입니다

`StepOutlierCard.vue` 는 `DrillSlideover.vue` 에서 세 덩어리를 복사해 왔습니다.

1. **면제 배지** — `EXEMPT_BADGE`/`EXEMPT_TITLE` 상수 두 개가 두 `<script setup>`
   에 글자 하나 다르지 않게 각각 있습니다 (`StepOutlierCard:125-129`,
   `DrillSlideover:109-111`). `EXEMPT_TITLE` 은 면제 규칙을 설명하는 두 줄짜리
   도메인 문장이라, 규칙이 바뀌면 두 곳을 고쳐야 합니다.
2. **초과 배지 클래스** — 이미 갈라졌습니다 (위 표).
3. **파라미터 행 블록 약 18줄** — `v-for` · `px-4 py-1.5` · `flex max-w-2xl gap-3`
   · `w-16`/`w-28` 폭까지 같고, `<table>` 을 쓰지 않은 이유를 적은 **주석까지**
   복사돼 있습니다 (`StepOutlierCard:86-104`, `DrillSlideover:66-86`). 이쪽도
   flagged 행 tint 와 글자 클래스가 갈라졌습니다 (`--sk-bad-soft` ↔
   `rose-100/50`, `.sk-field-name` ↔ 인라인 `font-mono text-[15px]`).

색만 고치면 다음 변경에서 같은 일이 다시 벌어집니다. 그래서 이 스펙은 **토큰
정리와 사본 제거를 한 묶음**으로 다룹니다.

## 목표

- "나쁨" 을 뜻하는 모든 배경·글자·테두리가 `--sk-bad` 계열에서 옵니다.
- `StepOutlierCard` 와 `DrillSlideover` 가 면제 문구와 파라미터 행을 **같은
  모듈에서** 가져옵니다.
- `rose-*` 가 남는 곳은 `DESIGN.md` 가 허용한 에러 메시지 줄뿐이고, 그 사실이
  문서와 코드에서 같은 값으로 적혀 있습니다.

## 결정 사항

### D1 — hover 토큰을 먼저 정의합니다 (문서 → `main.css` 순서)

`lot-outlier-merge` 가 `LotTable` 배지를 함께 옮기지 못한 이유가 이것입니다.
그 배지는 클릭 가능해서 `hover:bg-rose-200` / `dark:hover:bg-rose-950/80` 를
쓰는데, 대응하는 `--sk-bad-*-hover` 토큰이 `main.css` 에 없습니다. 기능 브랜치
끝에서 hover 값을 즉흥으로 만드는 것은 디자인 시스템이 빨강에 대한 네 번째
의견을 얻는 방식입니다.

`DESIGN.md` 규칙 7 — "이 문서가 먼저 바뀌고, `main.css` · `app.config.ts` ·
프리뷰 HTML 이 **같은 변경에서** 따라온다" — 를 그대로 따릅니다.

### D2 — 공유는 양쪽이 import 할 때만 성립합니다

`oc-discuss` 에서 확정된 결론입니다. 소비자가 하나뿐인 상수 모듈은 공유 원천이
아니라 드리프트를 줄이지 못하는 간접층입니다. 그러므로 이 작업은 반드시
`DrillSlideover.vue` 를 **함께** 고치고, measurement-rules 화면을 브라우저 확인
목록에 넣습니다. (`lot-outlier-merge` 의 D3 가 범위 밖으로 뒀던 바로 그 부분이며,
그 브랜치가 끝났으므로 이제 제약이 아닙니다.)

### D3 — 스윕 범위는 "나쁨을 칠하는 곳" 이지 `rose-` 전부가 아닙니다

`front-dev-home/app` 에 `rose-*` 가 22개 파일에 있습니다. 전부를 한 번에 건드리면
브라우저 확인이 불가능해집니다. 세 부류로 나눕니다.

| 부류 | 처리 |
| --- | --- |
| 이번 드리프트 (device-statistics ↔ measurement-rules 초과/위반) | 이 스펙에서 고칩니다 |
| 에러 메시지 줄 (`text-rose-600 dark:text-rose-*`) | `DESIGN.md:62` 가 허용 — **값이 문서와 같은지만** 확인 |
| 그 외 화면 (recipe-*, hardware, storage, afm, activity …) | 목록만 만들고 이 스펙에서 손대지 않습니다 |

세 번째 부류를 미루는 이유는 화면마다 빨강의 **뜻이 다를 수 있기 때문**입니다 —
어떤 곳은 "나쁨" 이고 어떤 곳은 단순 강조입니다. 뜻을 확인하지 않은 채 토큰으로
바꾸는 것은 색을 통일하는 게 아니라 의미를 지우는 것입니다.

## 완료 조건

1. `DESIGN.md` 의 Semantic 절에 `--sk-bad` hover 값이 적혀 있고, `main.css` 의
   light·dark 두 블록에 같은 값이 있습니다.
2. `StepOutlierCard.vue` 와 `DrillSlideover.vue` 가 면제 문구와 파라미터 행
   마크업을 같은 모듈에서 가져옵니다. 두 파일 어디에도 `rose-` 가 남지 않습니다.
3. `LotTable.vue:200,346` 의 배지가 토큰만 쓰고, hover 가 눈에 보이게 동작합니다.
4. measurement-rules 의 cap 위반 슬라이드오버가 라이트·다크 모두에서 이전과 같이
   보입니다 (색상 계열이 rose → `--sk-bad` 로 바뀌는 것은 의도된 변화).
5. `npm test` · `npm run typecheck` · `npm run lint` 통과.
6. 남은 `rose-*` 목록이 `issues/04-rose-audit.md` 에 뜻과 함께 분류돼 있습니다.

## 검증

자동 E2E 가 없으므로 브라우저 확인은 손으로 합니다 (`verify` 스킬). 확인 항목은
`issues/05-browser-verify.md` 에 있습니다. **두 화면**을 봐야 합니다 —
device-statistics comparison 과 measurement-rules.
