# 01 — `--sk-bad` hover 값을 정의한다

Status: resolved
Spec: [`../spec.md`](../spec.md) · 결정: D1

클릭 가능한 "나쁨" 요소에 쓸 hover 값이 시스템에 없습니다. 지금 그 자리를 raw
`hover:bg-rose-200` / `dark:hover:bg-rose-950/80` 가 채우고 있습니다
(`LotTable.vue:200` — 저장소 전체에서 유일한 `hover:*rose*` 사용).

`--sk-ok` / `--sk-warn` 도 hover 값이 없지만, **이 티켓은 `--sk-bad` 만
정의합니다.** 셋을 한꺼번에 만들면 실제로 쓰이지 않는 값 두 개가 문서에 들어가고,
그 값이 처음 쓰이는 날 아무도 그것이 검증된 적 없다는 걸 모릅니다.

**Files:**

- Edit: `DESIGN.md` — `### Semantic` 절 (`:58` 근처)
- Edit: `front-dev-home/app/assets/css/main.css` — light `:root` (`:168-170`)
  와 dark 블록 (`:229-231`) **양쪽**

**정할 것:**

- 이름: `--sk-bad-soft-hover` (배경 tint 의 hover). 글자·테두리는 hover 에서
  바뀌지 않으므로 새 토큰이 필요 없습니다 — 현재 코드도 배경만 바꿉니다.
- 값: light 는 `--sk-bad-soft` (`oklch(0.94 0.04 30)`) 보다 한 단계 진하게,
  dark 는 `oklch(0.32 0.06 28)` 보다 한 단계 밝게. 기존 rose 계단
  (`rose-100 → rose-200`, `rose-950/50 → rose-950/80`) 이 실제로 쓰여 온
  체감 폭이므로 그 정도를 목표로 합니다.

**주의:**

`DESIGN.md` 규칙 7 — 문서가 먼저 바뀌고 `main.css` 가 **같은 커밋에서** 따라옵니다.
문서만 바꾸고 CSS 를 다음 티켓으로 미루면 토큰을 쓰는 코드가 조용히 투명해집니다.

**완료 조건:**

- `DESIGN.md` 의 Semantic 절에 새 토큰이 값과 함께 적혀 있습니다.
- `main.css` 의 light·dark 두 블록에 같은 이름이 있습니다.
- `npm run lint` · `npm run lint:md` clean.
