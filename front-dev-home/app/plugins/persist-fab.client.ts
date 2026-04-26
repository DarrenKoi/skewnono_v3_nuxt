import { useNavigationStore } from '~/stores/navigation'

// New key (was 'skewnono:fab') — old fac_id values like "R3"/"M11" are no longer valid
// fab_names, so dropping the old key avoids redirecting users to no-data URLs after deploy.
const STORAGE_KEY = 'skewnono:fab_name'

// Matches fab_name shape: R or M, 1-2 digits, optional A-C suffix. Permissive enough to accept
// any future fab_name from the API; strict enough to reject stale fac_id values.
const FAB_NAME_PATTERN = /^[RM]\d{1,2}[A-C]?$/

export default defineNuxtPlugin(() => {
  const store = useNavigationStore()

  const saved = window.localStorage.getItem(STORAGE_KEY)
  if (saved && saved !== 'all' && FAB_NAME_PATTERN.test(saved)) {
    store.setFab(saved)
  }

  watch(() => store.fab.value, (next) => {
    if (next === 'all') {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, next)
    }
  })
})
