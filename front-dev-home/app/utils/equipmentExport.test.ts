import { test } from 'node:test'
import assert from 'node:assert/strict'

import { buildTatEquipmentWorkbook } from './equipmentExport.ts'
import type {
  RecipeTatEquipmentRow,
  RecipeTatEquipmentCompareResponse
} from '~/composables/useRecipeTatApi'

// 판정 필드(tat_index, occupancy, usage_ratio)까지 채워둡니다 — 시트에
// **나오지 않아야** 한다는 것이 이 테스트가 지키는 성질이라, 값이 없으면
// 아무것도 증명하지 못합니다.
const equipment = (
  eqpId: string,
  over: Partial<RecipeTatEquipmentRow> = {}
): RecipeTatEquipmentRow => ({
  eqp_id: eqpId,
  fab_name: 'M14',
  eqp_model_cd: 'TP-5000',
  exec_count: 430,
  total_meastime: 8040,
  avg_meastime: 18.7,
  recipe_count: 12,
  top_recipe: 'QC/FAST_001',
  top_recipe_share: 0.42,
  tat_index: 1.08,
  occupancy: 0.62,
  usage_ratio: 1.13,
  ...over
})

const compare = (
  over: Partial<RecipeTatEquipmentCompareResponse> = {}
): RecipeTatEquipmentCompareResponse => ({
  tool_type: 'cd-sem',
  fab_names: ['M14'],
  start_date: '2026-08-01',
  end_date: '2026-08-02',
  eqp_ids: ['TP-1203', 'TP-1204'],
  trends: [
    {
      eqp_id: 'TP-1203',
      points: [
        { date: '2026-08-01', total_meastime: 3000, exec_count: 100 },
        { date: '2026-08-02', total_meastime: 5040, exec_count: 330 }
      ]
    },
    {
      eqp_id: 'TP-1204',
      points: [
        { date: '2026-08-01', total_meastime: 1000, exec_count: 40 },
        { date: '2026-08-02', total_meastime: 0, exec_count: 0 }
      ]
    }
  ],
  recipes: [
    {
      class_name: 'QC',
      recipe_name: 'FAST_001',
      full_name: 'QC/FAST_001',
      total_meastime: 6000,
      cells: [
        { eqp_id: 'TP-1203', meas_counts: 200, total_meastime: 4000, avg_meastime: 20 },
        { eqp_id: 'TP-1204', meas_counts: 100, total_meastime: 2000, avg_meastime: 20 }
      ]
    },
    {
      class_name: 'ADI',
      recipe_name: 'SLOW_002',
      full_name: 'ADI/SLOW_002',
      total_meastime: 3040,
      cells: [
        { eqp_id: 'TP-1203', meas_counts: 40, total_meastime: 3040, avg_meastime: 76 },
        // 돌지 않은 장비: 백엔드가 0으로 채워 보냅니다.
        { eqp_id: 'TP-1204', meas_counts: 0, total_meastime: 0, avg_meastime: 0 }
      ]
    }
  ],
  ...over
})

test('장비를 고르지 않으면 장비 시트 하나만 나온다', () => {
  const sheets = buildTatEquipmentWorkbook({
    equipments: [equipment('TP-1203')],
    compare: null
  })

  assert.deepEqual(sheets.map(s => s.name), ['장비'])
})

test('장비 시트에 지수·점유율·신호 열이 없다', () => {
  const [sheet] = buildTatEquipmentWorkbook({
    equipments: [equipment('TP-1203')],
    compare: null
  })

  assert.deepEqual(sheet!.rows[0], [
    'eqp_id', 'fab', 'model', 'exec_count',
    'total_meastime_sec', 'avg_meastime_sec', 'recipe_count'
  ])
  assert.deepEqual(sheet!.rows[1], ['TP-1203', 'M14', 'TP-5000', 430, 8040, 18.7, 12])
})

test('레시피 시트는 장비마다 세 열로 펼치고 미실행 평균은 빈 칸이다', () => {
  const sheets = buildTatEquipmentWorkbook({
    equipments: [equipment('TP-1203'), equipment('TP-1204')],
    compare: compare()
  })
  const sheet = sheets.find(s => s.name === '레시피')!

  assert.deepEqual(sheet.rows[0], [
    'full_name', 'total_meastime_sec',
    'TP-1203_meas_counts', 'TP-1203_total_meastime_sec', 'TP-1203_avg_meastime_sec',
    'TP-1204_meas_counts', 'TP-1204_total_meastime_sec', 'TP-1204_avg_meastime_sec'
  ])
  assert.deepEqual(sheet.rows[1], ['QC/FAST_001', 6000, 200, 4000, 20, 100, 2000, 20])
  // 돌지 않은 장비: 건수·합계는 0, 평균은 빈 칸.
  assert.deepEqual(sheet.rows[2], ['ADI/SLOW_002', 3040, 40, 3040, 76, 0, 0, ''])
})

test('일별추이 시트는 날짜마다 한 행이고 장비마다 두 열이다', () => {
  const sheets = buildTatEquipmentWorkbook({
    equipments: [equipment('TP-1203'), equipment('TP-1204')],
    compare: compare()
  })
  const sheet = sheets.find(s => s.name === '일별추이')!

  assert.deepEqual(sheet.rows[0], [
    'date',
    'TP-1203_total_meastime_sec', 'TP-1203_exec_count',
    'TP-1204_total_meastime_sec', 'TP-1204_exec_count'
  ])
  assert.deepEqual(sheet.rows[1], ['2026-08-01', 3000, 100, 1000, 40])
  assert.deepEqual(sheet.rows[2], ['2026-08-02', 5040, 330, 0, 0])
})

test('열 순서는 플릿 표가 아니라 응답의 eqp_ids 를 따른다', () => {
  // 플릿 표는 총 TAT 내림차순이라 선택 순서와 다를 수 있습니다. 매트릭스의
  // cells 는 eqp_ids 순서로 0채움되어 오므로, 헤더가 그 순서를 따르지 않으면
  // 열이 통째로 밀려 다른 장비의 숫자를 보여줍니다.
  const sheets = buildTatEquipmentWorkbook({
    equipments: [equipment('TP-1204'), equipment('TP-1203')],
    compare: compare()
  })
  const sheet = sheets.find(s => s.name === '레시피')!

  assert.equal(sheet.rows[0]![2], 'TP-1203_meas_counts')
})
