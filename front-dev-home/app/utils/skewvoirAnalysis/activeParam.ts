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
}

/** Which parameters get a vote on whether the URL `mp` is valid. */
export const activeParamPool = (input: ActiveParamInput): string[] =>
  input.scope === 'set' && input.setParams.length > 0
    ? input.setParams
    : input.focusParams

export const resolveActiveParam = (input: ActiveParamInput): string => {
  const pool = activeParamPool(input)
  // `!= null` rather than a truthy test: the unnamed MP's name is '', and a
  // truthy check would reject that explicit pick and bounce elsewhere.
  if (input.urlMp != null && pool.includes(input.urlMp)) return input.urlMp
  const named = pool.filter(isNamedParam)
  return named[0] ?? pool[0] ?? input.urlMp ?? ''
}
