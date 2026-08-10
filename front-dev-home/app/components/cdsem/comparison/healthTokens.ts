// Health palette — warm-paper harmonized soft tints.
// Tailwind defaults (red-50 / amber-50 / green-50) clash with --sk-canvas cream,
// so we publish brand-correlated oklch tokens for lot rows + cards.

// HealthLevel 의 정의는 utils/ruleEngine.ts 한 곳입니다. 이 파일은 색만 갖습니다.
// 예전에는 두 벌이 있었고(여기 + ruleEngine), classifyHealth 와 threshold 도 각각
// 있어서 같은 이름이 서로 다른 판정을 할 수 있었습니다.
import type { HealthLevel } from '~/utils/ruleEngine'

export type { HealthLevel }

export interface HealthSwatch {
  tint: string
  tintDark: string
  ink: string
  inkDark: string
  edge: string
  edgeDark: string
  dot: string
}

export const healthSwatches: Record<HealthLevel, HealthSwatch> = {
  red: {
    tint: 'oklch(0.93 0.045 30)',
    tintDark: 'oklch(0.31 0.055 30)',
    ink: 'oklch(0.42 0.13 30)',
    inkDark: 'oklch(0.85 0.12 30)',
    edge: 'oklch(0.62 0.16 30)',
    edgeDark: 'oklch(0.72 0.17 30)',
    dot: 'oklch(0.60 0.18 28)'
  },
  yellow: {
    tint: 'oklch(0.94 0.055 80)',
    tintDark: 'oklch(0.32 0.05 75)',
    ink: 'oklch(0.46 0.10 70)',
    inkDark: 'oklch(0.86 0.10 80)',
    edge: 'oklch(0.66 0.13 75)',
    edgeDark: 'oklch(0.78 0.13 80)',
    dot: 'oklch(0.74 0.14 80)'
  },
  green: {
    tint: 'oklch(0.94 0.04 145)',
    tintDark: 'oklch(0.30 0.045 150)',
    ink: 'oklch(0.42 0.11 145)',
    inkDark: 'oklch(0.85 0.10 150)',
    edge: 'oklch(0.58 0.14 145)',
    edgeDark: 'oklch(0.74 0.13 150)',
    dot: 'oklch(0.62 0.13 145)'
  }
}

// 아래 두 함수가 여기 있는 이유는 이 파일 머리말과 같습니다: swatch 를 실제
// 색으로 바꾸는 규칙이 화면마다 한 벌씩 생기면, 같은 판정이 화면마다 다른
// 색으로 보일 수 있습니다. health 를 색으로 옮기는 일은 전부 이 파일이 합니다.
//
// `health === null` 은 "룰이 없어 판정하지 않았다" 입니다. 초록이 아니라
// 중성 회색으로 나가야 합니다 — 초록은 "판정했고 괜찮다" 라는 뜻이라,
// 아무 말도 하지 않은 것과 섞이면 없는 보증을 준 것이 됩니다.

/** 카드 왼쪽 띠 색. 판정 없음이면 테두리색(중성). */
export const healthStripeColor = (health: HealthLevel | null): string =>
  health ? healthSwatches[health].dot : 'var(--sk-border)'

/** tint 배경 + ink 글자. 판정 없음이면 호출부가 중성 배지를 그립니다. */
export const healthBadgeStyle = (health: HealthLevel, isDark: boolean) => {
  const swatch = healthSwatches[health]
  return {
    background: isDark ? swatch.tintDark : swatch.tint,
    color: isDark ? swatch.inkDark : swatch.ink
  }
}

// Parameter category palette — an ORDINAL ramp, not five categorical hues.
// para_over_16 → para_5 is an ordered measurement-density scale, so a single
// warm hue (45°, the --sk-accent family) carries identity through lightness
// alone.
//
// The previous palette swept four hues (32/65/100/165) and was *declared* a
// "heaviest → lightest" gradient, but its lightness ran 0.62 → 0.72 → 0.66 →
// 0.62 — not monotone. That collision left para_13 and para_9 ΔE 10.2 apart in
// normal vision (the floor is 15) and ΔE 3.1 under protanopia, i.e. the same
// colour for a red-green reader. It matters most in the stacked area, where
// those two bands sit physically adjacent.
//
// Lightness is monotone here, so the ramp is colour-vision-safe by construction
// rather than by luck. Both steps pass every check in the dataviz palette
// validator (--ordinal) against --sk-surface in their respective modes.
// Keep the adjacent ΔL ≥ 0.06 if you retune — paraTrendSeries.test.ts asserts it.
//
// The 2026-08-10 range split added a fifth bucket. The ramp was RESPACED
// between the same two endpoints rather than extended past them: pushing a new
// darkest step below 0.40 (light) / 0.52 (dark) would have left the validated
// contrast window, and in dark mode a step that dark stops separating from the
// surface. Five steps across the same span still clear the ΔL floor.
export const paraColors = {
  para_over_16: 'oklch(0.40 0.110 45)', // darkest — most parameters
  para_16: 'oklch(0.49 0.128 45)',
  para_13: 'oklch(0.58 0.135 45)',
  para_9: 'oklch(0.67 0.128 45)',
  para_5: 'oklch(0.76 0.100 45)' // lightest — fewest parameters
} as const

export const paraColorsDark = {
  para_over_16: 'oklch(0.52 0.135 45)',
  para_16: 'oklch(0.60 0.145 45)',
  para_13: 'oklch(0.68 0.145 45)',
  para_9: 'oklch(0.77 0.115 45)',
  para_5: 'oklch(0.85 0.080 45)'
} as const

export const paraOrder = ['para_over_16', 'para_16', 'para_13', 'para_9', 'para_5'] as const

// classifyHealth / healthThresholds / healthOrder 는 여기 없습니다.
//
// 판정은 서버가 주는 룰의 thresholds 로 utils/ruleEngine.ts 의 classifyHealth 가
// 합니다 (fab 마다 다를 수 있습니다). 예전에 이 파일이 갖고 있던 0.10 / 0.20 은
// 프런트엔드에 박힌 상수라, 사무실에서 경계를 바꿔도 화면이 따라가지 않았습니다.
// 정렬 순서는 판정 없음(룰 없는 fab)까지 다뤄야 하므로 utils/lotHealth.ts 의
// verdictSortValue 가 갖습니다.
