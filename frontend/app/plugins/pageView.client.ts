import { createPageViewTracker, buildPageViewPath } from '~/utils/pageIdentity'
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

  // Which navigations count as a page open lives in the tracker, where it is
  // tested: fab switches, filter changes and the 장비 상태 landing do not.
  const isPageOpen = createPageViewTracker()

  const report = (path: string, query: Record<string, unknown>) => {
    if (!isPageOpen(path, query)) return

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
