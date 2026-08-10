# 03 — Fail 장비별 워크북 빌더

Status: open
Plan: [`../plan.md`](../plan.md)
Blocked by: 01

Align/Meas 탭의 장비별 결과를 시트 3개로 조립합니다. 02의 TAT 빌더와 같은
파일에 나란히 둡니다 — 두 탭의 시트 규격이 서로를 참조해야 어긋나지 않고,
어긋나면 두 탭의 파일이 다른 모양이 됩니다.

**Files:**

- Modify: `front-dev-home/app/utils/equipmentExport.ts` (02가 만든 파일에 추가)
- Modify: `front-dev-home/app/utils/equipmentExport.test.ts` (02가 만든 파일에 추가)

**Interfaces:**

- Consumes: `WorkbookSheet` (`./xlsx.ts`), `EQUIPMENT_HEADERS`·`BLANK` (02가 같은 파일에 둔 상수)
- Produces:

```ts
export type FailSection = 'align' | 'meas'
export interface FailEquipmentWorkbookInput {
  equipments: FailIssueEquipmentRow[]
  compare: FailIssueEquipmentCompareResponse | null
  section: FailSection
}
export function buildFailEquipmentWorkbook(
  input: FailEquipmentWorkbookInput
): WorkbookSheet[]
```

**시트 규격** (`<축>`은 `align` 또는 `meas`)

| 시트 | 헤더 |
| --- | --- |
| `장비` | `eqp_id`, `fab`, `model`, `exec_count`, `<축>_fail_count`, `<축>_fail_rate_pct`, `recipe_count` |
| `레시피` | `full_name`, `total_exec_count`, `total_<축>_fail_count`, 그리고 장비마다 `<eqp>_exec_count`, `<eqp>_<축>_fail_count`, `<eqp>_<축>_fail_rate_pct` |
| `일별추이` | `date`, 그리고 장비마다 `<eqp>_exec_count`, `<eqp>_<축>_fail_count` |

보고 있는 축만 냅니다. 응답은 두 축을 다 담고 있지만, 파일에 둘이 섞이면
어느 축인지 파일만 보고는 알 수 없습니다.

레시피 행은 **활성 축의 실패 건수 내림차순**입니다 — 화면이 같은 정렬을
하므로 파일과 화면의 행 순서가 같아야 합니다.

---

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`front-dev-home/app/utils/equipmentExport.test.ts` 아래에 이어 붙입니다.
상단 import 두 줄도 함께 고칩니다:

```ts
import {
  buildFailEquipmentWorkbook,
  buildTatEquipmentWorkbook
} from './equipmentExport.ts'
import type {
  FailIssueEquipmentRow,
  FailIssueEquipmentCompareResponse
} from '~/composables/useFailIssueApi'
```

이어 붙일 테스트:

```ts
// 지수·구간까지 채워둡니다 — 시트에 나오지 않아야 한다는 것이 이 테스트가
// 지키는 성질입니다.
const failEquipment = (
  eqpId: string,
  over: Partial<FailIssueEquipmentRow> = {}
): FailIssueEquipmentRow => ({
  eqp_id: eqpId,
  fab_name: 'M14',
  eqp_model_cd: 'TP-5000',
  exec_count: 430,
  align_fail_count: 12,
  align_fail_rate: 0.0279,
  align_expected: 9.4,
  align_index: 1.28,
  align_index_low: 1.02,
  align_index_high: 1.61,
  meas_fail_count: 4,
  meas_fail_rate: 0.0093,
  meas_expected: 6.1,
  meas_index: 0.66,
  meas_index_low: 0.21,
  meas_index_high: 1.54,
  recipe_count: 12,
  top_recipe: 'QC/FAST_001',
  top_recipe_share: 0.42,
  ...over
})

const failCompare = (
  over: Partial<FailIssueEquipmentCompareResponse> = {}
): FailIssueEquipmentCompareResponse => ({
  tool_type: 'cd-sem',
  fab_names: ['M14'],
  start_date: '2026-08-01',
  end_date: '2026-08-02',
  eqp_ids: ['TP-1203', 'TP-1204'],
  trends: [
    {
      eqp_id: 'TP-1203',
      points: [
        { date: '2026-08-01', exec_count: 100, align_fail_count: 3, meas_fail_count: 1 },
        { date: '2026-08-02', exec_count: 330, align_fail_count: 9, meas_fail_count: 3 }
      ]
    },
    {
      eqp_id: 'TP-1204',
      points: [
        { date: '2026-08-01', exec_count: 40, align_fail_count: 1, meas_fail_count: 0 },
        { date: '2026-08-02', exec_count: 0, align_fail_count: 0, meas_fail_count: 0 }
      ]
    }
  ],
  recipes: [
    {
      class_name: 'QC',
      recipe_name: 'FAST_001',
      full_name: 'QC/FAST_001',
      total_exec_count: 300,
      total_align_fail_count: 3,
      total_meas_fail_count: 9,
      cells: [
        { eqp_id: 'TP-1203', exec_count: 200, align_fail_count: 2, meas_fail_count: 6 },
        { eqp_id: 'TP-1204', exec_count: 100, align_fail_count: 1, meas_fail_count: 3 }
      ]
    },
    {
      class_name: 'ADI',
      recipe_name: 'SLOW_002',
      full_name: 'ADI/SLOW_002',
      total_exec_count: 40,
      total_align_fail_count: 10,
      total_meas_fail_count: 1,
      cells: [
        { eqp_id: 'TP-1203', exec_count: 40, align_fail_count: 10, meas_fail_count: 1 },
        { eqp_id: 'TP-1204', exec_count: 0, align_fail_count: 0, meas_fail_count: 0 }
      ]
    }
  ],
  ...over
})

test('fail 장비 시트에 지수·구간·신호 열이 없다', () => {
  const [sheet] = buildFailEquipmentWorkbook({
    equipments: [failEquipment('TP-1203')],
    compare: null,
    section: 'align'
  })

  assert.deepEqual(sheet!.rows[0], [
    'eqp_id', 'fab', 'model', 'exec_count',
    'align_fail_count', 'align_fail_rate_pct', 'recipe_count'
  ])
  assert.deepEqual(sheet!.rows[1], ['TP-1203', 'M14', 'TP-5000', 430, 12, 2.79, 12])
})

test('section 이 meas 면 align 숫자가 파일에 나오지 않는다', () => {
  const [sheet] = buildFailEquipmentWorkbook({
    equipments: [failEquipment('TP-1203')],
    compare: null,
    section: 'meas'
  })

  assert.deepEqual(sheet!.rows[0], [
    'eqp_id', 'fab', 'model', 'exec_count',
    'meas_fail_count', 'meas_fail_rate_pct', 'recipe_count'
  ])
  assert.deepEqual(sheet!.rows[1], ['TP-1203', 'M14', 'TP-5000', 430, 4, 0.93, 12])
})

test('fail 레시피 시트는 활성 축 내림차순이고 미실행 비율은 빈 칸이다', () => {
  const sheets = buildFailEquipmentWorkbook({
    equipments: [failEquipment('TP-1203'), failEquipment('TP-1204')],
    compare: failCompare(),
    section: 'align'
  })
  const sheet = sheets.find(s => s.name === '레시피')!

  assert.deepEqual(sheet.rows[0], [
    'full_name', 'total_exec_count', 'total_align_fail_count',
    'TP-1203_exec_count', 'TP-1203_align_fail_count', 'TP-1203_align_fail_rate_pct',
    'TP-1204_exec_count', 'TP-1204_align_fail_count', 'TP-1204_align_fail_rate_pct'
  ])
  // align 은 ADI/SLOW_002(10건) > QC/FAST_001(3건) 이라 응답 순서와 반대입니다.
  assert.deepEqual(sheet.rows[1], ['ADI/SLOW_002', 40, 10, 40, 10, 25, 0, 0, ''])
  assert.deepEqual(sheet.rows[2], ['QC/FAST_001', 300, 3, 200, 2, 1, 100, 1, 1])
})

test('fail 레시피 정렬은 section 을 따른다', () => {
  const sheets = buildFailEquipmentWorkbook({
    equipments: [failEquipment('TP-1203')],
    compare: failCompare(),
    section: 'meas'
  })
  const sheet = sheets.find(s => s.name === '레시피')!

  // meas 는 QC/FAST_001(9건) > ADI/SLOW_002(1건).
  assert.equal(sheet.rows[1]![0], 'QC/FAST_001')
  assert.equal(sheet.rows[2]![0], 'ADI/SLOW_002')
})

test('fail 일별추이 시트는 활성 축만 낸다', () => {
  const sheets = buildFailEquipmentWorkbook({
    equipments: [failEquipment('TP-1203'), failEquipment('TP-1204')],
    compare: failCompare(),
    section: 'align'
  })
  const sheet = sheets.find(s => s.name === '일별추이')!

  assert.deepEqual(sheet.rows[0], [
    'date',
    'TP-1203_exec_count', 'TP-1203_align_fail_count',
    'TP-1204_exec_count', 'TP-1204_align_fail_count'
  ])
  assert.deepEqual(sheet.rows[1], ['2026-08-01', 100, 3, 40, 1])
  assert.deepEqual(sheet.rows[2], ['2026-08-02', 330, 9, 0, 0])
})

test('장비를 고르지 않으면 fail 도 장비 시트 하나뿐이다', () => {
  const sheets = buildFailEquipmentWorkbook({
    equipments: [failEquipment('TP-1203')],
    compare: null,
    section: 'align'
  })

  assert.deepEqual(sheets.map(s => s.name), ['장비'])
})
```

- [ ] **Step 2: 실패를 확인한다**

Run: `cd front-dev-home && npx node --test "app/utils/equipmentExport.test.ts"`
Expected: FAIL — `buildFailEquipmentWorkbook is not a function` (02의 테스트
5건은 계속 통과합니다).

- [ ] **Step 3: 빌더를 구현한다**

`front-dev-home/app/utils/equipmentExport.ts`의 import 블록에 추가:

```ts
import type {
  FailIssueEquipmentRow,
  FailIssueEquipmentCompareResponse
} from '~/composables/useFailIssueApi'
```

파일 끝에 이어 붙입니다:

```ts
export type FailSection = 'align' | 'meas'

/** 0..1 비율을 소수 둘째 자리 퍼센트 **숫자**로. 문자열로 내면 스프레드시트가
 *  다시 숫자로 바꿔야 합니다. */
const asPercent = (rate: number) => Number((rate * 100).toFixed(2))

export interface FailEquipmentWorkbookInput {
  /** 플릿 표에 실제로 보이는 행(검색·정렬 적용 후). */
  equipments: FailIssueEquipmentRow[]
  /** 장비를 고르지 않았으면 null. */
  compare: FailIssueEquipmentCompareResponse | null
  /** 보고 있는 축. 응답은 둘 다 담고 있지만 파일에는 이쪽만 나갑니다. */
  section: FailSection
}

export function buildFailEquipmentWorkbook(
  input: FailEquipmentWorkbookInput
): WorkbookSheet[] {
  const isAlign = input.section === 'align'
  const axis = isAlign ? 'align' : 'meas'

  const sheets: WorkbookSheet[] = [{
    name: '장비',
    rows: [
      [
        'eqp_id', 'fab', 'model', 'exec_count',
        `${axis}_fail_count`, `${axis}_fail_rate_pct`, 'recipe_count'
      ],
      ...input.equipments.map(row => [
        row.eqp_id,
        row.fab_name,
        row.eqp_model_cd,
        row.exec_count,
        isAlign ? row.align_fail_count : row.meas_fail_count,
        asPercent(isAlign ? row.align_fail_rate : row.meas_fail_rate),
        row.recipe_count
      ])
    ]
  }]

  const compare = input.compare
  if (!compare) return sheets

  const eqpIds = compare.eqp_ids

  // 화면이 활성 축으로 다시 정렬하므로 파일도 같은 순서여야 합니다. 백엔드
  // 순서는 두 축의 합이라 어느 탭에서도 그대로는 맞지 않습니다.
  const recipes = [...compare.recipes].sort((a, b) =>
    (isAlign ? b.total_align_fail_count : b.total_meas_fail_count)
    - (isAlign ? a.total_align_fail_count : a.total_meas_fail_count))

  sheets.push({
    name: '레시피',
    rows: [
      [
        'full_name', 'total_exec_count', `total_${axis}_fail_count`,
        ...eqpIds.flatMap(id => [
          `${id}_exec_count`, `${id}_${axis}_fail_count`, `${id}_${axis}_fail_rate_pct`
        ])
      ],
      ...recipes.map(recipe => [
        recipe.full_name,
        recipe.total_exec_count,
        isAlign ? recipe.total_align_fail_count : recipe.total_meas_fail_count,
        ...eqpIds.flatMap((_, index) => {
          const cell = recipe.cells[index]
          if (!cell || cell.exec_count === 0) return [0, 0, BLANK]
          const fails = isAlign ? cell.align_fail_count : cell.meas_fail_count
          return [cell.exec_count, fails, asPercent(fails / cell.exec_count)]
        })
      ])
    ]
  })

  const dates = compare.trends[0]?.points.map(point => point.date) ?? []

  sheets.push({
    name: '일별추이',
    rows: [
      [
        'date',
        ...eqpIds.flatMap(id => [`${id}_exec_count`, `${id}_${axis}_fail_count`])
      ],
      ...dates.map((date, dayIndex) => [
        date,
        ...eqpIds.flatMap((id) => {
          const point = compare.trends
            .find(series => series.eqp_id === id)?.points[dayIndex]
          if (!point) return [0, 0]
          return [
            point.exec_count,
            isAlign ? point.align_fail_count : point.meas_fail_count
          ]
        })
      ])
    ]
  })

  return sheets
}
```

- [ ] **Step 4: 테스트 통과를 확인한다**

Run: `cd front-dev-home && npx node --test "app/utils/equipmentExport.test.ts"`
Expected: PASS 11건 (02의 5건 + 이번 6건).

- [ ] **Step 5: 타입체크·린트**

Run:

```bash
cd front-dev-home
npm run typecheck
npm run lint
```

- [ ] **Step 6: 커밋**

```bash
git add front-dev-home/app/utils/equipmentExport.ts \
        front-dev-home/app/utils/equipmentExport.test.ts
git commit -m "feat(front): Fail 장비별 워크북 빌더를 추가한다

TAT 빌더와 같은 세 시트 규격을 align/meas 축에 맞춰 냅니다. 보고 있는
축만 파일에 나가고, 레시피 행은 화면과 같이 활성 축 내림차순으로
정렬합니다 — 백엔드 순서는 두 축의 합이라 어느 탭에서도 그대로는
맞지 않습니다.

미실행 칸의 비율은 0 이 아니라 빈 칸입니다. 0 은 '돌았는데 한 번도
실패하지 않았다'로 읽힙니다."
```
