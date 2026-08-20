// LOT 단위 health — 비교 페이지의 요약 표가 읽는 판정.
//
// 이 모듈이 대체한 것: 예전에는 useLotHealthMock.ts 가 프런트엔드 안에 cap 표를
// 직접 들고 있었습니다. 그 표는 para_16/13/9/5 **티어별** 상한이었는데, 실제 룰은
// 그런 축이 아닙니다 — 파라미터 **종류별**(WAFER/LEVEL/EDGE/EDGE_EX/_other) 상한을
// recipe 하나하나에 적용합니다. 두 체계는 같은 것을 재던 게 아니라 서로 다른 질문에
// 답하고 있었습니다.
//
// 이제 판정은 서버가 주는 룰(GET /cdsem/device-statistics/rules)과 이미 검증된
// ruleEngine.evaluateLot 이 합니다. 이 모듈은 그 결과를 요약 행에 붙이는 얇은 층입니다.
//
// 값 import 는 상대 경로 + 확장자로 유지합니다 — app/utils 관례대로 node --test 가
// 그대로 실행합니다. **타입 전용** import 는 alias(`~/`)여도 안전합니다: Node 가
// 타입을 지운 뒤 실행하므로 해석 자체를 하지 않습니다 (ruleMatrix.ts 와 같은 방식).
import {
  evaluateLot,
  type HealthLevel,
  type JudgeOptions,
  type RecipeInput,
  type RuleCell,
  type Thresholds
} from './ruleEngine.ts'
import type { SummaryRow } from '~/composables/useRecipeStatisticsApi'

/** 한 fab 의 룰 묶음. `null` 은 그 fab 에 룰이 없다는 뜻입니다. */
export interface RuleSet {
  cells: RuleCell[]
  thresholds: Thresholds
}

/**
 * `judged` — 룰이 있어 판정한 lot.
 * `no-rules` — 이 fab 에 룰 자체가 없음. M 계열이 그렇습니다(D22 로 폐기).
 *   지어낸 cap 으로 색을 칠하지 않고 판정 없음을 그대로 말합니다.
 */
export type VerdictKind = 'judged' | 'no-rules'

export interface LotVerdict {
  kind: VerdictKind
  /** `no-rules` 이면 null — 색이 없는 것과 초록은 다릅니다. */
  health: HealthLevel | null
  violation_ratio: number | null
  violation_recipes: number
  /** 비율의 분모 — gray 를 뺀 실제 판정 대상 수. */
  judged_recipes: number
  /** 선택된 버킷 안의 recipe 수. */
  total_recipes: number
  gray_recipes: number
  /** "memory_class 미설정" 등 사유별 건수. 툴팁이 그대로 보여줍니다. */
  gray_reasons: Record<string, number>
  /**
   * 판정 외 job(_*CDU/_FULL/_HALF/_MTX) 건수. total_recipes 에 **포함되지 않고**
   * coverage 에도 영향이 없습니다 — 툴팁이 알려주기 위한 집계일 뿐입니다.
   */
  exempt_recipes: number
  /** judged / total. 0 이면 아무것도 판정하지 못했습니다. */
  coverage: number
}

/** `lot_cd`+`recipe_id` 한 쌍의 키. 버킷 필터가 이 키로 좁힙니다. */
export const recipeKey = (lotCd: string, recipeId: string): string =>
  `${lotCd}\u0000${recipeId}`

// 특수 측정 job. recipe 이름에 이 토큰이 **들어 있으면** CDU·full/half-map 측정
// job 입니다. 웨이퍼를 통째로 훑는 것이 목적이라 **측정 규모가 정상 recipe 와
// 다른 차원**이고, 그래서 두 분석 모두에서 빠집니다.
//
//   판정(cap) — gray(판정 보류 — 분모에 남아 coverage 를 낮춤)와 달리 분자·분모
//               **모두**에서 빠집니다. 애초에 판정 범위 밖인 recipe 입니다.
//   outlier   — 중앙값 기준선에서도, 초과 표시 대상에서도 빠집니다
//               (outlierDetect.ts). 남겨 두면 이 job 들의 큰 point_count 가
//               기준선을 끌어올려 정상 recipe 의 진짜 과다 측정을 가립니다.
//
// CDU 쪽은 **목록이 아니라 패턴**입니다 — "_*CDU" 면 전부입니다 (user-confirmed
// 2026-08-05). 앞 글자는 어떤 map 을 재는지를 뜻할 뿐이고(W=wafer, F=field,
// B=…), 종류는 늘 수 있습니다. _WCDU/_FCDU 를 하나씩 적어 두었더니 _BCDU 가
// 그대로 새어 나왔습니다 — 접미사를 열거하는 방식 자체가 틀린 모양이었습니다.
// _FULL/_HALF/_MTX 는 CDU 가 아닌 별개의 job 이라 계속 이름으로 답니다
// (_MTX user-confirmed 2026-08-05).
//
// **끝에 고정하지 않습니다** — 실물에 "_BCDU_NEW" 처럼 토큰 뒤에 꼬리가 더
// 붙는 이름이 있습니다 (user-confirmed 2026-08-11). 이름의 끝을 보는 규칙은 그
// 이름을 정상 recipe 로 흘려보냈습니다. 이 job 을 가리키는 것은 이름의 위치가
// 아니라 토큰 자체이므로, 토큰이 어디에 있든 잡습니다.
//
// 방향을 이렇게 잡은 이유는 두 오판의 값이 다르기 때문입니다. 놓치면(under-match)
// 웨이퍼 전면 job 의 큰 point_count 가 중앙값 기준선에 섞여 정상 recipe 의 진짜
// 과다 측정을 가립니다. 넘겨 잡으면(over-match) recipe 한 건이 판정 범위에서
// 빠지고 툴팁의 특수 job 건수에 잡혀 눈에 보입니다 — 조용히 틀리지 않습니다.
const EXEMPT_JOB_TOKEN = /(_[A-Z]*CDU|_FULL|_HALF|_MTX)/i

/** recipe 이름에 특수 job 토큰("_*CDU"/_FULL/_HALF/_MTX)이 들어 있는가. */
export const isExemptJob = (recipeId: string): boolean =>
  EXEMPT_JOB_TOKEN.test((recipeId || '').trim())

/**
 * recipe-params 를 선택된 버킷의 범위로 좁힙니다 — **두 축을 한 번에**.
 *
 * 1. recipe 축: `bucketKeys` 에 있는 recipe 만. 요약 행은 버킷 단위인데
 *    recipe-params 에는 버킷 축이 없으므로, 좁히지 않으면 버킷을 바꿔도 health
 *    만 그대로인 모순이 생깁니다. recipe_id 로 좁힐 수 있는 것은 그것이 표면을
 *    가로지르는 조인 키이기 때문입니다 (docs/datatables/idp_ver.txt L55).
 * 2. 파라미터 축: `motherOnly` 면 mother 파라만. mother_normal 은 스텝을 더
 *    좁히는 버킷이 아니라 **한 단계 아래로 들어가는** 버킷이기 때문입니다.
 *
 * 이 함수가 따로 있는 이유는 소비처가 둘이기 때문입니다 — `buildLotVerdicts`
 * (health/violations/판정범위)와 `buildDeviceOutliers`(중앙값/outlier)가 **같은**
 * 배열을 받아야 표 한 행의 열들이 서로 다른 모수집단을 말하지 않습니다. 각자
 * 좁히게 두면 언젠가 한쪽만 고쳐집니다.
 *
 * 순수 함수라 `node --test` 가 그대로 실행합니다 — 페이지 컴포넌트 안에 두면
 * 테스트가 볼 수 없습니다.
 */
export const scopeRecipesToBucket = (
  recipes: RecipeInput[],
  bucketKeys: Set<string>,
  motherOnly: boolean
): RecipeInput[] => {
  const scoped: RecipeInput[] = []
  for (const recipe of recipes) {
    if (!bucketKeys.has(recipeKey(recipe.lot_cd, recipe.recipe_id))) continue
    scoped.push(
      motherOnly
        ? { ...recipe, parameters: recipe.parameters.filter(p => p.mother) }
        : recipe
    )
  }
  return scoped
}

const emptyVerdict = (): LotVerdict => ({
  kind: 'no-rules',
  health: null,
  violation_ratio: null,
  violation_recipes: 0,
  judged_recipes: 0,
  total_recipes: 0,
  gray_recipes: 0,
  gray_reasons: {},
  exempt_recipes: 0,
  coverage: 0
})

/**
 * lot 별 판정.
 *
 * `bucketKeys` 는 선택된 버킷에 속한 recipe 의 키 집합입니다. 요약 행은 버킷
 * 단위인데 recipe-params 는 버킷 축이 없으므로, 이걸로 좁히지 않으면 버킷을
 * 바꿔도 health 만 그대로인 모순이 생깁니다. `null` 이면 좁히지 않습니다.
 *
 * recipe_id 로 좁힐 수 있는 것은 그것이 표면을 가로지르는 조인 키이기 때문입니다
 * (docs/datatables/idp_ver.txt L55).
 */
export const buildLotVerdicts = (
  recipeParams: RecipeInput[],
  rulesByFab: Record<string, RuleSet | null>,
  bucketKeys: Set<string> | null = null,
  opts: JudgeOptions = {}
): Map<string, LotVerdict> => {
  const byLot = new Map<string, RecipeInput[]>()
  const exemptByLot = new Map<string, number>()

  for (const row of recipeParams) {
    if (bucketKeys && !bucketKeys.has(recipeKey(row.lot_cd, row.recipe_id))) continue
    // 판정 외 job 은 분자·분모 어디에도 들어가지 않습니다 — 건수만 세어 툴팁이
    // "빠진 게 아니라 범위 밖" 임을 말할 수 있게 합니다.
    if (isExemptJob(row.recipe_id)) {
      exemptByLot.set(row.lot_cd, (exemptByLot.get(row.lot_cd) ?? 0) + 1)
      continue
    }
    const bucket = byLot.get(row.lot_cd)
    if (bucket) bucket.push(row)
    else byLot.set(row.lot_cd, [row])
  }

  const verdicts = new Map<string, LotVerdict>()

  for (const [lotCd, recipes] of byLot) {
    const facId = recipes[0]?.fac_id ?? ''
    const rules = rulesByFab[facId] ?? null

    // 룰이 없는 fab 은 판정하지 않습니다. evaluateLot 에 빈 cells 를 넘기면 전부
    // gray 로 "판정했으나 아무것도 못 봤다" 가 되어, 룰이 없다는 사실과 룰은
    // 있는데 어노테이션이 없다는 사실이 한 값으로 뭉갭니다.
    if (!rules || rules.cells.length === 0) {
      verdicts.set(lotCd, {
        ...emptyVerdict(),
        total_recipes: recipes.length,
        exempt_recipes: exemptByLot.get(lotCd) ?? 0
      })
      continue
    }

    const health = evaluateLot(lotCd, recipes, rules.cells, undefined, rules.thresholds, opts)

    // 사유별 gray 집계만 여기서 합니다 — 분모(judged_recipes)는 엔진이 이미
    // 계산했습니다. 다시 세면 같은 분모의 정의가 둘이 됩니다.
    const grayReasons: Record<string, number> = {}
    for (const recipe of health.recipes) {
      if (recipe.gray == null) continue
      const reason = recipe.gray_reason ?? '룰 미정'
      grayReasons[reason] = (grayReasons[reason] ?? 0) + 1
    }

    const { total_recipes: total, judged_recipes: judged } = health

    verdicts.set(lotCd, {
      // 판정한 recipe 가 하나도 없으면 룰이 있어도 "판정 없음" 입니다. 예전에는
      // fab 에 룰이 없는 경우만 잡았고, 룰은 있는데 전부 gray 인 lot 은 ratio 0
      // → green 으로 새어 나왔습니다.
      kind: health.health === null ? 'no-rules' : 'judged',
      health: health.health,
      violation_ratio: health.violation_ratio,
      violation_recipes: health.violation_recipes,
      judged_recipes: judged,
      total_recipes: total,
      gray_recipes: total - judged,
      gray_reasons: grayReasons,
      exempt_recipes: exemptByLot.get(lotCd) ?? 0,
      coverage: total === 0 ? 0 : judged / total
    })
  }

  // 전 recipe 가 판정 외 job 인 lot 은 byLot 에 아예 없습니다. verdict 를 빈
  // 손으로 두면 "0 / 0" 이 데이터 유실처럼 읽히므로, 판정 외 건수만 실은 verdict
  // 를 만들어 툴팁이 사유를 말하게 합니다.
  for (const [lotCd, exempt] of exemptByLot) {
    if (verdicts.has(lotCd)) continue
    verdicts.set(lotCd, { ...emptyVerdict(), exempt_recipes: exempt })
  }

  return verdicts
}

/** 정렬용 순위 — 붉을수록 앞, 판정 없음은 항상 맨 뒤. */
export const verdictSortValue = (verdict: LotVerdict | undefined): number => {
  if (!verdict || verdict.kind === 'no-rules' || verdict.health == null) return 100
  const rank: Record<HealthLevel, number> = { red: 0, yellow: 1, green: 2 }
  // 같은 색 안에서는 위반 비율이 높은 쪽이 먼저입니다.
  return rank[verdict.health] - (verdict.violation_ratio ?? 0) / 10
}

// ── lot 단위 개발 단계 칩 ────────────────────────────────────────────────
// recipe 하나하나의 family/phase 는 backend 가 주지만 **lot 안에서 섞입니다** —
// 한 lot 이 Core/Pool/VG 와 t-EV/EV/TV/PV 를 모두 갖습니다. 그래서 이 칩은
// 여전히 lot 단위 라벨인 ctn_desc 에서 읽습니다. cap 선택에는 더 이상 쓰이지
// 않고(그건 서버 룰이 합니다), 표를 훑을 때의 식별자로만 남습니다.

export type DevStage = 'EV' | 'TV' | 'PV' | 'Pool' | '?'

const STAGE_PATTERNS: Array<{ stage: DevStage, regex: RegExp }> = [
  { stage: 'PV', regex: /\bPV\b|\bP\.?V\b|\bpv\b/ },
  { stage: 'EV', regex: /\bEV\b|\bE\.?V\b|\bev\b/ },
  { stage: 'TV', regex: /\bTV\b|\bT\.?V\b|\btv\b/ },
  { stage: 'Pool', regex: /\bPool\b|\bpool\b|\bPOOL\b/ }
]

export const extractStage = (ctnDesc: string | undefined): DevStage => {
  if (!ctnDesc) return '?'
  for (const { stage, regex } of STAGE_PATTERNS) {
    if (regex.test(ctnDesc)) return stage
  }
  return '?'
}

/** 요약 행에 덧붙는 필드. 화면 컴포넌트가 읽는 것은 이 셋뿐입니다. */
export interface LotHealthFields {
  dev_stage: DevStage
  /** ctn_desc 에 단계 키워드가 없어 추론하지 못한 경우 true. */
  stage_inferred: boolean
  verdict: LotVerdict
}

/** 표가 다루는 행의 최종 형태. 네 곳에서 따로 선언하지 말고 이걸 쓰십시오. */
export type HealthAugmentedRow = SummaryRow & LotHealthFields

/**
 * 다섯 구간 버킷의 합. 서버의 `para_all` 과 같은 값이며, 계약이 그렇게
 * 정의합니다 — 구간이 point 수 전체를 덮으므로 이 값은 파라미터 총 개수이기도
 * 합니다.
 *
 * `para_over_16` 을 `?? 0` 으로 읽는 것은 2026-08-10 이전에 쓰인 주차 스냅샷에
 * 그 키가 없기 때문입니다. 트렌드 화면은 8주 전까지 거슬러 읽으므로, 없는 키를
 * 그대로 더하면 합계가 통째로 NaN 이 됩니다.
 */
export const paraTotal = (
  row: Pick<SummaryRow, 'para_16' | 'para_13' | 'para_9' | 'para_5'> & { para_over_16?: number }
): number =>
  (row.para_over_16 ?? 0) + row.para_16 + row.para_13 + row.para_9 + row.para_5

/** 요약 행 + 판정. */
export const augmentRow = (
  row: SummaryRow,
  verdict: LotVerdict | undefined
): HealthAugmentedRow => {
  const stage = extractStage(row.ctn_desc)
  return {
    ...row,
    dev_stage: stage,
    stage_inferred: stage === '?',
    verdict: verdict ?? emptyVerdict()
  }
}
