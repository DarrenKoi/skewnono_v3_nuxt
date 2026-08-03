import type { ComputedRef } from 'vue'
import type { FocusImageCtx } from '~/composables/useFocusImageCtx'

// MSR contexts already handed to the backend this session. Module-level on
// purpose: navigating away and back must not queue the same tool work twice.
const warmed = new Set<string>()

/**
 * Warm the MinIO image cache for the images the user is about to click.
 *
 * POST /api/msr-images with a `names` scope runs the tool-FTP fetch of exactly
 * those files server-side and writes them into the shared cache. Firing it
 * when the active parameter's rows resolve means point clicks land on cache
 * hits instead of paying a cold in-request FTP fetch, which on the cloud is
 * exactly the request the ingress 502s (the <img> auto-retry then papers over
 * it, slowly). Scoped to the ACTIVE PARAMETER, not the whole MSR directory —
 * a parameter switch warms the newly active set, and images of parameters
 * never opened are never pulled from the tool. Fire-and-forget: the job
 * outlives navigation, progress is irrelevant here, and a refusal (429 at the
 * 2-job cap, tool down) simply leaves the per-click path — cache-miss fetch
 * plus auto-retry — to do its job, so the key is un-marked to let a later
 * focus try again.
 */
export const useMsrImageWarmer = (
  ctx: ComputedRef<FocusImageCtx>,
  names: () => string[]
) => {
  const { startDownloadAll } = useMsrImageApi()

  watch(
    () => {
      const { eqp_ip, class_name, msr } = ctx.value
      return `${eqp_ip}|${class_name}|${msr}|${[...names()].sort().join(',')}`
    },
    async (key) => {
      const { eqp_ip, class_name, msr } = ctx.value
      const wanted = names()
      if (!eqp_ip || !class_name || !msr || !wanted.length || warmed.has(key)) return
      warmed.add(key)
      try {
        await startDownloadAll(eqp_ip, class_name, msr, wanted)
      } catch {
        warmed.delete(key)
      }
    },
    { immediate: true }
  )
}
