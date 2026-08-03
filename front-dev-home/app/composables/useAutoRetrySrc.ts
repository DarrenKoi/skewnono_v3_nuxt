import { IMAGE_RETRY_DELAYS_MS, retryDelayMs, withRetrySeq } from '../utils/imageRetry.ts'

/**
 * An <img> src that survives the cloud ingress killing a slow first load.
 *
 * On the cloud, a cold /api/msr-image request does the tool-FTP fetch inside
 * the request; when that outlives the ingress timeout the browser sees a 502
 * — but Flask finishes and writes the MinIO cache anyway. So a bounded
 * auto-retry (2.5s, then 5s) turns "first view of every image is broken"
 * into "the image appears a few seconds later". `exhausted` flips only after
 * the budget is spent — hosts show their terminal failure state on that, and
 * may call `reset()` from a manual 재시도 affordance.
 *
 * `source` is a getter so a computed/prop chain stays reactive; a source
 * change (new image) abandons any pending retry and restores the budget.
 */
export const useAutoRetrySrc = (source: () => string | null | undefined) => {
  const seq = ref(0)
  const exhausted = ref(false)
  let remaining = IMAGE_RETRY_DELAYS_MS.length
  let timer: ReturnType<typeof setTimeout> | null = null

  const clear = () => {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  const src = computed(() => {
    const base = source()
    return base ? withRetrySeq(base, seq.value) : base
  })

  const onError = () => {
    if (!source()) return
    if (remaining <= 0) {
      exhausted.value = true
      return
    }
    const delay = retryDelayMs(IMAGE_RETRY_DELAYS_MS.length - remaining)
    remaining -= 1
    clear()
    // seq keeps counting up across manual resets, so every re-request is a
    // string the browser has not seen for this image.
    timer = setTimeout(() => {
      timer = null
      seq.value += 1
    }, delay)
  }

  /** Manual retry: refill the auto budget and re-request immediately. */
  const reset = () => {
    clear()
    remaining = IMAGE_RETRY_DELAYS_MS.length
    exhausted.value = false
    seq.value += 1
  }

  watch(source, () => {
    clear()
    remaining = IMAGE_RETRY_DELAYS_MS.length
    exhausted.value = false
    seq.value = 0
  })

  onScopeDispose(clear)

  return { src, onError, exhausted, reset }
}
