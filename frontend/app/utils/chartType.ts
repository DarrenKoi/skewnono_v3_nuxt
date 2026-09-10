// 차트 안의 활자. ECharts 는 캔버스에 글자를 직접 그리므로 CSS 변수
// (--font-mono)도, main.css 의 sk-* 역할 클래스도 닿지 않습니다. 차트 축과
// 카드 본문이 같은 활자로 보이려면 그 값을 이렇게 한 번 더 적어 주는 수밖에
// 없고, 그렇다면 최소한 한 군데에만 적혀 있어야 합니다.
//
// 13px 인 이유는 행 카드 계층의 바닥과 같습니다 (DESIGN.md §The row-card
// tier) — 축 눈금도 사람이 읽는 값이라 그 아래로 내려가지 않습니다.

export const CHART_MONO = '\'JetBrains Mono\', ui-monospace, \'SF Mono\', Menlo, Consolas, monospace'

/** 축 눈금 — 숫자든 날짜든 mono 로, 자릿수가 흔들리지 않게. */
export const CHART_AXIS_LABEL = { fontSize: 13, fontFamily: CHART_MONO } as const

/** 범례 · 축 이름 등 축 눈금 옆에 붙는 글자. */
export const CHART_LEGEND_LABEL = { fontSize: 13 } as const
