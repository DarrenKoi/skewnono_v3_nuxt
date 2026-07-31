/**
 * Send a caller nobody could identify to the self-identification form.
 *
 * This gate is CLIENT-side on purpose. The server-side version would have to
 * live in Flask's first `before_request`, where returning a response answers
 * `index.html` and every bundle with it — the exact shape of the Phase 3
 * blank-window deploy. A Nuxt route middleware can only affect routing, so the
 * worst it can do is send someone to the wrong page.
 *
 * It is therefore UX, not a security boundary: `curl` bypasses it entirely.
 * The one rule enforced server-side is that a declared identity can never be
 * an admin (`back_dev_home/_auth/admin.py`).
 */
export default defineNuxtRouteMiddleware(async (to) => {
  // ssr is false for this app, but the middleware still runs during prerender
  // on some Nuxt paths, where there is no session cookie to consult.
  if (import.meta.server) return

  // Without this the redirect below would target the page it is already on.
  if (to.path === '/identify') return

  const { identity, isAnonymous, refresh } = useIdentity()

  // One fetch per session, not per navigation: /api/* allows 20 requests per
  // 5 seconds and this runs on every route change.
  if (identity.value === null) await refresh()

  // A failed /api/me leaves it null. Fall through rather than trapping the
  // user behind a gate that could not evaluate them — the backend is what
  // actually refuses data, and it will say so in a way the UI can render.
  if (identity.value === null) return

  if (!isAnonymous.value) return

  return navigateTo({ path: '/identify', query: { next: to.fullPath } })
})
