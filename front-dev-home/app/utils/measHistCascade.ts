// Pure: cascade the skewvoir search dropdowns — FAB → 카테고리 → 장비 모델 → EQ.
//
// Facets give the option universe (values that actually have documents in
// retention, with doc counts); sem_list gives the fleet join table that links
// the levels together (which models live in which fab, which eqp_id runs which
// model). Narrowing therefore happens client-side against data both dropdown
// sources already have — no extra facets round-trip per pick.
//
// Degradation rule: every constraint that needs the sem_list mapping is
// SKIPPED while sem_list is empty (still loading, or the fetch failed) rather
// than emptying the dropdowns. The static model→category rule keeps working
// regardless. Likewise a facet value missing from sem_list (a retired tool
// still inside retention) stays offered until a pick requires mapping it.

import type { MeasHistFacetValue, MeasHistToolType } from '~/composables/useMeasHistApi'
import type { SemListRow } from '~/composables/useSemListApi'
// Import-free util, so it does not break this module's node:test-runnability.
import { normalizeFab } from './fab.ts'

// Display labels are the filter values ('CD-SEM'), tool types are the wire
// values ('cd-sem'). Exactly one picked category scopes the search to one
// index; zero (or both) means the backend searches both aliases.
export const SKEWVOIR_CATEGORIES = ['CD-SEM', 'HV-SEM'] as const
export type SkewvoirCategory = (typeof SKEWVOIR_CATEGORIES)[number]

export const CATEGORY_TO_TOOL_TYPE: Record<SkewvoirCategory, MeasHistToolType> = {
  'CD-SEM': 'cd-sem',
  'HV-SEM': 'hv-sem'
}

// Mirrors classifyToolType (utils/toolType.ts) / TOOL_SPECS (_tool_specs.py)
// for the two families skewvoir indexes. Local copy because categoryOfModel
// is not the same function as classifyToolType: it returns
// SkewvoirCategory | null and returns null for VeritySEM/Provision, which
// classifyToolType resolves to 'verity-sem' / 'provision'. A mechanical
// import swap would therefore be a behavior regression (AMAT models would
// start passing as a skewvoir category); unifying them needs a narrowing
// map, not an import, and is tracked separately.
export const categoryOfModel = (eqpModelCd: string): SkewvoirCategory | null => {
  if (eqpModelCd.startsWith('CG') || eqpModelCd.startsWith('GT')) return 'CD-SEM'
  if (eqpModelCd.startsWith('TP')) return 'HV-SEM'
  return null
}

export interface CascadeSelections {
  fab: string[]
  category: string[]
  model: string[]
}

export interface CascadedOptions {
  category: MeasHistFacetValue[]
  model: MeasHistFacetValue[]
  eq: MeasHistFacetValue[]
}

const pickedCategories = (values: string[]): Set<SkewvoirCategory> =>
  new Set(values.filter((v): v is SkewvoirCategory => v === 'CD-SEM' || v === 'HV-SEM'))

export const buildCascadedOptions = (
  facets: { model: MeasHistFacetValue[], eq: MeasHistFacetValue[] },
  semRows: SemListRow[],
  picked: CascadeSelections
): CascadedOptions => {
  // The FAB picks come from the facets endpoint and fab_name from sem_list — different DBs,
  // which report casing differently. Both sides are canonicalized so the join still matches.
  const fabs = new Set(picked.fab.map(normalizeFab))
  const categories = pickedCategories(picked.category)
  const models = new Set(picked.model)
  const hasFleet = semRows.length > 0

  // 카테고리 counts are DOC counts (sum of the model facet per family), so the
  // number means the same thing it does on every other dropdown. They are not
  // narrowed by the FAB pick — facets carry no fab×model breakdown, and a
  // count that silently changed meaning would be worse than one that is
  // simply global.
  const docCount = new Map<SkewvoirCategory, number>()
  for (const opt of facets.model) {
    const category = categoryOfModel(opt.value)
    if (category) docCount.set(category, (docCount.get(category) ?? 0) + opt.count)
  }
  // Both families are always offered: hiding one because the fleet table has
  // no current tool for it would also hide retired-tool history.
  const category: MeasHistFacetValue[] = SKEWVOIR_CATEGORIES.map(value => ({
    value,
    count: docCount.get(value) ?? 0
  }))

  // Fleet joins: which fabs a model runs in, and each eqp_id's row.
  const modelFabs = new Map<string, Set<string>>()
  const byEqpId = new Map<string, SemListRow>()
  for (const row of semRows) {
    byEqpId.set(row.eqp_id, row)
    let set = modelFabs.get(row.eqp_model_cd)
    if (!set) modelFabs.set(row.eqp_model_cd, set = new Set())
    set.add(normalizeFab(row.fab_name))
  }

  const model = facets.model.filter((opt) => {
    if (categories.size) {
      const family = categoryOfModel(opt.value)
      if (!family || !categories.has(family)) return false
    }
    if (fabs.size && hasFleet) {
      const inFabs = modelFabs.get(opt.value)
      if (!inFabs || ![...inFabs].some(fab => fabs.has(fab))) return false
    }
    return true
  })

  const eqNeedsMapping = fabs.size > 0 || categories.size > 0 || models.size > 0
  const eq = facets.eq.filter((opt) => {
    if (!eqNeedsMapping || !hasFleet) return true
    const row = byEqpId.get(opt.value)
    if (!row) return false
    if (fabs.size && !fabs.has(normalizeFab(row.fab_name))) return false
    if (categories.size) {
      const family = categoryOfModel(row.eqp_model_cd)
      if (!family || !categories.has(family)) return false
    }
    if (models.size && !models.has(row.eqp_model_cd)) return false
    return true
  })

  return { category, model, eq }
}

// Drop downstream picks the narrowed options no longer offer (e.g. a CD-SEM
// model pick surviving a switch to HV-SEM would silently zero every search).
// Returns null when nothing changed so callers can tell a real prune from a
// no-op and avoid re-triggering their own watchers.
export const pruneCascadedFilters = <T extends { model: string[], eq: string[] }>(
  filters: T,
  options: CascadedOptions
): T | null => {
  const offeredModels = new Set(options.model.map(o => o.value))
  const offeredEqs = new Set(options.eq.map(o => o.value))
  const model = filters.model.filter(v => offeredModels.has(v))
  const eq = filters.eq.filter(v => offeredEqs.has(v))
  if (model.length === filters.model.length && eq.length === filters.eq.length) return null
  return { ...filters, model, eq }
}
