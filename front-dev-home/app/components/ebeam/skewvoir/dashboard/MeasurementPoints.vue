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
      <UTooltip text="클립보드 복사">
        <UButton
          color="neutral"
          variant="ghost"
          size="xs"
          icon="i-lucide-clipboard"
          aria-label="표를 클립보드에 복사"
          :disabled="!rows.length"
          @click="copyPoints"
        />
      </UTooltip>
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
      ref="scrollEl"
      tabindex="0"
      role="grid"
      class="min-h-0 flex-1 overflow-auto outline-none focus-visible:ring-1 focus-visible:ring-(--sk-brand)/40"
      @keydown="onKeydown"
    >
      <table class="w-full border-collapse text-xs">
        <thead class="sticky top-0 z-10 bg-(--sk-surface)">
          <tr class="border-b border-(--sk-border) font-mono text-[11px] text-(--sk-ink-muted)">
            <template
              v-for="col in columns"
              :key="col.key"
            >
              <th
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
                v-if="col.key === 'mp'"
                scope="col"
                class="px-1.5 py-1.5 text-center font-semibold"
              >
                <UCheckbox
                  size="xs"
                  aria-label="보이는 측정점 전체 선택"
                  :model-value="headerCheck === 'all'"
                  :indeterminate="headerCheck === 'some'"
                  @update:model-value="toggleAllVisible"
                />
              </th>
            </template>
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
            :data-row-key="p.key"
            :aria-selected="p.seq === analysis.focusedSequence.value"
            class="cursor-pointer border-b border-(--sk-border-soft) transition-colors duration-200 last:border-0"
            :class="[
              p.kind === 'failed' ? 'text-(--sk-ink-muted)' : 'text-(--sk-ink)',
              p.seq === analysis.focusedSequence.value ? 'bg-(--sk-brand)/15' : 'hover:bg-(--sk-chip-bg)'
            ]"
            @click="onRowClick(p)"
          >
            <td
              v-if="multiParam"
              class="max-w-32 truncate px-1.5 py-1.5 font-mono"
              :class="p.param === analysis.activeParam.value ? 'text-(--sk-brand)' : ''"
            >
              {{ p.param }}
            </td>
            <td class="px-1.5 py-1.5 text-right font-mono tabular-nums">
              {{ p.mp >= 0 ? p.mp : '—' }}
            </td>
            <td
              class="px-1.5 py-1.5 text-center"
              @click.stop
            >
              <UCheckbox
                size="xs"
                :aria-label="`측정점 ${p.seq} 선택`"
                :model-value="selectedSet.has(p.seq)"
                @update:model-value="analysis.toggleSelectedSequence(p.seq)"
              />
            </td>
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
import { nextCursorIndex, type CursorKey } from '~/utils/tableCursor'
import { headerState, pickExportRows } from '~/utils/mpSelection'

const props = defineProps<{ analysis: SkewvoirAnalysis }>()

const filter = ref<'전체' | '이상·실패'>('전체')

// Multi-selection: one table over every selected parameter, so they can be
// read together. The PARAM column only appears once ≥2 params are selected.
const selectedParams = computed(() => props.analysis.selectedParams.value)
const multiParam = computed(() => selectedParams.value.length > 1)

type SortKey = 'param' | 'mp' | 'seq' | 'x' | 'y' | 'cd' | 'radius'
const columns = computed<{ key: SortKey, label: string, align: 'left' | 'right' }[]>(() => [
  ...(multiParam.value ? [{ key: 'param' as const, label: 'PARAM', align: 'left' as const }] : []),
  { key: 'mp', label: 'MP', align: 'right' },
  { key: 'seq', label: 'SEQ', align: 'left' },
  { key: 'x', label: 'X', align: 'right' },
  { key: 'y', label: 'Y', align: 'right' },
  { key: 'cd', label: 'DATA', align: 'right' },
  { key: 'radius', label: 'R (mm)', align: 'right' }
])
// mp_number is the primary sort key (row order convention), sequence the
// tie-break — matches the parameter chips/summary ordering.
const sortKey = ref<SortKey>('mp')
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

// Severity per (parameter, sequence), from the single overview source — so a
// row's badge here agrees with the wafer ◎ rings and each parameter chip's dot.
// One map per selected parameter, since the overview evaluates per parameter.
const flagByParamSeq = computed(() => {
  const byParam = new Map<string, Map<number, SiteKind>>()
  for (const param of selectedParams.value) {
    const m = new Map<number, SiteKind>()
    for (const r of props.analysis.overviewFor(param).tableRows) m.set(r.sequence, r.kind)
    byParam.set(param, m)
  }
  return byParam
})

interface Point {
  key: string
  param: string
  mp: number
  seq: number
  x: number | null
  y: number | null
  cd: number | null
  radius: number
  kind: SiteKind | 'normal'
}

// EVERY point for every SELECTED parameter — measured AND failed (cd_value:
// null) — so 전체 genuinely means all sites, including the 이상·실패 ones.
const allPoints = computed<Point[]>(() => {
  const chosen = new Set(selectedParams.value)
  return props.analysis.siteRows.value
    .filter(r => chosen.has(r.parameter))
    .map((r, i) => {
      const xy = parseChipXY(r.chip_number)
      return {
        key: `${r.msr}-${r.parameter}-${r.sequence}-${i}`,
        param: r.parameter,
        mp: r.mp_number,
        seq: r.sequence,
        x: xy ? xy[0] : null,
        y: xy ? xy[1] : null,
        cd: r.cd_value,
        radius: siteRadiusMm(r.stage_coordinate, props.analysis.waferGeo.value) ?? 0,
        kind: (flagByParamSeq.value.get(r.parameter)?.get(r.sequence) ?? 'normal') as SiteKind | 'normal'
      }
    })
})

// Compare on one key with `dir` applied to real values only, so nulls (and the
// negative-mp no-measurement sentinel, which is not a real MP) stay last in
// both directions. Ties fall through mp → seq — always ascending, matching the
// parameter-info reading order.
const compareOn = (a: Point, b: Point, key: SortKey, dir: number): number => {
  if (key === 'param') return a.param.localeCompare(b.param) * dir
  const av = key === 'mp' && a.mp < 0 ? null : a[key]
  const bv = key === 'mp' && b.mp < 0 ? null : b[key]
  if (av == null && bv == null) return 0
  if (av == null) return 1 // nulls last regardless of direction
  if (bv == null) return -1
  return (av - bv) * dir
}

const rows = computed(() => {
  const base = filter.value === '전체'
    ? allPoints.value
    : allPoints.value.filter(p => p.kind !== 'normal')
  const dir = sortDir.value === 'asc' ? 1 : -1
  const key = sortKey.value
  return [...base].sort((a, b) =>
    compareOn(a, b, key, dir) || compareOn(a, b, 'mp', 1) || compareOn(a, b, 'seq', 1)
  )
})

// Keyboard cursor: identify the focused row by its stable `key` so sort/filter
// changes don't desync it. Current index is re-derived from the visible rows.
const scrollEl = ref<HTMLElement | null>(null)
const cursorKey = ref<string | null>(null)

const cursorIndex = computed(() => {
  if (cursorKey.value) {
    const i = rows.value.findIndex(r => r.key === cursorKey.value)
    if (i >= 0) return i
  }
  // Fall back to the first row matching the shared focused sequence.
  const fseq = props.analysis.focusedSequence.value
  return fseq == null ? -1 : rows.value.findIndex(r => r.seq === fseq)
})

const focusRowAt = (index: number) => {
  const row = rows.value[index]
  if (!row) return
  cursorKey.value = row.key
  props.analysis.setFocusedSequence(row.seq)
  nextTick(() => {
    scrollEl.value
      ?.querySelector(`[data-row-key="${CSS.escape(row.key)}"]`)
      ?.scrollIntoView({ block: 'nearest' })
  })
}

const onRowClick = (p: Point) => {
  cursorKey.value = p.key
  props.analysis.setFocusedSequence(p.seq)
  scrollEl.value?.focus()
}

// Selection: derived off the visible rows so the header checkbox and export
// scoping always agree with what's currently on screen.
const selectedSet = computed(() => new Set(props.analysis.selectedSequences.value))
const visibleSeqs = computed(() => rows.value.map(r => r.seq))
const headerCheck = computed(() => headerState(visibleSeqs.value, selectedSet.value))

const toggleAllVisible = () => {
  if (headerCheck.value === 'all') {
    // Clear only the visible rows from the selection (keep off-screen picks).
    const visible = new Set(visibleSeqs.value)
    props.analysis.setSelectedSequences(
      props.analysis.selectedSequences.value.filter(s => !visible.has(s)))
  } else {
    // Add every visible seq (union with any off-screen picks).
    const union = new Set(props.analysis.selectedSequences.value)
    for (const s of visibleSeqs.value) union.add(s)
    props.analysis.setSelectedSequences([...union])
  }
}

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === ' ') {
    e.preventDefault()
    const row = rows.value[cursorIndex.value]
    if (row) props.analysis.toggleSelectedSequence(row.seq)
    return
  }
  const nav = ['ArrowDown', 'ArrowUp', 'Home', 'End']
  if (!nav.includes(e.key)) return
  e.preventDefault()
  const next = nextCursorIndex(e.key as CursorKey, cursorIndex.value, rows.value.length)
  if (next != null) focusRowAt(next)
}

const toast = useToast()

// Build the current (filtered + sorted) rows as headers + a value matrix,
// shared by CSV download and clipboard copy.
const pointsTable = () => ({
  headers: ['PARAM', 'MP', 'SEQ', 'X', 'Y', 'DATA', 'RADIUS_mm', 'STATUS'],
  rows: pickExportRows(rows.value, selectedSet.value).map(p => [
    p.param,
    p.mp,
    p.seq,
    p.x ?? '',
    p.y ?? '',
    p.cd ?? '',
    p.radius.toFixed(2),
    badgeLabel(p.kind)
  ])
})

const exportFileName = () => {
  const paramPart = multiParam.value ? `${selectedParams.value.length}params` : props.analysis.activeParam.value
  return `${props.analysis.focusFile.value?.msr ?? 'msr'}_${paramPart}_points.csv`
}

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
const meta = computed(() => {
  const paramNote = multiParam.value ? `${selectedParams.value.length} params · ` : ''
  const selNote = selectedSet.value.size ? ` · ${selectedSet.value.size} 선택` : ''
  return (filter.value === '전체'
    ? `${paramNote}${allPoints.value.length} sites · ${flaggedCount.value} 이상·실패`
    : `${paramNote}${flaggedCount.value} 이상·실패`) + selNote
})

const emptyLabel = computed(() => {
  if (filter.value === '이상·실패') {
    return props.analysis.activeOverview.value.status === 'evaluated'
      ? '이상·실패 사이트가 없습니다.'
      : '측정 site 부족 — 이상 평가 불가'
  }
  return `${selectedParams.value.join(', ') || props.analysis.activeParam.value} 측정점이 없습니다.`
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
