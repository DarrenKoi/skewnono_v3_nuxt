// Pure pieces of the SEM-image auto-retry policy (useAutoRetrySrc wires them
// to timers and refs; this module stays importable by `npm test`).
//
// Why retrying works at all: /api/msr-image writes the fetched image into the
// shared MinIO cache BEFORE building the response. When the cloud ingress
// gives up on a slow first fetch (tool FTP inside the request) and hands the
// browser a 502, Flask still finishes and caches — so a re-request a few
// seconds later is a fast cache hit. Confirmed on skewnono.skhynix.com
// 2026-08-03: the exact URL that 502'd in-page rendered fine when opened
// manually a moment later.

/** Automatic reload attempts per image, and the wait before each. The first
 * wait matches a typical tool-FTP round trip finishing server-side; the
 * second covers a queued worker. More than two just delays the terminal
 * "이미지 없음" verdict the user can still act on. */
export const IMAGE_RETRY_DELAYS_MS = [2500, 5000] as const

/**
 * Decorate an image URL for re-request `seq` (0 = the original URL).
 *
 * The param serves two masters: it makes the <img> src a NEW string (Vue
 * re-renders, the browser re-requests instead of reusing its in-memory
 * failure), and the backend ignores unknown query args, so the server-side
 * cache key is unchanged — the retry hits the entry the failed request wrote.
 */
export const withRetrySeq = (url: string, seq: number): string =>
  seq <= 0 ? url : `${url}${url.includes('?') ? '&' : '?'}retry=${seq}`
