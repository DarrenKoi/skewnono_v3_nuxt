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
  GrayField, MemoryClassOrigin, MergedRecipe, ParamCapSource, ParamResult, RecipeResult, RuleCell
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

/**
 * 파라미터 행의 출처 표기. gray recipe 는 셀이 없어 cap 을 정한 곳도 없으므로
 * null — 엔진이 그 행에 적어 둔 `unset` 을 "cap 없음" 으로 보이면 안 됩니다.
 */
export const capSourceLabel = (p: ParamResult, gray: boolean): string | null =>
  gray ? null : CAP_SOURCE_LABEL[p.cap_source] + (p.judged ? '' : EXCLUDED_SUFFIX)

/** 적용된 셀이 키로 쓴 축. 둘 다 안 쓰는 셀(Sample · VG)은 null. */
type Axis = 'phase' | 'yield_check' | null

export type ExplainCell
  = | { kind: 'cell', id: string, summary: string }
    | { kind: 'gray', gray: 'A' | 'B', reason: string }

export interface RecipeExplanation {
  /** 판정 입력을 화면의 key/value 줄로 편 것. 컴포넌트는 이것을 그리기만 합니다. */
  input_rows: { label: string, value: string }[]
  cell: ExplainCell
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

const axisOf = (cell: RuleCell): Axis =>
  cell.selector.yield_check ? 'yield_check' : cell.selector.phase_in ? 'phase' : null

const inputRows = (r: MergedRecipe, axis: Axis, gray: boolean): RecipeExplanation['input_rows'] => {
  const rows = [
    { label: 'recipe', value: r.recipe_id },
    { label: 'recipe class', value: r.recipe_class },
    { label: '제품군', value: familyLabel(r.family) }
  ]
  // 셀이 실제로 쓴 축만 적습니다. gray 는 셀이 없으니 무엇이 비었는지 보이도록
  // 둘 다 적습니다.
  if (gray || axis === 'phase') rows.push({ label: 'phase', value: r.phase ?? '없음' })
  if (gray || axis === 'yield_check') {
    rows.push({ label: 'yield_check', value: r.yield_check ? YIELD_LABEL[r.yield_check] : '미설정' })
  }
  // Pool 은 판정에서 phase 를 이깁니다(CONTEXT.md §Product Family). phase 값이
  // 있는데 셀 선택에 쓰이지 않았다는 것을 말해 두지 않으면, 칩은 PV 인데 cap 은
  // Pool 룰인 것이 어긋남으로 읽힙니다.
  if (!gray && r.family === 'Pool' && r.phase) {
    rows.push({ label: 'phase', value: `${r.phase} (Pool 은 셀 선택에 phase 를 쓰지 않습니다)` })
  }
  rows.push({
    label: 'memory_class',
    value: r.memory_class
      ? `${r.memory_class}${r.memory_class_origin ? ` (${ORIGIN_LABEL[r.memory_class_origin]})` : ''}`
      : '미설정'
  })
  return rows
}

/** 문장 앞머리 — 셀이 키로 쓴 입력만. 예: `Core · t-EV · DRAM`. */
const readAs = (r: MergedRecipe, axis: Axis, cell: RuleCell): string => {
  const s = cell.selector
  return [
    s.family ? familyLabel(r.family) : r.recipe_class,
    axis === 'phase' ? r.phase : axis === 'yield_check' && r.yield_check ? YIELD_LABEL[r.yield_check] : null,
    s.memory_class && r.memory_class
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
    // 이유는 파라미터 행의 출처 열과 같은 말로 적습니다 — 면제(`exempt`), cap 없음
    // (`unset`), cap 없는 mother 를 물려받은 son(`inherited`). 행과 문장이 한
    // 파라미터를 두 이름으로 부르지 않게 하려는 것입니다.
    const why = [...new Set(uncapped.map(p => CAP_SOURCE_LABEL[p.cap_source]))].join('·')
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

const graySentence = (gray: 'A' | 'B', field: GrayField | undefined): string =>
  gray === 'A'
    ? '맞는 룰 셀이 없어 판정하지 않았습니다(Gray-A).'
    : field
      ? `${field} 가 없어 판정하지 않았습니다(Gray-B).`
      : '어노테이션이 없어 판정하지 않았습니다(Gray-B).'

/**
 * 판정 하나의 근거. `recipe` 와 `cell` 은 그 판정이 **실제로 쓴** 것이어야 합니다
 * — `RecipeResult.basis` 가 그것을 들고 있습니다.
 */
export const explainRecipe = (
  recipe: MergedRecipe,
  result: RecipeResult,
  cell: RuleCell | null
): RecipeExplanation => {
  // 셀 없이 판정된 결과는 없습니다. 그래도 셀이 안 넘어오면 Gray-A 로 다룹니다 —
  // 없는 셀의 cap 출처를 적는 것보다 낫습니다.
  if (result.gray || !cell) {
    const gray = result.gray ?? 'A'
    return {
      input_rows: inputRows(recipe, null, true),
      cell: { kind: 'gray', gray, reason: result.gray_reason ?? '룰 미정' },
      sentence: graySentence(gray, result.gray_field)
    }
  }
  const axis = axisOf(cell)
  return {
    input_rows: inputRows(recipe, axis, false),
    cell: { kind: 'cell', id: cell.id, summary: selectorSummary(cell) },
    sentence: `${readAs(recipe, axis, cell)} 으로 읽혀 ${cell.id} 셀이 적용됐고, ${verdictClause(result)}`
  }
}
