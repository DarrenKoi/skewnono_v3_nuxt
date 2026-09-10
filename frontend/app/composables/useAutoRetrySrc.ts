import { IMAGE_RETRY_DELAYS_MS, withRetrySeq } from '../utils/imageRetry.ts'

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
  // seq only counts up (also across manual resets), so every re-request is a
  // URL string the browser has not seen for this image. attempts counts the
  // current image's errors; one more error than there are delays means the
  // budget is spent.
  const seq = ref(0)
  const attempts = ref(0)
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

  const exhausted = computed(() => attempts.value > IMAGE_RETRY_DELAYS_MS.length)

  const onError = () => {
    if (!source() || exhausted.value) return
    const delay = IMAGE_RETRY_DELAYS_MS[attempts.value]
    attempts.value += 1
    if (delay === undefined) return // budget spent — exhausted just flipped
    timer = setTimeout(() => {
      timer = null
      seq.value += 1
    }, delay)
  }

  /** Manual retry: refill the auto budget and re-request immediately. */
  const reset = () => {
    clear()
    attempts.value = 0
    seq.value += 1
  }

  watch(source, () => {
    clear()
    attempts.value = 0
    seq.value = 0
  })

  onScopeDispose(clear)

  return { src, onError, exhausted, reset }
}
