import { usePersistedState } from '~/composables/usePersistedState'
import { storedPanels, normalizePanels, DEFAULT_PANELS, type LabPanel } from '~/utils/labView'

// Which analyses the 실험실 page draws, remembered once for the page.
//
// Once, not per (toolType, fab) like the scope is, because this says which
// cards to draw and not what to compute: carrying it across a fab switch is the
// behaviour a display preference should have, and the scope's own reason for
// being per-fab (a comparison belongs to one fab) does not apply.
//
// It was keyed per ROUTE until 2026-09-01, when /pm-planning stopped being a
// route — see utils/labView for the stored shape that key left behind and how
// it is read now. Missing entry = DEFAULT_PANELS, so a reader who has never
// touched 보기 keeps getting the preset even after we change what it is.

const STORAGE_KEY = 'lab-panels'

export const useLabPanels = () => {
  const panels = usePersistedState<LabPanel[]>(
    'lab-panels-store',
    STORAGE_KEY,
    {
      default: () => [...DEFAULT_PANELS],
      normalize: storedPanels,
      // Everything unticked is a real choice, not a vacant one: the default
      // isEmpty would delete the key and hand the reader the preset back on
      // the next load.
      isEmpty: () => false
    }
  )

  const has = (panel: LabPanel) => panels.value.includes(panel)

  // Replaces the array rather than mutating it: usePersistedState watches the
  // ref, and an in-place push would not trip it.
  const setPanels = (next: LabPanel[]) => {
    panels.value = normalizePanels(next) ?? []
  }

  return { panels, has, setPanels }
}
