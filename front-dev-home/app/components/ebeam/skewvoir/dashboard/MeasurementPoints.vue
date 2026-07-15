<template>
  <EbeamSkewvoirPanelFrame
    v-model="filter"
    title="Measurement Points"
    :meta="meta"
    :toggles="['전체', '이상·실패']"
    icon="i-lucide-list-ordered"
    body-class="flex flex-col"
  >
    <template #actions>
      <UButton
        color="neutral"
        variant="ghost"
        size="xs"
        icon="i-lucide-clipboard"
        aria-label="표를 클립보드에 복사"
        title="표를 클립보드에 복사 (엑셀에 붙여넣기)"
        :disabled="!rows.length"
        @click="copyPoints"
      />
      <UButton
        color="neutral"
        variant="ghost"
        size="xs"
        icon="i-lucide-download"
        label="Excel"
        :disabled="!rows.length"
        @click="exportCsv"
      />
    </template>

    <div
      v-if="analysis.focusPending.value"
      class="flex flex-1 items-center justify-center gap-2 sk-body"
    >
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 animate-spin"
      />
      불러오는 중…
    </div>

    <div
      v-else-if="rows.length"
      class="min-h-0 flex-1 overflow-auto"
    >
      <table class="w-full border-collapse text-xs">
        <thead class="sticky top-0 z-10 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border) font-mono text-[11px] text-(--sk-ink-muted)">
            <th
              v-for="col in columns"
              :key="col.key"
              scope="col"
              :aria-sort="ariaSort(col.key)"
              class="cursor-pointer select-none px-1.5 py-1.5 font-semibold whitespace-nowrap hover:text-(--sk-ink)"
              :class="col.align === 'right' ? 'text-right' : 'text-left'"
              @click="sortBy(col.key)"
            >
              <span
                class="inline-flex items-center gap-0.5"
                :class="col.align === 'right' ? 'flex-row-reverse' : ''"
              >
                {{ col.label }}
                <UIcon
                  :name="sortIcon(col.key)"
                  class="h-3 w-3"
                  :class="sortKey === col.key ? 'text-(--sk-brand)' : 'text-(--sk-ink-subtle)'"
                />
              </span>
            </th>
            <th
              scope="col"
              class="px-1.5 py-1.5 text-right font-semibold"
            >
              상태
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in rows"
            :key="p.key"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors duration-200 last:border-0"
            :class="[
              p.kind === 'failed' ? 'text-(--sk-ink-muted)' : 'text-(--sk-ink)',
              p.seq === analysis.focusedSequence.value ? 'bg-(--sk-brand)/15' : 'hover:bg-(--sk-chip-bg)'
            ]"
            @click="analysis.setFocusedSequence(p.seq)"
          >
            <td class="px-1.5 py-1.5 font-mono">
              {{ p.seq }}
            </td>
            <td class="px-1.5 py-1.5 text-right font-mono tabular-nums">
              {{ p.x ?? '—' }}
            </td>
            <td class="px-1.5 py-1.5 text-right font-mono tabular-nums">
              {{ p.y ?? '—' }}
            </td>
            <td class="px-1.5 py-1.5 text-right font-mono font-medium tabular-nums">
              {{ p.cd != null ? p.cd.toFixed(2) : '—' }}
            </td>
            <td class="px-1.5 py-1.5 text-right font-mono tabular-nums">
              {{ p.radius.toFixed(1) }}
            </td>
            <td class="px-1.5 py-1.5 text-right">
              <span
                v-if="p.kind !== 'normal'"
                class="rounded-(--sk-r-chip) px-1.5 py-0.5 font-mono text-[11px] font-semibold"
                :class="badgeClass(p.kind)"
              >{{ badgeLabel(p.kind) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div
      v-else
      class="flex flex-1 items-center justify-center px-3 text-center sk-body"
    >
      {{ emptyLabel }}
    </div>
  </EbeamSkewvoirPanelFrame>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { SiteKind } from '~/utils/overview'
import { siteRadiusMm } from '~/utils/waferGeometry'
import { copyTableToClipboard, downloadCsv } from '~/utils/csvDownload'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const filter = ref<'전체' | '이상·실패'>('전체')

type SortKey = 'seq' | 'x' | 'y' | 'cd' | 'radius'
const columns: { key: SortKey, label: string, align: 'left' | 'right' }[] = [
  { key: 'seq', label: 'SEQ', align: 'left' },
  { key: 'x', label: 'X', align: 'right' },
  { key: 'y', label: 'Y', align: 'right' },
  { key: 'cd', label: 'DATA', align: 'right' },
  { key: 'radius', label: 'R (mm)', align: 'right' }
]
const sortKey = ref<SortKey>('seq')
const sortDir = ref<'asc' | 'desc'>('asc')
const sortBy = (key: SortKey) => {
  if (sortKey.value === key) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else {
    sortKey.value = key
    sortDir.value = 'asc'
  }
}
const sortIcon = (key: SortKey) =>
  sortKey.value !== key
    ? 'i-lucide-arrow-up-down'
    : sortDir.value === 'asc' ? 'i-lucide-arrow-up-narrow-wide' : 'i-lucide-arrow-down-wide-narrow'
const ariaSort = (key: SortKey): 'none' | 'ascending' | 'descending' =>
  sortKey.value !== key ? 'none' : sortDir.value === 'asc' ? 'ascending' : 'descending'

// Severity per sequence, from the single overview source — so a row's badge here
// agrees with the wafer ◎ rings and the parameter chip's dot.
const flagBySeq = computed(() => {
  const m = new Map<number, SiteKind>()
  for (const r of props.analysis.activeOverview.value.tableRows) m.set(r.sequence, r.kind)
  return m
})

// EVERY point for the active parameter — measured AND failed (cd_value: null) —
// so 전체 genuinely means all sites, including the 이상·실패 ones.
const allPoints = computed(() =>
  props.analysis.siteRows.value
    .filter(r => r.parameter === props.analysis.activeParam.value)
    .map((r, i) => {
      const xy = parseChipXY(r.chip_number)
      return {
        key: `${r.msr}-${r.sequence}-${i}`,
        seq: r.sequence,
        x: xy ? xy[0] : null,
        y: xy ? xy[1] : null,
        cd: r.cd_value,
        radius: siteRadiusMm(r.stage_coordinate, props.analysis.waferGeo.value) ?? 0,
        kind: (flagBySeq.value.get(r.sequence) ?? 'normal') as SiteKind | 'normal'
      }
    })
)

const rows = computed(() => {
  const base = filter.value === '전체'
    ? allPoints.value
    : allPoints.value.filter(p => p.kind !== 'normal')
  const dir = sortDir.value === 'asc' ? 1 : -1
  const key = sortKey.value
  return [...base].sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    if (av == null && bv == null) return 0
    if (av == null) return 1 // nulls last regardless of direction
    if (bv == null) return -1
    return (av - bv) * dir
  })
})

const toast = useToast()

// Build the current (filtered + sorted) rows as headers + a value matrix,
// shared by CSV download and clipboard copy.
const pointsTable = () => ({
  headers: ['SEQ', 'X', 'Y', 'DATA', 'RADIUS_mm', 'STATUS'],
  rows: rows.value.map(p => [
    p.seq,
    p.x ?? '',
    p.y ?? '',
    p.cd ?? '',
    p.radius.toFixed(2),
    badgeLabel(p.kind)
  ])
})

const exportFileName = () =>
  `${props.analysis.focusFile.value?.msr ?? 'msr'}_${props.analysis.activeParam.value}_points.csv`

const exportCsv = () => {
  const { headers, rows: data } = pointsTable()
  downloadCsv(exportFileName(), headers, data)
}

const copyPoints = async () => {
  const { headers, rows: data } = pointsTable()
  const ok = await copyTableToClipboard(headers, data)
  toast.add(
    ok
      ? { title: '클립보드에 복사됨', icon: 'i-lucide-check', color: 'success' }
      : { title: '복사에 실패했습니다', icon: 'i-lucide-x', color: 'error' }
  )
}

const flaggedCount = computed(() => allPoints.value.filter(p => p.kind !== 'normal').length)
const meta = computed(() =>
  filter.value === '전체'
    ? `${allPoints.value.length} sites · ${flaggedCount.value} 이상·실패`
    : `${flaggedCount.value} 이상·실패`
)

const emptyLabel = computed(() => {
  if (filter.value === '이상·실패') {
    return props.analysis.activeOverview.value.status === 'evaluated'
      ? '이상·실패 사이트가 없습니다.'
      : '측정 site 부족 — 이상 평가 불가'
  }
  return `${props.analysis.activeParam.value} 측정점이 없습니다.`
})

const badgeLabel = (kind: SiteKind | 'normal') =>
  kind === 'abnormal' ? '이상' : kind === 'watch' ? '주의' : kind === 'failed' ? '실패' : ''

const badgeClass = (kind: SiteKind | 'normal') =>
  kind === 'abnormal'
    ? 'bg-(--sk-bad-soft) text-(--sk-bad)'
    : kind === 'watch'
      ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400'
      : 'bg-(--sk-chip-bg) text-(--sk-ink-subtle)'
</script>
