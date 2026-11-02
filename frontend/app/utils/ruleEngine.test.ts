// Pure-logic tests for ruleEngine. Zero deps — run with Node's built-in runner:
//   node --test app/utils/ruleEngine.test.ts        (Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  deriveType, deriveMemoryClass,
  capFor, resolveCap, applyAnnotation, resolveRuleCell, evaluateRecipe, evaluateLot,
  classifyHealth, groupCaps, effectiveCap, type RuleCell, type RecipeInput
} from './ruleEngine.ts'

// --- fixtures ---
const coreEarlyDram: RuleCell = {
  id: 'r3-core-tev-dram',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['EV', 'tEV', 'DTV', 'TTV'], memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 9 },
  name_overrides: [{ patterns: ['DSPT', 'WF', 'WAFER'], match: 'contains', cap: 13 }]
}
const sampleDram: RuleCell = {
  id: 'r3-sample-dram',
  selector: { fac_id: 'R3', recipe_class: 'Sample', memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 0 },
  // providers/rules.py `_SAMPLE_OVERRIDES` 를 그대로 옮긴 것입니다 — DUMMY 면제
  // (user-confirmed 2026-08-05)와 ALIGN 면제(2026-08-10) 포함.
  name_overrides: [
    { patterns: ['WAFER', 'WF'], match: 'affix', cap: null },
    { patterns: ['DUMMY'], match: 'affix', cap: null },
    { patterns: ['ALIGN'], match: 'affix', cap: null }
  ]
}
const wfOverride = { patterns: ['DSPT', 'WF', 'WAFER'], match: 'contains' as const, cap: 13 }
// D8 — Core early NAND (EDGE 8), Core TV/PV (EDGE/EDGE_EX 16, no memory split)
const coreEarlyNand: RuleCell = {
  id: 'r3-core-tev-nand',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['EV', 'tEV', 'DTV', 'TTV'], memory_class: 'NAND' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 8, EDGE_EX: 0, _other: 9 },
  name_overrides: [wfOverride]
}
const coreTvPv: RuleCell = {
  id: 'r3-core-tvpv',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['TV', 'PV'] },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 16, EDGE_EX: 16, _other: 9 },
  name_overrides: [wfOverride]
}
// Pool제 — 수율 전/후 구분 없이 후 기준 하나 (user-confirmed 2026-11-02)
const poolDram: RuleCell = {
  id: 'r3-pool-dram',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Pool', memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 10, _other: 9 },
  name_overrides: [wfOverride]
}
// Core 가 아닌 전부(RTC·Cubic·요소기술·메모리 기타) — RTC 룰, phase·memory 무관
const otherCell: RuleCell = {
  id: 'r3-other',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Other' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 9 },
  name_overrides: [wfOverride]
}
const sampleNand: RuleCell = {
  id: 'r3-sample-nand',
  selector: { fac_id: 'R3', recipe_class: 'Sample', memory_class: 'NAND' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 8, EDGE_EX: 0, _other: 0 },
  // providers/rules.py `_SAMPLE_OVERRIDES` 를 그대로 옮긴 것입니다 — DUMMY 면제
  // (user-confirmed 2026-08-05)와 ALIGN 면제(2026-08-10) 포함.
  name_overrides: [
    { patterns: ['WAFER', 'WF'], match: 'affix', cap: null },
    { patterns: ['DUMMY'], match: 'affix', cap: null },
    { patterns: ['ALIGN'], match: 'affix', cap: null }
  ]
}
// D15 — same selector shape, different fab (M-fab recipe_class × memory_class)
const mfabMainDram: RuleCell = {
  id: 'm14-main-dram',
  selector: { fac_id: 'M14', recipe_class: 'Main', family: 'Core', phase_in: ['EV', 'tEV', 'DTV', 'TTV'], memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 99, EDGE_EX: 99, _other: 99 },
  name_overrides: []
}
const recipe = (over: Partial<RecipeInput>): RecipeInput => ({
  lot_cd: 'R3K-12', recipe_id: 'R', fac_id: 'R3', ctn_desc: '[tEV / DRAM] Cubit tEV Cell', prod_catg_cd: 'DRAM',
  recipe_class: 'Main', family: 'Core', phase: 'tEV', memory_class_auto: 'DRAM', parameters: [], ...over
})

// --- description 표준 포맷 (user-confirmed 2026-11-02) ---
// backend 가 device description 앞 괄호 `[phase / memory]` 를 못 읽으면 family 가
// null 입니다. 그 recipe 는 family 를 안 단 셀까지 포함해 **어떤 셀에도** 붙지
// 않고 룰 미정으로 빠져야 합니다 — 옛 토큰 추론으로 되돌아가지 않기로 했습니다.
test('description 미준수(family=null)는 Gray-A — family 없는 셀도 주장하지 못한다', () => {
  const r = applyAnnotation(recipe({
    family: null, phase: null, memory_class_auto: 'unknown', ctn_desc: 'DRAM Pool제 (@Spica PV)',
    parameters: [{ name: 'EDGE', point_count: 99 }]
  }), { memory_class: 'DRAM' })
  const res = resolveRuleCell(r, [sampleDram, { ...coreEarlyDram, selector: { fac_id: 'R3', recipe_class: 'Main' } }])
  assert.equal(res.kind === 'gray' && res.gray, 'A')
  assert.equal(res.kind === 'gray' && res.reason, 'description 포맷 미준수')
})
test('memory_class 는 description 괄호 값이 어노테이션보다 우선', () => {
  const r = applyAnnotation(recipe({ memory_class_auto: 'DRAM' }), { memory_class: 'NAND' })
  assert.deepEqual([r.memory_class, r.memory_class_origin], ['DRAM', 'auto'])
})

// --- D10 deriveType: longest-prefix, suffix allowed, Class-independent ---
test('deriveType', () => {
  assert.equal(deriveType('WAFER'), 'WAFER')
  assert.equal(deriveType('WAFER_2'), 'WAFER') // suffix allowed
  assert.equal(deriveType('EDGE_EX'), 'EDGE_EX')
  assert.equal(deriveType('EDGE_EX_3'), 'EDGE_EX') // longest match beats EDGE
  assert.equal(deriveType('EDGE_WF_CD'), 'EDGE') // prefix EDGE, inner WF ignored
  assert.equal(deriveType('DSPT_CD'), 'OTHER')
  assert.equal(deriveType('X_WF'), 'OTHER')
})

// --- D7 derivation ---
// deriveFamily/derivePhase 의 테스트는 그 함수와 함께 지웠습니다 — family/phase
// 파생은 backend(`desc_format.parse_device_desc`)의 것이고, 그쪽 회귀는
// backend/ebeam/device_statistics/tests/test_desc_format.py 가 봅니다.
test('deriveType tolerates empty/malformed name', () => {
  assert.equal(deriveType(''), 'OTHER')
  assert.equal(deriveType(undefined as unknown as string), 'OTHER')
})
test('deriveMemoryClass DRAM/NAND/FLASH + unknown', () => {
  assert.equal(deriveMemoryClass('DRAM'), 'DRAM')
  assert.equal(deriveMemoryClass('NAND'), 'NAND')
  assert.equal(deriveMemoryClass('FLASH'), 'NAND')
  assert.equal(deriveMemoryClass('Tech'), 'unknown')
  assert.equal(deriveMemoryClass('Advanced'), 'unknown')
})

// --- D9 capFor: type wins over name-override ---
test('capFor: type cap beats name-override', () => {
  assert.equal(capFor({ name: 'EDGE_WF_CD', point_count: 12 }, coreEarlyDram), 10) // EDGE, NOT 13
  assert.equal(capFor({ name: 'EDGE_EX', point_count: 0 }, coreEarlyDram), 0)
})
test('capFor: OTHER param uses name-override then _other', () => {
  assert.equal(capFor({ name: 'DSPT_CD', point_count: 13 }, coreEarlyDram), 13) // override
  assert.equal(capFor({ name: 'RANDOM', point_count: 5 }, coreEarlyDram), 9) // _other
})
test('capFor: Sample affix exemption returns null (no limit)', () => {
  assert.equal(capFor({ name: 'X_WF', point_count: 99 }, sampleDram), null) // exempt
  assert.equal(capFor({ name: 'RANDOM', point_count: 1 }, sampleDram), 0) // _other 0
})

// Sample 셀의 _other 는 0 이라, 면제가 없으면 자리 표시용 DUMMY 가 point 1 만
// 있어도 항상 위반입니다 (user-confirmed 2026-08-05).
test('capFor: Sample DUMMY is exempt, not capped at 0', () => {
  assert.equal(capFor({ name: 'Dummy', point_count: 1 }, sampleDram), null)
  assert.equal(capFor({ name: 'Dummy_1', point_count: 9 }, sampleDram), null)
  assert.equal(capFor({ name: 'CD_Dummy', point_count: 9 }, sampleDram), null)
})

test('evaluateRecipe: a Sample DUMMY no longer makes the recipe violate', () => {
  const merged = applyAnnotation(recipe({
    recipe_class: 'Sample',
    parameters: [{ name: 'WAFER_CD', point_count: 13 }, { name: 'Dummy', point_count: 1 }]
  }))
  const evaluated = evaluateRecipe(merged, resolveRuleCell(merged, [sampleDram]))

  assert.equal(evaluated.pass, true)
  assert.deepEqual(evaluated.violation_params, [])
  // 목록에서 빼는 것이 아니라 판정에서만 빼므로 파라미터 수는 그대로입니다.
  assert.equal(evaluated.total_params, 2)
  assert.equal(evaluated.results.find(r => r.name === 'Dummy')?.cap, null)
})

// --- D8/D14 cell resolution ---
test('resolveRuleCell: match / Gray-A / Gray-B', () => {
  const merged = applyAnnotation(recipe({}))
  assert.equal(resolveRuleCell(merged, [coreEarlyDram]).kind, 'cell')

  const other = applyAnnotation(recipe({ family: 'Other' }))
  const grayA = resolveRuleCell(other, [coreEarlyDram])
  assert.equal(grayA.kind, 'gray')
  assert.equal(grayA.kind === 'gray' && grayA.gray, 'A') // no rule

  const tech = applyAnnotation(recipe({ memory_class_auto: 'unknown' }))
  const grayB = resolveRuleCell(tech, [coreEarlyDram])
  assert.equal(grayB.kind === 'gray' && grayB.gray, 'B') // memory_class 미설정
})
test('annotation overrides auto memory_class → resolves', () => {
  const tech = recipe({ memory_class_auto: 'unknown' })
  const merged = applyAnnotation(tech, { memory_class: 'DRAM' })
  assert.equal(resolveRuleCell(merged, [coreEarlyDram]).kind, 'cell')
})

// --- D5 evaluation: under-measuring is never a violation ---
test('evaluateRecipe: over=violation, under=OK', () => {
  const over = applyAnnotation(recipe({ parameters: [{ name: 'EDGE', point_count: 12 }] }))
  const rOver = evaluateRecipe(over, resolveRuleCell(over, [coreEarlyDram]))
  assert.equal(rOver.pass, false)
  assert.equal(rOver.violation_params.length, 1)

  const under = applyAnnotation(recipe({ parameters: [{ name: 'EDGE', point_count: 8 }] }))
  const rUnder = evaluateRecipe(under, resolveRuleCell(under, [coreEarlyDram]))
  assert.equal(rUnder.pass, true) // 8 ≤ 10
})
test('evaluateRecipe: gray recipe is pass (conservative)', () => {
  const other = applyAnnotation(recipe({ family: 'Other', parameters: [{ name: 'EDGE', point_count: 999 }] }))
  const r = evaluateRecipe(other, resolveRuleCell(other, [coreEarlyDram]))
  assert.equal(r.pass, true)
  assert.equal(r.gray, 'A')
})

// --- D14 lot roll-up: gray excluded from denominator ---
test('evaluateLot: ratio, health, gray excluded', () => {
  const recipes = [
    recipe({ recipe_id: 'r1', parameters: [{ name: 'EDGE', point_count: 12 }] }), // violation
    recipe({ recipe_id: 'r2', parameters: [{ name: 'EDGE', point_count: 8 }] }), // ok
    recipe({ recipe_id: 'r3', memory_class_auto: 'unknown', parameters: [{ name: 'EDGE', point_count: 12 }] }) // gray-B
  ]
  const h = evaluateLot('R3K-12', recipes, [coreEarlyDram])
  assert.equal(h.total_recipes, 3)
  assert.equal(h.violation_recipes, 1)
  assert.equal(h.violation_ratio, 0.5) // 1 / 2 evaluated (gray excluded)
  assert.equal(h.health, 'red')
})

test('classifyHealth thresholds', () => {
  assert.equal(classifyHealth(0.05), 'green')
  assert.equal(classifyHealth(0.15), 'yellow')
  assert.equal(classifyHealth(0.25), 'red')
})

// --- D15 fab is a real axis: a cell from another fab must never match ---
test('resolveRuleCell: cross-fab cell is ignored (D15)', () => {
  // R3 recipe, only an M14 cell present → no rule (Gray-A), not a silent match
  const r3 = applyAnnotation(recipe({}))
  assert.equal(resolveRuleCell(r3, [mfabMainDram]).kind, 'gray')
  // both fabs present → R3 recipe resolves to the R3 cell, not M14's cap=99
  const both = resolveRuleCell(r3, [mfabMainDram, coreEarlyDram])
  assert.equal(both.kind === 'cell' && both.cell.id, 'r3-core-tev-dram')
  // an M14 recipe resolves to the M14 cell
  const m14 = applyAnnotation(recipe({ fac_id: 'M14' }))
  const mres = resolveRuleCell(m14, [mfabMainDram, coreEarlyDram])
  assert.equal(mres.kind === 'cell' && mres.cell.id, 'm14-main-dram')
})

// --- Sample 은 Main 과 같은 EDGE 계열 cap (D23, user-confirmed 2026-11-02) ---
const sampleOverrides = sampleDram.name_overrides
const sampleCoreTvpv: RuleCell = {
  id: 'r3-sample-core-tvpv',
  selector: { fac_id: 'R3', recipe_class: 'Sample', family: 'Core', phase_in: ['TV', 'PV'] },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 16, EDGE_EX: 16, _other: 0 },
  name_overrides: sampleOverrides
}
test('Sample Core TV/PV: EDGE_EX 16 은 허용, 17 은 위반', () => {
  const at = (n: number) => applyAnnotation(recipe({
    recipe_class: 'Sample', phase: 'PV', parameters: [{ name: 'EDGE_EX', point_count: n }]
  }))
  assert.equal(evaluateRecipe(at(16), resolveRuleCell(at(16), [sampleCoreTvpv])).pass, true)
  assert.equal(evaluateRecipe(at(17), resolveRuleCell(at(17), [sampleCoreTvpv])).pass, false)
})
test('first-match: 배열에서 앞선 셀이 겹치는 뒤 셀을 이긴다 (엔진 일반 성질)', () => {
  const broad: RuleCell = { ...sampleCoreTvpv, id: 'broad', selector: { fac_id: 'R3', recipe_class: 'Sample', family: 'Core' } }
  const r = applyAnnotation(recipe({ recipe_class: 'Sample', phase: 'PV' }))
  assert.equal((resolveRuleCell(r, [sampleCoreTvpv, broad]) as { cell: RuleCell }).cell.id, 'r3-sample-core-tvpv')
  assert.equal((resolveRuleCell(r, [broad, sampleCoreTvpv]) as { cell: RuleCell }).cell.id, 'broad')
})

// --- 룰 표 (user-confirmed 2026-11-02) ---
test('Core early NAND: EDGE cap 8', () => {
  const r = applyAnnotation(recipe({ memory_class_auto: 'NAND', parameters: [{ name: 'EDGE', point_count: 10 }] }))
  const res = evaluateRecipe(r, resolveRuleCell(r, [coreEarlyNand]))
  assert.equal(res.pass, false) // 10 > 8
})
test('Core DTV·TTV 는 EV 급 — EDGE_EX 0', () => {
  for (const phase of ['DTV', 'TTV'] as const) {
    const r = applyAnnotation(recipe({ phase, parameters: [{ name: 'EDGE_EX', point_count: 1 }] }))
    const res = resolveRuleCell(r, [coreTvPv, coreEarlyDram])
    assert.equal(res.kind === 'cell' && res.cell.id, 'r3-core-tev-dram', phase)
    assert.equal(evaluateRecipe(r, res).pass, false, phase)
  }
})
test('Core TV/PV: EDGE/EDGE_EX cap 16, no memory split', () => {
  const r = applyAnnotation(recipe({ phase: 'PV', parameters: [{ name: 'EDGE', point_count: 16 }, { name: 'EDGE_EX', point_count: 16 }] }))
  const res = evaluateRecipe(r, resolveRuleCell(r, [coreTvPv]))
  assert.equal(res.pass, true) // 16 ≤ 16 boundary
})
test('Pool제: 수율 구분 없이 EDGE_EX 10 (DRAM) — 어노테이션 없이 판정된다', () => {
  const ok = applyAnnotation(recipe({ family: 'Pool', phase: null, parameters: [{ name: 'EDGE_EX', point_count: 10 }] }))
  assert.equal(evaluateRecipe(ok, resolveRuleCell(ok, [poolDram])).pass, true)
  const over = applyAnnotation(recipe({ family: 'Pool', phase: null, parameters: [{ name: 'EDGE_EX', point_count: 11 }] }))
  assert.equal(evaluateRecipe(over, resolveRuleCell(over, [poolDram])).pass, false)
})
test('Other(RTC 룰): phase·memory 와 무관하게 한 셀, EDGE_EX 0', () => {
  for (const [phase, mem] of [[null, 'DRAM'], ['TV', 'unknown']] as const) {
    const r = applyAnnotation(recipe({
      family: 'Other', phase, memory_class_auto: mem, parameters: [{ name: 'EDGE_EX', point_count: 1 }]
    }))
    const res = resolveRuleCell(r, [coreTvPv, otherCell])
    assert.equal(res.kind === 'cell' && res.cell.id, 'r3-other')
    assert.equal(evaluateRecipe(r, res).pass, false)
  }
})

// --- D5 boundaries: equality passes, cap 0 means any measurement violates ---
test('D5 boundary: point_count === cap passes', () => {
  const r = applyAnnotation(recipe({ parameters: [{ name: 'EDGE', point_count: 10 }] }))
  assert.equal(evaluateRecipe(r, resolveRuleCell(r, [coreEarlyDram])).pass, true) // 10 ≤ 10
})
test('D5 cap 0: EDGE_EX 0 passes, 1 violates', () => {
  const ok = applyAnnotation(recipe({ parameters: [{ name: 'EDGE_EX', point_count: 0 }] }))
  assert.equal(evaluateRecipe(ok, resolveRuleCell(ok, [coreEarlyDram])).pass, true)
  const bad = applyAnnotation(recipe({ parameters: [{ name: 'EDGE_EX', point_count: 1 }] }))
  assert.equal(evaluateRecipe(bad, resolveRuleCell(bad, [coreEarlyDram])).pass, false)
})

// --- D6 Sample matrix: per-type caps + NAND EDGE 8 ---
test('D6 Sample DRAM caps per type', () => {
  assert.equal(capFor({ name: 'WAFER', point_count: 13 }, sampleDram), 13)
  assert.equal(capFor({ name: 'LEVEL', point_count: 4 }, sampleDram), 4)
  assert.equal(capFor({ name: 'EDGE', point_count: 10 }, sampleDram), 10)
  assert.equal(capFor({ name: 'EDGE_EX', point_count: 0 }, sampleDram), 0)
})
test('D6 Sample NAND: EDGE cap 8', () => {
  assert.equal(capFor({ name: 'EDGE', point_count: 8 }, sampleNand), 8)
})

// --- D16/D17/D18 thresholds are injected, not hardcoded ---
test('D16 classifyHealth honors injected thresholds', () => {
  const t = { yellow_at: 0.3, red_at: 0.6 }
  assert.equal(classifyHealth(0.25, t), 'green') // would be red under seed 0.1/0.2
  assert.equal(classifyHealth(0.45, t), 'yellow')
  assert.equal(classifyHealth(0.7, t), 'red')
})
test('D17 evaluateLot threads thresholds through to health', () => {
  const recipes = [
    recipe({ recipe_id: 'r1', parameters: [{ name: 'EDGE', point_count: 12 }] }), // violation
    recipe({ recipe_id: 'r2', parameters: [{ name: 'EDGE', point_count: 8 }] }) // ok
  ]
  // ratio 0.5 → red under seed, but green under a permissive saved threshold
  assert.equal(evaluateLot('R3K-12', recipes, [coreEarlyDram]).health, 'red')
  assert.equal(evaluateLot('R3K-12', recipes, [coreEarlyDram], { thresholds: { yellow_at: 0.6, red_at: 0.8 } }).health, 'green')
})

// --- SEQ group (region): son 은 mother 의 cap 을 물려받습니다 (user-confirmed 2026-08-18) ---
// idp 의 한 Region 은 image definition 1개이고, 그 안에서 Mother_Para=True 인
// parameter 1개가 mother, 나머지는 son 입니다. son 은 mother 와 **같은 image** 에서
// 자기 cd_value 를 얻으므로 자기 이름의 타입 cap 이 아니라 mother 의 cap 을 씁니다.
const seqRecipe = (params: Array<{ name: string, point_count: number, mother?: boolean, region?: number | null }>) =>
  recipe({ parameters: params.map(p => ({ mother: false, ...p })) })

test('SEQ group: son 이 mother(WAFER 13) 의 cap 을 물려받아 13 이 위반이 아니다', () => {
  // 실물 관찰: WAFER 1/8, CELL_SP 2/8, LWR 3/8 이 같은 Region 이고 모두 13 point.
  const r = seqRecipe([
    { name: 'WAFER', point_count: 13, mother: true, region: 1 },
    { name: 'CELL_SP', point_count: 13, region: 1 },
    { name: 'LWR', point_count: 13, region: 1 }
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [coreEarlyDram]))
  assert.deepEqual(res.violation_params.map(p => p.name), [])
  assert.deepEqual(res.results.map(p => p.cap), [13, 13, 13])
})

test('SEQ group: 물려받은 cap 에도 이빨이 있다 — LEVEL(4) mother 의 son 은 13 이면 위반', () => {
  const r = seqRecipe([
    { name: 'LEVEL_1', point_count: 4, mother: true, region: 2 },
    { name: 'CELL_SP', point_count: 13, region: 2 }
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [coreEarlyDram]))
  assert.deepEqual(res.violation_params.map(p => p.name), ['CELL_SP'])
  // CELL_SP 의 cap 출처는 `_other` 라 상속이 걸립니다 — mother 의 4 를 그대로
  // 물려받고, 13 은 위반입니다.
  assert.equal(res.results[1]?.cap, 4)
})

test('SEQ group: mother 의 면제(cap=null)도 son 에게 이어진다', () => {
  // Sample 셀의 WAFER/WF affix override 는 cap=null(무제한)입니다. 이 override 는
  // OTHER 타입에만 걸리므로(D9) mother 이름을 'CD_WF' 로 둡니다 — 'WAFER_CD' 는
  // 타입이 WAFER 라 타입 cap 13 이 이깁니다.
  const r = recipe({
    recipe_class: 'Sample',
    parameters: [
      { name: 'CD_WF', point_count: 40, mother: true, region: 1 },
      { name: 'CELL_SP', point_count: 40, mother: false, region: 1 }
    ]
  })
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [sampleDram]))
  assert.deepEqual(res.violation_params.map(p => p.name), [])
})

test('SEQ group: region 이 다르면 물려받지 않는다', () => {
  const r = seqRecipe([
    { name: 'WAFER', point_count: 13, mother: true, region: 1 },
    { name: 'CELL_SP', point_count: 13, region: 2 } // 다른 image — 스스로 잽니다
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [coreEarlyDram]))
  assert.deepEqual(res.violation_params.map(p => p.name), ['CELL_SP'])
})

test('SEQ group: mother 가 없는 region 은 각자 자기 cap 으로 판정한다', () => {
  const r = seqRecipe([
    { name: 'WAFER', point_count: 13, region: 3 },
    { name: 'CELL_SP', point_count: 13, region: 3 }
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [coreEarlyDram]))
  assert.deepEqual(res.violation_params.map(p => p.name), ['CELL_SP'])
})

test('SEQ group: region 이 없는(판별 불가) 파라미터는 예전 그대로 자기 cap', () => {
  const r = seqRecipe([
    { name: 'WAFER', point_count: 13, mother: true },
    { name: 'CELL_SP', point_count: 13 }
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [coreEarlyDram]))
  assert.deepEqual(res.violation_params.map(p => p.name), ['CELL_SP'])
})

test('SEQ group: mother 자신은 언제나 자기 cap 으로 판정한다', () => {
  const r = seqRecipe([
    { name: 'CELL_SP', point_count: 13, mother: true, region: 1 }, // _other 9
    { name: 'LWR', point_count: 13, region: 1 }
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [coreEarlyDram]))
  // mother 가 자기 cap 을 넘었으므로 둘 다 위반입니다 (son 은 물려받은 9 를 넘음).
  assert.deepEqual(res.violation_params.map(p => p.name), ['CELL_SP', 'LWR'])
})

// ── 그룹 cap 은 D9 면제를 덮지 않습니다 (b5d8dcdb 회귀 방지) ──────────────────
test('effectiveCap: DUMMY son keeps its own 면제, it does not inherit the mother cap', () => {
  // b5d8dcdb 가 user-confirmed 2026-08-05 로 확정한 규칙입니다 — Sample 셀은
  // `_other` cap 이 0 이라 DUMMY 는 point 1 개만 있어도 자동 위반이 되고, 그
  // 위반은 recipe 를 고쳐 없앨 수 있는 종류가 아니라 고칠 수 있는 진짜 위반을
  // 목록에서 밀어냅니다. name_override 의 cap=null 이 "상한 없음 = 절대 위반
  // 아님" 입니다.
  //
  // 그룹 cap(2026-08-18)이 들어오면서 son 은 무조건 mother 의 cap 을 물려받게
  // 되었고, 그래서 region 이 붙은 DUMMY 는 자기 면제를 잃습니다. 집에서는 mock
  // 이 Dummy·Align 에 region 을 주지 않아 이 경로가 아예 만들어지지 않지만,
  // office 의 `_param_regions` 는 이름을 가리지 않고 모든 row 에 region 을
  // 붙입니다 — 그래서 사무실에서만 터지는 모양입니다.
  const mother = { name: 'SOME_OTHER_PARAM', point_count: 1, mother: true, region: 1 }
  const dummySon = { name: 'DUMMY', point_count: 1, mother: false, region: 1 }

  assert.equal(capFor(dummySon, sampleDram), null, '이름만으로는 면제입니다')

  const caps = groupCaps([mother, dummySon], sampleDram)
  assert.equal(
    effectiveCap(dummySon, sampleDram, caps), null,
    'DUMMY 는 그룹에 묶여도 절대 위반이 아닙니다'
  )
})

test('effectiveCap: a plain OTHER son still inherits its mother cap', () => {
  // 면제 예외가 그룹 상속 자체를 무너뜨리면 안 됩니다 — 이빨은 남아야 합니다.
  const mother = { name: 'WAFER_X', point_count: 13, mother: true, region: 2 }
  const son = { name: 'CELL_SP', point_count: 13, mother: false, region: 2 }
  const caps = groupCaps([mother, son], coreEarlyDram)
  assert.equal(effectiveCap(son, coreEarlyDram, caps), 13)
})

// ── 그룹 상속은 fallback cap 에만 걸립니다 (D9) ──────────────────────────────
// 규칙과 그 이유는 ruleEngine.effectiveCap 의 주석에 있습니다. 여기서 고정하는
// 것은 "D9 가 실제로 정한 cap 은 상속이 덮지 않는다" 세 갈래 전부입니다 —
// 갈래마다 따로 막던 시절에 갈래마다 하나씩 샜기 때문입니다. (면제 갈래는 위
// DUMMY 테스트가 이미 봅니다.)
test('effectiveCap: D9 가 정한 cap 을 가진 son 은 mother 의 cap 을 물려받지 않는다', () => {
  const mother = { name: 'LEVEL_1', point_count: 4, mother: true, region: 1 }
  // WAFER_CD 는 타입 cap 13, CD_WF_1 은 OTHER 이지만 name_override(contains WF)로 13.
  // 후자는 타입만 보는 방어를 그대로 통과하던 갈래입니다.
  for (const name of ['WAFER_CD', 'CD_WF_1']) {
    const son = { name, point_count: 13, mother: false, region: 1 }
    assert.equal(effectiveCap(son, coreEarlyDram, groupCaps([mother, son], coreEarlyDram)), 13, name)
  }
})

test('SEQ group: EDGE son 은 WAFER mother 의 13 을 물려받지 않는다', () => {
  // EDGE 상한(8/10)은 "가장자리를 몇 점 재느냐" 라는 고유의 룰이라 WAFER 파라미터와
  // 다르게 판정되어야 합니다 (user-confirmed 2026-08-21). 상속이 이것까지 올려 주면
  // EDGE 룰이 사라집니다 — 홈 기준 recipe 6,208 건이 그렇게 가려지고 있었습니다.
  const r = seqRecipe([
    { name: 'WAFER_CD', point_count: 13, mother: true, region: 1 },
    { name: 'EDGE_R', point_count: 11, region: 1 }
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [coreEarlyDram]))
  assert.equal(res.results[1]?.cap, 10, 'EDGE 는 자기 룰을 지킵니다')
  assert.deepEqual(res.violation_params.map(p => p.name), ['EDGE_R'])
})

test('SEQ group: WAFER 13 을 재는 son 은 위반이 아니다 (사무실 모양)', () => {
  const r = seqRecipe([
    { name: 'LEVEL_1', point_count: 4, mother: true, region: 1 },
    { name: 'WAFER_CD', point_count: 13, region: 1 }
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [coreEarlyDram]))
  assert.deepEqual(res.violation_params.map(p => p.name), [])
  assert.equal(res.results[1]?.cap, 13)
})

test('resolveCap: cap 의 출처를 함께 돌려준다', () => {
  // 상속이 읽는 것이 값이 아니라 이 출처입니다. capFor 는 얇은 wrapper 라
  // 기존 호출부가 그대로 남습니다.
  assert.deepEqual(resolveCap({ name: 'WAFER_CD', point_count: 13 }, coreEarlyDram), { cap: 13, source: 'type' })
  assert.deepEqual(resolveCap({ name: 'CD_WF_1', point_count: 13 }, coreEarlyDram), { cap: 13, source: 'name' })
  assert.deepEqual(resolveCap({ name: 'CELL_SP', point_count: 13 }, coreEarlyDram), { cap: 9, source: 'fallback' })
  assert.deepEqual(resolveCap({ name: 'Dummy', point_count: 1 }, sampleDram), { cap: null, source: 'name' })
})

// ── son 판정 토글 (judgeSons) ────────────────────────────────────────────────
// 무엇을 왜 빼는지는 ruleEngine.JudgeOptions 의 주석에 있습니다.
test('judgeSons=false: son 은 cap 을 넘어도 위반이 아니다', () => {
  const r = seqRecipe([
    { name: 'CELL_SP', point_count: 13, mother: true, region: 1 },
    { name: 'LWR', point_count: 13, region: 1 }
  ])
  const merged = applyAnnotation(r)
  const res = resolveRuleCell(merged, [coreEarlyDram])
  const off = evaluateRecipe(merged, res, { judgeSons: false })
  assert.deepEqual(off.violation_params.map(p => p.name), ['CELL_SP'], 'mother 는 계속 판정합니다')
  // cap 을 지우지 않는 것이 요점입니다 — `judged` 와 함께라야 화면이 "상한 9 인데
  // 13, 판정 제외" 를 말할 수 있고, 준수한 파라미터와 구별됩니다.
  assert.equal(off.results[1]?.cap, 9)
  assert.equal(off.results[1]?.judged, false)
  assert.equal(off.results[0]?.judged, true)
})

test('judgeSons=false: mother 가 없는 recipe 는 통째로 빠지지 않는다', () => {
  // `mother` 플래그가 false 라는 것만으로 son 이라고 보면, 원천이 mother 를
  // 기록하지 않은 recipe 의 **모든** 파라미터가 판정에서 빠집니다. 집 mock 에서만
  // 판정 대상의 15.2%(31,021건)가 그런 recipe 이고, 그 recipe 들의 위반
  // 13,755 건이 토글 한 번에 통째로 사라졌습니다 — 독립적으로 잰 파라미터까지.
  //
  // region 이 있어도 그 region 에 mother 가 없으면 마찬가지입니다. 얹혀 갈 상대가
  // 없으므로 자기 측정입니다.
  const noMother = seqRecipe([
    { name: 'WAFER_CD', point_count: 99, region: 1 },
    { name: 'EDGE_L', point_count: 99 }
  ])
  const merged = applyAnnotation(noMother)
  const res = resolveRuleCell(merged, [coreEarlyDram])
  const off = evaluateRecipe(merged, res, { judgeSons: false })
  assert.deepEqual(off.violation_params.map(p => p.name), ['WAFER_CD', 'EDGE_L'])
  assert.ok(off.results.every(p => p.judged), '묶을 근거가 없으면 판정합니다')
})

test('evaluateLot: judgeSons=false 가 lot 집계까지 이어진다', () => {
  const sonOnly = recipe({
    recipe_id: 'ADI/CD_BIAS_R000_001',
    parameters: [
      // son 은 mother 와 **같은** region 이어야 합니다 — 다른 region 에 두면 얹혀
      // 갈 mother 가 없어 son 이 아니고, 토글과 무관하게 판정됩니다.
      { name: 'WAFER_CD', point_count: 13, mother: true, region: 1 },
      { name: 'LWR', point_count: 99, mother: false, region: 1 }
    ]
  })
  assert.equal(evaluateLot('R000', [sonOnly], [coreEarlyDram]).violation_recipes, 1)
  const off = evaluateLot('R000', [sonOnly], [coreEarlyDram], { judgeSons: false })
  assert.equal(off.violation_recipes, 0)
  assert.equal(off.judged_recipes, 1, '판정 대상에서 빠지는 것은 파라미터이지 recipe 가 아닙니다')
})

// ── Align 면제 (user-confirmed 2026-08-10) ───────────────────────────────────
// DUMMY 와 같은 근거입니다 — 정렬은 측정이 아니라 측정을 위한 준비라 "얼마나
// 많이 쟀는가" 의 답에 들어가면 안 됩니다. Sample 셀의 `_other` 가 0 이라 면제가
// 없으면 point 1~3 개짜리 Align 이 자동 위반이 되고, 그 위반은 recipe 를 고쳐
// 없앨 수 없으므로 진짜 위반을 목록에서 밀어냅니다. 집 mock 만으로도 2,607 건이
// 이렇게 잡히고 있었습니다.
test('capFor: Sample 셀의 Align 은 DUMMY 와 같이 면제', () => {
  for (const name of ['Align', 'ALIGN', 'CD_Align', 'Align_1']) {
    assert.equal(capFor({ name, point_count: 3 }, sampleDram), null, name)
  }
})

test('capFor: 이름 한복판의 align 은 면제가 아니다 (affix 규칙)', () => {
  assert.equal(capFor({ name: 'X_ALIGN_Y', point_count: 3 }, sampleDram), 0)
})

// --- role: idp Mother_Para 그대로 — mother 가 아니면 전부 son (user-confirmed 2026-09-02) ---
test('role: mother 는 mother, 나머지는 region 유무와 무관하게 son', () => {
  const r = seqRecipe([
    { name: 'WAFER', point_count: 13, mother: true, region: 1 },
    { name: 'CELL_SP', point_count: 13, region: 1 },
    { name: 'LWR', point_count: 13, region: 3 }, // mother 없는 region
    { name: 'EDGE_L', point_count: 13 } // region 을 읽지 못함
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [coreEarlyDram]))
  assert.deepEqual(res.results.map(p => [p.name, p.role]), [
    ['WAFER', 'mother'], ['CELL_SP', 'son'], ['LWR', 'son'], ['EDGE_L', 'son']
  ])
})

test('role: gray recipe 의 결과에도 role 은 실린다', () => {
  const r = seqRecipe([
    { name: 'WAFER', point_count: 13, mother: true, region: 1 },
    { name: 'CELL_SP', point_count: 13, region: 1 }
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), []))
  assert.equal(res.gray, 'A')
  assert.deepEqual(res.results.map(p => p.role), ['mother', 'son'])
})

// 이름표와 판정 제외는 다른 술어입니다 — son 이라도 mother 없는 region 이면
// 얹혀 갈 상대가 없어 토글과 무관하게 판정됩니다(ridesOnMother).
test('role: judgeSons=false 는 mother 있는 region 의 son 만 뺀다 — 이름표가 son 이어도', () => {
  const r = seqRecipe([
    { name: 'WAFER', point_count: 13, mother: true, region: 1 },
    { name: 'CELL_SP', point_count: 13, region: 1 },
    { name: 'LWR', point_count: 13, region: 3 }
  ])
  const res = evaluateRecipe(applyAnnotation(r), resolveRuleCell(applyAnnotation(r), [coreEarlyDram]), { judgeSons: false })
  assert.deepEqual(res.results.map(p => [p.role, p.judged]), [
    ['mother', true], ['son', false], ['son', true]
  ])
})

// ---- 판정 근거 필드 (cap_source · over_by · basis) — 판정을 바꾸지 않는 기록 ----
test('over_by 는 위반일 때만 point_count - cap 이고, basis 는 적용된 셀을 가리킵니다', () => {
  const merged = applyAnnotation(recipe({ parameters: [
    { name: 'WAFER_CD', point_count: 13 },
    { name: 'EDGE_L', point_count: 16 },
    { name: 'CELL_SP', point_count: 9 }
  ] }))
  const res = evaluateRecipe(merged, resolveRuleCell(merged, [coreEarlyDram]))
  assert.equal(res.basis.cell?.id, 'r3-core-tev-dram')
  assert.deepEqual(res.results.map(p => [p.name, p.cap_source, p.over_by]), [
    ['WAFER_CD', 'type', null],
    ['EDGE_L', 'type', 6],
    ['CELL_SP', 'fallback', null]
  ])
  assert.ok(res.results.every(p => (p.over_by !== null) === p.violation))
})

test('judgeSons=false 로 뺀 son 은 cap 을 넘어도 over_by 가 null 입니다', () => {
  const merged = applyAnnotation(recipe({ parameters: [
    { name: 'WAFER_CD', point_count: 13, mother: true, region: 1 },
    { name: 'EDGE_L', point_count: 16, mother: false, region: 1 }
  ] }))
  const res = evaluateRecipe(merged, resolveRuleCell(merged, [coreEarlyDram]), { judgeSons: false })
  const son = res.results[1]!
  assert.deepEqual([son.over_cap, son.violation, son.over_by], [true, false, null])
})

test('gray 는 basis.cell 이 null 이고 파라미터의 cap_source 는 unset 입니다', () => {
  const merged = applyAnnotation(recipe({ parameters: [{ name: 'EDGE_L', point_count: 99 }] }))
  const res = evaluateRecipe(merged, resolveRuleCell(merged, []))
  assert.equal(res.gray, 'A')
  assert.equal(res.basis.cell, null)
  assert.equal(res.gray_field, undefined)
  assert.deepEqual(res.results.map(p => [p.cap_source, p.over_by]), [['unset', null]])
})

test('Gray-B 는 비어 있던 어노테이션 필드를 gray_field 로 남깁니다', () => {
  const merged = applyAnnotation(recipe({ memory_class_auto: 'unknown', parameters: [{ name: 'EDGE_L', point_count: 1 }] }))
  const res = evaluateRecipe(merged, resolveRuleCell(merged, [coreEarlyDram]))
  assert.deepEqual([res.gray, res.gray_field], ['B', 'memory_class'])
})

test('applyAnnotation 은 memory_class 의 출처를 남깁니다', () => {
  const base = recipe({})
  assert.equal(applyAnnotation(base).memory_class_origin, 'auto')
  const unknown = { ...base, memory_class_auto: 'unknown' as const }
  assert.equal(applyAnnotation(unknown).memory_class_origin, null)
  assert.equal(applyAnnotation(unknown, { memory_class: 'NAND' }).memory_class_origin, 'annotation')
})
