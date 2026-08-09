/**
 * 프론트의 tool_type 단일 원천.
 *
 * 백엔드 `back_dev_home/ebeam/_tool_specs.py` 의 거울입니다. `model_to_tool_type()`
 * 는 AMAT 계열을 `veritysem` / `provision` (하이픈 없음) 으로 분류하고, 여기의
 * `classifyToolType` 도 동일한 값을 돌려줍니다 — 두 분류기는 지금 일치합니다.
 *
 * utils 에 있는 이유: `pendingToolMatrix.ts` 가 런타임에 쓰는 순수 함수인데
 * `npm test` 는 번들러 없이 `node --test` 로 돌기 때문에 `~/composables/…`
 * 임포트는 해석되지 않습니다. 호출부는 Nuxt auto-import 로 그대로 씁니다.
 *
 * AMAT 계열(veritysem/provision)에는 하이픈이 없습니다. 제품명이 한 단어이고,
 * 슬러그·tool_type·라우트가 같은 문자열이면 매핑 테이블이 생기지 않습니다.
 * 이중 표기는 Hitachi 레거시(cdsem ↔ cd-sem)로만 남습니다.
 */
export const TOOL_TYPES = ['cd-sem', 'hv-sem', 'veritysem', 'provision'] as const

export type ToolType = (typeof TOOL_TYPES)[number]

/** CD/HV 전용 화면이 담는 범위. 'AMAT 이 아닌 것' 으로 흉내내지 않습니다. */
export const SEM_TOOL_TYPES = ['cd-sem', 'hv-sem'] as const satisfies readonly ToolType[]

const TOOL_SLUGS: Record<ToolType, string> = {
  'cd-sem': 'cdsem',
  'hv-sem': 'hvsem',
  'veritysem': 'veritysem',
  'provision': 'provision'
}

/** 백엔드 `/api/<tool_slug>/…` 에 들어가는 슬러그. */
export const toolSlug = (toolType: ToolType): string => TOOL_SLUGS[toolType]

export const classifyToolType = (eqpModelCd: string): ToolType | null => {
  const model = eqpModelCd.trim().toUpperCase()
  if (model.startsWith('CG') || model.startsWith('GT')) return 'cd-sem'
  if (model.startsWith('TP')) return 'hv-sem'
  if (model.startsWith('VERITYSEM') || model.startsWith('VERITY_SEM')) return 'veritysem'
  if (model.startsWith('PROVISION')) return 'provision'
  return null
}

/**
 * CD-SEM ↔ HV-SEM 의 짝. 그 밖에는 짝이 없으므로 null 입니다.
 *
 * skewvoir 의 "다른 SEM 계열 이력도 함께 조회" 는 두 계열만 있을 때 성립하는
 * 개념입니다. 삼항(`x === 'cd-sem' ? 'hv-sem' : 'cd-sem'`)으로 쓰면 AMAT 계열이
 * 조용히 'cd-sem' 이 되어 엉뚱한 계열의 데이터를 나란히 그립니다.
 */
export const otherSemFamily = (toolType: ToolType): ToolType | null => {
  if (toolType === 'cd-sem') return 'hv-sem'
  if (toolType === 'hv-sem') return 'cd-sem'
  return null
}
