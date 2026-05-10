import type { Ref, ComputedRef } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

type Fallback = RouteLocationRaw | Ref<RouteLocationRaw> | ComputedRef<RouteLocationRaw>

export const useHistoryBack = (fallback: Fallback) => {
  const router = useRouter()

  const goBack = () => {
    if (import.meta.client && window.history.length > 1) {
      router.back()
      return
    }
    const target = (fallback && typeof fallback === 'object' && 'value' in fallback) ? fallback.value : fallback
    router.push(target)
  }

  return { goBack }
}
