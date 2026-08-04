export const chipClass = (active: boolean) => active
  ? 'bg-(--sk-accent) text-white ring-(--sk-accent)'
  : 'bg-white text-(--sk-ink) ring-zinc-200 hover:bg-zinc-50 dark:bg-zinc-900 dark:ring-zinc-700 dark:hover:bg-zinc-800'

// Geometry for a chip on the row-card screens (디바이스 통계 / 디바이스 분석):
// 34px tall with a 14px label, so a filter is a comfortable click target and
// its text sits at the same size as the card values it filters.
//
// Kept next to chipClass rather than inlined at each call site because the two
// always appear together — `[CHIP_BASE, chipClass(active)]` — and a chip that
// got only one of them (right colour, wrong height) is the exact drift this
// pairing exists to prevent.
export const CHIP_BASE = 'inline-flex h-[34px] items-center gap-1.5 rounded-lg px-3.5 text-sm font-semibold ring-1 transition-colors'

// Mono variant — for chips whose label is an identifier (lot_cd), not a word.
export const CHIP_BASE_MONO = `${CHIP_BASE} font-mono tabular-nums`
