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

// D3 — family/phase 는 여기서 파생하지 않습니다. backend 가 **device 의**
// ctn_desc 에서 뽑아 `RecipeInput.family`/`.phase` 컬럼으로 실어 보내고
// (office_example.py `_family_of`/`_phase_of`), 프런트는 소비만 합니다.
//
// 예전에 여기 있던 `deriveFamily`/`derivePhase` 사본은 지웠습니다. 호출자가
// 테스트뿐이었던 데다, `RecipeInput.ctn_desc` 가 두 provider 에서 서로 다른
// 것을 뜻하기 때문입니다 — mock 은 device 설명문이지만 사무실은 그 recipe 가
// 걸린 **공정 스텝 이름**(oper_desc)입니다. 그래서 누가 그 사본을
// `recipe.ctn_desc` 에 쓰면 집에서는 맞고 사무실에서는 전부 Core 로
// 무너집니다. 파서를 office 어댑터 한 곳에만 두어 그 함정을 없앴습니다.

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
 * cap 이 **어디서 왔는가**. `_other` 만이 "달리 볼 근거가 없어서 쓴 값" 입니다.
 *
 * 이 구분이 값 자체만큼 중요한 이유는 그룹 상속(아래 `effectiveCap`)이 오직
 * fallback 에만 걸려야 하기 때문입니다. 출처를 버리고 숫자만 넘기면 상속하는
 * 쪽이 "이 cap 이 fallback 이었나" 를 이름으로 되짚어야 하고, 그 되짚기는
 * 번번이 한 경로씩 빠뜨렸습니다.
 */
export type CapSource = 'type' | 'name' | 'fallback'

/**
 * D9 — type cap wins; name-override only touches OTHER params.
 * Returns the cap, or null = "no limit / exempt" (never a violation).
 *
 * `type` 을 받는 것은 호출자가 이미 알고 있을 때 `deriveType` 을 다시 돌리지
 * 않기 위해서입니다 — 사무실 규모(한 fab 판정에 파라미터 약 1.4M)에서 이
 * 한 번이 전체 판정 시간의 10% 대입니다.
 */
export const resolveCap = (
  param: Parameter,
  cell: RuleCell,
  type: ParamType = deriveType(param.name)
): { cap: number | null, source: CapSource } => {
  if (type !== 'OTHER') {
    const c = cell.caps[type]
    return { cap: c === undefined ? null : c, source: 'type' }
  }
  for (const ov of cell.name_overrides) {
    if (matchName(param.name, ov)) return { cap: ov.cap, source: 'name' }
  }
  return { cap: cell.caps._other, source: 'fallback' }
}

/** D9 cap 만 필요할 때. 출처까지 필요하면 :func:`resolveCap`. */
export const capFor = (param: Parameter, cell: RuleCell, type?: ParamType): number | null =>
  resolveCap(param, cell, type).cap

// =================== 그룹 cap — SEQ 묶음 (user-confirmed 2026-08-18) ===================

/**
 * 파라미터가 image 그룹 안에서 맡는 역할.
 *
 *   'mother' — 그 image 의 주인(idp 의 `Mother_Para`).
 *   'son'    — **mother 가 실제로 있는** region 의 나머지. mother 의 측정에 얹혀
 *              가므로 cap 도 물려받고(`effectiveCap`), `judgeSons: false` 가 빼는
 *              것도 정확히 이 파라미터입니다.
 *   null     — 묶을 근거가 없음. region 을 읽지 못했거나, region 은 있는데 그 안에
 *              mother 가 없는 경우입니다. 원천이 mother 를 기록하지 않은 recipe 는
 *              모든 파라미터가 `mother: false` 인데, 그것을 son 이라 부르면 판정은
 *              빼지 않는 행을 화면과 파일이 son 이라 소개하게 됩니다.
 *
 * 화면(DrillParamRows)·CSV·워크북이 "mother 인가 son 인가" 를 적을 때 쓰는 술어이자
 * 판정이 son 을 뺄 때 쓰는 술어입니다 — 둘이 한 함수라야 "son 판정 제외" 가 붙지
 * 않는 행에 son 이 적히는 일이 없습니다.
 */
export type ParamRole = 'mother' | 'son' | null

/** mother 가 한 명이라도 있는 region 의 집합. `groupCaps` 의 키와 같은 집합입니다. */
export const motherRegions = (params: Parameter[]): Set<number> => {
  const regions = new Set<number>()
  for (const p of params) if (p.mother && p.region != null) regions.add(p.region)
  return regions
}

export const paramRole = (p: Parameter, regions: ReadonlySet<number>): ParamRole =>
  p.mother ? 'mother' : (p.region != null && regions.has(p.region)) ? 'son' : null

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
 * cap 이고, son 은 **자기 cap 이 `_other` fallback 일 때만** mother 의 cap 을
 * 물려받습니다.
 *
 * 상속이 fallback 에만 걸리는 이유. `_other`(9)는 "이름으로 타입을 정하지 못해
 * 달리 볼 근거가 없을 때 쓰는 값" 입니다 — CELL_SP·LWR 처럼요. 그런 파라미터가
 * mother 의 image 를 함께 쓴다면 mother 의 13 이 `_other` 보다 나은 근거이고,
 * 그것이 2026-08-18 상속이 겨냥한 것입니다(그 전에는 `_other` 에 걸려 고칠 수
 * 없는 위반이 되고 있었습니다).
 *
 * 반대로 룰이 **값으로 정해 둔** cap — 타입 cap(WAFER/LEVEL/EDGE/EDGE_EX)과
 * name_override — 은 상속이 어느 방향으로도 덮지 않습니다. EDGE 가 그 이유를
 * 가장 잘 보여 줍니다: EDGE 상한(8/10)은 "가장자리를 몇 점 재느냐" 라는 **고유의
 * 룰**이라 WAFER 파라미터와 다르게 판정되어야 합니다 (user-confirmed
 * 2026-08-21). WAFER mother 의 image 에 얹혔다는 이유로 13 이 되면 EDGE 룰이
 * 사라집니다.
 *
 * 내리는 방향이 만든 위반은 전부 **고칠 수 없는 위반**이었습니다. 셋 다 실제로
 * 있었습니다.
 *
 *   타입 cap: LEVEL(4) mother 밑의 WAFER son 이 13 point 를 재면 위반이 되고,
 *     룰 화면은 같은 파라미터를 두고 "상한 13" 이라고 적습니다.
 *   name_override(숫자): `CD_WF_1` 은 DSPT/WF/WAFER contains 로 13 을 받는데
 *     타입이 OTHER 라, 타입만 보는 방어를 그대로 통과해 4 로 내려갔습니다.
 *   name_override(면제, cap=null): Sample 셀의 `_other` 는 0 이라, DUMMY 가
 *     mother 밑에 묶였다는 이유로 0 을 물려받으면 point 1 개짜리 DUMMY 가 다시
 *     자동 위반이 됩니다 (b5d8dcdb, user-confirmed 2026-08-05).
 *
 * 앞의 둘은 타입을 특수 케이스로, 셋째는 `null` 을 특수 케이스로 막던 자리였고
 * 특수 케이스마다 한 경로씩 샜습니다. 출처 하나로 물으면 셋이 함께 닫힙니다.
 *
 * 집에서는 내리는 경로가 생기지 않습니다: mock 은 Dummy·Align 에 region 을 주지
 * 않고 WAFER son 을 늘 mother 없는 region 에 넣습니다. office 의
 * `_param_regions` 는 이름을 가리지 않고 모든 row 에 region 을 붙입니다.
 *
 * 이빨은 그대로입니다 — LEVEL(4) mother 의 CELL_SP son 은 `_other` 가 출처라
 * 4 를 물려받고, 13 이면 여전히 위반입니다.
 *
 * 올리는 방향도 함께 좁아집니다. EDGE son 이 WAFER mother 의 13 을 받지 못하게
 * 되어 홈 기준 recipe 6,208 건(34.2% -> 37.2%)이 새로 위반으로 잡힙니다 — 없던
 * 위반이 생기는 것이 아니라, 상속이 가리고 있던 EDGE 룰 위반이 드러나는 것입니다.
 */
export const effectiveCap = (
  param: Parameter,
  cell: RuleCell,
  caps: Map<number, number | null>,
  type?: ParamType
): number | null => {
  const { cap, source } = resolveCap(param, cell, type)
  if (param.mother || param.region == null || source !== 'fallback') return cap
  return caps.has(param.region) ? caps.get(param.region)! : cap
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
  // D3 — Pool 은 phase 를 이깁니다. ctn_desc 에 Pool 과 phase 가 함께 들어 있는
  // device 가 실제로 있고("DRAM Pool제 (@Spica PV)", user-confirmed 2026-08-25),
  // 그때 판정 기준은 Pool 입니다. phase 값 자체는 payload 에 그대로 남기고
  // (Pool 제품도 t-EV→PV 를 거치므로 — CONTEXT.md §Product Family), 여기 판정에서만
  // 무시합니다. Pool 은 오직 yield_check 로만 키잉됩니다(D8).
  //
  // 이 줄이 없으면 불변식이 룰 **데이터**에만 있습니다 — 지금 Pool cell 이 이기는
  // 것은 `rules.py` 가 Pool cell 에 `phase_in` 을 안 달아 둔 덕이지 판정 로직이
  // 아닙니다. `resolveRuleCell` 은 배열 첫 매칭을 집으므로, 나중에 누가 family
  // 없는 phase cell 을 seed 에 하나 끼워 넣으면 Pool recipe 의 EDGE_EX 상한이
  // 0 에서 조용히 벌어집니다.
  if (s.phase_in && r.family === 'Pool') return false
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

export interface ParamResult {
  name: string
  point_count: number
  type: ParamType
  cap: number | null
  /**
   * 이 파라미터가 판정 대상이었는가. `judgeSons: false` 인 son 과 gray recipe 의
   * 파라미터가 `false` 입니다.
   *
   * `violation: false` 와 구별되어야 합니다 — 하나는 "재 봤더니 상한 안" 이고
   * 다른 하나는 "아예 안 쟀다" 입니다. 이 둘이 한 값이면 화면이 준수한
   * 파라미터와 판정에서 뺀 파라미터를 똑같이 그립니다 (deviceDrill 의 `note`).
   */
  judged: boolean
  /**
   * point_count 가 cap 을 넘었는가 — **판정 대상이었는지와 무관하게**.
   *
   * `violation` 은 `judged && over_cap` 입니다. 둘을 나눠 두는 이유는 화면과
   * 파일이 "판정에서 뺐지만 상한은 넘긴" 파라미터를 그렇게 말해야 하기
   * 때문입니다 — 그 술어를 소비처가 각자 다시 쓰면(`!p.judged &&
   * p.point_count > p.cap`) 판정 규칙이 세 곳에 생기고, 상한의 정의가 바뀌는
   * 날 한 곳만 고쳐집니다. cap 이 없으면(면제) 언제나 false 입니다.
   */
  over_cap: boolean
  violation: boolean
  /** mother / son / 묶을 근거 없음 — `paramRole`. 판정이 아니라 recipe 의 사실이라 gray 에도 실립니다. */
  role: ParamRole
}

/**
 * 판정 범위·기준 — `evaluateRecipe`/`evaluateLot` 의 꼬리 인자.
 *
 * `judgeSons: false` 면 son 파라미터를 **위반 판정에서만** 뺍니다. 근거는
 * 상속과 같습니다 — son 은 mother 와 한 image 를 쓰므로 son 을 재는 데 드는
 * 측정 point 가 따로 없고, 그래서 "상한이 겨냥한 대상이 아니다" 라고 볼 여지가
 * 있습니다. 어느 쪽이 옳은지는 도메인 판단이라 코드가 정하지 않습니다.
 *
 * 여기서 son 은 **mother 가 있는 region 에 속한** 파라미터입니다 — `mother`
 * 플래그가 false 인 것만으로는 부족합니다(`evaluateRecipe` 의 주석 참고).
 *
 * 빼는 것은 파라미터이지 recipe 가 아닙니다 — 분모(`judged_recipes`)는 그대로고
 * `cap` 도 계속 계산해 돌려주므로, 화면은 `judged` 와 함께 "상한 9 인데 13,
 * 판정 제외" 를 말할 수 있습니다.
 */
export interface JudgeOptions {
  judgeSons?: boolean
  annotation?: Annotation
  thresholds?: Thresholds
}

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
export const evaluateRecipe = (
  recipe: MergedRecipe,
  res: CellResolution,
  opts: JudgeOptions = {}
): RecipeResult => {
  const regions = motherRegions(recipe.parameters)
  if (res.kind === 'gray') {
    return {
      recipe_id: recipe.recipe_id,
      total_params: recipe.parameters.length,
      violation_params: [],
      pass: true, // conservative: gray ≠ violation (D14)
      gray: res.gray,
      gray_reason: res.reason,
      results: recipe.parameters.map(p => ({ name: p.name, point_count: p.point_count, type: deriveType(p.name), cap: null, judged: false, over_cap: false, violation: false, role: paramRole(p, regions) }))
    }
  }
  // son 은 mother 와 같은 image 를 쓰므로 자기 타입 cap 이 아니라 그룹 mother 의
  // cap 으로 잽니다 (groupCaps 참고).
  const caps = groupCaps(recipe.parameters, res.cell)
  const judgeSons = opts.judgeSons ?? true
  const results = recipe.parameters.map((p): ParamResult => {
    // 타입은 여기서 한 번만 구해 `effectiveCap` 까지 넘깁니다 — 사무실 규모에서
    // 파라미터당 `deriveType` 한 번이 판정 시간의 10% 대입니다.
    const type = deriveType(p.name)
    const cap = effectiveCap(p, res.cell, caps, type)
    // "son" 은 **mother 가 실제로 있는 그룹에 속한** 파라미터입니다. `mother`
    // 플래그가 false 라는 것만으로는 부족합니다 — 원천이 mother 를 기록하지 않은
    // recipe 에서는 모든 파라미터가 false 이고, 그것은 "son" 이 아니라 "묶을
    // 근거가 없음" 입니다. 집 mock 만 봐도 판정 대상의 15.2%(31,021건)가 mother
    // 없는 recipe 이고, 그 조건을 빼면 토글을 끌 때 그 recipe 들의 위반
    // 13,755 건이 통째로 사라집니다 — 독립적으로 잰 파라미터까지 함께.
    //
    // `effectiveCap` 이 region 없는 파라미터를 자기 cap 으로 재는 것과 같은
    // 원칙이고, 실제로 같은 술어입니다: 상속이 걸릴 수 있는 파라미터가 곧
    // "mother 의 측정에 얹혀 가는" 파라미터입니다.
    const role = paramRole(p, regions)
    const judged = judgeSons || role !== 'son'
    const over_cap = typeof cap === 'number' && p.point_count > cap
    return { name: p.name, point_count: p.point_count, type, cap, judged, over_cap, violation: judged && over_cap, role }
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
  opts: JudgeOptions = {}
): LotHealth => {
  const thresholds = opts.thresholds ?? SEED_THRESHOLDS
  const results = recipes.map((r) => {
    const merged = applyAnnotation(r, opts.annotation)
    return evaluateRecipe(merged, resolveRuleCell(merged, cells), opts)
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
