<template>
  <dl class="flex flex-wrap items-center gap-x-3 gap-y-1">
    <!-- delta 가 없는 항목은 예전 그대로 한 줄입니다(비교가 없는 화면이 이
         스트립을 같이 씁니다). delta 가 있으면 값 아래에 한 줄을 더 둡니다. -->
    <div
      v-for="item in items"
      :key="item.label"
      class="items-baseline gap-x-1 whitespace-nowrap"
      :class="item.delta ? 'inline-grid min-w-36 grid-cols-[auto_auto] justify-start' : 'inline-flex'"
    >
      <dt class="sk-label">
        {{ item.label }}
      </dt>
      <dd
        class="font-mono text-xs font-semibold tabular-nums"
        :class="recipeStatusSummaryValueClass(item.tone)"
      >
        {{ item.value }}
      </dd>
      <!-- 이전 동일 기간 대비. 폭 0(w-0, 넘치는 글자는 그대로 보임)이라 글자
           길이가 항목 폭을 바꾸지 못하고, 높이는 text-xs 한 줄(h-4)로 고정이라
           이전 구간 요약이 늦게 도착해도 옆 항목과 아래 줄이 움직이지
           않습니다. min-w-36 은 넘친 글자가 옆 항목에 닿지 않게 하는 여유입니다. -->
      <dd
        v-if="item.delta"
        class="col-span-2 h-4 w-0 font-mono text-xs leading-4 tabular-nums"
        :class="recipeStatusDeltaClass(item.delta.tone)"
        :title="item.delta.title || undefined"
      >
        {{ item.delta.text }}
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
