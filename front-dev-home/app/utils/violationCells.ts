/**
 * 판정 결과를 **표의 칸**으로 옮기는 말들.
 *
 * 내보내기가 둘 있고(측정 룰 탭의 디바이스별 워크북, 비교 탭의 lot 파라미터
 * CSV) 둘 다 같은 질문에 답합니다 — "이 recipe 는 상한을 넘겼는가", "이
 * 파라미터는 왜 판정에서 빠졌는가". 각자 답을 적으면 한쪽만 고친 날 두 파일이
 * 같은 사실을 다른 말로 말합니다. 화면 쪽에서 `deviceDrill.ts` 가 맡는 역할을
 * 파일 쪽에서 맡습니다.
 *
 * 판단은 하지 않습니다 — `ruleEngine` 이 이미 내린 판정을 문자열로 옮길
 * 뿐입니다. 순수 함수라 `node --test` 가 그대로 실행합니다.
 */
import type { ParamResult, RecipeResult } from './ruleEngine.ts'

/**
 * 초과 칸의 값. 정상은 **빈 칸**입니다 — '정상' 을 적으면 두 문자열이 같은
 * 폭으로 늘어서서, 열을 훑을 때 초과가 눈에 튀지 않습니다. 빈 칸이면 자동
 * 필터 한 번으로 초과만 남습니다.
 */
export const OVER = '초과'
export const NOT_OVER = ''

/**
 * recipe 층 판정 한 마디.
 *
 * `fallback` 은 판정 자체가 없을 때(룰 없는 fab, 판정 범위 밖 job) 쓰는 말로,
 * 호출자가 정합니다 — 어느 쪽인지는 여기서 알 수 없고, 둘을 한 말로 뭉개면
 * "룰이 없다" 와 "이 job 은 원래 안 본다" 가 파일에서 같아집니다.
 */
export const recipeVerdictCell = (
  recipe: RecipeResult | undefined,
  fallback: string
): string =>
  recipe == null
    ? fallback
    : recipe.gray != null
      ? '판정 제외'
      : recipe.pass ? '정상' : '상한 초과'

/** 파라미터가 상한을 넘겼는가. 판정 대상이 아니었으면 넘겼어도 빈 칸입니다 —
 *  그 사실은 아래 `paramNoteCell` 이 말합니다. */
export const overCell = (param: ParamResult | undefined): string =>
  param?.violation ? OVER : NOT_OVER

/**
 * 왜 이 행이 판정에서 빠졌는가. 빠지지 않았으면 빈 칸.
 *
 * 적지 않으면 "재 봤더니 상한 안" 과 "아예 안 쟀다" 가 파일에서 같은 빈 칸이
 * 되고, 그러면 gray recipe 가 깨끗한 recipe 로 읽힙니다 (deviceDrill 의 `note`
 * 와 같은 이유). gray 는 recipe 통째로 빠진 것이라 그 recipe 의 모든 행에 같은
 * 사유가 붙습니다 — 되풀이되지만, 한 행만 떼어 봐도 말이 되는 것이 평평한
 * 표의 값입니다.
 */
export const paramNoteCell = (
  recipe: RecipeResult | undefined,
  param: ParamResult | undefined,
  fallback: string
): string => {
  if (recipe == null || param == null) return fallback
  if (recipe.gray != null) return recipe.gray_reason ?? '룰 미정'
  if (param.judged) return ''
  // 판정에서 빠지는 것은 son 뿐입니다(ruleEngine 의 JudgeOptions). 상한을 넘긴
  // son 은 넘겼다는 사실까지 적습니다 — son 판정 토글을 껐다는 것이 숫자가
  // 줄었다는 것 말고도 파일에 남습니다.
  const over = typeof param.cap === 'number' && param.point_count > param.cap
  return over ? 'son 판정 제외 · 상한 초과' : 'son 판정 제외'
}

/** cap 칸. 룰이 상한을 두지 않은 파라미터(면제)는 빈 칸입니다. */
export const capCell = (param: ParamResult | undefined): number | string =>
  typeof param?.cap === 'number' ? param.cap : ''

/** recipe_id → 판정. 두 내보내기 모두 이 조인으로 원본 행에 판정을 붙입니다. */
export const indexResults = (recipes: RecipeResult[]): Map<string, RecipeResult> =>
  new Map(recipes.map(r => [r.recipe_id, r]))
