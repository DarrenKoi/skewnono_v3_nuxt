<template>
  <USlideover
    :open="open"
    :title="device?.lot_cd ?? ''"
    :description="device?.ctn_desc || ''"
    :ui="{ content: 'w-[80vw] sm:max-w-[80vw]', title: 'font-mono text-lg', description: 'sk-card-desc' }"
    @update:open="(v: boolean) => emit('update:open', v)"
  >
    <template #body>
      <div class="space-y-2.5">
        <div class="flex flex-wrap items-center gap-x-5 gap-y-1.5">
          <span class="sk-hint">
            recipe <span class="sk-field-value font-semibold text-(--sk-ink)">{{ device?.recipes.length ?? 0 }}</span>개
          </span>
          <span class="sk-hint inline-flex items-center gap-2">
            <span class="inline-block h-2.5 w-2.5 rounded-full bg-rose-500" />
            {{ highlightLabel }} recipe <span class="sk-field-value font-semibold text-(--sk-ink)">{{ device?.flagged_recipe_count ?? 0 }}</span>개
            · 파라미터 <span class="sk-field-value font-semibold text-(--sk-ink)">{{ device?.flagged_param_count ?? 0 }}</span>개
          </span>
        </div>

        <div
          v-for="recipe in device?.recipes ?? []"
          :key="recipe.recipe_id"
          class="flex items-stretch overflow-hidden rounded-xl ring-1 ring-(--sk-border)"
          :class="recipe.flagged ? 'bg-rose-50/60 dark:bg-rose-950/20' : 'bg-(--sk-surface)'"
        >
          <!-- 초과 recipe 는 왼쪽 4px 띠로 표시합니다. 접힌 상태에서도 어느
               recipe 를 펼쳐 봐야 하는지 목록 가장자리만 훑어 알 수 있습니다. -->
          <span
            v-if="recipe.flagged"
            class="w-1 flex-none bg-rose-500"
            aria-hidden="true"
          />
          <div class="min-w-0 flex-1">
            <button
              type="button"
              class="flex h-12 w-full items-center justify-between gap-3 px-4 text-left"
              :aria-expanded="expanded.has(recipe.recipe_id)"
              @click="toggle(recipe.recipe_id)"
            >
              <span class="flex min-w-0 items-center gap-2">
                <UIcon
                  :name="expanded.has(recipe.recipe_id) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                  class="h-4 w-4 flex-none text-(--sk-ink-subtle)"
                />
                <span class="truncate font-mono text-[17px] font-semibold text-(--sk-ink)">{{ recipe.recipe_id }}</span>
              </span>
              <span class="flex flex-none items-center gap-3">
                <span class="text-sm tabular-nums text-(--sk-ink-muted)">{{ recipe.total_params }} params</span>
                <!-- 특수 job 은 파라미터당 point 수가 정상 recipe 의 몇 배라,
                     이 배지가 없으면 큰 숫자가 초과 표시 없이 놓인 것이 규칙
                     고장으로 읽힙니다. -->
                <span
                  v-if="recipe.exempt"
                  class="sk-badge bg-(--sk-muted-surface) font-sans font-semibold text-(--sk-ink-muted) ring-1 ring-(--sk-border) ring-inset"
                  :title="EXEMPT_TITLE"
                >{{ EXEMPT_BADGE }}</span>
                <span
                  v-else-if="recipe.flagged_count > 0"
                  class="sk-badge sk-badge-lg bg-rose-100 font-bold text-rose-700 dark:bg-rose-950/50 dark:text-rose-300"
                >{{ highlightLabel }} {{ recipe.flagged_count }}</span>
              </span>
            </button>

            <!-- 표가 아니라 라벨 달린 행입니다. 열이 셋뿐이고 헤더도 없어서,
                 <table> 이 주는 정렬 이점보다 12px 글자의 대가가 컸습니다. -->
            <div
              v-if="expanded.has(recipe.recipe_id)"
              class="border-t border-(--sk-border)"
            >
              <div
                v-for="param in recipe.parameters"
                :key="param.name"
                class="px-4 py-1.5"
                :class="param.flagged ? 'bg-rose-100/50 dark:bg-rose-950/30' : ''"
              >
                <!-- 배경 tint 는 행 전체를 덮되 글자는 max-w 안에 묶습니다.
                     슬라이드오버가 뷰포트의 80% 라, 이름과 값을 양 끝으로
                     밀어 두면 둘 사이를 1000px 넘게 눈으로 건너야 합니다. -->
                <div class="flex max-w-2xl items-center gap-3">
                  <span class="min-w-0 flex-1 font-mono text-[15px] text-(--sk-ink)">{{ param.name }}</span>
                  <span class="w-16 flex-none text-right font-mono text-base font-semibold tabular-nums text-(--sk-ink)">{{ param.point_count }}</span>
                  <span class="w-28 flex-none text-right sk-field-label tabular-nums">{{ param.note ?? '' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </USlideover>
</template>

<script setup lang="ts">
import type { DrillDevice } from '~/utils/deviceDrill'

// Dumb drill-down: renders a pre-computed DrillDevice. The page decides what
// "flagged" means (outlier vs cap-violation) and passes the label (D22).
const props = defineProps<{
  open: boolean
  device: DrillDevice | null
  highlightLabel?: string
}>()

const emit = defineEmits<{ 'update:open': [boolean] }>()

// 웨이퍼 전면을 훑는 job 이라 설계대로 많이 잽니다 — "초과" 가 아닙니다.
const EXEMPT_BADGE = '분석 제외'
const EXEMPT_TITLE = 'CDU·full/half-map 측정 job(_WCDU/_FCDU/_FULL/_HALF)입니다. '
  + '설계상 측정 규모가 정상 recipe 와 달라 중앙값 기준선과 초과 판정에서 모두 빠집니다.'

const highlightLabel = computed(() => props.highlightLabel ?? '초과')
const expanded = ref<Set<string>>(new Set())

const toggle = (recipeId: string) => {
  const next = new Set(expanded.value)
  if (next.has(recipeId)) next.delete(recipeId)
  else next.add(recipeId)
  expanded.value = next
}

// Collapse all when the slideover is reopened for a different device.
watch(() => props.device?.lot_cd, () => {
  expanded.value = new Set()
})
</script>
