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
            <span class="inline-block h-2.5 w-2.5 rounded-full bg-(--sk-bad)" />
            {{ highlightLabel }} recipe <span class="sk-field-value font-semibold text-(--sk-ink)">{{ device?.flagged_recipe_count ?? 0 }}</span>개
            · 파라미터 <span class="sk-field-value font-semibold text-(--sk-ink)">{{ device?.flagged_param_count ?? 0 }}</span>개
          </span>
        </div>

        <div
          v-for="recipe in device?.recipes ?? []"
          :key="recipe.recipe_id"
          class="flex items-stretch overflow-hidden rounded-xl ring-1 ring-(--sk-border)"
          :class="recipe.flagged ? 'bg-(--sk-bad-tint)' : 'bg-(--sk-surface)'"
        >
          <!-- 초과 recipe 는 왼쪽 4px 띠로 표시합니다. 접힌 상태에서도 어느
               recipe 를 펼쳐 봐야 하는지 목록 가장자리만 훑어 알 수 있습니다. -->
          <span
            v-if="recipe.flagged"
            class="w-1 flex-none bg-(--sk-bad)"
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
                <!-- exempt 는 기본 크기, flagged 는 sk-badge-lg — 이 화면에
                     원래 있던 차이라 공유하면서도 그대로 둡니다. -->
                <EbeamDevstatDrillFlagBadge
                  v-if="recipe.exempt"
                  variant="exempt"
                />
                <EbeamDevstatDrillFlagBadge
                  v-else-if="recipe.flagged_count > 0"
                  variant="flagged"
                  :count="recipe.flagged_count"
                  :label="highlightLabel"
                  large
                />
              </span>
            </button>

            <EbeamDevstatDrillParamRows
              v-if="expanded.has(recipe.recipe_id)"
              :parameters="recipe.parameters"
            />
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
