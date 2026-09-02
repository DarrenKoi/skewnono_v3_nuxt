// Pure-logic tests for recipeParamExport. Run: node --test app/utils/recipeParamExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildParamWorkbook,
  buildRecipeWorkbook,
  paramExportFilename,
  recipeExportFilename,
  EXPORT_IMAGE_SLOTS
} from './recipeParamExport.ts'
import type { ParamExportInput, ParamWorkbook } from './recipeParamExport.ts'

const LOCATOR = { eqp_ip: '10.1.2.3', class_name: 'CLS', idw: 'IDW_A', idp: 'IDP_B' }

const IDP = {
  Parameter: 'Para_13',
  SEQ: 4,
  Last_SEQ: 6,
  Region: 1,
  Addressing: true,
  Mother_Para: false,
  Double_Addressing: false,
  Meas_Counting: 5,
  dnumber_removed: false,
  img_add1: 'IMMP0004',
  img_add2: 'PRMP0000',
  image_add3: 'non',
  img_meas1: 'IMMS0000',
  img_meas2: 'PRMS0000'
}

const DETAIL = {
  parameter: 'Para_13',
  amp: { source: 'PRMS0000', rows: [{ key: 'ACCV', value: '800' }] },
  af_pr: {
    source: 'ENMP0000',
    rows: [
      { key: 'MODE', value: 'AUTO', section: 'ADD1' },
      { key: 'MODE', value: 'MANUAL', section: 'ADD2' }
    ]
  },
  images: [
    {
      slot: 'img_add1',
      stage: 'Addressing 1',
      name: 'IMMP0004.jpeg',
      cond: { source: 'cond.txt', rows: [{ key: 'MAG', value: '50k' }] }
    },
    {
      slot: 'img_meas1',
      stage: 'Measure 1',
      name: 'IMMS0000.jpeg',
      cond: { source: 'cond.txt', rows: [{ key: 'MAG', value: '120k' }] }
    }
  ]
}

const POINT = {
  ChipNo_X: 3,
  ChipNo_Y: 4,
  Coordinate_X: 1.25,
  Coordinate_Y: -2.5,
  P_No: 1,
  D_No: 7,
  Diff: false,
  Rel: true,
  Rel_MoveX: 0.1,
  Rel_MoveY: 0.2,
  Coordinate_X_r: 1.35,
  Coordinate_Y_r: -2.3,
  Parameter: 'Para_13',
  img_meas2: 1
}

const input = (slots: string[]): ParamExportInput => ({
  recipeId: 'RCP_001',
  fabName: 'M11',
  toolLabel: 'CD-SEM',
  locator: LOCATOR,
  idp: IDP,
  detail: DETAIL,
  mpRows: [POINT],
  slots,
  exportedAt: '2026-08-02T06:00:00+09:00'
})

const sheet = (wb: ParamWorkbook, name: string) =>
  wb.sheets.find(s => s.name === name)!

const MEASURE = [...EXPORT_IMAGE_SLOTS.measure]
const EVERY_SLOT = [...EXPORT_IMAGE_SLOTS.measure, ...EXPORT_IMAGE_SLOTS.addressing]

test('measurement-only export has the five sheets in order', () => {
  const wb = buildParamWorkbook(input(MEASURE))
  assert.deepEqual(wb.sheets.map(s => s.name), ['개요', 'AMP', 'AF_PR', '이미지', '측정 위치'])
})

test('측정 위치 is a header row plus one row per point, without img_meas2', () => {
  // img_meas2 is P_No again in this table (user-confirmed 2026-08-05) and
  // would read as a second fact.
  const rows = sheet(buildParamWorkbook(input(MEASURE)), '측정 위치').rows
  assert.equal(rows.length, 2)
  assert.ok(rows[0]!.includes('Coordinate_X_r'))
  assert.ok(!rows[0]!.includes('img_meas2'))
  const point = new Map(rows[0]!.map((key, i) => [String(key), rows[1]![i]]))
  assert.equal(point.get('Parameter'), 'Para_13')
  assert.equal(point.get('ChipNo_X'), 3)
  assert.equal(point.get('Diff'), false)
})

test('a parameter with no points still gets a readable 측정 위치 sheet', () => {
  const rows = sheet(buildParamWorkbook({ ...input(MEASURE), mpRows: [] }), '측정 위치').rows
  assert.equal(rows.length, 2)
  assert.ok(String(rows[1]![0]).includes('측정 포인트가 없습니다'))
})

test('개요 carries the idp row, the locator and the export time', () => {
  const wb = buildParamWorkbook(input(MEASURE))
  const flat = new Map(sheet(wb, '개요').rows.map(r => [String(r[0]), r[1]]))
  assert.equal(flat.get('recipe_id'), 'RCP_001')
  assert.equal(flat.get('Parameter'), 'Para_13')
  assert.equal(flat.get('SEQ'), 4)
  assert.equal(flat.get('Meas_Counting'), 5)
  assert.equal(flat.get('eqp_ip'), '10.1.2.3')
  assert.equal(flat.get('exported_at'), '2026-08-02T06:00:00+09:00')
})

test('개요 keeps false apart from missing', () => {
  // Mother_Para false is a real answer — "this parameter is not a mother" —
  // and must not render as the same blank a truly absent field gets.
  const wb = buildParamWorkbook(input(MEASURE))
  const flat = new Map(sheet(wb, '개요').rows.map(r => [String(r[0]), r[1]]))
  assert.equal(flat.get('Mother_Para'), false)
  assert.equal(flat.get('dnumber_removed'), false)
})

test('AMP keeps reader order and records its source file as a row', () => {
  const wb = buildParamWorkbook(input([]))
  const rows = sheet(wb, 'AMP').rows
  assert.deepEqual(rows[0], ['source: PRMS0000'])
  assert.deepEqual(rows[1], ['key', 'value'])
  assert.deepEqual(rows[2], ['ACCV', '800'])
})

test('AF_PR keeps section as its own column, not a flattened label', () => {
  // A row's identity is (section, key): two addressing passes carry the SAME
  // inner key, so a flattened "ADD1.MODE" label would need string surgery to
  // read back, and a bare "MODE" would show one pass's value under both.
  const wb = buildParamWorkbook(input([]))
  const rows = sheet(wb, 'AF_PR').rows
  assert.deepEqual(rows[0], ['source: ENMP0000'])
  assert.deepEqual(rows[1], ['section', 'key', 'value'])
  assert.deepEqual(rows[2], ['ADD1', 'MODE', 'AUTO'])
  assert.deepEqual(rows[3], ['ADD2', 'MODE', 'MANUAL'])
})

test('AF_PR keeps three columns even when no row carries a section', () => {
  // The sheet's shape is a contract a script may parse. Derivation may ADD the
  // column (see below) but must never be able to take it away.
  const wb = buildParamWorkbook({
    ...input([]),
    detail: {
      ...DETAIL,
      af_pr: { source: 'ENMP0000', rows: [{ key: 'MODE', value: 'AUTO' }] }
    }
  })
  const rows = sheet(wb, 'AF_PR').rows
  assert.deepEqual(rows[1], ['section', 'key', 'value'])
  assert.deepEqual(rows[2], ['', 'MODE', 'AUTO'])
})

test('the section column is derived from the rows, not the sheet name', () => {
  // AMP has no sections today, but a file that grows them must not lose the
  // column just because its call site once said "not sectioned".
  const wb = buildParamWorkbook({
    ...input([]),
    detail: {
      ...DETAIL,
      amp: { source: 'PRMS0000', rows: [{ key: 'ACCV', value: '800', section: 'G1' }] }
    }
  })
  assert.deepEqual(sheet(wb, 'AMP').rows[1], ['section', 'key', 'value'])
})

test('no sheet is written that the builder did not lay out', () => {
  // anchorRow indexes into sheet.rows, so a source line the WRITER prepended
  // would shift every embedded picture down one. Sources are rows here.
  const wb = buildParamWorkbook(input(MEASURE))
  for (const s of wb.sheets) {
    assert.ok(!('source' in s), `${s.name} still carries a source field`)
  }
})

test('이미지 includes only the requested slots', () => {
  const wb = buildParamWorkbook(input(MEASURE))
  assert.deepEqual(wb.images.map(i => i.slot), ['img_meas1'])
  const text = sheet(wb, '이미지').rows.flat().join('\n')
  assert.ok(text.includes('Measure 1'))
  assert.ok(!text.includes('Addressing 1'))
})

test('addressing slots come along when asked for, in slot order', () => {
  const wb = buildParamWorkbook(input(EVERY_SLOT))
  assert.deepEqual(wb.images.map(i => i.slot), ['img_add1', 'img_meas1'])
})

test('a requested slot with no image is labelled rather than dropped', () => {
  // image_add3 is "non" in this recipe, so no ParamImage exists for it. Naming
  // it is what lets a reader tell "not requested" from "not present".
  const wb = buildParamWorkbook(input(EVERY_SLOT))
  const text = sheet(wb, '이미지').rows.flat().join('\n')
  assert.ok(text.includes('Addressing 3'))
  assert.ok(text.includes('없음'))
  assert.ok(!wb.images.some(i => i.slot === 'image_add3'))
})

test('each placement anchors at a row that exists and is blank', () => {
  const wb = buildParamWorkbook(input(EVERY_SLOT))
  const rows = sheet(wb, '이미지').rows
  for (const placement of wb.images) {
    assert.ok(placement.anchorRow < rows.length)
    assert.deepEqual(rows[placement.anchorRow], [])
  }
})

test('each image carries its own beam condition below the picture', () => {
  const wb = buildParamWorkbook(input(MEASURE))
  const text = sheet(wb, '이미지').rows.flat().join('\n')
  assert.ok(text.includes('120k'))
  assert.ok(!text.includes('50k'))
})

test('an HV-SEM slot exports every suffixed file, not just the last one', () => {
  // One slot, several stem-suffixed files (2026-08-08). The old
  // one-ParamImage-per-slot Map kept only the LAST file — the export dropped
  // the rest with no cue.
  const multi = {
    ...DETAIL,
    images: [
      {
        slot: 'img_meas1', stage: 'Measure 1', name: 'IMMS0000-U.jpeg',
        cond: { source: '.IMMS0000-U.jpeg/cond.txt', rows: [{ key: 'MAG', value: '110k' }] }
      },
      {
        slot: 'img_meas1', stage: 'Measure 1', name: 'IMMS0000-L.jpeg',
        cond: { source: '.IMMS0000-L.jpeg/cond.txt', rows: [{ key: 'MAG', value: '130k' }] }
      }
    ]
  }
  const wb = buildParamWorkbook({ ...input(MEASURE), detail: multi })

  assert.deepEqual(wb.images.map(i => i.name), ['IMMS0000-U.jpeg', 'IMMS0000-L.jpeg'])
  const text = sheet(wb, '이미지').rows.flat().join('\n')
  assert.ok(text.includes('110k'), 'first variant cond exported')
  assert.ok(text.includes('130k'), 'second variant cond exported')
  // Placements still anchor at existing blank rows.
  const rows = sheet(wb, '이미지').rows
  for (const placement of wb.images) {
    assert.deepEqual(rows[placement.anchorRow], [])
  }
})

test('no slots requested still produces a readable 이미지 sheet', () => {
  const wb = buildParamWorkbook(input([]))
  assert.deepEqual(wb.images, [])
  assert.ok(sheet(wb, '이미지').rows.flat().join(' ').includes('포함된 이미지가 없습니다'))
})

test('a null detail still produces a readable workbook', () => {
  const wb = buildParamWorkbook({ ...input(MEASURE), detail: null })
  assert.deepEqual(wb.sheets.map(s => s.name), ['개요', 'AMP', 'AF_PR', '이미지', '측정 위치'])
  assert.ok(sheet(wb, 'AMP').rows.flat().join(' ').includes('파일 없음'))
  assert.deepEqual(wb.images, [])
})

test('filename is recipe and parameter, sanitised', () => {
  assert.equal(paramExportFilename('RCP/001', 'Para_13'), 'RCP_001_Para_13.xlsx')
  assert.equal(paramExportFilename('', ''), 'unknown_unknown.xlsx')
})

// ── whole recipe ──────────────────────────────────────────────────────────

const recipeInput = () => ({
  recipeId: 'RCP_001',
  fabName: 'M11',
  toolLabel: 'CD-SEM',
  locator: LOCATOR,
  idpRows: [IDP, { ...IDP, Parameter: 'Para_2', SEQ: 5 }],
  mpRows: [POINT, { ...POINT, Parameter: 'Para_2', P_No: 2 }],
  exportedAt: '2026-08-02T06:00:00+09:00'
})

test('whole-recipe workbook has three sheets and no image placements', () => {
  const wb = buildRecipeWorkbook(recipeInput())
  assert.deepEqual(wb.sheets.map(s => s.name), ['개요', '파라미터', '측정 위치'])
  assert.deepEqual(wb.images, [])
})

test('whole-recipe 개요 counts the rows it ships', () => {
  const flat = new Map(sheet(buildRecipeWorkbook(recipeInput()), '개요').rows.map(r => [String(r[0]), r[1]]))
  assert.equal(flat.get('recipe_id'), 'RCP_001')
  assert.equal(flat.get('parameter_rows'), 2)
  assert.equal(flat.get('points'), 2)
  assert.equal(flat.get('idp'), 'IDP_B')
})

test('whole-recipe 파라미터 keeps every row, including repeated parameter names', () => {
  // A row is one image definition; Para_13 twice is two rows, not a dup.
  const rows = sheet(buildRecipeWorkbook({
    ...recipeInput(),
    idpRows: [IDP, { ...IDP, SEQ: 11 }]
  }), '파라미터').rows
  assert.equal(rows.length, 3)
  assert.equal(rows[0]![0], 'Parameter')
  assert.deepEqual(rows.slice(1).map(r => r[1]), [4, 11])
})

test('whole-recipe 측정 위치 carries every parameter\'s points', () => {
  const rows = sheet(buildRecipeWorkbook(recipeInput()), '측정 위치').rows
  assert.deepEqual(rows.slice(1).map(r => r[0]), ['Para_13', 'Para_2'])
})

test('whole-recipe filename is the recipe, sanitised', () => {
  assert.equal(recipeExportFilename('RCP/001'), 'RCP_001_all.xlsx')
})
