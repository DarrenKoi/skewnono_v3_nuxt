import type { MeasHistRow, MeasHistToolType } from '~/composables/useMeasHistApi'
import {
  addMeasHistSelection,
  removeMeasHistSelection,
  setMeasHistSelections,
  toggleMeasHistSelection
} from '~/utils/measHistSelection'

// Mirrors recipe-search's persistent working set. Search results may be
// replaced repeatedly; selected measurements remain available by tool type.
const storageKey = (toolType: MeasHistToolType) =>
  `skewnono:skewvoir.selection.${toolType}`

const normalizeRows = (parsed: unknown): MeasHistRow[] => {
  if (!Array.isArray(parsed)) return []
  // A blank msr is not an identity (msr_check "No" rows -- see
  // utils/measHistSelection.ts hasMsrIdentity): such an entry could never be
  // deselected (toggle keys on msr) and would duplicate the workbench's
  // v-for keys, so it is dropped at the storage boundary.
  return parsed.filter((item): item is MeasHistRow =>
    typeof item === 'object'
    && item !== null
    && typeof (item as { msr?: unknown }).msr === 'string'
    && (item as { msr: string }).msr.trim() !== ''
  )
}

export const useSkewvoirSearchSelection = (toolType: MeasHistToolType) => {
  const selected = usePersistedState<MeasHistRow[]>(
    `skewvoir:search-selection:${toolType}`,
    storageKey(toolType),
    { default: () => [], normalize: normalizeRows }
  )

  const has = (msr: string) => selected.value.some(row => row.msr === msr)

  const add = (row: MeasHistRow) => {
    selected.value = addMeasHistSelection(selected.value, row)
  }

  const remove = (msr: string) => {
    selected.value = removeMeasHistSelection(selected.value, msr)
  }

  const toggle = (row: MeasHistRow) => {
    selected.value = toggleMeasHistSelection(selected.value, row)
  }

  const setMany = (rows: MeasHistRow[], enabled: boolean) => {
    selected.value = setMeasHistSelections(selected.value, rows, enabled)
  }

  const clear = () => {
    selected.value = []
  }

  const count = computed(() => selected.value.length)

  return { selected, count, has, add, remove, toggle, setMany, clear }
}
