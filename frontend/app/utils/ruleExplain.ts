// 계측 룰 판정 근거 — "왜 이 recipe 가 이 cap 으로 판정됐는가" 를 말로 옮깁니다.
//
// **두 번째 판정이 아닙니다.** 여기서는 셀을 고르지도, cap 을 구하지도, 초과를
// 따지지도 않습니다. `ruleEngine` 이 이미 낸 결과(`RecipeResult`)와 그 판정이 쓴
// 입력·셀을 받아 읽기 좋게 늘어놓기만 합니다. 판정 규칙이 바뀌면 이 파일은
// 고칠 것이 없어야 합니다.
//
// Run: node --test app/utils/ruleExplain.test.ts
import { familyLabel } from './ruleMatrix.ts'
import type {
  Family, MemoryClass, MemoryClassOrigin, MergedRecipe, ParamCapSource, ParamType,
  Phase, RecipeClass, RecipeResult, RuleCell
} from './ruleEngine.ts'

/** cap 출처의 화면 표기. 파라미터 행의 출처 열과 근거 블록이 같은 말을 씁니다. */
export const CAP_SOURCE_LABEL: Record<ParamCapSource, string> = {
  type: '타입 cap',
  name: '이름 예외',
  fallback: '_other fallback',
  inherited: 'mother 상속',
  exempt: '면제',
  unset: 'cap 없음'
}

const ORIGIN_LABEL: Record<MemoryClassOrigin, string> = {
  annotation: '어노테이션',
  auto: '자동',
  family: 'VG·RTC·Cubic 기본값'
}

const YIELD_LABEL = { before: '수율 전', after: '수율 후' } as const

/** 출처 뒤에 붙는 "판정에서 뺐다" 꼬리. deviceDrill 의 `cap N · 제외` 와 같은 말입니다. */
const EXCLUDED_SUFFIX = ' · 제외'

export interface ExplainParam {
  name: string
  type: ParamType
  point_count: number
  cap: number | null
  /** gray recipe 는 셀이 없어 cap 을 정한 곳도 없습니다 — null. */
  cap_source: ParamCapSource | null
  /** `CAP_SOURCE_LABEL` + 판정에서 뺀 파라미터면 ` · 제외`. gray 는 null. */
  source_label: string | null
  over_by: number | null
  judged: boolean
}

export interface ExplainInputs {
  recipe_id: string
  recipe_class: RecipeClass
  family: Family
  /** 적용된 셀이 키로 쓴 축. 둘 다 안 쓰는 셀(Sample · VG)과 gray 는 null. */
  axis: 'phase' | 'yield_check' | null
  phase: Phase | null
  yield_check: 'before' | 'after' | null
  memory_class: MemoryClass | null
  memory_class_origin: MemoryClassOrigin | null
}

export type ExplainCell
  = | { kind: 'cell', id: string, summary: string }
    | { kind: 'gray', gray: 'A' | 'B', reason: string }

export interface RecipeExplanation {
  inputs: ExplainInputs
  /** `inputs` 를 화면의 key/value 줄로 편 것. 컴포넌트는 이것을 그리기만 합니다. */
  input_rows: { label: string, value: string }[]
  cell: ExplainCell
  params: ExplainParam[]
  sentence: string
}

/** 셀 selector 를 한 줄로. 예: `R3 · Main · Core · t-EV/EV · DRAM`. */
export const selectorSummary = (cell: RuleCell): string => {
  const s = cell.selector
  return [
    s.fac_id,
    s.recipe_class,
    familyLabel(s.family),
    s.phase_in?.join('/'),
    s.yield_check && YIELD_LABEL[s.yield_check],
    s.memory_class
  ].filter(Boolean).join(' · ')
}

const axisOf = (cell: RuleCell | null): ExplainInputs['axis'] =>
  cell?.selector.yield_check ? 'yield_check' : cell?.selector.phase_in ? 'phase' : null

const inputRows = (i: ExplainInputs, gray: boolean): RecipeExplanation['input_rows'] => {
  const rows = [
    { label: 'recipe', value: i.recipe_id },
    { label: 'recipe class', value: i.recipe_class },
    { label: '제품군', value: familyLabel(i.family) }
  ]
  // 셀이 실제로 쓴 축만 적습니다. gray 는 셀이 없으니 무엇이 비었는지 보이도록
  // 둘 다 적습니다.
  if (gray || i.axis === 'phase') rows.push({ label: 'phase', value: i.phase ?? '없음' })
  if (gray || i.axis === 'yield_check') {
    rows.push({ label: 'yield_check', value: i.yield_check ? YIELD_LABEL[i.yield_check] : '미설정' })
  }
  // Pool 은 판정에서 phase 를 이깁니다(CONTEXT.md §Product Family). phase 값이
  // 있는데 셀 선택에 쓰이지 않았다는 것을 말해 두지 않으면, 칩은 PV 인데 cap 은
  // Pool 룰인 것이 어긋남으로 읽힙니다.
  if (!gray && i.family === 'Pool' && i.phase) {
    rows.push({ label: 'phase', value: `${i.phase} (Pool 은 셀 선택에 phase 를 쓰지 않습니다)` })
  }
  rows.push({
    label: 'memory_class',
    value: i.memory_class
      ? `${i.memory_class}${i.memory_class_origin ? ` (${ORIGIN_LABEL[i.memory_class_origin]})` : ''}`
      : '미설정'
  })
  return rows
}

/** 문장 앞머리 — 셀이 키로 쓴 입력만. 예: `Core · t-EV · DRAM`. */
const readAs = (i: ExplainInputs, cell: RuleCell): string => {
  const s = cell.selector
  return [
    s.family ? familyLabel(i.family) : i.recipe_class,
    i.axis === 'phase' ? i.phase : i.axis === 'yield_check' && i.yield_check ? YIELD_LABEL[i.yield_check] : null,
    s.memory_class && i.memory_class
  ].filter(Boolean).join(' · ')
}

const verdictClause = (result: RecipeResult): string => {
  if (result.results.length === 0) return '판정할 파라미터가 없습니다.'
  const over = result.violation_params
  if (over.length === 0) {
    const judged = result.results.filter(p => p.judged)
    // cap 이 없는 파라미터(cap 없음 · 면제)는 견줄 숫자가 없었던 것이지 "이내" 가
    // 아닙니다. 한데 묶어 "모두 cap 이내" 라고 하면 재지 않은 것을 쟀다고 말하게
    // 됩니다.
    const uncapped = judged.filter(p => p.cap === null)
    const capped = judged.length - uncapped.length
    // 판정에서 뺀 파라미터가 있을 때도 "모든" 이라고 하지 않습니다 — 같은 이유입니다.
    const allJudged = judged.length === result.results.length
    if (uncapped.length === 0) {
      return allJudged ? '모든 파라미터가 cap 이내입니다.' : '판정한 파라미터는 모두 cap 이내입니다.'
    }
    const why = uncapped.every(p => p.cap_source === 'exempt')
      ? CAP_SOURCE_LABEL.exempt
      : uncapped.every(p => p.cap_source === 'unset')
        ? CAP_SOURCE_LABEL.unset
        : `${CAP_SOURCE_LABEL.unset}·${CAP_SOURCE_LABEL.exempt}`
    const scope = allJudged ? '' : '판정한 파라미터 중 '
    return capped === 0
      ? `${scope}cap 이 있는 파라미터가 없습니다(${uncapped.length}개 ${why}).`
      : `${scope}cap 이 있는 파라미터 ${capped}개는 모두 이내이고, ${uncapped.length}개는 ${why}입니다.`
  }
  // 가장 많이 넘긴 하나를 이름으로 듭니다. 동률이면 측정 순서상 앞선 것.
  const worst = over.reduce((a, b) => (b.over_by ?? 0) > (a.over_by ?? 0) ? b : a)
  const head = `${worst.name} 가 cap ${worst.cap} 를 ${worst.over_by}`
  return over.length === 1
    ? `${head} 초과했습니다.`
    : `${head} 초과하는 등 파라미터 ${over.length}개가 cap 을 넘었습니다.`
}

const graySentence = (gray: 'A' | 'B', reason: string): string =>
  gray === 'B'
    // 엔진의 사유는 "<필드> 미설정" 꼴입니다(resolveRuleCell). 필드 이름만 씁니다.
    ? `${reason.split(' ')[0]} 가 없어 판정하지 않았습니다(Gray-B).`
    : '맞는 룰 셀이 없어 판정하지 않았습니다(Gray-A).'

/**
 * 판정 하나의 근거. `recipe` 와 `cell` 은 그 판정이 **실제로 쓴** 것이어야 합니다
 * — `RecipeResult.basis` 가 그것을 들고 있습니다.
 */
export const explainRecipe = (
  recipe: MergedRecipe,
  result: RecipeResult,
  cell: RuleCell | null
): RecipeExplanation => {
  // 셀 없이 판정된 결과는 없습니다. 그래도 셀이 안 넘어오면 gray 로 다룹니다 —
  // 없는 셀의 cap 출처를 적는 것보다 낫습니다.
  const gray = result.gray ?? (cell ? null : 'A')
  const inputs: ExplainInputs = {
    recipe_id: recipe.recipe_id,
    recipe_class: recipe.recipe_class,
    family: recipe.family,
    axis: gray ? null : axisOf(cell),
    phase: recipe.phase,
    yield_check: recipe.yield_check,
    memory_class: recipe.memory_class,
    memory_class_origin: recipe.memory_class_origin
  }
  const params = result.results.map((p): ExplainParam => ({
    name: p.name,
    type: p.type,
    point_count: p.point_count,
    cap: p.cap,
    cap_source: gray ? null : p.cap_source,
    source_label: gray ? null : CAP_SOURCE_LABEL[p.cap_source] + (p.judged ? '' : EXCLUDED_SUFFIX),
    over_by: p.over_by,
    judged: p.judged
  }))
  if (gray || !cell) {
    const reason = result.gray_reason ?? '룰 미정'
    return {
      inputs,
      input_rows: inputRows(inputs, true),
      cell: { kind: 'gray', gray: gray ?? 'A', reason },
      params,
      sentence: graySentence(gray ?? 'A', reason)
    }
  }
  return {
    inputs,
    input_rows: inputRows(inputs, false),
    cell: { kind: 'cell', id: cell.id, summary: selectorSummary(cell) },
    params,
    sentence: `${readAs(inputs, cell)} 으로 읽혀 ${cell.id} 셀이 적용됐고, ${verdictClause(result)}`
  }
}
