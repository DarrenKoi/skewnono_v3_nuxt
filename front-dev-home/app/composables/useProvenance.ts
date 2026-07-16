import type { DerivedValue } from '~/utils/skewvoirAnalysis/features'

// The COMMON contract for "근거 보기" (view provenance): any chart/table that
// renders a DerivedValue (from analysis.featureRows / analysis.featureRegistry,
// or any other feature-table consumer) opens the SAME drawer with the SAME
// composable, instead of each view wiring its own open/close prop pair.
// ProvenanceDrawer.vue reads this state directly — mount it once (e.g. at the
// Workspace root) and every caller just does `useProvenance().open(derived, label)`.
//
// useState (not a module-scope ref) so it survives remounts, matching the rest
// of the analysis view-state composables (focusedSequence, focusedSite, …).
export const useProvenance = () => {
  const current = useState<DerivedValue<unknown> | null>('skewvoir-provenance-current', () => null)
  const label = useState<string | null>('skewvoir-provenance-label', () => null)

  const open = (derived: DerivedValue<unknown>, title?: string) => {
    current.value = derived
    label.value = title ?? null
  }
  const close = () => {
    current.value = null
    label.value = null
  }

  return {
    current,
    label,
    isOpen: computed(() => current.value !== null),
    open,
    close
  }
}
