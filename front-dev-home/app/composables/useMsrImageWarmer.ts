import type { ComputedRef } from 'vue'
import type { FocusImageCtx } from '~/composables/useFocusImageCtx'

// MSR contexts already handed to the backend this session. Module-level on
// purpose: navigating away and back must not queue the same tool work twice.
const warmed = new Set<string>()

/**
 * Warm the MinIO image cache for the focused MSR before any image is clicked.
 *
 * POST /api/msr-images runs the tool-FTP fan-out server-side and writes every
 * image into the shared cache — the machinery behind the gallery's bulk
 * download. Firing it once per focused MSR means point clicks land on cache
 * hits instead of paying a cold in-request FTP fetch, which on the cloud is
 * exactly the request the ingress 502s (the <img> auto-retry then papers over
 * it, slowly). Fire-and-forget: the job outlives navigation, progress is
 * irrelevant here, and a refusal (429 at the 2-job cap, tool down) simply
 * leaves the per-click path — cache-miss fetch plus auto-retry — to do its
 * job, so the context is un-marked to let a later focus try again.
 */
export const useMsrImageWarmer = (ctx: ComputedRef<FocusImageCtx>) => {
  const { startDownloadAll } = useMsrImageApi()

  watch(
    () => `${ctx.value.eqp_ip}|${ctx.value.class_name}|${ctx.value.msr}`,
    async (key) => {
      const { eqp_ip, class_name, msr } = ctx.value
      if (!eqp_ip || !class_name || !msr || warmed.has(key)) return
      warmed.add(key)
      try {
        await startDownloadAll(eqp_ip, class_name, msr)
      } catch {
        warmed.delete(key)
      }
    },
    { immediate: true }
  )
}
