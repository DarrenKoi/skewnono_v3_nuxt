<template>
  <dl class="flex flex-wrap items-center gap-x-3 gap-y-1">
    <div
      v-for="item in items"
      :key="item.label"
      class="inline-flex items-baseline gap-1 whitespace-nowrap"
    >
      <dt class="sk-label">
        {{ item.label }}
      </dt>
      <dd
        class="font-mono text-xs font-semibold tabular-nums"
        :class="recipeStatusSummaryValueClass(item.tone)"
      >
        {{ item.value }}
        <!-- 이전 동일 기간 대비. 이전 구간 요약이 아직 오지 않았으면 text 가
             비어 있고, 자리는 min-width 로 잡아 둬 도착할 때 줄이 덜 밀립니다. -->
        <span
          v-if="item.delta"
          class="ml-0.5 inline-block min-w-[6ch] text-xs font-mono font-normal tabular-nums"
          :class="recipeStatusDeltaClass(item.delta.tone)"
          :title="item.delta.title || undefined"
        >{{ item.delta.text }}</span>
      </dd>
    </div>
  </dl>
  <span
    v-if="deltaCaption"
    class="sk-meta whitespace-nowrap"
  >{{ deltaCaption }}</span>
</template>

<script setup lang="ts">
import {
  recipeStatusDeltaCaption,
  recipeStatusDeltaClass,
  recipeStatusSummaryValueClass,
  type RecipeStatusSummaryItem
} from '~/utils/recipeStatusSummary'

const props = defineProps<{
  items: readonly RecipeStatusSummaryItem[]
}>()

const deltaCaption = computed(() => recipeStatusDeltaCaption(props.items))
</script>
