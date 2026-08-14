# 03 — Lot 표의 outlier 배지를 토큰으로 옮긴다

Status: open
Spec: [`../spec.md`](../spec.md)
Blocked by: 01

`lot-outlier-merge` 가 모달 안의 초과 표시를 `--sk-bad` 로 옮겼지만, **그 모달을
여는 표의 배지**는 raw rose 로 남았습니다. 지금 사용자는 빨간 배지를 눌러 다른
빨강으로 칠해진 모달을 엽니다.

**Files:**

- Edit: `front-dev-home/app/components/cdsem/comparison/LotTable.vue` — `:200`
  (클릭 가능한 배지, hover 있음) 과 `:346` (`countPill`, hover 없음)

**두 자리의 성격이 다릅니다:**

- `:200` 은 `<button>` 이고 `transition-colors hover:bg-rose-200
  dark:hover:bg-rose-950/80` 를 씁니다 → 티켓 01 의 `--sk-bad-soft-hover` 가
  있어야 옮길 수 있습니다. 이 티켓이 01 에 막혀 있는 유일한 이유입니다.
- `:346` 은 정적 pill 이라 지금 당장 옮길 수 있습니다.

**완료 조건:**

- `LotTable.vue` 에 `rose-` 가 남지 않습니다.
- 배지에 마우스를 올리면 색이 **눈에 띄게** 변합니다 (라이트·다크 모두). 토큰이
  기존 rose 계단보다 미묘해지면 hover 가 사라진 것처럼 보입니다 — 확인은 티켓 05.
- `npm run typecheck` · `npm run lint` 통과.
