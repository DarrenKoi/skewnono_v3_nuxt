import { usePersistedState } from '~/composables/usePersistedState'
import {
  DEFAULT_PANELS,
  normalizePanels,
  type LabPanel,
  type LabViewSlug
} from '~/utils/labView'

// Which analyses the 실험실 page draws, remembered per ROUTE rather than once
// for the whole page.
//
// Per route because the route is the preset: /tttm opens on the comparison and
// /pm-planning on the tuning target, and a single shared selection would make
// the second URL mean whatever the user last did on the first. Keyed by slug
// only — NOT by (toolType, fab) like the scope is — because this says which
// cards to draw, not what to compute: carrying it across a fab switch is the
// behaviour a display preference should have, and the scope's own reason for
// being per-fab (a comparison belongs to one fab) does not apply.
//
// Missing entry = that route's default preset, so a user who has never touched
// 보기 keeps getting the preset even after we change what the preset is.

export type LabPanelPrefs = Partial<Record<LabViewSlug, LabPanel[]>>

const STORAGE_KEY = 'lab-panels'

const normalize = (raw: unknown): LabPanelPrefs => {
  if (typeof raw !== 'object' || raw === null) return {}
  const out: LabPanelPrefs = {}
  for (const slug of Object.keys(DEFAULT_PANELS) as LabViewSlug[]) {
    const panels = normalizePanels((raw as Record<string, unknown>)[slug])
    if (panels) out[slug] = panels
  }
  return out
}

export const useLabPanels = (view: MaybeRefOrGetter<LabViewSlug>) => {
  const prefs = usePersistedState<LabPanelPrefs>(
    'lab-panels-store',
    STORAGE_KEY,
    {
      default: () => ({}),
      normalize,
      isEmpty: value => Object.keys(value).length === 0
    }
  )

  const slug = computed(() => toValue(view))
  const panels = computed<LabPanel[]>(() => prefs.value[slug.value] ?? DEFAULT_PANELS[slug.value])
  const has = (panel: LabPanel) => panels.value.includes(panel)

  // Replaces the whole object rather than mutating a nested array:
  // usePersistedState watches the ref, and an in-place push would not trip it.
  const setPanels = (next: LabPanel[]) => {
    prefs.value = { ...prefs.value, [slug.value]: normalizePanels(next) ?? [] }
  }

  return { panels, has, setPanels }
}
