/**
 * AFM is hidden while it is being built, so its pages must not be reachable
 * either — a bookmark, browser-history entry or hand-typed URL would land on
 * a half-finished page. Gated by AFM_ENABLED in useAfmAvailability.ts.
 */
export default defineNuxtRouteMiddleware((to) => {
  if (AFM_ENABLED) return
  if (!to.path.startsWith('/afm')) return

  return navigateTo('/')
})
