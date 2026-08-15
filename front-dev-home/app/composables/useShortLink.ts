/**
 * Short links — trade a long in-app path for a `/s/<code>` one.
 *
 * A skewvoir analysis link is the reason this exists: the URL is the single
 * source of truth for what the workspace is looking at, so a six-MSR comparison
 * carries every msr id in full and lands near 500 characters, most of it the
 * same recipe and date repeated per member. That pastes into a messenger as a
 * wall of text and gets clipped by anything that wraps.
 *
 * The code is derived from the target, so minting the same screen twice returns
 * the SAME code — re-sharing does not fork the link a colleague already has.
 */

/** What the mint endpoint returns; `created_at` is unused here. */
interface ShortLinkResponse {
  code: string
  target: string
  created_at: string
}

export const useShortLink = () => {
  /**
   * Mint a short link for a root-relative in-app path and return it as an
   * absolute URL, or `null` when it could not be minted.
   *
   * `null` rather than a throw because EVERY caller has the same correct
   * response — copy the long URL instead. A share button that fails outright
   * because the shortener is down would be a worse feature than no shortener:
   * the user came to copy a link, and the long one still works.
   *
   * The origin is prepended here rather than server-side because the backend
   * has no reliable view of it — Nitro proxies /api in dev, and production is
   * plain http:// on an internal host.
   */
  const createShortLink = async (path: string): Promise<string | null> => {
    if (!import.meta.client || !path.startsWith('/')) return null
    try {
      const link = await $fetch<ShortLinkResponse>('/api/short-links', {
        method: 'POST',
        body: { target: path }
      })
      return link?.code ? `${window.location.origin}/s/${link.code}` : null
    } catch {
      // 400 (a target the server refused), 503 (store down) and a dead backend
      // are all the same decision at this layer.
      return null
    }
  }

  return { createShortLink }
}
