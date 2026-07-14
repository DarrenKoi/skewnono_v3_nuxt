<template>
  <div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-(--sk-border-soft) pt-2.5">
    <div class="flex shrink-0 items-center gap-1.5">
      <span class="font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">SCOPE</span>
      <UPopover :content="{ align: 'start' }">
        <UButton
          color="neutral"
          variant="ghost"
          size="xs"
          icon="i-lucide-circle-help"
          aria-label="검색 문법 보기"
          class="h-5 px-1 text-(--sk-ink-subtle)"
        />

        <template #content>
          <div class="w-72 p-3 text-[11.5px] text-(--sk-ink-muted)">
            <p class="font-semibold text-(--sk-ink)">
              검색 문법
            </p>
            <p class="mt-1 leading-5">
              일반 키워드는 장비, Recipe, Lot, MSR 전체에서 찾습니다. 정확한 범위를 지정하려면 아래 접두어를 사용하세요.
            </p>
            <div class="mt-2 grid grid-cols-[62px_1fr] gap-x-2 gap-y-1 font-mono text-[10.5px]">
              <span class="text-(--sk-brand)">eq:</span><span>장비 ID</span>
              <span class="text-(--sk-brand)">recipe:</span><span>Recipe 이름</span>
              <span class="text-(--sk-brand)">lot:</span><span>Lot ID</span>
              <span class="text-(--sk-brand)">msr:</span><span>측정 ID</span>
              <span class="text-(--sk-brand)">date:</span><span>YYYY-MM-DD</span>
            </div>
          </div>
        </template>
      </UPopover>
    </div>

    <div class="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
      <span
        v-for="item in items"
        :key="`${item.label}:${item.value}`"
        class="inline-flex min-w-0 items-baseline gap-1 font-mono text-[10.5px]"
      >
        <span class="text-(--sk-ink-subtle)">{{ item.label }}</span>
        <span
          class="max-w-72 truncate font-semibold text-(--sk-ink)"
          :title="item.value"
        >{{ item.value }}</span>
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ParsedQuery } from '~/utils/measHistQuery'
import { buildSearchScopeSummary } from '~/utils/skewvoirSearchUi'

const props = defineProps<{
  parsed: ParsedQuery
  range: { start: string, end: string }
  retentionDays: number
  searched: boolean
  total: number
  capped: boolean
}>()

const items = computed(() => buildSearchScopeSummary({
  parsed: props.parsed,
  range: props.range,
  retentionDays: props.retentionDays,
  searched: props.searched,
  total: props.total,
  capped: props.capped
}))
</script>
