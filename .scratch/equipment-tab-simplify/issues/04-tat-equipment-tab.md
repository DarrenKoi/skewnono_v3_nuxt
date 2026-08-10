# 04 — TAT 장비별 탭

Status: open
Plan: [`../plan.md`](../plan.md)
Blocked by: 02

TAT 탭의 장비별 화면에서 판정 레이어를 걷어내고, 요약 칩을 정리하고, CSV
버튼 두 개를 통합 Excel 버튼 하나로 바꿉니다. 세 변경이 한 티켓인 이유는
같은 파일들을 함께 건드리기 때문입니다 — 열을 지우면 그 열을 내보내던 CSV
빌더가 함께 죽고, Excel 빌더가 그 자리를 대신합니다.

**Files:**

- Modify: `front-dev-home/app/components/ebeam/RecipeTatFleetTable.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeTatEquipmentView.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeTatEquipmentCompare.vue`

**Interfaces:**

- Consumes: `buildTatEquipmentWorkbook`, `TatEquipmentWorkbookInput` (티켓 02),
  `downloadWorkbook` (티켓 01)
- Produces: `RecipeTatEquipmentCompare`가 `loaded` 이벤트를 냅니다 —
  `defineEmits<{ loaded: [RecipeTatEquipmentCompareResponse | null] }>()`

---

## 4-1. 플릿 표 단순화

- [ ] **Step 1: `RecipeTatFleetTable.vue`에서 판정 열을 지운다**

`columns` 배열에서 세 줄을 삭제합니다:

```ts
  { accessorKey: 'occupancy', header: '점유율', size: 88 },
  { accessorKey: 'tat_index', header: 'TAT index', size: 100 },
  { id: 'signals', header: '신호', size: 140 }
```

`avg_meastime`은 `recipe_count` 앞에 그대로 둡니다. 최종 열 순서는
`pick, eqp_id, fab, model, 실행수, 총 TAT, 평균, 레시피수` 입니다.

- [ ] **Step 2: 템플릿에서 죽은 셀 슬롯과 배너를 지운다**

`<template #occupancy-cell>`, `<template #tat_index-cell>`,
`<template #signals-cell>` 세 블록을 통째로 삭제합니다.

`v-if="!peerGroupComparable"`인 `<p>` 배너(58-72줄)도 삭제합니다 — 문구가
"신호 배지"와 "TAT index 열"을 설명하는데 둘 다 사라져 문장 자체가
거짓이 됩니다.

- [ ] **Step 3: 헤더 툴팁을 정리한다**

`OCCUPANCY_HEADER_TOOLTIP`, `TAT_INDEX_HEADER_TOOLTIP`,
`TAT_INDEX_MIXED_FAB_TOOLTIP`, `headerTooltip` 을 모두 삭제합니다. 남는 열에는
설명이 필요한 것이 없습니다.

템플릿의 정렬 헤더에서 `<UTooltip>` 래퍼를 벗기고 `<UButton>`만 남깁니다:

```vue
      <template
        v-for="id in sortableColumnIds"
        :key="id"
        #[`${id}-header`]="{ column }"
      >
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
          :trailing-icon="getSortIcon(column.getIsSorted())"
          @click="column.toggleSorting(column.getIsSorted() === 'asc')"
        >
          {{ column.columnDef.header }}
        </UButton>
      </template>
```

- [ ] **Step 4: 정렬을 단순화한다**

`sortableColumnIds`를 줄입니다:

```ts
const sortableColumnIds = [
  'exec_count', 'total_meastime', 'avg_meastime', 'recipe_count'
] as const
```

`sortedRows`의 null 처리를 걷어냅니다. nullable 열은 `tat_index` 하나뿐이었고
이제 없습니다:

```ts
const sortedRows = computed(() => {
  const current = sorting.value[0]
  if (!current) return filteredRows.value
  const id = current.id as SortableColumnId
  const dir = current.desc ? -1 : 1
  return [...filteredRows.value].sort((a, b) => (a[id] - b[id]) * dir)
})
```

`sorting`의 기본값(`total_meastime` 내림차순)과 `sortingOptions`
(`MANUAL_SORTING_OPTIONS`)은 **그대로 둡니다.** 이 표가 자기 행을 스스로
정렬한다는 사실은 지수와 무관합니다. 다만 `sortingOptions` 위 주석의
마지막 문장이 TAT index를 예로 들고 있으므로 다음으로 갈아끼웁니다:

```ts
// 이 표는 자기 행을 스스로 정렬합니다(`filteredRows` 를 검색으로 줄인 뒤
// `sortedRows` 에서 정렬). `manualSorting` 이 왜 지워지면 안 되는지는
// utils/tableSorting.ts 에 한 번만 적혀 있습니다 — 지우면 UTable 이
// 정렬된 배열을 한 번 더 정렬해 검색 결과와 순서가 어긋납니다.
```

- [ ] **Step 5: props와 import를 줄인다**

`defineProps`에서 `percentiles`와 `peerGroupComparable` 두 줄(그리고 그 위
주석 블록)을 삭제하고, `signalsFor` 함수와 아래 import를 삭제합니다:

```ts
import {
  equipmentSignals,
  SIGNAL_META,
  type FleetPercentiles
} from '~/utils/equipmentSignals'
```

- [ ] **Step 6: CSV 버튼을 Excel 버튼으로 바꾼다**

템플릿의 CSV 버튼을 교체합니다:

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

emit 이름(`download`)과 페이로드(화면에 보이는 행)는 그대로입니다 — 바뀐 것은
부모가 그 행으로 무엇을 만드느냐뿐입니다. 그 위 주석도 "내보내기는 화면에
보이는 것을 그대로 냅니다"라는 계약을 여전히 설명하므로 유지합니다.

## 4-2. 비교 패널

- [ ] **Step 7: `RecipeTatEquipmentCompare.vue`가 payload를 위로 올린다**

`props` 선언 바로 아래에 emit을 추가합니다:

```ts
// 통합 워크북은 플릿 행(부모가 가짐)과 이 응답을 한 파일에 담아야 합니다.
// 부모가 캐시 키를 다시 조립해 훔쳐보는 대신 올려보냅니다 — 키 문자열이 두
// 곳에 살면 한쪽이 바뀔 때 조용히 빈 시트가 나옵니다.
const emit = defineEmits<{
  loaded: [RecipeTatEquipmentCompareResponse | null]
}>()
```

`~/composables/useRecipeTatApi` import 목록에
`type RecipeTatEquipmentCompareResponse`를 추가합니다.

`useAsyncData` 호출 바로 아래에 watch를 답니다:

```ts
watch(data, value => emit('loaded', value ?? null), { immediate: true })
```

- [ ] **Step 8: 요약 칩 문법을 통일한다**

칩의 `<span class="text-(--sk-ink-muted)">` 내용을 바꿉니다:

```vue
        <span class="text-(--sk-ink-muted)">
          측정 {{ row.exec_count.toLocaleString() }} ·
          레시피 {{ row.recipe_count }} ·
          총 {{ formatSecondsCompact(row.total_meastime) }}
        </span>
```

- [ ] **Step 9: 매트릭스 CSV 버튼을 지운다**

템플릿에서 `label="CSV"` 버튼을 삭제합니다. **클립보드 복사 버튼(`UTooltip` +
`i-lucide-clipboard`)은 남깁니다** — 표 하나를 빨리 붙여넣는 용도라 통합
파일과 성격이 다릅니다.

스크립트에서 `exportFileName`과 `downloadMatrixCsv`를 삭제합니다.
`matrixTable`과 `copyMatrix`는 복사 버튼이 계속 쓰므로 남깁니다.

import 두 줄을 정리합니다 — `downloadCsv`와 `todayStamp`가 미사용이 됩니다:

```ts
import { copyTableToClipboard } from '~/utils/csvDownload'
```

(`import { todayStamp } from '~/utils/dateTime'` 줄은 삭제)

`matrixTable`의 주석에서 "CSV는"을 "복사는"으로 고칩니다 — 이제 이 함수의
유일한 소비자는 클립보드입니다.

## 4-3. 뷰 배선

- [ ] **Step 10: `RecipeTatEquipmentView.vue`를 다시 배선한다**

import 블록을 교체합니다. 삭제:

```ts
import {
  equipmentSignals,
  isPeerGroupComparable,
  SIGNAL_META
} from '~/utils/equipmentSignals'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'
```

추가:

```ts
import { copyTableToClipboard } from '~/utils/csvDownload'
import { buildTatEquipmentWorkbook } from '~/utils/equipmentExport'
import { downloadWorkbook } from '~/utils/xlsx'
```

`useRecipeTatApi` import 목록에 `type RecipeTatEquipmentCompareResponse`를
추가합니다.

`percentiles`와 `peerGroupComparable` computed(그리고 그 위 주석 블록)를
삭제합니다.

`selected` 선언 아래에 compare payload 보관소를 둡니다:

```ts
// 비교 패널이 올려보내는 응답. 장비 선택이 비면 패널이 언마운트되므로
// 여기서 직접 비웁니다 — 그러지 않으면 이전 선택의 시트가 파일에 남습니다.
const comparePayload = ref<RecipeTatEquipmentCompareResponse | null>(null)
watch(selected, (value) => {
  if (value.length === 0) comparePayload.value = null
})
```

`cacheKey` watch(선택 초기화)는 그대로 둡니다.

- [ ] **Step 11: 내보내기 블록을 갈아끼운다**

`fleetTable`, `downloadFleetCsv` 그리고 `exportFileName`을 다음으로 교체합니다
(`copyFleetTable`은 헤더/행 출처만 바뀝니다):

```ts
// 내보내기 -------------------------------------------------------------------

// 화면·클립보드·파일이 같은 열을 쓰도록 `장비` 시트 하나에서 다 끌어옵니다.
// 열 목록을 두 벌 두면 한쪽만 고쳐지고, 그 어긋남은 파일을 열기 전까지
// 보이지 않습니다.
const equipmentSheet = (rows: RecipeTatEquipmentRow[]) =>
  buildTatEquipmentWorkbook({ equipments: rows, compare: null })[0]!

const exportFileName = computed(() => {
  const fab = (props.fabs.join('+') || 'all').toLowerCase()
  return `${props.toolType}-${fab}-recipe-tat-equipments-${todayStamp()}.xlsx`
})

const toast = useToast()

const downloadFleetExcel = async (rows: RecipeTatEquipmentRow[]) => {
  await downloadWorkbook(
    exportFileName.value,
    buildTatEquipmentWorkbook({ equipments: rows, compare: comparePayload.value })
  )
}

const copyFleetTable = async (rows: RecipeTatEquipmentRow[]) => {
  const sheet = equipmentSheet(rows)
  const ok = await copyTableToClipboard(sheet.rows[0] as string[], sheet.rows.slice(1))
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}
```

`import { todayStamp } from '~/utils/dateTime'`는 파일명이 계속 쓰므로
**남깁니다**.

- [ ] **Step 12: 템플릿의 props와 핸들러를 맞춘다**

```vue
      <EbeamRecipeTatFleetTable
        :rows="equipmentRows"
        :selected="selected"
        :max-selected="MAX_COMPARE_EQPS"
        @update:selected="selected = $event"
        @download="downloadFleetExcel"
        @copy="copyFleetTable"
      />

      <EbeamRecipeTatEquipmentCompare
        v-if="selected.length"
        :tool-type="toolType"
        :fabs="fabs"
        :date-range="dateRange"
        :eqp-ids="selected"
        :rows="selectedRows"
        @loaded="comparePayload = $event"
      />
```

- [ ] **Step 13: 정적 게이트**

Run:

```bash
cd front-dev-home
npm test 2>&1 | tail -5
npm run typecheck
npm run lint
```

Expected: 전부 통과. 특히 `equipmentSignals.test.ts`가 계속 통과해야 합니다 —
파일을 남기기로 했으므로 그래야 정상이고, 깨진다면 이 티켓이 의도보다 멀리
간 것입니다.

- [ ] **Step 14: 미사용 auto-import 확인**

Run:

```bash
cd front-dev-home/app
grep -rn "equipmentSignals\|SIGNAL_META\|isPeerGroupComparable" \
  components/ebeam/RecipeTat*.vue
```

Expected: 히트 0건.

- [ ] **Step 15: 커밋**

```bash
git add front-dev-home/app/components/ebeam/RecipeTatFleetTable.vue \
        front-dev-home/app/components/ebeam/RecipeTatEquipmentView.vue \
        front-dev-home/app/components/ebeam/RecipeTatEquipmentCompare.vue
git commit -m "feat(recipe-tat): 장비별 탭을 관측만 남기고 Excel 내보내기로 바꾼다

플릿 표에서 점유율·TAT index·신호 열과 다중 fab 경고 배너를 뺐습니다.
장비별 탭에서 필요한 질문은 '어떤 장비가 어떤 레시피를 얼마나 돌고
얼마나 걸리는가'이고, 판정 레이어는 그 질문에 답하지 않으면서 화면
복잡도의 대부분을 차지했습니다. 계산은 백엔드와 utils 에 그대로 있어
고도화 때 배선만 다시 꽂으면 됩니다.

요약 칩은 '측정 N · 레시피 M · 총 시간'으로 통일했고, CSV 버튼 2개는
시트 3개(장비/레시피/일별추이)짜리 xlsx 버튼 하나로 합쳤습니다.
일별추이는 지금까지 차트로만 존재해 내보낼 수 없던 데이터입니다."
```
