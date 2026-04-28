<script setup lang="ts">
import type { Fab } from '~/stores/navigation'

type RecipeStatus = 'Released' | 'Review' | 'Draft'
type ServicedRecipeToolType = 'cd-sem' | 'hv-sem'

type RecipeRow = {
  recipeId: string
  title: string
  equipment: string
  layer: string
  lot: string
  owner: string
  status: RecipeStatus
  updatedAt: string
  tags: string[]
}

type RecipeCatalog = {
  quickSearches: string[]
  rows: RecipeRow[]
}

const props = defineProps<{
  fab: Fab
  toolLabel: string
  toolType: ServicedRecipeToolType
}>()

const recipeCatalog: Record<ServicedRecipeToolType, RecipeCatalog> = {
  'cd-sem': {
    quickSearches: [
      'overlay',
      'contact',
      'CD bias',
      'nightly check',
      'R3'
    ],
    rows: [
      {
        recipeId: 'RCP-CDSEM-OVL-1024',
        title: 'Overlay monitor recipe',
        equipment: 'HITACHI-CG6300',
        layer: 'OVL',
        lot: 'M16A-PROD-0428',
        owner: 'Process Team',
        status: 'Released',
        updatedAt: '2026-04-27 09:20',
        tags: ['overlay', 'production', 'golden']
      },
      {
        recipeId: 'RCP-CDSEM-CNT-2048',
        title: 'Contact CD sampling',
        equipment: 'HITACHI-CG7300',
        layer: 'CNT',
        lot: 'M16A-ENG-1771',
        owner: 'Yield Team',
        status: 'Review',
        updatedAt: '2026-04-26 18:45',
        tags: ['contact', 'sample', 'review']
      },
      {
        recipeId: 'RCP-CDSEM-GATE-0312',
        title: 'Gate CD bias check',
        equipment: 'HITACHI-CG6380',
        layer: 'GATE',
        lot: 'R3-PROD-2190',
        owner: 'Device Team',
        status: 'Released',
        updatedAt: '2026-04-25 13:10',
        tags: ['CD bias', 'gate', 'R3']
      },
      {
        recipeId: 'RCP-CDSEM-DAILY-0007',
        title: 'Nightly tool matching',
        equipment: 'HITACHI-CG6300',
        layer: 'QC',
        lot: 'M16A-QC-0007',
        owner: 'Metrology Team',
        status: 'Draft',
        updatedAt: '2026-04-24 22:30',
        tags: ['nightly check', 'matching', 'QC']
      }
    ]
  },
  'hv-sem': {
    quickSearches: [
      'defect review',
      'TP4000',
      'high voltage',
      'wafer edge',
      'R3'
    ],
    rows: [
      {
        recipeId: 'RCP-HVSEM-DEF-4100',
        title: 'Defect review high-voltage scan',
        equipment: 'AMAT-TP4000',
        layer: 'DEF',
        lot: 'R3-PROD-4100',
        owner: 'Defect Team',
        status: 'Released',
        updatedAt: '2026-04-27 10:05',
        tags: ['defect review', 'high voltage', 'R3']
      },
      {
        recipeId: 'RCP-HVSEM-EDGE-2216',
        title: 'Wafer edge inspection',
        equipment: 'AMAT-TP3500',
        layer: 'EDGE',
        lot: 'M16B-ENG-2216',
        owner: 'Process Team',
        status: 'Review',
        updatedAt: '2026-04-26 16:20',
        tags: ['wafer edge', 'review', 'inspection']
      },
      {
        recipeId: 'RCP-HVSEM-MATL-1108',
        title: 'Material contrast monitor',
        equipment: 'AMAT-TP4500',
        layer: 'MATL',
        lot: 'M15A-PROD-1108',
        owner: 'Integration Team',
        status: 'Released',
        updatedAt: '2026-04-25 11:40',
        tags: ['contrast', 'monitor', 'TP4500']
      },
      {
        recipeId: 'RCP-HVSEM-DAILY-0012',
        title: 'Daily HV column qualification',
        equipment: 'AMAT-TP3000',
        layer: 'QC',
        lot: 'R4-QC-0012',
        owner: 'Metrology Team',
        status: 'Draft',
        updatedAt: '2026-04-24 21:10',
        tags: ['daily check', 'qualification', 'TP3000']
      }
    ]
  }
}

const query = ref('')
const submittedQuery = ref('')

const quickSearches = computed(() => recipeCatalog[props.toolType].quickSearches)
const recipeRows = computed(() => recipeCatalog[props.toolType].rows)

const activeSearch = computed(() => submittedQuery.value.trim())

const normalizedSearch = computed(() => activeSearch.value.toLowerCase())

const filteredRows = computed(() => {
  const term = normalizedSearch.value

  if (!term) {
    return recipeRows.value
  }

  return recipeRows.value.filter((row) => {
    return [
      row.recipeId,
      row.title,
      row.equipment,
      row.layer,
      row.lot,
      row.owner,
      row.status,
      row.updatedAt,
      ...row.tags
    ].some(value => value.toLowerCase().includes(term))
  })
})

const resultSummary = computed(() => {
  if (!activeSearch.value) {
    return `${recipeRows.value.length} sample recipes`
  }

  return `${filteredRows.value.length} results for "${activeSearch.value}"`
})

const searchRecipes = () => {
  submittedQuery.value = query.value.trim()
}

const setQuickSearch = (value: string) => {
  query.value = value
  submittedQuery.value = value
}

const clearSearch = () => {
  query.value = ''
  submittedQuery.value = ''
}

const statusColor = (status: RecipeStatus) => {
  if (status === 'Released') return 'success'
  if (status === 'Review') return 'warning'
  return 'neutral'
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-col gap-1">
      <p class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
        {{ toolLabel }}
      </p>
      <h1 class="text-2xl font-bold text-zinc-950 dark:text-zinc-50">
        Recipe Search - {{ fab }}
      </h1>
    </div>

    <section class="mx-auto flex w-full max-w-4xl flex-col items-center gap-5 py-8 md:py-12">
      <form
        class="group flex h-14 w-full items-center gap-2 rounded-full border border-zinc-200 bg-white px-4 shadow-sm transition focus-within:border-zinc-300 focus-within:ring-4 focus-within:ring-zinc-200/70 dark:border-zinc-800 dark:bg-zinc-950 dark:focus-within:border-zinc-700 dark:focus-within:ring-zinc-800/70 md:h-16 md:px-5"
        @submit.prevent="searchRecipes"
      >
        <UIcon
          name="i-lucide-search"
          class="h-5 w-5 shrink-0 text-zinc-400"
        />

        <input
          v-model="query"
          class="min-w-0 flex-1 bg-transparent text-base text-zinc-950 outline-none placeholder:text-zinc-400 dark:text-zinc-50 md:text-lg"
          type="search"
          inputmode="search"
          autocomplete="off"
          placeholder="Search recipe ID, layer, lot, equipment, or keyword"
        >

        <UButton
          v-if="query"
          type="button"
          size="sm"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          aria-label="Clear search"
          class="rounded-full"
          @click="clearSearch"
        />

        <UButton
          type="submit"
          size="sm"
          color="neutral"
          variant="solid"
          icon="i-lucide-arrow-right"
          aria-label="Search recipes"
          class="rounded-full"
        />
      </form>

      <div class="flex w-full flex-wrap justify-center gap-2">
        <UButton
          v-for="item in quickSearches"
          :key="item"
          size="xs"
          color="neutral"
          variant="soft"
          class="rounded-full"
          @click="setQuickSearch(item)"
        >
          {{ item }}
        </UButton>
      </div>
    </section>

    <div class="space-y-3">
      <div class="flex items-center justify-between gap-3">
        <h2 class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          Search Results
        </h2>
        <p class="text-xs text-zinc-500 tabular-nums">
          {{ resultSummary }}
        </p>
      </div>

      <div
        v-if="filteredRows.length === 0"
        class="dashboard-surface rounded-2xl px-4 py-12 text-center text-sm text-zinc-500"
      >
        No recipes match the current search.
      </div>

      <div
        v-else
        class="grid gap-3"
      >
        <article
          v-for="row in filteredRows"
          :key="row.recipeId"
          class="dashboard-surface rounded-2xl p-4 transition hover:border-zinc-300 dark:hover:border-zinc-700"
        >
          <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div class="min-w-0 space-y-2">
              <div class="flex flex-wrap items-center gap-2">
                <p class="font-mono text-sm font-semibold tabular-nums text-zinc-950 dark:text-zinc-50">
                  {{ row.recipeId }}
                </p>
                <UBadge
                  :label="row.status"
                  :color="statusColor(row.status)"
                  size="xs"
                  variant="subtle"
                />
              </div>
              <p class="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                {{ row.title }}
              </p>
              <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500">
                <span>{{ row.equipment }}</span>
                <span>Layer {{ row.layer }}</span>
                <span>{{ row.lot }}</span>
                <span>{{ row.owner }}</span>
              </div>
            </div>

            <p class="shrink-0 text-xs text-zinc-500 tabular-nums">
              {{ row.updatedAt }}
            </p>
          </div>

          <div class="mt-3 flex flex-wrap gap-1.5">
            <UBadge
              v-for="tag in row.tags"
              :key="tag"
              :label="tag"
              color="neutral"
              size="xs"
              variant="soft"
            />
          </div>
        </article>
      </div>
    </div>
  </div>
</template>
