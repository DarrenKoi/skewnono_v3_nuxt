// Which parameter the analysis screen is showing.
//
// The URL `mp` is the user's stated pick, but a pick is only meaningful if some
// loaded measurement actually carries that parameter. Which measurements get a
// vote is the whole question:
//
//   • single scope — the focus file alone. Historic behaviour, unchanged.
//   • set scope    — ANY measurement in the curated set. A set spans recipes,
//                    so a parameter 22 of 30 measurements share is a legitimate
//                    pick even when the focus measurement is one of the 8.
//
// The set pool applies only once the set files are loaded. shouldLoadSet()
// excludes the dashboard view, so a scope=set + view=dashboard screen holds an
// EMPTY setFiles; judging against that empty pool would reject every parameter
// and let the caller's write-back watcher corrupt the URL.
//
// Pure and framework-free so it runs under raw `node --test`.
import type { AnalysisScope } from './types.ts'
import { isNamedParam } from './paramOrder.ts'

export interface ActiveParamInput {
  scope: AnalysisScope
  /** The URL `mp`. `undefined` when absent; `''` is the unnamed settling MP. */
  urlMp: string | undefined
  /** Parameters of the focus measurement's file. */
  focusParams: string[]
  /** Parameters across the curated set. Empty when the set is not loaded. */
  setParams: string[]
  /**
   * True when EVERY measurement the curated set expects has loaded — not merely
   * that some did. /api/msr-files returns found MSRs only and silently skips
   * the rest, so a set can settle part-loaded with nothing anywhere reporting
   * an error.
   *
   * Optional, and omitting it reads as `false`: a missing answer can only
   * suppress a URL write, never permit a wrong one.
   */
  setComplete?: boolean
}

/** The pool, plus whether it is entitled to rewrite the URL. */
export interface ActiveParamPool {
  params: string[]
  authoritative: boolean
}

/**
 * Which parameters get a vote, and whether that vote may rewrite the URL.
 *
 * The pool answers two masters, and they need different things from it:
 *
 *   • RENDERING may always fall back. Drawing the focus file's first parameter
 *     when the set has not loaded is honest — it is what the screen can draw.
 *   • The URL may NOT. Canonicalizing `mp` from a pool that is missing
 *     measurements DESTROYS a pick the user made, and nothing restores it.
 *
 * So the pool reports its own authority instead of leaving each caller to
 * re-derive it from whatever proxy is in reach. `authoritative` is false
 * whenever the set pool is anything less than the whole set: not loaded (the
 * dashboard, excluded by shouldLoadSet), loaded but carrying no parameters, or
 * part-loaded. `params` is unchanged in every case — the fallback the renderer
 * wants is exactly the pool that must not touch the URL.
 */
export const activeParamPool = (input: ActiveParamInput): ActiveParamPool => {
  const useSet = input.scope === 'set' && input.setParams.length > 0
  return {
    params: useSet ? input.setParams : input.focusParams,
    authoritative: input.scope !== 'set' || (useSet && input.setComplete === true)
  }
}

export const resolveActiveParam = (input: ActiveParamInput): string => {
  // Rendering ignores `authoritative` by design — see the contract above.
  const { params: pool } = activeParamPool(input)
  // `!= null` rather than a truthy test: the unnamed MP's name is '', and a
  // truthy check would reject that explicit pick and bounce elsewhere.
  if (input.urlMp != null && pool.includes(input.urlMp)) return input.urlMp
  const named = pool.filter(isNamedParam)
  return named[0] ?? pool[0] ?? input.urlMp ?? ''
}
