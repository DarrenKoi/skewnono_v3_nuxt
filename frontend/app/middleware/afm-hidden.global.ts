/**
 * When AFM_ENABLED (useAfmAvailability.ts) is false the feature is hidden, so
 * its pages must not be reachable either — a bookmark, browser-history entry
 * or hand-typed URL would land on a half-finished page. A no-op while it is true.
 */
export default defineNuxtRouteMiddleware((to) => {
  if (AFM_ENABLED) return
  if (!to.path.startsWith('/afm')) return

  return navigateTo('/')
})
