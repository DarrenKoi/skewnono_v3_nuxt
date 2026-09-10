<script setup lang="ts">
// One-line "meta bar" header for the 장비 상태 page (design option E).
// Collapses title + 장비 리스트/스토리지 toggle + summary stats + data freshness
// onto a single bar; the subtitle sits inline in the bar's dead space between the
// toggle and the stats (hidden on narrow viewports), no longer a line beneath.
// The title is intentionally stable ("장비 상태") so it no longer renames itself
// per sub-tab or duplicates the toggle label — the toggle owns that distinction.

export type MetaBarStatTone = 'ok' | 'bad' | 'warn' | 'accent' | 'neutral'

export type MetaBarStat = {
  key: string
  value: string | number
  label: string
  tone?: MetaBarStatTone
  // When interactive, reflects whether this stat's filter is currently engaged.
  active?: boolean
}

withDefaults(defineProps<{
  eyebrow?: string
  title: string
  subtitle?: string
  cadence?: string
  asOf?: string
  stats?: MetaBarStat[]
  // List view turns stats into a click-to-filter radiogroup; storage keeps them read-only.
  interactiveStats?: boolean
  statsLabel?: string
}>(), {
  eyebrow: '',
  subtitle: '',
  cadence: '',
  asOf: '',
  stats: () => [],
  interactiveStats: false,
  statsLabel: '요약 통계'
})

const emit = defineEmits<{ (e: 'select-stat', key: string): void }>()

const toneTextClass = (tone: MetaBarStatTone = 'neutral') => ({
  ok: 'text-(--sk-ok)',
  bad: 'text-(--sk-bad)',
  warn: 'text-(--sk-warn)',
  accent: 'text-(--sk-accent)',
  neutral: 'text-(--sk-ink)'
}[tone])

// Soft background tint for the engaged filter segment (interactive stats only).
const toneActiveBg = (tone: MetaBarStatTone = 'neutral') => ({
  ok: 'var(--sk-ok-soft)',
  bad: 'var(--sk-bad-soft)',
  warn: 'var(--sk-warn-soft)',
  accent: 'var(--sk-accent-tint)',
  neutral: 'var(--sk-muted-surface)'
}[tone])
</script>

<template>
  <div class="dashboard-surface flex flex-wrap items-stretch gap-y-1.5 rounded-[var(--sk-r-card)] p-1.5">
    <!-- LEFT cluster — leading action + title pod + toggle, locked together -->
    <div class="flex shrink-0 items-stretch">
      <!-- Leading is opt-in: sub-pages entered from a parent page put their
           돌아가기 button here, so back navigation reads left-to-right ahead of the
           title (the same shape as /tool-roster and Recipe 상세 nav) instead of
           sitting in the far-right #actions cluster. -->
      <template v-if="$slots.leading">
        <div class="flex items-center pl-1.5">
          <slot name="leading" />
        </div>

        <div class="my-2 mx-1.5 w-px bg-(--sk-border-soft)" />
      </template>

      <div
        class="flex flex-col justify-center py-1.5 pr-4"
        :class="{ 'pl-3': !$slots.leading }"
      >
        <p
          v-if="eyebrow"
          class="sk-eyebrow"
        >
          {{ eyebrow }}
        </p>
        <h1 class="text-lg font-extrabold leading-tight tracking-tight text-(--sk-ink)">
          {{ title }}
        </h1>
      </div>

      <!-- Toggle is opt-in: pages without a page-level toggle (Recipe 검색, H/W
           관리) omit the slot and the divider collapses with it. 장비 상태 pages
           pass EbeamEquipmentStatusSubTabs explicitly. -->
      <template v-if="$slots.toggle">
        <div class="my-2 mx-1 w-px bg-(--sk-border-soft)" />

        <div class="flex items-center px-1">
          <slot name="toggle" />
        </div>
      </template>
    </div>

    <!-- MIDDLE — subtitle fills the dead space between the toggle and the stats.
         As the flex-1 element it also pushes the right cluster to the edge; on
         narrow viewports it hides and the right cluster's ml-auto keeps stats right. -->
    <p
      v-if="subtitle"
      :title="subtitle"
      class="hidden min-w-0 flex-1 items-center truncate px-4 sk-meta md:flex"
    >
      {{ subtitle }}
    </p>

    <!-- RIGHT cluster — stats + freshness, hugs the right edge -->
    <div class="ml-auto flex min-w-0 flex-wrap items-center justify-end gap-2 pr-1">
      <div
        v-if="stats.length"
        class="inline-flex items-stretch"
        :role="interactiveStats ? 'radiogroup' : undefined"
        :aria-label="interactiveStats ? statsLabel : undefined"
      >
        <component
          :is="interactiveStats ? 'button' : 'div'"
          v-for="(stat, index) in stats"
          :key="stat.key"
          :type="interactiveStats ? 'button' : undefined"
          :role="interactiveStats ? 'radio' : undefined"
          :aria-checked="interactiveStats ? stat.active : undefined"
          class="flex flex-col justify-center border-r border-(--sk-border-soft) px-4 py-0.5 text-left transition-colors duration-200"
          :class="[
            index === 0 ? 'border-l' : '',
            interactiveStats ? 'cursor-pointer hover:bg-(--sk-accent-soft)' : ''
          ]"
          :style="interactiveStats && stat.active ? { background: toneActiveBg(stat.tone) } : undefined"
          @click="interactiveStats ? emit('select-stat', stat.key) : undefined"
        >
          <span
            class="text-2xl font-bold leading-[1.05] tracking-[-0.02em] tabular-nums"
            :class="toneTextClass(stat.tone)"
          >{{ stat.value }}</span>
          <!-- 11px micro-label: a caption naming the number, never a value. -->
          <span class="mt-0.5 sk-meta font-semibold">
            {{ stat.label }}
          </span>
        </component>
      </div>

      <EbeamDataFreshness
        v-if="cadence || asOf"
        :as-of="asOf"
        :cadence="cadence"
      />

      <slot name="actions" />
    </div>
  </div>
</template>
