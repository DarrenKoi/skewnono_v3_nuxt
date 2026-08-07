import { useNavigationStore } from '~/stores/navigation'
import { normalizeFab } from '~/utils/fab'

// New key (was 'skewnono:fab') — old fac_id values like "R3"/"M11" are no longer valid
// fab_names, so dropping the old key avoids redirecting users to no-data URLs after deploy.
// Since Phase 1 the value is a comma-joined multi-fab list; a pre-existing single value
// reads back as a one-element list with no migration step.
const STORAGE_KEY = 'skewnono:fab_name'

// Matches fab_name shape: R or M, 1-2 digits, optional A-C suffix. Validated per token so
// one stale entry drops alone instead of resetting the whole selection.
const FAB_NAME_PATTERN = /^[RM]\d{1,2}[A-C]?$/

export default defineNuxtPlugin(() => {
  const store = useNavigationStore()

  const saved = (window.localStorage.getItem(STORAGE_KEY) ?? '')
    .split(',')
    .map(normalizeFab)
    .filter(token => FAB_NAME_PATTERN.test(token))
  if (saved.length > 0) {
    store.setFabs(saved)
  }

  watch(() => store.fabs.value, (next) => {
    if (next.length === 0) {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, next.join(','))
    }
  })
})
