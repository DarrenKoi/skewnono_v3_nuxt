// Measurement-rule engine — pure, framework-free logic.
// Implements grilling decisions D1–D18 (docs/issues/ground_rules/).
// The backend ships RAW data (rules + parameters + annotations); ALL violation
// judgement happens here, client-side, so editing a cap recomputes instantly.

// =================== Types (rule-editor-structure.md §2) ===================

export type RecipeClass = 'Main' | 'Sample'
export type Family = 'Core' | 'Pool' | 'VG_RTC_Cubic'
export type Phase = 't-EV' | 'EV' | 'TV' | 'PV'
export type MemoryClass = 'DRAM' | 'NAND'
export type ParamType = 'WAFER' | 'LEVEL' | 'EDGE' | 'EDGE_EX' | 'OTHER'

/** Name-based override — applies ONLY to OTHER (non-WAFER-family) params (D9). */
export interface NameOverride {
  patterns: string[] // e.g. ['DSPT','WF','WAFER']
  match: 'contains' | 'affix' // affix = prefix OR suffix
  cap: number | null // null = exempt (no limit) — Sample WF/WAFER case
}

export type CapMap = Partial<Record<Exclude<ParamType, 'OTHER'>, number>> & { _other: number }

export interface RuleCell {
  id: string
  selector: {
    fac_id: string
    recipe_class: RecipeClass
    family?: Family
    phase_in?: Phase[] // Core keys on this (D8)
    yield_check?: 'before' | 'after' // Pool keys on this (D8)
    memory_class?: MemoryClass // only EDGE/EDGE_EX-split cells (D11)
  }
  caps: CapMap
  name_overrides: NameOverride[]
}

export interface Parameter {
  name: string
  point_count: number
  /**
   * 이 파라미터 자신이 mother 인가 (idp 의 `Mother_Para`). son 은 mother 와 같은
   * image 에서 자기 cd_value 를 얻으므로 측정 시간(TAT)을 움직이는 것은 mother
   * 수입니다. mother_normal 버킷이 이 플래그로 좁혀집니다
   * (lotHealth.scopeRecipesToBucket).
   *
   * optional 인 것은 룰 검증 테스트가 파라미터를 손으로 만들 때 이 필드를 쓰지
   * 않아도 되게 두었기 때문입니다. 없으면 son 으로 봅니다.
   */
  mother?: boolean
  /**
   * 이 파라미터가 속한 **image definition 묶음**(idp 의
   * `idp_image_info.Region`). 같은 region 인 파라미터들이 한 SEQ 그룹이고, 그
   * 안에서 `mother` 인 하나가 image 의 주인, 나머지는 son 입니다
   * (user-confirmed 2026-08-18). 화면에 "1/8, 2/8, 3/8" 으로 보이는 그 묶음이며,
   * 분모는 `Last_SEQ` 입니다.
   *
   * 판정이 이 값을 보는 이유는 아래 `groupCaps` 에 적어 두었습니다.
   *
   * optional 인 것은 원천에서 **읽지 못할 수 있기** 때문입니다 — 그때는
   * `undefined`/`null` 이고, 묶을 근거가 없으므로 파라미터마다 자기 cap 으로
   * 판정합니다(2026-08-18 이전과 같은 동작).
   */
  region?: number | null
}

/** One recipe as it arrives from the backend (recipe-params dataset). */
export interface RecipeInput {
  lot_cd: string
  recipe_id: string
  fac_id: string
  ctn_desc: string
  prod_catg_cd: string
  recipe_class: RecipeClass
  family: Family
  phase: Phase | null
  memory_class_auto: MemoryClass | 'unknown'
  parameters: Parameter[]
}

/** Manual per-lot annotation (annotations dataset, D4/D7). */
export interface Annotation {
  memory_class?: MemoryClass | null
  yield_check?: 'before' | 'after' | null
}

// =================== Derivation (D3 / D7 / D10) ===================

const STD_TYPES: Exclude<ParamType, 'OTHER'>[] = ['EDGE_EX', 'EDGE', 'WAFER', 'LEVEL']

/** D10 — longest-prefix match; suffix allowed; Class-independent. */
export const deriveType = (name: string): ParamType => {
  const up = (name || '').toUpperCase()
  for (const t of STD_TYPES) if (up.startsWith(t)) return t
  return 'OTHER'
}

/** D3 — VG·RTC·Cubic > Pool > Core. */
export const deriveFamily = (ctnDesc: string): Family => {
  const s = (ctnDesc || '').toLowerCase()
  if (/vertical gate|vertical|rtc|cubic/.test(s)) return 'VG_RTC_Cubic'
  if (/pool/.test(s)) return 'Pool'
  return 'Core'
}

/** D3 — t-EV checked before EV; null → caller applies strict fallback. */
export const derivePhase = (ctnDesc: string): Phase | null => {
  const s = ctnDesc || ''
  if (/\bt-?EV\b/i.test(s)) return 't-EV'
  if (/\bPV\b/i.test(s)) return 'PV'
  if (/\bTV\b/i.test(s)) return 'TV'
  if (/\bEV\b/i.test(s)) return 'EV'
  return null
}

/** D7 — DRAM→DRAM, NAND/FLASH→NAND, Tech/Advanced/absent→unknown (manual). */
export const deriveMemoryClass = (prodCatgCd: string): MemoryClass | 'unknown' => {
  const c = (prodCatgCd || '').toUpperCase()
  if (c === 'DRAM') return 'DRAM'
  if (c === 'NAND' || c === 'FLASH') return 'NAND'
  return 'unknown'
}

// =================== Cap resolution (D9) ===================

const matchName = (name: string, ov: NameOverride): boolean => {
  const up = (name || '').toUpperCase()
  return ov.patterns.some((p) => {
    const P = p.toUpperCase()
    return ov.match === 'contains' ? up.includes(P) : (up.startsWith(P) || up.endsWith(P))
  })
}

/**
 * D9 — type cap wins; name-override only touches OTHER params.
 * Returns the cap, or null = "no limit / exempt" (never a violation).
 */
export const capFor = (param: Parameter, cell: RuleCell): number | null => {
  const type = deriveType(param.name)
  if (type !== 'OTHER') {
    const c = cell.caps[type]
    return c === undefined ? null : c
  }
  for (const ov of cell.name_overrides) {
    if (matchName(param.name, ov)) return ov.cap
  }
  return cell.caps._other
}

// =================== 그룹 cap — SEQ 묶음 (user-confirmed 2026-08-18) ===================

/**
 * region -> **그 그룹 mother 의 cap**. mother 가 없는 region 은 아예 넣지 않습니다.
 *
 * 왜 필요한가. idp 의 한 `Region` 은 image definition 1개이고, 화면에 "1/8,
 * 2/8, 3/8 …" 으로 보이는 그 묶음입니다. 그 안에서 `Mother_Para` 인 하나가
 * image 의 주인이고 son 들은 **그 image 에서** 자기 cd_value 를 꺼냅니다 — 즉
 * 그룹 전체가 한 번의 측정이며, son 을 재는 데 드는 point 는 따로 없습니다.
 *
 * 그래서 son 을 자기 이름의 타입 cap 으로 재면 틀립니다. WAFER mother 가 13
 * point 로 허용되면 같은 image 를 쓰는 CELL_SP·LWR 도 13 이어야 하는데, 이름이
 * OTHER 라는 이유로 `_other`(9)에 걸려 **고칠 수 없는 위반**이 무더기로
 * 잡혔습니다. 룰 자체는 한 번도 바뀐 적이 없고(WAFER 13 / LEVEL 4 는 전 셀
 * 공통), 틀린 것은 "무엇을 무엇으로 재는가" 였습니다.
 *
 * 물려받는 것이 면제보다 나은 이유는 이빨이 남기 때문입니다 — LEVEL(4) mother
 * 의 son 이 13 이면 여전히 위반입니다. 그룹이 통째로 판정 밖으로 나가지 않습니다.
 *
 * `Map` 에 **없음**과 값이 `null`은 다릅니다: 없음은 "이 그룹에 mother 가 없다
 * (물려줄 것이 없음)", `null` 은 "mother 의 cap 이 무제한이며 son 도 무제한".
 */
export const groupCaps = (params: Parameter[], cell: RuleCell): Map<number, number | null> => {
  const caps = new Map<number, number | null>()
  for (const p of params) {
    if (!p.mother || p.region == null) continue
    // 한 region 에 mother 가 둘 이상이면 **먼저 나온 것**을 씁니다. 측정 순서가
    // 곧 SEQ 순서이므로 앞선 쪽이 그 image 의 머리입니다.
    if (!caps.has(p.region)) caps.set(p.region, capFor(p, cell))
  }
  return caps
}

/**
 * 이 파라미터를 실제로 재는 cap. mother 와 "묶일 곳이 없는" 파라미터는 자기
 * cap 이고, son 은 자기 그룹 mother 의 cap 입니다.
 */
export const effectiveCap = (
  param: Parameter,
  cell: RuleCell,
  caps: Map<number, number | null>
): number | null => {
  const own = capFor(param, cell)
  if (param.mother || param.region == null) return own
  // 자기 cap 이 이미 `null` 이면 그룹 cap 을 물려받지 않습니다. `null` 은 D9 의
  // "상한 없음 = 절대 위반 아님" 이고, 그 면제는 b5d8dcdb 가 user-confirmed
  // 2026-08-05 로 확정한 것입니다 — Sample 셀의 `_other` 는 0 이라, DUMMY 가
  // mother 밑에 묶였다는 이유로 0 을 물려받으면 point 1 개짜리 DUMMY 가 다시
  // 자동 위반이 되고, 그것은 recipe 를 고쳐 없앨 수 있는 위반이 아니라 고칠 수
  // 있는 진짜 위반을 목록에서 밀어내는 종류입니다.
  //
  // 집에서는 이 경로가 생기지 않습니다: mock 의 `_assign_regions` 는 Dummy·Align
  // 에 region 을 주지 않지만, office 의 `_param_regions` 는 이름을 가리지 않고
  // 모든 row 에 붙입니다. 면제를 여기서 지키면 두 provider 중 어느 쪽이 region 을
  // 주든 판정이 같아집니다.
  if (own === null) return null
  return caps.has(param.region) ? caps.get(param.region)! : own
}

// =================== Cell resolution (D8 / D14) ===================

export interface MergedRecipe extends Omit<RecipeInput, 'memory_class_auto'> {
  memory_class: MemoryClass | null
  yield_check: 'before' | 'after' | null
}

/** Merge manual annotation over backend-derived values (D4/D7). */
export const applyAnnotation = (recipe: RecipeInput, ann?: Annotation): MergedRecipe => {
  const auto = recipe.memory_class_auto === 'unknown' ? null : recipe.memory_class_auto
  const { memory_class_auto: _omit, ...rest } = recipe
  // D7 — VG·RTC·Cubic provisionally reduces to DRAM-side when no explicit class
  // is set (manual annotation still wins; backend auto-derivation still wins).
  const vgFallback = rest.family === 'VG_RTC_Cubic' ? 'DRAM' : null
  return {
    ...rest,
    memory_class: ann?.memory_class ?? auto ?? vgFallback,
    yield_check: ann?.yield_check ?? null
  }
}

const selectorMatches = (cell: RuleCell, r: MergedRecipe): boolean => {
  const s = cell.selector
  if (s.fac_id !== r.fac_id) return false // D15 — fab is a real axis
  if (s.recipe_class !== r.recipe_class) return false
  if (s.family != null && s.family !== r.family) return false
  if (s.phase_in && !(r.phase && s.phase_in.includes(r.phase))) return false
  if (s.yield_check && s.yield_check !== r.yield_check) return false
  if (s.memory_class && s.memory_class !== r.memory_class) return false
  return true
}

export type CellResolution
  = | { kind: 'cell', cell: RuleCell }
    | { kind: 'gray', gray: 'A' | 'B', reason: string }

/** D8 + D14 — find the cell, or classify why it's gray (A=룰미정, B=어노테이션미설정). */
export const resolveRuleCell = (r: MergedRecipe, cells: RuleCell[]): CellResolution => {
  const byClassFam = cells.filter(
    c => c.selector.fac_id === r.fac_id // D15 — gray detection is fab-scoped
      && c.selector.recipe_class === r.recipe_class
      && (c.selector.family == null || c.selector.family === r.family)
  )
  const match = byClassFam.find(c => selectorMatches(c, r))
  if (match) return { kind: 'cell', cell: match }

  const needsMem = byClassFam.some(c => c.selector.memory_class) && r.memory_class == null
  const needsYield = byClassFam.some(c => c.selector.yield_check) && r.yield_check == null
  if (needsMem) return { kind: 'gray', gray: 'B', reason: 'memory_class 미설정' }
  if (needsYield) return { kind: 'gray', gray: 'B', reason: 'yield_check 미설정' }
  return { kind: 'gray', gray: 'A', reason: '룰 미정' }
}

// =================== Evaluation (D5 / D14) ===================

export interface ParamResult { name: string, point_count: number, type: ParamType, cap: number | null, violation: boolean }

export interface RecipeResult {
  recipe_id: string
  total_params: number
  violation_params: ParamResult[]
  pass: boolean
  gray: 'A' | 'B' | null
  gray_reason?: string
  results: ParamResult[]
}

/** D5 — point_count ≤ cap; under-measuring is never a violation. */
export const evaluateRecipe = (recipe: MergedRecipe, res: CellResolution): RecipeResult => {
  if (res.kind === 'gray') {
    return {
      recipe_id: recipe.recipe_id,
      total_params: recipe.parameters.length,
      violation_params: [],
      pass: true, // conservative: gray ≠ violation (D14)
      gray: res.gray,
      gray_reason: res.reason,
      results: recipe.parameters.map(p => ({ name: p.name, point_count: p.point_count, type: deriveType(p.name), cap: null, violation: false }))
    }
  }
  // son 은 mother 와 같은 image 를 쓰므로 자기 타입 cap 이 아니라 그룹 mother 의
  // cap 으로 잽니다 (groupCaps 참고).
  const caps = groupCaps(recipe.parameters, res.cell)
  const results = recipe.parameters.map((p): ParamResult => {
    const cap = effectiveCap(p, res.cell, caps)
    return { name: p.name, point_count: p.point_count, type: deriveType(p.name), cap, violation: typeof cap === 'number' && p.point_count > cap }
  })
  const violation_params = results.filter(r => r.violation)
  return {
    recipe_id: recipe.recipe_id,
    total_params: recipe.parameters.length,
    violation_params,
    pass: violation_params.length === 0,
    gray: null,
    results
  }
}

// =================== Lot roll-up (D14) ===================

export type HealthLevel = 'green' | 'yellow' | 'red'

/** D16 — fab-level signal boundaries (lot roll-up ratio), shared on RuleVersion. */
export interface Thresholds { yellow_at: number, red_at: number }

/** D16/D18 — seed defaults; editable & versioned, but excluded from cap what-if. */
export const SEED_THRESHOLDS: Thresholds = { yellow_at: 0.1, red_at: 0.2 }

/** D12/D16 — one fab's current rule version: cells + shared thresholds + attribution.
 * The container type for what GET /rules ships (rule-editor-structure.md §2). */
export interface RuleVersion {
  fac_id: string
  version: number
  edited_by: string
  edited_at: string
  cells: RuleCell[]
  thresholds: Thresholds
}

/** D17 — thresholds are injected (no longer hardcoded); seed used when absent. */
export const classifyHealth = (
  violationRatio: number,
  thresholds: Thresholds = SEED_THRESHOLDS
): HealthLevel =>
  violationRatio < thresholds.yellow_at
    ? 'green'
    : violationRatio < thresholds.red_at
      ? 'yellow'
      : 'red'

export interface LotHealth {
  lot_cd: string
  total_recipes: number
  /** gray 를 뺀 실제 판정 대상 수 — violation_ratio 의 분모입니다. */
  judged_recipes: number
  violation_recipes: number
  /** 판정한 recipe 가 하나도 없으면 null — 0 이 아닙니다. */
  violation_ratio: number | null
  /**
   * 판정한 recipe 가 하나도 없으면 null.
   *
   * 예전에는 non-nullable 이었고, 전부 gray 인 lot 이 ratio 0 → classifyHealth(0)
   * → **green** 으로 나왔습니다. 아무것도 못 본 lot 과 다 보고 깨끗한 lot 이 같은
   * 색이었다는 뜻입니다. 판정 없음은 색이 아니라 값의 부재로 표현합니다.
   */
  health: HealthLevel | null
  recipes: RecipeResult[]
}

/** End-to-end: raw recipes + rules + annotation → per-recipe results + lot health. */
export const evaluateLot = (
  lot_cd: string,
  recipes: RecipeInput[],
  cells: RuleCell[],
  annotation?: Annotation,
  thresholds: Thresholds = SEED_THRESHOLDS
): LotHealth => {
  const results = recipes.map((r) => {
    const merged = applyAnnotation(r, annotation)
    return evaluateRecipe(merged, resolveRuleCell(merged, cells))
  })
  // gray recipes are excluded from the denominator (conservative, D14)
  const evaluated = results.filter(r => r.gray == null)
  const violation_recipes = evaluated.filter(r => !r.pass).length
  // 판정한 recipe 가 없으면 비율도 색도 없습니다. 예전에는 0 으로 떨어뜨렸고
  // classifyHealth(0) 이 green 이라, 전부 gray 인 lot 이 "깨끗함" 으로 보였습니다.
  const judged = evaluated.length
  const violation_ratio = judged ? violation_recipes / judged : null
  return {
    lot_cd,
    total_recipes: recipes.length,
    judged_recipes: judged,
    violation_recipes,
    violation_ratio,
    health: violation_ratio === null ? null : classifyHealth(violation_ratio, thresholds),
    recipes: results
  }
}
