import { useNavigationStore } from '~/stores/navigation'
import { normalizeFab } from '~/utils/fab'

// Key bumps drop stale values rather than migrating them: a fac_id that is not a real
// fab_name would otherwise sit in the selection forever, offering a fab the sem-list roster
// does not have and routing to no-data URLs.
//   'skewnono:fab'      -> 'skewnono:fab_name'     when the app moved from fac_id to fab_name
//   'skewnono:fab_name' -> 'skewnono:fab_name.v2'  because device-statistics used to write
//                          its fac_id-grained fab ('M16') here on mount. That token is
//                          syntactically a valid fab_name, so no filter can spot it —
//                          only a key bump clears the copies already written.
// The value is a comma-joined multi-fab list; a pre-existing single value reads back as a
// one-element list with no migration step.
const STORAGE_KEY = 'skewnono:fab_name.v2'

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
