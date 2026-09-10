// Shared keyboard-cursor math for the analysis dashboard tables. Pure so it can
// be unit-tested under `node --test` (the Nuxt runtime is unavailable there).
export type CursorKey = 'ArrowDown' | 'ArrowUp' | 'Home' | 'End'

/**
 * Next cursor index for a keypress over a list of `len` rows.
 * Returns null for an empty list (no-op). A `current` that is negative or out
 * of range means "nothing focused yet": ArrowDown starts at the first row,
 * ArrowUp at the last. Edges clamp (no wraparound).
 */
export function nextCursorIndex(key: CursorKey, current: number, len: number): number | null {
  if (len <= 0) return null
  const cur = current < 0 || current >= len ? -1 : current
  switch (key) {
    case 'ArrowDown': return cur < 0 ? 0 : Math.min(cur + 1, len - 1)
    case 'ArrowUp': return cur < 0 ? len - 1 : Math.max(cur - 1, 0)
    case 'Home': return 0
    case 'End': return len - 1
  }
}
