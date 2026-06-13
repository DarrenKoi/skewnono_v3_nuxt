<template>
  <div class="dashboard-surface flex flex-col gap-3 rounded-2xl p-4 lg:flex-row lg:items-center">
    <div class="min-w-0 flex-1">
      <p class="mb-1.5 text-[10px] font-bold tracking-wider text-(--sk-brand) uppercase">
        비교 대상 recipe · {{ selected.length }}
      </p>
      <div class="flex flex-wrap items-center gap-1.5">
        <span
          v-for="name in selected"
          :key="name"
          class="inline-flex max-w-[240px] items-center gap-1 rounded-full bg-(--sk-brand-soft)/60 py-1 pl-2.5 pr-1 font-mono text-[10.5px] text-zinc-700 dark:text-zinc-200"
        >
          <span class="truncate">{{ name }}</span>
          <button
            type="button"
            :aria-label="`Remove ${name}`"
            class="rounded-full p-0.5 hover:bg-zinc-300 dark:hover:bg-zinc-600"
            @click="emit('remove', name)"
          >
            <UIcon
              name="i-lucide-x"
              class="h-3 w-3"
            />
          </button>
        </span>

        <div class="relative">
          <input
            v-model="addQuery"
            type="search"
            autocomplete="off"
            placeholder="＋ recipe 추가…"
            aria-label="recipe 추가"
            class="w-44 rounded-full border border-dashed border-zinc-300 bg-transparent px-3 py-1 font-mono text-[10.5px] outline-none focus:border-(--sk-brand) dark:border-zinc-700"
          >
          <div
            v-if="suggestions.length"
            class="absolute z-30 mt-1 max-h-56 w-72 overflow-auto rounded-lg border border-zinc-200 bg-white shadow-lg dark:border-zinc-700 dark:bg-zinc-900"
          >
            <button
              v-for="name in suggestions"
              :key="name"
              type="button"
              class="block w-full truncate px-3 py-1.5 text-left font-mono text-[10.5px] hover:bg-zinc-100 dark:hover:bg-zinc-800"
              @click="pick(name)"
            >
              {{ name }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <UButton
      class="shrink-0"
      size="sm"
      color="success"
      variant="soft"
      icon="i-lucide-download"
      label="Excel 다운로드"
      :disabled="!canExport"
      @click="emit('download')"
    />
  </div>
</template>

<script setup lang="ts">
import type { RecipeSearchToolType } from '~/composables/useRecipeSearchApi'

const props = defineProps<{
  selected: string[]
  toolType: RecipeSearchToolType
  fab: string
  canExport: boolean
}>()

const emit = defineEmits<{
  remove: [name: string]
  add: [name: string]
  download: []
}>()

const { fetchRecipeList } = useRecipeSearchApi()

const { data: catalog } = await useAsyncData(
  () => `recipe-search:${props.toolType}:${props.fab || 'ALL'}`,
  () => fetchRecipeList({ toolType: props.toolType, fabName: props.fab }),
  {
    default: () => ({ tool_type: props.toolType, fab_name: props.fab || null, total: 0, rows: [] as string[] }),
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  }
)

const addQuery = ref('')

const suggestions = computed(() => {
  const term = addQuery.value.trim().toLowerCase()
  if (term.length < 3) return []
  const all = catalog.value?.rows ?? []
  const matches: string[] = []
  for (const name of all) {
    if (props.selected.includes(name)) continue
    if (name.toLowerCase().includes(term)) matches.push(name)
    if (matches.length >= 8) break
  }
  return matches
})

const pick = (name: string) => {
  emit('add', name)
  addQuery.value = ''
}
</script>
