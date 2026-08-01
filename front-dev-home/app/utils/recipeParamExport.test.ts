// Pure-logic tests for recipeParamExport. Run: node --test app/utils/recipeParamExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildParamWorkbook,
  paramExportFilename,
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

const input = (slots: string[]): ParamExportInput => ({
  recipeId: 'RCP_001',
  fabName: 'M11',
  toolLabel: 'CD-SEM',
  locator: LOCATOR,
  idp: IDP,
  detail: DETAIL,
  slots,
  exportedAt: '2026-08-02T06:00:00+09:00'
})

const sheet = (wb: ParamWorkbook, name: string) =>
  wb.sheets.find(s => s.name === name)!

const MEASURE = [...EXPORT_IMAGE_SLOTS.measure]
const EVERY_SLOT = [...EXPORT_IMAGE_SLOTS.measure, ...EXPORT_IMAGE_SLOTS.addressing]

test('measurement-only export has the four sheets in order', () => {
  const wb = buildParamWorkbook(input(MEASURE))
  assert.deepEqual(wb.sheets.map(s => s.name), ['개요', 'AMP', 'AF_PR', '이미지'])
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

test('AMP keeps reader order and records its source file', () => {
  const wb = buildParamWorkbook(input([]))
  const rows = sheet(wb, 'AMP').rows
  assert.deepEqual(rows[0], ['key', 'value'])
  assert.deepEqual(rows[1], ['ACCV', '800'])
  assert.equal(sheet(wb, 'AMP').source, 'PRMS0000')
})

test('AF_PR keeps section as its own column, not a flattened label', () => {
  // A row's identity is (section, key): two addressing passes carry the SAME
  // inner key, so a flattened "ADD1.MODE" label would need string surgery to
  // read back, and a bare "MODE" would show one pass's value under both.
  const wb = buildParamWorkbook(input([]))
  const rows = sheet(wb, 'AF_PR').rows
  assert.deepEqual(rows[0], ['section', 'key', 'value'])
  assert.deepEqual(rows[1], ['ADD1', 'MODE', 'AUTO'])
  assert.deepEqual(rows[2], ['ADD2', 'MODE', 'MANUAL'])
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

test('no slots requested still produces a readable 이미지 sheet', () => {
  const wb = buildParamWorkbook(input([]))
  assert.deepEqual(wb.images, [])
  assert.ok(sheet(wb, '이미지').rows.flat().join(' ').includes('포함된 이미지가 없습니다'))
})

test('a null detail still produces a readable workbook', () => {
  const wb = buildParamWorkbook({ ...input(MEASURE), detail: null })
  assert.deepEqual(wb.sheets.map(s => s.name), ['개요', 'AMP', 'AF_PR', '이미지'])
  assert.ok(sheet(wb, 'AMP').rows.flat().join(' ').includes('파일 없음'))
  assert.deepEqual(wb.images, [])
})

test('filename is recipe and parameter, sanitised', () => {
  assert.equal(paramExportFilename('RCP/001', 'Para_13'), 'RCP_001_Para_13.xlsx')
  assert.equal(paramExportFilename('', ''), 'unknown_unknown.xlsx')
})
