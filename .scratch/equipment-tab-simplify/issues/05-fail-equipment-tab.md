# 05 — Align/Meas 장비별 탭

Status: open
Plan: [`../plan.md`](../plan.md)
Blocked by: 03

04와 같은 변경을 fail-issue 쪽에 합니다. 파일이 다르고 축(align/meas)이
하나 더 있을 뿐 구조는 같습니다.

**Files:**

- Modify: `front-dev-home/app/components/ebeam/FailIssueFleetTable.vue`
- Modify: `front-dev-home/app/components/ebeam/FailIssueEquipmentView.vue`
- Modify: `front-dev-home/app/components/ebeam/FailIssueEquipmentCompare.vue`

**Interfaces:**

- Consumes: `buildFailEquipmentWorkbook` (티켓 03), `downloadWorkbook` (티켓 01)
- Produces: `FailIssueEquipmentCompare`가 `loaded` 이벤트를 냅니다 —
  `defineEmits<{ loaded: [FailIssueEquipmentCompareResponse | null] }>()`

---

## 5-1. 플릿 표 단순화

- [ ] **Step 1: 판정 열을 지운다**

`columns` computed에서 두 줄을 삭제합니다:

```ts
  { id: 'fail_index', header: 'fail index', size: 104 },
  { id: 'signals', header: '신호', size: 140 }
```

최종 열 순서는 `pick, eqp_id, fab, model, 실행수, <축> fail, fail율, 레시피수`
입니다.

- [ ] **Step 2: 템플릿에서 죽은 셀 슬롯과 배너를 지운다**

`<template #fail_index-cell>`과 `<template #signals-cell>` 블록을 통째로
삭제합니다. `#fail_count-cell`과 `#fail_rate-cell`은 남깁니다.

`v-if="!peerGroupComparable"`인 `<p>` 배너(58-72줄)도 삭제합니다.

- [ ] **Step 3: 판정 헬퍼와 툴팁을 지운다**

스크립트에서 다음을 모두 삭제합니다:

- `indexOf`, `indexLow`, `indexHigh`, `expectedOf`, `signalInput`,
  `signalsFor`, `conclusive`, `indexTooltip`
- `FAIL_INDEX_HEADER_TOOLTIP`, `FAIL_INDEX_MIXED_FAB_TOOLTIP`, `headerTooltip`
- import 블록 하나를 통째로:

```ts
import {
  FAIL_SIGNAL_META,
  failEquipmentSignals,
  isIndexConclusive,
  type FailPercentiles
} from '~/utils/failEquipmentSignals'
```

`formatRate`는 `#fail_rate-cell`이 계속 쓰므로 `~/composables/useFailIssueApi`
import는 그대로 둡니다.

`failCount`, `failRate`, `failLabel`은 남는 열이 쓰므로 **남깁니다.**

템플릿의 정렬 헤더에서 `<UTooltip>` 래퍼를 벗기고 `<UButton>`만 남깁니다
(04 Step 3과 같은 형태).

- [ ] **Step 4: 정렬을 단순화한다**

```ts
const sortableColumnIds = [
  'exec_count', 'fail_count', 'fail_rate', 'recipe_count'
] as const
```

`sortValue`에서 지수 분기를 없앱니다:

```ts
const sortValue = (row: FailIssueEquipmentRow, id: SortableColumnId): number => {
  if (id === 'exec_count') return row.exec_count
  if (id === 'recipe_count') return row.recipe_count
  if (id === 'fail_count') return failCount(row)
  return failRate(row)
}
```

`sortedRows`의 null 처리를 걷어냅니다:

```ts
const sortedRows = computed(() => {
  const current = sorting.value[0]
  if (!current) return filteredRows.value
  const id = current.id as SortableColumnId
  const dir = current.desc ? -1 : 1
  return [...filteredRows.value].sort((a, b) => (sortValue(a, id) - sortValue(b, id)) * dir)
})
```

기본 정렬(`fail_count` 내림차순)과 `MANUAL_SORTING_OPTIONS`는 그대로 둡니다.
`sortingOptions` 위 주석이 fail index를 예로 들고 있으면 04 Step 4와 같은
문장으로 갈아끼웁니다.

- [ ] **Step 5: props를 줄인다**

`defineProps`에서 `percentiles`와 `peerGroupComparable`(그리고 그 위 주석
블록)을 삭제합니다. `section`은 남깁니다.

- [ ] **Step 6: CSV 버튼을 Excel 버튼으로 바꾼다**

```vue
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-file-spreadsheet"
          label="Excel"
          :disabled="sortedRows.length === 0"
          @click="emit('download', sortedRows)"
        />
```

## 5-2. 비교 패널

- [ ] **Step 7: payload를 위로 올린다**

`props` 선언 아래에:

```ts
// 통합 워크북은 플릿 행(부모가 가짐)과 이 응답을 한 파일에 담아야 합니다.
// 부모가 캐시 키를 다시 조립해 훔쳐보는 대신 올려보냅니다 — 키 문자열이 두
// 곳에 살면 한쪽이 바뀔 때 조용히 빈 시트가 나옵니다.
const emit = defineEmits<{
  loaded: [FailIssueEquipmentCompareResponse | null]
}>()
```

`~/composables/useFailIssueApi` import 목록에
`type FailIssueEquipmentCompareResponse`를 추가하고, `useAsyncData` 아래에:

```ts
watch(data, value => emit('loaded', value ?? null), { immediate: true })
```

- [ ] **Step 8: 요약 칩 문법을 통일한다**

```vue
        <span class="text-(--sk-ink-muted)">
          측정 {{ row.exec_count.toLocaleString() }} ·
          레시피 {{ row.recipe_count }} ·
          실패 {{ chipFailCount(row).toLocaleString() }}
        </span>
```

실패율이 칩에서 빠집니다 — 플릿 표에 이미 열로 있습니다. 그러면
`chipFailRate`의 유일한 호출자가 사라지므로 함수도 삭제합니다.
`formatRate`는 매트릭스 셀(`(${formatRate(fails / cell.exec_count)})`)이 계속
쓰므로 import를 남깁니다.

- [ ] **Step 9: 매트릭스 CSV 버튼을 지운다**

템플릿에서 `label="CSV"` 버튼을 삭제합니다. 클립보드 복사 버튼은 남깁니다.

스크립트에서 `exportFileName`과 `downloadMatrixCsv`를 삭제하고, 미사용이 된
`downloadCsv`·`todayStamp` import를 정리합니다. `matrixTable`·`copyMatrix`는
남기고, `matrixTable` 위 주석의 "CSV는"을 "복사는"으로 고칩니다.

## 5-3. 뷰 배선

- [ ] **Step 10: `FailIssueEquipmentView.vue`를 다시 배선한다**

삭제할 import:

```ts
import { isPeerGroupComparable } from '~/utils/equipmentSignals'
import {
  FAIL_SIGNAL_META,
  failEquipmentSignals
} from '~/utils/failEquipmentSignals'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
```

추가할 import:

```ts
import { copyTableToClipboard } from '~/utils/csvDownload'
import { buildFailEquipmentWorkbook } from '~/utils/equipmentExport'
import { downloadWorkbook } from '~/utils/xlsx'
```

`useFailIssueApi` import 목록에 `type FailIssueEquipmentCompareResponse`를
추가합니다. `percentiles`·`peerGroupComparable` computed를 삭제합니다.

`selected` 아래에:

```ts
// 비교 패널이 올려보내는 응답. 장비 선택이 비면 패널이 언마운트되므로
// 여기서 직접 비웁니다 — 그러지 않으면 이전 선택의 시트가 파일에 남습니다.
const comparePayload = ref<FailIssueEquipmentCompareResponse | null>(null)
watch(selected, (value) => {
  if (value.length === 0) comparePayload.value = null
})
```

- [ ] **Step 11: 내보내기 블록을 갈아끼운다**

`fleetTable`과 `downloadFleetCsv`를 통째로 교체합니다:

```ts
// 내보내기 -------------------------------------------------------------------

// 표와 같은 축(align/meas)만 냅니다. 응답은 두 축을 다 담고 있지만, 보고 있는
// 탭과 다른 열이 섞여 나오면 파일만 보고는 어느 축인지 알 수 없습니다.
// 대신 파일명과 열 이름에 축을 박습니다.
//
// 화면·클립보드·파일이 같은 열을 쓰도록 `장비` 시트 하나에서 다 끌어옵니다.
const equipmentSheet = (rows: FailIssueEquipmentRow[]) =>
  buildFailEquipmentWorkbook({
    equipments: rows, compare: null, section: props.section
  })[0]!

const exportFileName = computed(() => {
  const fab = (props.fabs.join('+') || 'all').toLowerCase()
  return `${props.toolType}-${fab}-fail-issue-equipments`
    + `-${props.section}-${todayStamp()}.xlsx`
})

const toast = useToast()

const downloadFleetExcel = async (rows: FailIssueEquipmentRow[]) => {
  await downloadWorkbook(exportFileName.value, buildFailEquipmentWorkbook({
    equipments: rows,
    compare: comparePayload.value,
    section: props.section
  }))
}

const copyFleetTable = async (rows: FailIssueEquipmentRow[]) => {
  const sheet = equipmentSheet(rows)
  const ok = await copyTableToClipboard(sheet.rows[0] as string[], sheet.rows.slice(1))
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}
```

- [ ] **Step 12: 템플릿의 props와 핸들러를 맞춘다**

```vue
      <EbeamFailIssueFleetTable
        :rows="equipmentRows"
        :selected="selected"
        :max-selected="MAX_COMPARE_EQPS"
        :section="section"
        @update:selected="selected = $event"
        @download="downloadFleetExcel"
        @copy="copyFleetTable"
      />

      <EbeamFailIssueEquipmentCompare
        v-if="selected.length"
        :tool-type="toolType"
        :fabs="fabs"
        :date-range="dateRange"
        :eqp-ids="selected"
        :rows="selectedRows"
        :section="section"
        @loaded="comparePayload = $event"
      />
```

- [ ] **Step 13: 정적 게이트**

```bash
cd front-dev-home
npm test 2>&1 | tail -5
npm run typecheck
npm run lint
```

Expected: 전부 통과. `failEquipmentSignals.test.ts`도 계속 통과해야 합니다.

- [ ] **Step 14: 미사용 참조 확인**

```bash
cd front-dev-home/app
grep -rn "failEquipmentSignals\|FAIL_SIGNAL_META\|isIndexConclusive\|isPeerGroupComparable" \
  components/ebeam/FailIssue*.vue
```

Expected: 히트 0건.

- [ ] **Step 15: 커밋**

```bash
git add front-dev-home/app/components/ebeam/FailIssueFleetTable.vue \
        front-dev-home/app/components/ebeam/FailIssueEquipmentView.vue \
        front-dev-home/app/components/ebeam/FailIssueEquipmentCompare.vue
git commit -m "feat(fail-issue): 장비별 탭을 관측만 남기고 Excel 내보내기로 바꾼다

recipe-tat 쪽과 같은 변경입니다. 플릿 표에서 fail index·신호 열과 다중
fab 경고 배너를 뺐고, 실패수·실패율은 남겼습니다 — 간접표준화가 아니라
실패÷실행이라 열 이름 그대로 읽히고 '얼마나 fail 이 발생하는가'에 직접
답합니다.

요약 칩은 '측정 N · 레시피 M · 실패 K'로 통일했고(실패율은 표에 이미
열로 있습니다), CSV 버튼 2개는 활성 축만 담는 시트 3개짜리 xlsx 버튼
하나로 합쳤습니다."
```
