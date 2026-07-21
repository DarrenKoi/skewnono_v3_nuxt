// Plain-text summary of the current selection for the 요약 복사 rail action.
// Engineers paste this into messengers and reports, so empty fields are
// dropped entirely — the paste never carries "—" placeholder noise. The share
// URL rides along as the last line so the receiver can open the exact same
// workspace state.
//
// Pure and framework-free (mirrors setEditing.ts) so the format is
// unit-testable without Nuxt. Runs under raw `node --test`.
import type { SkewvoirSelection } from '~/composables/useSkewvoirWorkspace'

export const formatSelectionSummary = (
  sel: SkewvoirSelection,
  activeParam: string,
  shareUrl: string
): string => {
  const fields: Array<[string, string]> = [
    ['MSR', sel.msr],
    ['Param', activeParam],
    ['Lot', sel.lot],
    ['Recipe', sel.recipe],
    ['EQ', sel.eq],
    ['MP', sel.mp],
    ['Captured', sel.capturedAt],
    ['Link', shareUrl]
  ]
  return fields
    .filter(([, value]) => !!value)
    .map(([label, value]) => `${label}: ${value}`)
    .join('\n')
}
