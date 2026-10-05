<template>
  <!-- 기본은 접힘입니다. 근거는 "왜?" 가 생긴 recipe 에서만 읽는 글이라, 늘 펴 두면
       파라미터 행이 한 화면 아래로 밀립니다. -->
  <details class="group border-t border-(--sk-border)">
    <summary class="flex cursor-pointer list-none items-center gap-2 px-4 py-2 [&::-webkit-details-marker]:hidden">
      <UIcon
        name="i-lucide-chevron-right"
        class="h-3.5 w-3.5 text-(--sk-ink-muted) transition-transform duration-200 group-open:rotate-90"
      />
      <span class="sk-label">판정 근거</span>
    </summary>
    <div class="max-w-2xl space-y-2 px-4 pb-3">
      <p class="sk-body text-(--sk-ink)">
        {{ explanation.sentence }}
      </p>
      <dl class="flex flex-wrap gap-x-5 gap-y-1">
        <div
          v-for="(row, i) in explanation.input_rows"
          :key="i"
          class="sk-meta"
        >
          <dt class="inline">
            {{ row.label }}
          </dt>
          {{ ' ' }}
          <dd class="inline font-medium text-(--sk-ink)">
            {{ row.value }}
          </dd>
        </div>
      </dl>
      <p
        v-if="explanation.cell.kind === 'cell'"
        class="sk-meta"
      >
        적용 셀 <span class="font-mono text-(--sk-ink)">{{ explanation.cell.id }}</span>
        · {{ explanation.cell.summary }}
      </p>
      <p
        v-else
        class="sk-meta"
      >
        적용 셀 없음 · Gray-{{ explanation.cell.gray }} · {{ explanation.cell.reason }}
      </p>
    </div>
  </details>
</template>

<script setup lang="ts">
import type { RecipeExplanation } from '~/utils/ruleExplain'

// 그리기만 합니다. 문장·라벨·출처는 전부 `ruleExplain.explainRecipe` 가 만든
// 것이고, 그 함수는 `ruleEngine` 의 판정 결과를 늘어놓기만 합니다.
defineProps<{ explanation: RecipeExplanation }>()
</script>
