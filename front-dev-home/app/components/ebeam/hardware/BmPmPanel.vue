<template>
  <div class="mt-2 overflow-hidden rounded-xl bg-(--sk-surface) ring-1 ring-(--sk-border-soft)">
    <div class="flex items-center justify-between border-b border-(--sk-border-soft) px-3 py-1.5">
      <span class="sk-title">BM/PM 작업</span>
      <span class="font-mono text-xs text-(--sk-ink-muted)">
        이력 {{ pastItems.length }} · 예정 {{ planItems.length }}
      </span>
    </div>

    <p
      v-if="!selected"
      class="px-3 py-6 text-center sk-body"
    >
      표시할 작업이 없습니다.
    </p>

    <div
      v-else
      class="flex items-stretch"
    >
      <!-- Master: 예정 above 이력, each row one job in a single scannable line. -->
      <div class="max-h-[540px] w-[350px] shrink-0 overflow-y-auto border-r border-(--sk-border-soft)">
        <template
          v-for="group in groups"
          :key="group.key"
        >
          <div class="border-b border-(--sk-border-soft) bg-(--sk-muted-surface) px-3 py-1.5 sk-label">
            {{ group.label }} {{ group.items.length }}건
          </div>
          <button
            v-for="item in group.items"
            :key="item.key"
            type="button"
            class="w-full border-b border-(--sk-border-soft) px-3 py-2.5 text-left transition-colors"
            :class="item.key === selected.key
              ? 'bg-(--sk-accent-tint) shadow-[inset_2px_0_0_0_var(--sk-accent)]'
              : 'hover:bg-(--sk-muted-surface)'"
            :aria-current="item.key === selected.key"
            @click="selectedKey = item.key"
          >
            <span class="flex items-center gap-2">
              <span
                class="inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[11px] font-bold"
                :class="item.badge.class"
              >{{ item.badge.label }}</span>
              <span class="font-mono text-xs font-semibold tabular-nums text-(--sk-ink)">{{ item.start }}</span>
              <span class="ml-auto font-mono text-[11px] text-(--sk-ink-subtle)">{{ item.duration }}</span>
            </span>
            <span
              v-if="item.line"
              class="mt-1 block truncate text-xs text-(--sk-ink-muted)"
            >{{ item.line }}</span>
          </button>
        </template>
      </div>

      <!-- Detail: the selected job in full — no truncation, no click-to-expand. -->
      <div class="min-w-0 flex-1 px-5 py-4">
        <div class="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <span
            class="inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[11px] font-bold"
            :class="selected.badge.class"
          >{{ selected.badge.detailLabel }}</span>
          <span class="font-mono text-sm font-semibold tabular-nums text-(--sk-ink)">
            {{ selected.start }} → {{ selected.endLabel || 'Up 기록 없음' }}
          </span>
          <span class="font-mono text-xs text-(--sk-ink-subtle)">{{ selected.duration }}</span>
          <span class="ml-auto font-mono text-[11px] text-(--sk-ink-subtle)">{{ selected.eqpId }}</span>
        </div>

        <dl
          v-if="selected.meta.length"
          class="mt-3.5 flex flex-wrap gap-x-7 gap-y-2.5"
        >
          <div
            v-for="fieldItem in selected.meta"
            :key="fieldItem.key"
          >
            <dt class="sk-label">
              {{ fieldItem.label }}
            </dt>
            <dd class="mt-0.5 sk-value-num">
              {{ fieldItem.value }}
            </dd>
          </div>
        </dl>

        <div
          v-if="selected.notes.length"
          class="mt-4 flex flex-col gap-3.5 border-t border-(--sk-border-soft) pt-3.5"
        >
          <div
            v-for="note in selected.notes"
            :key="note.key"
          >
            <div
              class="sk-eyebrow"
              :class="noteTone(note.key)"
            >
              {{ note.label }}
            </div>
            <p class="mt-1.5 whitespace-pre-line text-sm leading-relaxed text-pretty text-(--sk-ink)">
              {{ note.value }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { HardwareMetricValue, HardwareTableColumn, HardwareTableSection } from '~/composables/useHardwareApi'
import { workDuration, workEndLabel } from '~/utils/bmPmWork'

const props = defineProps<{
  tables: HardwareTableSection[]
}>()

// The four keys the detail header already renders; every other column in the
// contract falls through to the meta grid (plain columns) or the notes stack
// (expandable ones), so a column added backend-side shows up without an edit.
const HEADER_KEYS = new Set(['eqp_id', 'job_starts', 'job_end', 'category'])

// Free-text notes carry their own severity: a problem is not a comment.
const NOTE_TONES: Record<string, string> = {
  zzproblem: 'text-(--sk-bad)',
  hltext: 'text-amber-700 dark:text-amber-300'
}
const noteTone = (key: string) => NOTE_TONES[key] ?? ''

interface WorkField {
  key: string
  label: string
  value: string
}

interface WorkItem {
  key: string
  category: string
  eqpId: string
  start: string
  endLabel: string
  duration: string
  line: string
  badge: { label: string, detailLabel: string, class: string }
  meta: WorkField[]
  notes: WorkField[]
}

const text = (value: HardwareMetricValue | undefined) =>
  value === undefined || value === null ? '' : String(value)

const field = (column: HardwareTableColumn, row: Record<string, HardwareMetricValue>): WorkField => ({
  key: column.key,
  label: column.label,
  value: text(row[column.key])
})

// Planned work is the same category in an outline chip — a scheduled BM is a
// BM, so the badge follows `category` rather than assuming every plan is a PM.
const badgeFor = (category: string, plan: boolean): WorkItem['badge'] => {
  const label = category || (plan ? '예정' : '미분류')
  const detailLabel = plan ? `${category} 예정`.trim() : label
  if (plan) {
    return {
      label,
      detailLabel,
      class: category === 'BM'
        ? 'border border-dashed border-(--sk-bad) text-(--sk-bad)'
        : category === 'PM'
          ? 'border border-dashed border-(--sk-ok) text-(--sk-ok)'
          : 'border border-dashed border-(--sk-border-soft) text-(--sk-ink-muted)'
    }
  }
  return {
    label,
    detailLabel,
    class: category === 'PM'
      ? 'bg-(--sk-ok-soft) text-(--sk-ok)'
      : category === 'BM'
        ? 'bg-(--sk-bad-soft) text-(--sk-bad)'
        : 'bg-(--sk-muted-surface) text-(--sk-ink-muted)'
  }
}

const buildItems = (section: HardwareTableSection | undefined, plan: boolean): WorkItem[] => {
  if (!section) return []
  const metaColumns = section.columns.filter(c => !HEADER_KEYS.has(c.key) && !c.expandable)
  const noteColumns = section.columns.filter(c => c.expandable)

  return section.rows.map((row, index): WorkItem => {
    const start = text(row.job_starts)
    const end = text(row.job_end)
    const duration = workDuration(start, end)
    const notes = noteColumns.map(c => field(c, row)).filter(f => f.value !== '')
    const category = text(row.category)

    return {
      key: `${plan ? 'f' : 'p'}${index}`,
      category,
      eqpId: text(row.eqp_id),
      start,
      endLabel: workEndLabel(start, end),
      // A past job with no Up stamp is still down, not instantaneous.
      duration: duration || (plan ? '' : '진행 중'),
      line: notes[0]?.value ?? '',
      badge: badgeFor(category, plan),
      meta: metaColumns.map(c => ({ ...field(c, row), value: text(row[c.key]) || '—' })),
      notes
    }
  })
}

const planItems = computed(() => buildItems(props.tables.find(t => t.key === 'future_work'), true))
const pastItems = computed(() => buildItems(props.tables.find(t => t.key === 'past_work'), false))

const groups = computed(() =>
  [
    { key: 'future_work', label: '예정', items: planItems.value },
    { key: 'past_work', label: '이력', items: pastItems.value }
  ].filter(g => g.items.length)
)

const selectedKey = ref('')
const selected = computed(() =>
  [...planItems.value, ...pastItems.value].find(i => i.key === selectedKey.value)
  ?? pastItems.value[0]
  ?? planItems.value[0]
)

// Row keys are positional, so a different tool's rows would silently inherit
// the current selection's slot. Clearing on payload swap lands every tool on
// its own newest history entry instead.
watch(() => props.tables, () => {
  selectedKey.value = ''
})
</script>
