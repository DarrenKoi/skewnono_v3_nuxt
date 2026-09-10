import type { NuxtApp } from '#app'

// The two `useAsyncData` options this app repeats. They are deliberately
// separate primitives rather than one `useCachedAsyncData(key, fetcher)`
// wrapper: caching and in-flight de-duplication are independent choices, and
// only 5 of the 18 call sites want the second one. Bundling them would hand
// de-duplication to the other 13 as a silent behaviour change — invisible at
// home, where the mocks answer instantly and two concurrent callers never
// actually overlap, and only observable at the office where requests are slow
// enough to collide.

/**
 * Serve a already-fetched payload instead of refetching.
 *
 * `payload.data` is what the current navigation has fetched; `static.data`
 * survives across them. Without this, every component mounting against a
 * shared key refires the request.
 */
export const payloadCache = (key: string, nuxtApp: NuxtApp) =>
  nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]

/**
 * Same, but only on the initial load — an explicit `refresh()` always refetches.
 *
 * For data the user refreshes to see change (the pending-tools roster). Serving
 * cache to a refresh would make the button look broken.
 */
export const payloadCacheOnInitial = (
  key: string,
  nuxtApp: NuxtApp,
  context: { cause: string }
) => (context.cause === 'initial' ? payloadCache(key, nuxtApp) : undefined)

export interface InFlightSlot<T> {
  /** Join the pending request if there is one, else start `fetcher`. */
  run: (fetcher: () => Promise<T>) => Promise<T>
  /** Drop the shared promise so the next `run` really hits the network. */
  reset: () => void
}

/**
 * Collapse concurrent calls onto one request.
 *
 * `useAsyncData`'s key-based de-duplication does not cover components that
 * mount in the same tick before any payload exists — exactly what happens when
 * several panels on a page share one resource. A rejected promise is cleared
 * so a failure stays retryable rather than being cached forever.
 *
 * Hold one slot per resource at module scope so the shared promise outlives any
 * single component. The fetcher is passed to `run` rather than to the factory
 * because callers resolve their URL inside the composable, where
 * `useRuntimeConfig()` is valid.
 */
export const createInFlightSlot = <T>(): InFlightSlot<T> => {
  let inFlight: Promise<T> | null = null
  return {
    run: (fetcher) => {
      if (!inFlight) {
        inFlight = fetcher().catch((err) => {
          inFlight = null
          throw err
        })
      }
      return inFlight
    },
    reset: () => {
      inFlight = null
    }
  }
}
