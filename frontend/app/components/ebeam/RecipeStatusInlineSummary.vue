<template>
  <dl class="flex flex-wrap items-center gap-x-3 gap-y-1">
    <!-- delta 가 없는 항목은 예전 그대로 한 줄입니다(비교가 없는 화면이 이
         스트립을 같이 씁니다). delta 가 있으면 값 아래에 한 줄을 더 둡니다. -->
    <div
      v-for="item in items"
      :key="item.label"
      class="items-baseline gap-x-1 whitespace-nowrap"
      :class="item.delta ? 'inline-grid min-w-36 grid-cols-[auto_1fr]' : 'inline-flex'"
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
      <!-- 이전 동일 기간 대비. w-0 + min-w-full: 퍼센트 min-width 는 항목의
           고유 폭 계산에 들어가지 않아 글자 길이가 항목을 넓히지 못하고, 줄은
           항목 폭만큼만 차지합니다. 넘치면 말줄임(truncate)하고 전체 글자는
           title 앞머리에 둡니다. 높이는 text-xs 한 줄(h-4)로 고정이라 이전
           구간 요약이 늦게 도착해도 옆 항목과 아래 줄이 움직이지 않습니다.
           min-w-36 은 보통 길이의 delta 가 잘리지 않게 하는 여유이고, 둘째
           열이 1fr 이라 delta 줄이 그 폭 전체를 씁니다(auto 면 라벨+값 폭뿐). -->
      <dd
        v-if="item.delta"
        class="col-span-2 h-4 w-0 min-w-full truncate font-mono text-xs leading-4 tabular-nums"
        :class="recipeStatusDeltaClass(item.delta.tone)"
        :title="recipeStatusDeltaTitle(item.delta)"
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
  recipeStatusDeltaTitle,
  recipeStatusSummaryValueClass,
  type RecipeStatusSummaryItem
} from '~/utils/recipeStatusSummary'

const props = defineProps<{
  items: readonly RecipeStatusSummaryItem[]
}>()

const deltaCaption = computed(() => recipeStatusDeltaCaption(props.items))
</script>
