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
 * 뿐입니다. 그래서 인자는 전부 **있는 판정**입니다: 판정이 없는 행을 무엇이라
 * 부를지는 조인을 소유한 쪽(lotParamExport)이 자기 자리에서 답합니다. 여기서
 * 는 어느 쪽인지 알 수 없기 때문입니다.
 *
 * 순수 함수라 `node --test` 가 그대로 실행합니다.
 */
import type { ParamResult, RecipeResult } from './ruleEngine.ts'

/**
 * 초과 칸의 값. 정상은 **빈 칸**입니다 — '정상' 을 적으면 두 문자열이 같은
 * 폭으로 늘어서서, 열을 훑을 때 초과가 눈에 튀지 않습니다. 빈 칸이면 자동
 * 필터 한 번으로 초과만 남습니다.
 *
 * 판정 대상이 아니었으면 상한을 넘겼어도 빈 칸입니다 — 그 사실은 아래
 * `paramNoteCell` 이 말합니다.
 */
export const overCell = (param: ParamResult): string => param.violation ? '초과' : ''

/**
 * recipe 층 판정 한 마디.
 *
 * 파라미터가 하나도 없는 recipe 를 '정상' 이라 부르지 않습니다. `evaluateRecipe`
 * 는 그런 recipe 에 `pass: true` 를 주지만(넘긴 파라미터가 0개이므로) 그것은
 * "재 봤더니 깨끗하다" 가 아니라 "잰 것이 없다" 입니다. 같은 실수를 lot 층에서
 * 한 적이 있습니다 — 전부 gray 인 lot 이 비율 0 → green 으로 나와 아무것도 못
 * 본 lot 과 다 보고 깨끗한 lot 이 같은 색이었습니다(d6e6aacb). 그 교훈을 recipe
 * 층에도 적용합니다.
 */
export const recipeVerdictCell = (recipe: RecipeResult): string =>
  recipe.gray != null
    ? '판정 제외'
    : recipe.results.length === 0
      ? NO_JUDGEMENT
      : recipe.pass ? '정상' : '상한 초과'

/**
 * 왜 이 행이 판정에서 빠졌는가. 빠지지 않았으면 빈 칸.
 *
 * 적지 않으면 "재 봤더니 상한 안" 과 "아예 안 쟀다" 가 파일에서 같은 빈 칸이
 * 되고, 그러면 gray recipe 가 깨끗한 recipe 로 읽힙니다 (deviceDrill 의 `note`
 * 와 같은 이유). gray 는 recipe 통째로 빠진 것이라 그 recipe 의 모든 행에 같은
 * 사유가 붙습니다 — 되풀이되지만, 한 행만 떼어 봐도 말이 되는 것이 평평한
 * 표의 값입니다.
 */
export const paramNoteCell = (recipe: RecipeResult, param: ParamResult): string => {
  if (recipe.gray != null) return recipe.gray_reason ?? '룰 미정'
  if (param.judged) return ''
  // 판정에서 빠지는 것은 son 뿐입니다(ruleEngine 의 JudgeOptions). 상한을 넘긴
  // son 은 넘겼다는 사실까지 적습니다 — son 판정 토글을 껐다는 것이 숫자가
  // 줄었다는 것 말고도 파일에 남습니다.
  return param.over_cap ? 'son 판정 제외 · 상한 초과' : 'son 판정 제외'
}

/** cap 칸. 룰이 상한을 두지 않은 파라미터(면제)는 빈 칸입니다. */
export const capCell = (param: ParamResult): number | string => param.cap ?? ''

/**
 * 판정이 나오지 않은 행의 말. 원인을 모르는 자리에서 아는 만큼만 적습니다 —
 * 지어낸 원인(예: '룰 없음')을 적으면 파일이 있지도 않은 문제를 지목합니다.
 */
export const NO_JUDGEMENT = '판정 결과 없음'

/**
 * 파라미터가 하나도 없는 recipe 의 비고.
 *
 * 두 내보내기 모두 그런 recipe 를 **한 줄로 남깁니다** — 건너뛰면 그 recipe 가
 * 파일에서 통째로 사라져, "측정 파라미터가 없는 recipe" 와 "받아오지 못한
 * recipe" 를 구분할 수 없습니다. 그 줄이 스스로를 설명하는 말이라 두 파일이
 * 같은 말을 써야 하고, 그래서 여기 있습니다.
 */
export const NO_PARAMS = '파라미터 없음'
