<script setup lang="ts">
definePageMeta({
  layout: 'hub'
})

const { toolTypes } = useToolData()
const { fabs: afmFabs, afmToolHref } = useAfmToolData()
const { fab, setFab, toolTypeHref } = useNavigation()

const { data: semRows } = await useSemList()
const { data: healthData, error: healthError } = useBackendHealth()

const fabOptions = computed(() => extractFabNames(semRows.value ?? []).map(name => ({
  label: name,
  value: name
})))

const selectedFab = computed<string | undefined>({
  get: () => fab.value === 'all' ? undefined : fab.value,
  set: value => setFab(value ?? 'all')
})

const rowsByToolType = computed(() => {
  const groups = new Map<string, typeof semRows.value>()
  for (const tool of toolTypes) {
    groups.set(tool.id, [])
  }

  for (const row of semRows.value ?? []) {
    const toolType = classifyToolType(row.eqp_model_cd)
    if (!toolType) continue
    groups.get(toolType)?.push(row)
  }

  return groups
})

const ebeamTools = computed(() => {
  return toolTypes.map(tool => ({
    ...tool,
    count: rowsByToolType.value.get(tool.id)?.length ?? tool.count
  }))
})

const systemStatus = computed(() => {
  return ebeamTools.value
    .filter(tool => tool.enabled)
    .map((tool) => {
      const rows = rowsByToolType.value.get(tool.id) ?? []

      return {
        ...tool,
        online: rows.filter(row => row.available === 'On').length,
        total: rows.length
      }
    })
})
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <section class="dashboard-surface rounded-3xl p-6 md:p-8">
      <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        <div>
          <p class="text-xs uppercase tracking-[0.18em] text-(--sk-ink-muted) font-semibold mb-2">
            측정 데이터 검색, 분석, 상태 확인을 한 곳에서
          </p>
          <h1 class="sk-page-title">
            METROLOGY WORKSPACE
          </h1>
          <div class="mt-5 flex w-full items-center gap-3 sm:w-80">
            <label
              for="landing-fab-select"
              class="shrink-0 text-xs font-semibold uppercase tracking-[0.14em] text-(--sk-ink-muted)"
            >
              FAB 선택
            </label>
            <USelect
              id="landing-fab-select"
              v-model="selectedFab"
              class="min-w-0 flex-1"
              size="lg"
              color="neutral"
              variant="subtle"
              icon="i-lucide-factory"
              placeholder="Select a FAB (default: R3)"
              :items="fabOptions"
            />
          </div>
        </div>
        <HomeBackendHealthCard
          :services="healthData?.services ?? []"
          :error="!!healthError"
        />
      </div>
    </section>

    <!-- Category Cards -->
    <div class="grid md:grid-cols-2 gap-6">
      <!-- E-Beam Metrology Card -->
      <UCard
        class="dashboard-surface rounded-3xl"
        :ui="{
          body: 'p-6'
        }"
      >
        <div class="flex items-start justify-between mb-4">
          <h2 class="text-xl font-semibold">
            E-Beam Metrology
          </h2>
          <UIcon
            name="i-lucide-microscope"
            class="w-6 h-6 text-zinc-700 dark:text-zinc-300"
          />
        </div>

        <nav class="space-y-2">
          <template
            v-for="tool in ebeamTools"
            :key="tool.id"
          >
            <NuxtLink
              v-if="tool.enabled"
              :to="toolTypeHref(tool.id)"
              class="flex items-center justify-between p-3 rounded-xl hover:bg-zinc-100 dark:hover:bg-zinc-800/80 transition-colors group"
            >
              <span class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-arrow-right"
                  class="w-4 h-4 text-(--sk-ink-muted) group-hover:text-zinc-800 dark:group-hover:text-zinc-200 transition-colors"
                />
                <span class="font-medium">
                  {{ tool.label }}
                </span>
              </span>
              <UBadge
                :label="String(tool.count)"
                color="neutral"
                variant="subtle"
              />
            </NuxtLink>
            <div
              v-else
              :aria-disabled="true"
              class="flex items-center justify-between p-3 rounded-xl text-(--sk-ink-muted) cursor-not-allowed"
            >
              <span class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-construction"
                  class="w-4 h-4"
                />
                <span class="font-medium">
                  {{ tool.label }}
                </span>
              </span>
              <span class="flex items-center gap-1.5">
                <UBadge
                  :label="String(tool.count)"
                  color="neutral"
                  variant="subtle"
                />
                <UBadge
                  label="개발 예정"
                  color="neutral"
                  variant="soft"
                />
              </span>
            </div>
          </template>
        </nav>
      </UCard>

      <!-- AFM Metrology Card -->
      <UCard
        class="dashboard-surface rounded-3xl"
        :ui="{
          body: 'p-6'
        }"
      >
        <div class="flex items-start justify-between mb-4">
          <h2 class="text-xl font-semibold">
            AFM Metrology
          </h2>
          <UIcon
            name="i-lucide-activity"
            class="w-6 h-6 text-zinc-700 dark:text-zinc-300"
          />
        </div>

        <nav class="space-y-3">
          <div
            v-for="fabGroup in afmFabs"
            :key="fabGroup.fab"
            class="space-y-1"
          >
            <div class="px-3 text-xs uppercase tracking-[0.16em] text-(--sk-ink-muted) font-semibold">
              {{ fabGroup.fab }}
            </div>
            <NuxtLink
              v-for="tool in fabGroup.tools"
              :key="tool.id"
              :to="afmToolHref(tool)"
              class="flex items-center justify-between p-3 rounded-xl hover:bg-zinc-100 dark:hover:bg-zinc-800/80 transition-colors group"
            >
              <span class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-arrow-right"
                  class="w-4 h-4 text-(--sk-ink-muted) group-hover:text-zinc-800 dark:group-hover:text-zinc-200 transition-colors"
                />
                <span class="font-medium">
                  {{ tool.label }}
                </span>
              </span>
              <UBadge
                :label="fabGroup.fab"
                color="neutral"
                variant="subtle"
              />
            </NuxtLink>
          </div>
        </nav>
      </UCard>
    </div>

    <!-- System Status -->
    <h3 class="sk-heading">
      System Status
    </h3>
    <UCard class="dashboard-surface rounded-3xl">
      <div class="flex flex-wrap gap-6">
        <div
          v-for="status in systemStatus"
          :key="status.id"
          class="flex items-center gap-2"
        >
          <span class="w-2 h-2 rounded-full bg-zinc-900 dark:bg-zinc-100" />
          <span class="text-sm">
            <span class="font-medium">{{ status.label }}:</span>
            <span class="text-zinc-600 dark:text-zinc-400"> {{ status.online }}/{{ status.total }}</span>
          </span>
        </div>
      </div>
    </UCard>
  </div>
</template>
