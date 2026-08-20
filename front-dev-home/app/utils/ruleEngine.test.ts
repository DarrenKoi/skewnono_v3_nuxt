// Pure-logic tests for ruleEngine. Zero deps — run with Node's built-in runner:
//   node --test app/utils/ruleEngine.test.ts        (Node 24+ strips types)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  deriveType, deriveFamily, derivePhase, deriveMemoryClass,
  capFor, applyAnnotation, resolveRuleCell, evaluateRecipe, evaluateLot,
  classifyHealth, groupCaps, effectiveCap, type RuleCell, type RecipeInput
} from './ruleEngine.ts'

// --- fixtures ---
const coreEarlyDram: RuleCell = {
  id: 'r3-core-tev-dram',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['t-EV', 'EV'], memory_class: 'DRAM' },
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
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['t-EV', 'EV'], memory_class: 'NAND' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 8, EDGE_EX: 0, _other: 9 },
  name_overrides: [wfOverride]
}
const coreTvPv: RuleCell = {
  id: 'r3-core-tvpv',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Core', phase_in: ['TV', 'PV'] },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 16, EDGE_EX: 16, _other: 9 },
  name_overrides: [wfOverride]
}
// D8 — Pool keys on yield_check (phase ignored); after-yield opens EDGE_EX
const poolBeforeDram: RuleCell = {
  id: 'r3-pool-before-dram',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Pool', yield_check: 'before', memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 0, _other: 9 },
  name_overrides: [wfOverride]
}
const poolAfterDram: RuleCell = {
  id: 'r3-pool-after-dram',
  selector: { fac_id: 'R3', recipe_class: 'Main', family: 'Pool', yield_check: 'after', memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 10, EDGE_EX: 10, _other: 9 },
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
  selector: { fac_id: 'M14', recipe_class: 'Main', family: 'Core', phase_in: ['t-EV', 'EV'], memory_class: 'DRAM' },
  caps: { WAFER: 13, LEVEL: 4, EDGE: 99, EDGE_EX: 99, _other: 99 },
  name_overrides: []
}
const recipe = (over: Partial<RecipeInput>): RecipeInput => ({
  lot_cd: 'R3K-12', recipe_id: 'R', fac_id: 'R3', ctn_desc: 't-EV DRAM dev', prod_catg_cd: 'DRAM',
  recipe_class: 'Main', family: 'Core', phase: 't-EV', memory_class_auto: 'DRAM', parameters: [], ...over
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

// --- D3/D7 derivations ---
test('deriveFamily priority VG > Pool > Core', () => {
  assert.equal(deriveFamily('vertical gate pool lot'), 'VG_RTC_Cubic')
  assert.equal(deriveFamily('Pool제 dram'), 'Pool')
  assert.equal(deriveFamily('plain core lot'), 'Core')
})
test('derivePhase t-EV before EV, null fallback', () => {
  assert.equal(derivePhase('t-EV dram'), 't-EV')
  assert.equal(derivePhase('PV transfer'), 'PV')
  assert.equal(derivePhase('TV qual'), 'TV')
  assert.equal(derivePhase('EV early'), 'EV')
  assert.equal(derivePhase('no keyword'), null)
})
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

  const vg = applyAnnotation(recipe({ family: 'VG_RTC_Cubic' }))
  const grayA = resolveRuleCell(vg, [coreEarlyDram])
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
  const vg = applyAnnotation(recipe({ family: 'VG_RTC_Cubic', parameters: [{ name: 'EDGE', point_count: 999 }] }))
  const r = evaluateRecipe(vg, resolveRuleCell(vg, [coreEarlyDram]))
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

// --- D19 Sample Core TV/PV EDGE bumps to 16; specific cell must precede phase-blind ---
test('D19 Sample Core TV/PV EDGE 16 beats phase-blind Sample (order = precedence)', () => {
  const sampleCoreTvpv: RuleCell = {
    id: 'r3-sample-core-tvpv',
    selector: { fac_id: 'R3', recipe_class: 'Sample', family: 'Core', phase_in: ['TV', 'PV'] },
    caps: { WAFER: 13, LEVEL: 4, EDGE: 16, EDGE_EX: 0, _other: 0 },
    // providers/rules.py `_SAMPLE_OVERRIDES` 를 그대로 옮긴 것입니다 — DUMMY 면제
    // 포함 (user-confirmed 2026-08-05).
    name_overrides: [
      { patterns: ['WAFER', 'WF'], match: 'affix', cap: null },
      { patterns: ['DUMMY'], match: 'affix', cap: null }
    ]
  }
  const coreTvpvSample = applyAnnotation(
    recipe({ recipe_class: 'Sample', family: 'Core', phase: 'PV', parameters: [{ name: 'EDGE', point_count: 14 }] })
  )
  // specific cell first → first-match picks it; EDGE 14 ≤ 16 passes
  const res = resolveRuleCell(coreTvpvSample, [sampleCoreTvpv, sampleDram])
  assert.equal(res.kind === 'cell' && res.cell.id, 'r3-sample-core-tvpv')
  assert.equal(evaluateRecipe(coreTvpvSample, res).pass, true)
  // without the specific cell, the phase-blind cap 10 would (wrongly) flag it — documents the gap D19 closes
  const fallback = resolveRuleCell(coreTvpvSample, [sampleDram])
  assert.equal(evaluateRecipe(coreTvpvSample, fallback).pass, false)
})

// --- D7 VG·RTC·Cubic reduces to DRAM-side when class is otherwise unset ---
test('applyAnnotation: VG/RTC/Cubic falls back to DRAM (D7)', () => {
  const vg = applyAnnotation(recipe({ family: 'VG_RTC_Cubic', memory_class_auto: 'unknown' }))
  assert.equal(vg.memory_class, 'DRAM')
  // manual annotation still wins over the fallback
  const forced = applyAnnotation(recipe({ family: 'VG_RTC_Cubic', memory_class_auto: 'unknown' }), { memory_class: 'NAND' })
  assert.equal(forced.memory_class, 'NAND')
})

// --- D8 Main matrix: NAND EDGE 8, Core TV/PV EDGE 16, Pool yield_check keying ---
test('D8 Core early NAND: EDGE cap 8', () => {
  const r = applyAnnotation(recipe({ memory_class_auto: 'NAND', parameters: [{ name: 'EDGE', point_count: 10 }] }))
  const res = evaluateRecipe(r, resolveRuleCell(r, [coreEarlyNand]))
  assert.equal(res.pass, false) // 10 > 8
})
test('D8 Core TV/PV: EDGE/EDGE_EX cap 16, no memory split', () => {
  const r = applyAnnotation(recipe({ phase: 'PV', parameters: [{ name: 'EDGE', point_count: 16 }, { name: 'EDGE_EX', point_count: 16 }] }))
  const res = evaluateRecipe(r, resolveRuleCell(r, [coreTvPv]))
  assert.equal(res.pass, true) // 16 ≤ 16 boundary
})
test('D8 Pool keys on yield_check, ignores phase', () => {
  // before-yield: EDGE_EX must be 0
  const before = applyAnnotation(
    recipe({ family: 'Pool', ctn_desc: 'PV Pool제 dram', phase: 'PV', parameters: [{ name: 'EDGE_EX', point_count: 5 }] }),
    { yield_check: 'before' }
  )
  assert.equal(evaluateRecipe(before, resolveRuleCell(before, [poolBeforeDram, poolAfterDram])).pass, false)
  // after-yield: EDGE_EX up to 10 allowed
  const after = applyAnnotation(
    recipe({ family: 'Pool', phase: 'PV', parameters: [{ name: 'EDGE_EX', point_count: 5 }] }),
    { yield_check: 'after' }
  )
  assert.equal(evaluateRecipe(after, resolveRuleCell(after, [poolBeforeDram, poolAfterDram])).pass, true)
})
test('D14 Pool missing yield_check → Gray-B', () => {
  const r = applyAnnotation(recipe({ family: 'Pool', parameters: [{ name: 'EDGE_EX', point_count: 5 }] }))
  const res = resolveRuleCell(r, [poolBeforeDram, poolAfterDram])
  assert.equal(res.kind === 'gray' && res.gray, 'B')
  assert.equal(res.kind === 'gray' && res.reason, 'yield_check 미설정')
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
  assert.equal(evaluateLot('R3K-12', recipes, [coreEarlyDram], undefined, { yellow_at: 0.6, red_at: 0.8 }).health, 'green')
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

// ── 그룹 cap 은 명시적 타입 cap 을 덮지 않습니다 (D9) ────────────────────────
// 상속(2026-08-18)은 son 의 cap 을 **올리려고** 넣은 것입니다 — WAFER mother 의
// image 를 함께 쓰는 CELL_SP·LWR 이 `_other`(9)에 걸려 고칠 수 없는 위반이 되던
// 것을 없앴습니다. 그런데 같은 코드가 반대 방향으로도 걸려서, 이름으로 타입이
// 정해지는 파라미터의 cap 을 **내리기도** 했습니다: WAFER son 이 LEVEL(4) mother
// 밑에 있으면 13 point 를 재는 것이 위반으로 잡힙니다.
//
// D9 는 "타입 cap 이 이긴다" 입니다(`capFor`). 그 우선순위를 상속이 덮으면
// 룰 화면이 "WAFER 13" 이라고 적어 둔 값과 판정이 어긋납니다.
//
// 집에서는 이 모양이 만들어지지 않습니다 — mock 의 WAFER son 49,009 개가 전부
// mother 없는 region 에 있어 상속이 아예 발동하지 않습니다. office 의
// `_param_regions` 는 이름을 가리지 않고 모든 row 에 region 을 붙이므로 거기서만
// 나타납니다. DUMMY 면제(b5d8dcdb)와 같은 blind spot 이고, 그때는 면제 하나만
// 막고 타입 cap 은 같은 방식으로 지키지 않았습니다.
test('effectiveCap: WAFER son 은 LEVEL mother 밑에서도 자기 타입 cap 13 을 지킨다', () => {
  const mother = { name: 'LEVEL_1', point_count: 4, mother: true, region: 1 }
  const son = { name: 'WAFER_CD', point_count: 13, mother: false, region: 1 }
  const caps = groupCaps([mother, son], coreEarlyDram)
  assert.equal(effectiveCap(son, coreEarlyDram, caps), 13)
})

test('effectiveCap: WAFER son 은 OTHER mother 밑에서도 _other(9) 로 내려가지 않는다', () => {
  const mother = { name: 'OVL_X', point_count: 6, mother: true, region: 1 }
  const son = { name: 'WAFER_CD', point_count: 13, mother: false, region: 1 }
  const caps = groupCaps([mother, son], coreEarlyDram)
  assert.equal(effectiveCap(son, coreEarlyDram, caps), 13)
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

test('effectiveCap: 타입 cap 우선은 상속의 이빨을 건드리지 않는다 — OTHER son 은 그대로 물려받는다', () => {
  // 위 두 테스트가 상속 자체를 무력화하지 않았음을 고정합니다. CELL_SP 는 이름으로
  // 타입이 정해지지 않는(OTHER) 파라미터라 `_other` 가 fallback 일 뿐이고, 그래서
  // mother 의 cap 을 물려받는 것이 맞습니다 — 올리는 쪽도 내리는 쪽도.
  const raise = groupCaps(
    [{ name: 'WAFER_X', point_count: 13, mother: true, region: 1 },
      { name: 'CELL_SP', point_count: 13, mother: false, region: 1 }], coreEarlyDram)
  assert.equal(effectiveCap({ name: 'CELL_SP', point_count: 13, mother: false, region: 1 }, coreEarlyDram, raise), 13)

  const lower = groupCaps(
    [{ name: 'LEVEL_1', point_count: 4, mother: true, region: 2 },
      { name: 'CELL_SP', point_count: 13, mother: false, region: 2 }], coreEarlyDram)
  assert.equal(effectiveCap({ name: 'CELL_SP', point_count: 13, mother: false, region: 2 }, coreEarlyDram, lower), 4)
})

// ── son 판정 토글 (judgeSons) ────────────────────────────────────────────────
// son 은 mother 와 같은 image 에서 cd_value 를 꺼내므로 son 을 재는 데 드는
// 측정 point 가 따로 없습니다. 그래서 "son 은 애초에 상한이 겨냥한 대상이
// 아니다" 라고 볼 수도 있습니다. 어느 쪽이 옳은지는 도메인 판단이라 기본값
// (판정함)을 유지한 채 화면에서 끌 수 있게 둡니다.
test('judgeSons=false: son 은 cap 을 넘어도 위반이 아니다 (cap 표시는 남는다)', () => {
  const r = seqRecipe([
    { name: 'CELL_SP', point_count: 13, mother: true, region: 1 },
    { name: 'LWR', point_count: 13, region: 1 }
  ])
  const merged = applyAnnotation(r)
  const res = resolveRuleCell(merged, [coreEarlyDram])
  assert.deepEqual(
    evaluateRecipe(merged, res).violation_params.map(p => p.name), ['CELL_SP', 'LWR'],
    '기본값은 son 도 판정합니다'
  )
  const off = evaluateRecipe(merged, res, { judgeSons: false })
  assert.deepEqual(off.violation_params.map(p => p.name), ['CELL_SP'], 'mother 는 계속 판정합니다')
  assert.equal(off.results[1]?.cap, 9, 'son 의 cap 은 판정을 껐어도 화면에 그대로 보입니다')
})

test('judgeSons=false: mother 만 위반이던 recipe 의 판정은 달라지지 않는다', () => {
  const r = seqRecipe([
    { name: 'EDGE_R', point_count: 40, mother: true, region: 1 },
    { name: 'CELL_SP', point_count: 4, region: 1 }
  ])
  const merged = applyAnnotation(r)
  const res = resolveRuleCell(merged, [coreEarlyDram])
  assert.equal(evaluateRecipe(merged, res, { judgeSons: false }).pass, false)
})

test('evaluateLot: judgeSons=false 가 lot 집계까지 이어진다', () => {
  const sonOnly = recipe({
    recipe_id: 'ADI/CD_BIAS_R000_001',
    parameters: [
      { name: 'WAFER_CD', point_count: 13, mother: true, region: 1 },
      { name: 'LWR', point_count: 99, mother: false, region: 2 }
    ]
  })
  const on = evaluateLot('R000', [sonOnly], [coreEarlyDram])
  assert.equal(on.violation_recipes, 1)
  const off = evaluateLot('R000', [sonOnly], [coreEarlyDram], undefined, undefined, { judgeSons: false })
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
