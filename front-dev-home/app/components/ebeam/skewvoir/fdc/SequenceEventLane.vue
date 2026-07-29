<template>
  <div class="space-y-1.5">
    <div class="flex items-center gap-3 text-[11px] text-(--sk-ink-muted)">
      <span class="sk-eyebrow">이벤트 레인</span>
      <span class="flex items-center gap-1">
        <span class="inline-block h-2 w-2 rounded-full bg-(--sk-bad)" /> 측정 실패
      </span>
      <span class="flex items-center gap-1">
        <span class="inline-block h-2 w-2 rounded-full bg-sky-600 dark:bg-sky-400" /> 이미지
      </span>
      <span class="flex items-center gap-1">
        <span class="inline-block h-2 w-2 rounded-full bg-(--sk-ok)" /> 정렬
      </span>
    </div>

    <!-- One column per sequence, aligned left→right with the pane axes. -->
    <div class="flex items-stretch gap-px overflow-x-auto pb-1">
      <button
        v-for="cell in cells"
        :key="cell.sequence"
        type="button"
        class="group flex min-w-[18px] flex-1 flex-col items-center gap-0.5 rounded-[4px] px-0.5 py-1 transition-colors duration-150"
        :class="cell.sequence === focused
          ? 'bg-(--sk-brand)/15 ring-1 ring-(--sk-brand)'
          : 'hover:bg-(--sk-chip-bg)'"
        :title="cell.title"
        @click="emit('select', cell.sequence)"
      >
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="cell.failure ? 'bg-(--sk-bad)' : 'bg-transparent'"
        />
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="cell.image ? 'bg-sky-600 dark:bg-sky-400' : 'bg-transparent'"
        />
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="cell.alignment ? 'bg-(--sk-ok)' : 'bg-transparent'"
        />
        <span class="mt-0.5 font-mono text-[9px] text-(--sk-ink-subtle) tabular-nums">
          {{ cell.sequence }}
        </span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SeqEvent } from '~/utils/skewvoirAnalysis/sequence'

const props = defineProps<{
  // The shared sequence axis (same order as the panes).
  sequences: number[]
  events: SeqEvent[]
  focused?: number | null
}>()

const emit = defineEmits<{ select: [sequence: number] }>()

const cells = computed(() => {
  const bySeq = new Map(props.events.map(e => [e.sequence, e]))
  return props.sequences.map((sequence) => {
    const e = bySeq.get(sequence)
    const failure = e?.failure ?? false
    const image = e?.image ?? false
    const alignment = e?.alignment ?? false
    const tags: string[] = []
    if (failure) tags.push('측정 실패')
    if (image) tags.push('이미지')
    if (alignment) tags.push('정렬')
    const chip = e?.chip ? ` · ${e.chip}` : ''
    return {
      sequence,
      failure,
      image,
      alignment,
      title: `측정 순서 ${sequence}${chip}${tags.length ? ` · ${tags.join(', ')}` : ' · 이벤트 없음'}`
    }
  })
})
</script>
