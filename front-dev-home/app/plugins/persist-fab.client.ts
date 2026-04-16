import type { Fab } from '~/stores/navigation'
import { useNavigationStore } from '~/stores/navigation'

const STORAGE_KEY = 'skewnono:fab'
const VALID_FABS: Fab[] = ['all', 'R3', 'M11', 'M12', 'M14', 'M15', 'M16']

export default defineNuxtPlugin(() => {
  const store = useNavigationStore()

  const saved = window.localStorage.getItem(STORAGE_KEY)
  if (saved && VALID_FABS.includes(saved as Fab) && saved !== 'all') {
    store.setFab(saved as Fab)
  }

  watch(() => store.fab.value, (next) => {
    if (next === 'all') {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, next)
    }
  })
})
