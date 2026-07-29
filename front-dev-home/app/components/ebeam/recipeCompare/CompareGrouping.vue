<template>
  <div class="flex flex-col gap-1.5">
    <div
      v-for="field in fields"
      :key="field.key"
      class="flex flex-wrap items-center gap-2 border-b border-zinc-100 py-2 dark:border-zinc-800/60"
    >
      <span class="w-28 shrink-0 sk-label">{{ field.label }}</span>
      <button
        v-for="bucket in field.buckets"
        :key="bucket.value"
        type="button"
        class="rounded-md px-2.5 py-1 font-mono text-[11px] transition"
        :class="bucket.isOutlier
          ? 'bg-rose-500/15 text-rose-600 ring-1 ring-rose-500/40 dark:text-rose-300'
          : 'bg-emerald-500/12 text-emerald-700 dark:text-emerald-300'"
        @click="toggleExpand(field.key, bucket.value)"
      >
        {{ bucket.value }} ×{{ bucket.count }}<span v-if="bucket.isOutlier"> ⚠</span>
      </button>
      <div
        v-if="expanded === `${field.key}::pick`"
        class="basis-full pt-1 pl-28 font-mono text-[10px] text-(--sk-ink-muted)"
      >
        {{ expandedRecipeIds.join(', ') }}
      </div>
    </div>
    <p
      v-if="fields.length === 0"
      class="py-6 text-center sk-meta"
    >
      차이가 있는 항목이 없습니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { CompareRecipe } from '~/composables/useRecipeCompareApi'
import {
  type CompareParamDetail,
  type MatrixRow,
  type ValueBucket,
  buildSettingRows,
  buildIdpRows,
  groupFieldValues
} from '~/utils/recipeCompare'
import type { ImageSlotKey } from '~/utils/recipeView'

const props = defineProps<{
  recipes: CompareRecipe[]
  parameter: string
  slotKey: ImageSlotKey
  diffOnly: boolean
  /** Aligned with `recipes` by index — the visible cell's settings per recipe. */
  details: (CompareParamDetail | null)[]
}>()

interface GroupedField {
  key: string
  label: string
  buckets: ValueBucket[]
}

const recipeIds = computed(() => props.recipes.map(r => r.recipe_id))

const groupRow = (row: MatrixRow): GroupedField => ({
  key: row.key,
  label: row.label,
  buckets: groupFieldValues(row.values.map((value, i) => ({ recipeId: recipeIds.value[i]!, value })))
})

const fields = computed<GroupedField[]>(() => {
  const rows = [
    ...buildIdpRows(props.recipes, props.parameter),
    ...buildSettingRows(props.details, props.slotKey)
  ]
  const grouped = rows.map(groupRow)
  return props.diffOnly ? grouped.filter(f => f.buckets.length > 1) : grouped
})

const expanded = ref<string | null>(null)
const expandedRecipeIds = ref<string[]>([])

const toggleExpand = (fieldKey: string, value: string) => {
  const token = `${fieldKey}::pick`
  const field = fields.value.find(f => f.key === fieldKey)
  const bucket = field?.buckets.find(b => b.value === value)
  if (expanded.value === token && expandedRecipeIds.value.join() === (bucket?.recipeIds ?? []).join()) {
    expanded.value = null
    expandedRecipeIds.value = []
    return
  }
  expanded.value = token
  expandedRecipeIds.value = bucket?.recipeIds ?? []
}
</script>
