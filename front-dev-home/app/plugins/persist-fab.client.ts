import { useNavigationStore } from '~/stores/navigation'
import { NO_FAB, hasFab, normalizeFab } from '~/utils/fab'

// New key (was 'skewnono:fab') — old fac_id values like "R3"/"M11" are no longer valid
// fab_names, so dropping the old key avoids redirecting users to no-data URLs after deploy.
const STORAGE_KEY = 'skewnono:fab_name'

// Matches fab_name shape: R or M, 1-2 digits, optional A-C suffix. Permissive enough to accept
// any future fab_name from the API; strict enough to reject stale fac_id values. Tested against
// the normalized (uppercase) form, since a value persisted from a lowercase API response would
// otherwise be rejected here and silently reset the user's fab on the next load.
const FAB_NAME_PATTERN = /^[RM]\d{1,2}[A-C]?$/

export default defineNuxtPlugin(() => {
  const store = useNavigationStore()

  const saved = normalizeFab(window.localStorage.getItem(STORAGE_KEY))
  if (hasFab(saved) && FAB_NAME_PATTERN.test(saved)) {
    store.setFab(saved)
  }

  watch(() => store.fab.value, (next) => {
    if (next === NO_FAB) {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, next)
    }
  })
})
