<template>
  <!-- aria-label 은 prop 이 아니라 fallthrough 속성으로 받습니다. 같은 이름의
       prop 을 두면 Vue 가 둘 중 어느 쪽을 쓸지 호출부에서 헷갈립니다. -->
  <div
    role="radiogroup"
    class="inline-flex items-center gap-1 rounded-lg bg-(--sk-muted-surface) p-1 ring-1 ring-(--sk-border-soft) ring-inset"
  >
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="model === option.value"
      class="inline-flex h-[30px] items-center gap-1.5 rounded-md px-3 text-sm font-semibold transition-colors"
      :class="model === option.value
        ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm ring-1 ring-(--sk-border)'
        : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
      @click="model = option.value"
    >
      <UIcon
        :name="option.icon"
        class="h-4 w-4"
      />
      {{ option.label }}
    </button>
  </div>
</template>

<script setup lang="ts">
import type { RowCardView } from '~/composables/useRowCardView'

// 행 보기 / 표 보기 세그먼트. 한쪽 라벨만 보여 주는 단일 토글이 아니라 두 칸을
// 모두 그립니다 — "표 보기" 한 칸만 있으면 그것이 현재 상태인지 누르면 갈 곳인지
// 읽는 사람이 알 수 없습니다.
const model = defineModel<RowCardView>({ required: true })

const options: { value: RowCardView, label: string, icon: string }[] = [
  { value: 'cards', label: '행 보기', icon: 'i-lucide-rows-3' },
  { value: 'table', label: '표 보기', icon: 'i-lucide-table' }
]
</script>
