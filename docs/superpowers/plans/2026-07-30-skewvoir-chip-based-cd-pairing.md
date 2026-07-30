# Skewvoir Chip-Based CD Pairing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skewvoir `상관 / 분포`에서 sequence가 다른 두 CD parameter를 `chip_number` 기준으로 연결하고, 같은 chip의 복수 관측치는 가능한 경우 `chip_coordinate`로 세분화하되 불완전하면 chip 평균으로 비교합니다.

**Architecture:** `buildCdCdRelationship`이 CD↔CD 매칭의 유일한 소유자가 됩니다. 이 순수 함수는 chip을 기본 grain으로 사용하고 복수 관측치에만 coordinate 세분화 또는 평균 fallback을 적용하며, 단일 MSR과 SET scope는 모두 함수가 반환한 `PairedPoint[]`를 차트에 전달합니다.

**Tech Stack:** Vue 3, Nuxt 4, TypeScript, Node 내장 test runner, ECharts

## Global Constraints

- CD↔CD 매칭 키에 `sequence`를 사용하지 않습니다.
- `chip_coordinate`는 같은 chip에 복수 관측치가 있을 때만 보조 키로 사용합니다.
- 복수 관측치의 coordinate가 비었거나 양쪽 집합이 다르면 parameter별 chip 평균으로 pair 하나를 만듭니다.
- CD↔FDC의 per-sequence 매칭은 변경하지 않습니다.
- backend API, response shape, URL query, parameter 선택 UI 및 차트 배치를 변경하지 않습니다.
- 측정 실패 row는 기존 `isMeasuredRow` 계약으로 제외합니다.
- frontend 코드는 2-space indentation, no trailing commas 및 `1tbs` 규칙을 지킵니다.

---

## 파일 구조

- `front-dev-home/app/utils/skewvoirAnalysis/relationships.ts`: CD↔CD 및 CD↔FDC 관계 계산의 단일 소유자입니다.
- `front-dev-home/app/utils/skewvoirAnalysis/relationships.test.ts`: chip/coordinate/평균 fallback/missing 계약을 순수 테스트로 고정합니다.
- `front-dev-home/app/components/ebeam/skewvoir/views/Correlation.vue`: 단일 MSR과 SET scope 모두 중앙 관계 함수의 point를 차트에 전달합니다.
- `front-dev-home/app/components/ebeam/skewvoir/CorrelationScatter.vue`: 이미 계산된 `PairedPoint[]`만 렌더링하며 자체 조인을 하지 않습니다.

---

### Task 1: CD↔CD 관계를 chip 기준 적응형 매칭으로 변경

**Files:**

- Modify: `front-dev-home/app/utils/skewvoirAnalysis/relationships.ts:1-163`
- Modify: `front-dev-home/app/utils/skewvoirAnalysis/relationships.test.ts:1-126`

**Interfaces:**

- Consumes: `isMeasuredRow(row): row is MeasuredMsrRow`
- Produces: `buildCdCdRelationship(rows: MsrFileRow[], paramX: string, paramY: string): RelationshipResult`
- Preserves: `buildCdFdcRelationship(rows, cdParam, fdcParam, dynamicFdc): RelationshipResult`
- Preserves: `PairedPoint = { key, chip, sequence, x, y }`

- [ ] **Step 1: 실제 sequence 계약을 반영한 기본 실패 테스트를 작성합니다.**

`twoParamRows()`의 Y sequence를 X와 겹치지 않게 바꾸고 chip 기준 assertion을
사용합니다.

```ts
const twoParamRows = (): MsrFileRow[] => [
  row({ sequence: 1, chip_number: '0,0', parameter: 'CD_TOP', cd_value: 100 }),
  row({ sequence: 3, chip_number: '1,0', parameter: 'CD_TOP', cd_value: 110 }),
  row({ sequence: 5, chip_number: '2,0', parameter: 'CD_TOP', cd_value: 120 }),
  row({ sequence: 7, chip_number: '3,0', parameter: 'CD_TOP', cd_value: 130 }),
  row({ sequence: 2, chip_number: '0,0', parameter: 'CD_BOT', cd_value: 200 }),
  row({ sequence: 4, chip_number: '1,0', parameter: 'CD_BOT', cd_value: 205 }),
  row({ sequence: 6, chip_number: '2,0', parameter: 'CD_BOT', cd_value: 210 }),
  row({ sequence: 8, chip_number: '3,0', parameter: 'CD_BOT', cd_value: 215 })
]

test('CD↔CD pairs same-chip values even when every sequence differs', () => {
  const res = buildCdCdRelationship(twoParamRows(), 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 4)
  assert.equal(res.missingN, 0)
  assert.deepEqual(res.points.map(p => p.chip), ['0,0', '1,0', '2,0', '3,0'])
  assert.deepEqual(res.points[0], {
    key: '0,0',
    chip: '0,0',
    sequence: 1,
    x: 100,
    y: 200
  })
})

test('different chips produce zero pairs and an unavailable result', () => {
  const rows = [
    row({ sequence: 1, chip_number: '0,0', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 2, chip_number: '1,0', parameter: 'CD_BOT', cd_value: 200 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 0)
  assert.equal(res.missingN, 2)
  assert.equal(res.readiness, 'unavailable')
})
```

- [ ] **Step 2: 기본 테스트가 현재 구현에서 실패하는지 확인합니다.**

Run:

```bash
cd front-dev-home
node --test app/utils/skewvoirAnalysis/relationships.test.ts
```

Expected: FAIL — `pairN`이 `0`이며 같은 chip의 다른 sequence가 연결되지 않습니다.

- [ ] **Step 3: 복수 관측치의 coordinate 매칭과 평균 fallback 실패 테스트를 추가합니다.**

```ts
test('one row per axis pairs by chip and ignores coordinate differences', () => {
  const rows = [
    row({ sequence: 11, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 12, chip_number: '0,0', chip_coordinate: '20,20', parameter: 'CD_BOT', cd_value: 200 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 1)
  assert.equal(res.points[0]?.key, '0,0')
})

test('repeated rows with equal coordinate sets pair per coordinate and average repeats', () => {
  const rows = [
    row({ sequence: 11, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 12, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_TOP', cd_value: 104 }),
    row({ sequence: 13, chip_number: '0,0', chip_coordinate: '20,20', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 21, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_BOT', cd_value: 200 }),
    row({ sequence: 22, chip_number: '0,0', chip_coordinate: '20,20', parameter: 'CD_BOT', cd_value: 220 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.deepEqual(res.points.map(p => [p.key, p.x, p.y]), [
    ['0,0#10,10', 102, 200],
    ['0,0#20,20', 110, 220]
  ])
})

test('missing coordinates fall back to one per-parameter chip mean', () => {
  const rows = [
    row({ sequence: 11, chip_number: '0,0', chip_coordinate: '', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 12, chip_number: '0,0', chip_coordinate: '', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 21, chip_number: '0,0', chip_coordinate: '', parameter: 'CD_BOT', cd_value: 200 }),
    row({ sequence: 22, chip_number: '0,0', chip_coordinate: '', parameter: 'CD_BOT', cd_value: 220 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.deepEqual(res.points[0], {
    key: '0,0',
    chip: '0,0',
    sequence: 11,
    x: 105,
    y: 210
  })
})

test('different coordinate sets fall back to one per-parameter chip mean', () => {
  const rows = [
    row({ sequence: 11, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 12, chip_number: '0,0', chip_coordinate: '20,20', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 21, chip_number: '0,0', chip_coordinate: '10,10', parameter: 'CD_BOT', cd_value: 200 }),
    row({ sequence: 22, chip_number: '0,0', chip_coordinate: '30,30', parameter: 'CD_BOT', cd_value: 220 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 1)
  assert.deepEqual([res.points[0]?.x, res.points[0]?.y], [105, 210])
})
```

기존 missing 테스트는 sequence gap이 아니라 한쪽에만 존재하는 chip으로 바꿉니다.

```ts
test('a chip present on only one axis is dropped and counted once', () => {
  const rows = [
    row({ sequence: 1, chip_number: '0,0', parameter: 'CD_TOP', cd_value: 100 }),
    row({ sequence: 3, chip_number: '1,0', parameter: 'CD_TOP', cd_value: 110 }),
    row({ sequence: 2, chip_number: '0,0', parameter: 'CD_BOT', cd_value: 200 })
  ]
  const res = buildCdCdRelationship(rows, 'CD_TOP', 'CD_BOT')
  assert.equal(res.pairN, 1)
  assert.equal(res.missingN, 1)
  assert.equal(res.points[0]?.chip, '0,0')
})
```

- [ ] **Step 4: 새 복수 관측치 테스트가 모두 실패하는지 확인합니다.**

Run:

```bash
cd front-dev-home
node --test app/utils/skewvoirAnalysis/relationships.test.ts
```

Expected: FAIL — current `chip_number#sequence` 조인은 모든 새 fixture에서 pair를
만들지 못합니다.

- [ ] **Step 5: chip grouping과 적응형 coordinate 처리를 구현합니다.**

`relationships.ts`의 CD↔CD 부분에 다음 작은 helper를 둡니다.

```ts
const meanCd = (rows: MeasuredMsrRow[]): number =>
  rows.reduce((sum, row) => sum + row.cd_value, 0) / rows.length

const groupBy = (
  rows: MeasuredMsrRow[],
  keyOf: (row: MeasuredMsrRow) => string
): Map<string, MeasuredMsrRow[]> => {
  const groups = new Map<string, MeasuredMsrRow[]>()
  for (const row of rows) {
    const key = keyOf(row)
    const group = groups.get(key) ?? []
    group.push(row)
    groups.set(key, group)
  }
  return groups
}

const sameKeys = (
  left: Map<string, MeasuredMsrRow[]>,
  right: Map<string, MeasuredMsrRow[]>
): boolean =>
  left.size === right.size && [...left.keys()].every(key => right.has(key))
```

`buildCdCdRelationship`은 parameter별 measured row를 chip으로 모은 뒤 다음 규칙을
적용합니다.

```ts
const measured = rows.filter(isMeasuredRow)
const xByChip = groupBy(measured.filter(row => row.parameter === paramX), row => row.chip_number)
const yByChip = groupBy(measured.filter(row => row.parameter === paramY), row => row.chip_number)

for (const [chip, xRows] of xByChip) {
  const yRows = yByChip.get(chip)
  if (!yRows) {
    missingN++
    continue
  }

  if (xRows.length === 1 && yRows.length === 1) {
    points.push({
      key: chip,
      chip,
      sequence: xRows[0]!.sequence,
      x: xRows[0]!.cd_value,
      y: yRows[0]!.cd_value
    })
    continue
  }

  const coordinatesComplete = [...xRows, ...yRows]
    .every(row => row.chip_coordinate.trim().length > 0)
  const xByCoordinate = groupBy(xRows, row => row.chip_coordinate.trim())
  const yByCoordinate = groupBy(yRows, row => row.chip_coordinate.trim())

  if (coordinatesComplete && sameKeys(xByCoordinate, yByCoordinate)) {
    for (const [coordinate, coordinateXRows] of xByCoordinate) {
      const coordinateYRows = yByCoordinate.get(coordinate)!
      points.push({
        key: `${chip}#${coordinate}`,
        chip,
        sequence: Math.min(...coordinateXRows.map(row => row.sequence)),
        x: meanCd(coordinateXRows),
        y: meanCd(coordinateYRows)
      })
    }
    continue
  }

  points.push({
    key: chip,
    chip,
    sequence: Math.min(...xRows.map(row => row.sequence)),
    x: meanCd(xRows),
    y: meanCd(yRows)
  })
}

for (const chip of yByChip.keys()) {
  if (!xByChip.has(chip)) missingN++
}
```

마지막에 `points`를 `sequence`, 그다음 `key` 순으로 정렬하고 기존 `finalize`를
호출합니다. 파일 상단의 CD↔CD 주석도 chip 기반 규칙으로 고칩니다.

- [ ] **Step 6: 관계 테스트를 통과시킵니다.**

Run:

```bash
cd front-dev-home
node --test app/utils/skewvoirAnalysis/relationships.test.ts
```

Expected: PASS — CD↔CD 신규 테스트와 CD↔FDC 기존 테스트가 모두 통과합니다.

- [ ] **Step 7: Task 1 변경만 커밋합니다.**

```bash
git add front-dev-home/app/utils/skewvoirAnalysis/relationships.ts \
  front-dev-home/app/utils/skewvoirAnalysis/relationships.test.ts
git diff --cached --check
git commit -m "fix(skewvoir): pair CD values by chip location"
```

---

### Task 2: 단일 MSR과 SET scope가 같은 pair를 렌더링하도록 통합

**Files:**

- Modify: `front-dev-home/app/components/ebeam/skewvoir/views/Correlation.vue:100-187`
- Modify: `front-dev-home/app/components/ebeam/skewvoir/CorrelationScatter.vue:12-72`
- Test: `front-dev-home/app/utils/skewvoirAnalysis/relationships.test.ts`

**Interfaces:**

- Consumes: `buildCdCdRelationship(rows, paramX, paramY): RelationshipResult`
- Consumes: required `points: PairedPoint[]` prop
- Produces: single/SET scope 모두 중앙 관계 함수가 계산한 point를 사용하는 화면

- [ ] **Step 1: SET scope 관계 계산을 부모 view에 추가합니다.**

`Correlation.vue`의 SET state 아래에 다음 computed를 추가합니다.

```ts
const setRelationship = computed(() =>
  buildCdCdRelationship(
    props.analysis.siteRows.value,
    paramX.value,
    paramY.value
  )
)
```

SET scope 차트 호출은 raw rows 대신 point와 readiness를 전달합니다.

```vue
<EbeamSkewvoirCorrelationScatter
  :points="setRelationship.points"
  :param-x="paramX"
  :param-y="paramY"
  :unit-x="unitOf(paramX)"
  :unit-y="unitOf(paramY)"
  :readiness-reason="setRelationship.reason"
/>
```

- [ ] **Step 2: `CorrelationScatter.vue`의 legacy 조인을 제거합니다.**

`MsrFileRow`, `measuredRows`, `rows?` prop 및 `legacyPairs` computed를 삭제합니다.
`points`를 필수 prop으로 만들고 렌더 입력을 단일화합니다.

```ts
const props = defineProps<{
  points: PairedPoint[]
  paramX: string
  paramY: string
  unitX: string
  unitY: string
  readinessReason?: string | null
}>()

const pairs = computed<[number, number][]>(() =>
  props.points.map(point => [point.x, point.y])
)

const scatterData = computed(() =>
  props.points.map(point => ({
    value: [point.x, point.y] as [number, number],
    name: point.chip
  }))
)
```

주석은 차트가 이미 매칭된 point만 렌더링하고 조인 책임은
`relationships.ts`에 있음을 설명하도록 수정합니다.

- [ ] **Step 3: 관련 순수 테스트와 TypeScript 검사를 실행합니다.**

Run:

```bash
cd front-dev-home
node --test app/utils/skewvoirAnalysis/relationships.test.ts
npm run typecheck
```

Expected: PASS — 두 CorrelationScatter 호출 모두 required `points`를 제공하며
Vue/TypeScript 오류가 없습니다.

- [ ] **Step 4: frontend 전체 회귀 검사를 실행합니다.**

Run:

```bash
cd front-dev-home
npm test
npm run lint
```

Expected: `npm test` PASS. `npm run lint`에서 기존 untouched-file 오류가 있으면
별도로 기록하되, 다음 명령으로 변경 파일에 새 lint 오류가 없는지 확인합니다.

```bash
npx eslint \
  app/utils/skewvoirAnalysis/relationships.ts \
  app/utils/skewvoirAnalysis/relationships.test.ts \
  app/components/ebeam/skewvoir/views/Correlation.vue \
  app/components/ebeam/skewvoir/CorrelationScatter.vue
```

- [ ] **Step 5: 실행 화면에서 CD↔CD 결과를 확인합니다.**

Backend와 frontend가 실행 중인 상태에서 Skewvoir 분석의 `상관 / 분포`로 이동합니다.

1. Y 유형으로 `CD`를 선택합니다.
2. 서로 다른 X/Y parameter를 선택합니다.
3. Paired Scatter의 `n`이 0보다 큰지 확인합니다.
4. Marginal Distribution과 Paired Evidence가 같은 pair 수를 반영하는지 확인합니다.
5. SET scope에서도 산점도가 비어 있지 않은지 확인합니다.
6. Y 유형을 `FDC`로 바꿔 기존 sequence 기반 결과가 유지되는지 확인합니다.

- [ ] **Step 6: Task 2 변경만 커밋합니다.**

```bash
git add \
  front-dev-home/app/components/ebeam/skewvoir/views/Correlation.vue \
  front-dev-home/app/components/ebeam/skewvoir/CorrelationScatter.vue
git diff --cached --check
git commit -m "refactor(skewvoir): reuse CD pairing across scopes"
```

---

## 완료 조건

- 같은 chip의 X/Y CD는 서로 다른 sequence여도 pair가 됩니다.
- 복수 관측치는 완전한 coordinate 대응 시 좌표별로 비교됩니다.
- 불완전한 coordinate는 parameter별 chip 평균으로 안전하게 대체됩니다.
- 한쪽에만 존재하는 chip은 한 번만 missing으로 계산됩니다.
- 단일 MSR과 SET scope가 같은 중앙 매칭 함수를 사용합니다.
- CD↔FDC sequence 매칭과 UI/URL/backend 계약은 변경되지 않습니다.
- targeted relationship test, frontend 전체 test 및 typecheck가 통과합니다.
- 실행 화면에서 CD↔CD Paired Scatter와 분포가 실제 pair를 표시합니다.
