import { resolvePageIdentity, buildPageViewPath } from '~/utils/pageIdentity'
import { joinApiPath } from '~/utils/apiPath'

/** Reports page opens for 사용 통계. See
 *  docs/superpowers/specs/2026-08-04-activity-page-view-beacon-design.md
 *
 *  Fire-and-forget by design: usage telemetry must never block navigation or
 *  surface an error. A dropped beacon costs one row. */
export default defineNuxtPlugin(() => {
  const router = useRouter()
  const config = useRuntimeConfig()
  const url = joinApiPath(config.public.apiBase, '/page-view')

  let lastIdentity: string | null = null

  const report = (path: string, query: Record<string, unknown>) => {
    const identity = resolvePageIdentity(path, query)
    // null = identity not resolvable yet (recipe-status before its tab lands).
    // Unchanged = a fab switch or a filter change, not a new page open.
    if (!identity || identity === lastIdentity) return
    lastIdentity = identity

    $fetch(url, {
      method: 'POST',
      body: { path: buildPageViewPath(path, query) }
    }).catch(() => {
      // Swallowed on purpose. A 429 from the shared rate limiter is the
      // expected failure under fast tab-flipping and is not worth a console
      // line the user cannot act on.
    })
  }

  router.afterEach((to) => {
    report(to.path, to.query)
  })

  // afterEach does not run for the first load.
  const start = router.currentRoute.value
  report(start.path, start.query)
})
