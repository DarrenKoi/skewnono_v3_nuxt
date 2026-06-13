<template>
  <USlideover
    :open="open"
    :title="device?.lot_cd ?? ''"
    :description="device?.ctn_desc || ''"
    :ui="{ content: 'w-[80vw] sm:max-w-[80vw]' }"
    @update:open="(v: boolean) => emit('update:open', v)"
  >
    <template #body>
      <div class="space-y-2">
        <div class="flex flex-wrap items-center gap-3 text-[12px] text-(--sk-ink-muted)">
          <span>recipe {{ device?.recipes.length ?? 0 }}개</span>
          <span class="inline-flex items-center gap-1.5">
            <span class="inline-block h-2 w-2 rounded-full bg-rose-500" />
            {{ highlightLabel }} recipe {{ device?.flagged_recipe_count ?? 0 }}개 · 파라미터 {{ device?.flagged_param_count ?? 0 }}개
          </span>
        </div>

        <div
          v-for="recipe in device?.recipes ?? []"
          :key="recipe.recipe_id"
          class="rounded-xl ring-1 ring-(--sk-border)"
          :class="recipe.flagged ? 'bg-rose-50/60 dark:bg-rose-950/20' : 'bg-(--sk-surface)'"
        >
          <button
            type="button"
            class="flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
            @click="toggle(recipe.recipe_id)"
          >
            <span class="flex items-center gap-2 font-mono text-[12px] text-(--sk-ink)">
              <UIcon
                :name="expanded.has(recipe.recipe_id) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                class="h-3.5 w-3.5 text-(--sk-ink-subtle)"
              />
              {{ recipe.recipe_id }}
            </span>
            <span class="flex items-center gap-3 text-[11px] tabular-nums text-(--sk-ink-muted)">
              <span>{{ recipe.total_params }} params</span>
              <span
                v-if="recipe.flagged_count > 0"
                class="inline-flex h-5 items-center rounded bg-rose-100 px-1.5 font-semibold text-rose-700 dark:bg-rose-950/50 dark:text-rose-300"
              >{{ highlightLabel }} {{ recipe.flagged_count }}</span>
            </span>
          </button>

          <table
            v-if="expanded.has(recipe.recipe_id)"
            class="w-full border-t border-(--sk-border) text-[12px]"
          >
            <tbody>
              <tr
                v-for="param in recipe.parameters"
                :key="param.name"
                :class="param.flagged ? 'bg-rose-100/50 dark:bg-rose-950/30' : ''"
              >
                <td class="px-3 py-1 font-mono text-(--sk-ink)">
                  {{ param.name }}
                </td>
                <td class="px-3 py-1 text-right font-mono tabular-nums text-(--sk-ink)">
                  {{ param.point_count }}
                </td>
                <td class="px-3 py-1 text-right font-mono text-[11px] text-(--sk-ink-subtle)">
                  {{ param.note ?? '' }}
                </td>
              </tr>
            </tbody>
          </table>
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
watch(() => props.device?.lot_cd, () => { expanded.value = new Set() })
</script>
