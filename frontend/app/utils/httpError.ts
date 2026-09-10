// What a rejected $fetch tells us, in the shapes Nuxt actually hands over.
//
// Lives here rather than in one caller because "not every 429 is the same
// 429" keeps coming up in different features — the /api/* rate limit answers
// 429 alongside every application-level refusal — and each place that has to
// tell them apart needs the same two-shape lookup first.

/** The HTTP status of a failed request, or `undefined` when it never reached a
 * server (network error, abort). $fetch rejects with `statusCode` in some
 * paths and a `response` in others, and a check that reads only one of them
 * silently classifies half the failures as "no status". */
export const httpStatus = (err: unknown): number | undefined => {
  const e = err as { response?: { status?: number }, statusCode?: number } | null
  return e?.response?.status ?? e?.statusCode
}
