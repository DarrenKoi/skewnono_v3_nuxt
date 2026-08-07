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
    // An unresolvable page still ENDS the previous one, so it must clear the
    // key rather than leave it standing. Two cases produce null:
    //  - recipe-status before its tab lands: harmless to clear, since this
    //    step never had a beacon to suppress and the mount-time
    //    router.replace resolves within a tick, firing exactly once either
    //    way.
    //  - every other unresolvable path (chiefly `/`, the fab/tool picker):
    //    leaving lastIdentity standing would make the NEXT visit to that same
    //    page look like a filter change and drop its beacon — and
    //    "home -> pick a fab -> 장비 상태" is exactly that loop.
    if (!identity) {
      lastIdentity = null
      return
    }
    // Unchanged = a fab switch or a filter change, not a new page open.
    if (identity === lastIdentity) return
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
