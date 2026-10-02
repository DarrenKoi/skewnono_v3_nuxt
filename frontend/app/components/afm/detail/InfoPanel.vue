<template>
  <AfmCard
    icon="i-lucide-info"
    title="측정 정보"
    :count="entries.length"
    flush
  >
    <p
      v-if="!entries.length"
      class="px-4 py-10 text-center sk-body"
    >
      측정 정보가 없습니다.
    </p>
    <dl
      v-else
      class="divide-y divide-(--sk-border-soft)"
    >
      <div
        v-for="[key, value] in entries"
        :key="key"
        class="flex items-baseline justify-between gap-4 px-4 py-2"
      >
        <dt class="shrink-0 text-[13px] text-(--sk-ink-muted)">
          {{ key }}
        </dt>
        <dd
          class="min-w-0 truncate text-right font-mono text-[13px] font-medium tabular-nums text-(--sk-ink)"
          :title="value"
        >
          {{ value }}
        </dd>
      </div>
    </dl>
  </AfmCard>
</template>

<script setup lang="ts">
// The file's information block, one key per row. Keys are whatever the tool
// wrote, so they are shown as given; the site summary that used to sit under
// them moved into 사이트별 요약, beside the chart it tabulates.
import type { AfmInformation } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  information: AfmInformation
}>()

const entries = computed(() =>
  Object.entries(props.information).map(([key, value]) =>
    [key, value === null || value === '' ? '–' : String(value)] as const
  )
)
</script>
