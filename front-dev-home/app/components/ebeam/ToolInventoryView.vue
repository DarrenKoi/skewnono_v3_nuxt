<script setup lang="ts">
import type { Fab, ToolType } from '~/stores/navigation'

const props = withDefaults(defineProps<{
  fab?: Fab
  subtitle: string
  title: string
  toolType: ToolType
}>(), {
  fab: 'all'
})

const { fetchToolInventory, filterRows } = useEbeamToolApi()

const asyncKey = `ebeam-tool-inventory:${props.toolType}:${props.fab}`

const { data } = await useAsyncData(asyncKey, async () => {
  const inventory = await fetchToolInventory()
  const rows = filterRows(inventory, props.toolType, props.fab)
  const fabSummaries = props.fab === 'all' ? summarizeRowsByFab(rows) : []

  return {
    rows,
    fabSummaries
  }
})

const rows = computed(() => data.value?.rows ?? [])
const fabSummaries = computed(() => data.value?.fabSummaries ?? [])
const onlineCount = computed(() => rows.value.filter(row => row.available === 'On').length)
const offlineCount = computed(() => rows.value.filter(row => row.available === 'Off').length)
const fabCount = computed(() => new Set(rows.value.map(row => row.fab_name)).size)
</script>

<template>
  <div class="space-y-6">
    <div>
      <h1 class="text-2xl font-bold">
        {{ title }}
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        {{ subtitle }}
      </p>
    </div>

    <div class="grid gap-4 md:grid-cols-4">
      <UCard class="dashboard-surface rounded-2xl">
        <div class="text-center">
          <div class="text-3xl font-bold text-zinc-900 dark:text-zinc-100">
            {{ rows.length }}
          </div>
          <div class="text-sm text-gray-500">
            Total Tools
          </div>
        </div>
      </UCard>

      <UCard class="dashboard-surface rounded-2xl">
        <div class="text-center">
          <div class="text-3xl font-bold text-zinc-800 dark:text-zinc-200">
            {{ onlineCount }}
          </div>
          <div class="text-sm text-gray-500">
            Online
          </div>
        </div>
      </UCard>

      <UCard class="dashboard-surface rounded-2xl">
        <div class="text-center">
          <div class="text-3xl font-bold text-zinc-700 dark:text-zinc-300">
            {{ offlineCount }}
          </div>
          <div class="text-sm text-gray-500">
            Offline
          </div>
        </div>
      </UCard>

      <UCard class="dashboard-surface rounded-2xl">
        <div class="text-center">
          <div class="text-3xl font-bold text-zinc-600 dark:text-zinc-400">
            {{ fabCount }}
          </div>
          <div class="text-sm text-gray-500">
            Fabs
          </div>
        </div>
      </UCard>
    </div>

    <template v-if="props.fab === 'all' && fabSummaries.length > 0">
      <div>
        <h2 class="text-lg font-semibold mb-4">
          Fab Breakdown
        </h2>
        <div class="grid gap-4 md:grid-cols-3">
          <UCard
            v-for="summary in fabSummaries"
            :key="summary.fab_name"
            class="dashboard-surface rounded-2xl"
          >
            <div class="flex items-center justify-between mb-3">
              <h3 class="font-semibold">
                {{ summary.fab_name }}
              </h3>
              <UBadge
                :label="`${summary.online}/${summary.total} online`"
                color="neutral"
                variant="subtle"
              />
            </div>

            <div class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-gray-500">
                  Total Tools
                </span>
                <span class="font-medium">
                  {{ summary.total }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">
                  Online
                </span>
                <span class="font-medium">
                  {{ summary.online }}
                </span>
              </div>
              <div class="flex justify-between">
                <span class="text-gray-500">
                  Offline
                </span>
                <span class="font-medium">
                  {{ summary.offline }}
                </span>
              </div>
            </div>

            <div class="mt-4">
              <NuxtLink
                :to="`/ebeam/${toolType}/${summary.fab_name.toLowerCase()}`"
                class="text-sm font-medium text-zinc-700 hover:text-zinc-900 dark:text-zinc-300 dark:hover:text-zinc-100"
              >
                View Details ->
              </NuxtLink>
            </div>
          </UCard>
        </div>
      </div>
    </template>

    <div>
      <h2 class="text-lg font-semibold mb-4">
        Tool Inventory
      </h2>
      <UCard class="dashboard-surface rounded-2xl">
        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="border-b border-gray-200 dark:border-gray-700">
                <th class="px-4 py-3 text-left font-medium text-gray-500">
                  Fab
                </th>
                <th class="px-4 py-3 text-left font-medium text-gray-500">
                  Equipment ID
                </th>
                <th class="px-4 py-3 text-left font-medium text-gray-500">
                  Model
                </th>
                <th class="px-4 py-3 text-left font-medium text-gray-500">
                  IP Address
                </th>
                <th class="px-4 py-3 text-left font-medium text-gray-500">
                  Version
                </th>
                <th class="px-4 py-3 text-left font-medium text-gray-500">
                  Available
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rows"
                :key="row.eqp_id"
                class="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
              >
                <td class="px-4 py-3 font-medium">
                  {{ row.fab_name }}
                </td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-300">
                  {{ row.eqp_id }}
                </td>
                <td class="px-4 py-3 text-gray-600 dark:text-gray-300">
                  {{ row.eqp_model_cd }}
                </td>
                <td class="px-4 py-3 text-gray-500">
                  {{ row.eqp_ip }}
                </td>
                <td class="px-4 py-3 text-gray-500">
                  {{ row.version }}
                </td>
                <td class="px-4 py-3">
                  <UBadge
                    :label="row.available"
                    :color="row.available === 'On' ? 'success' : 'neutral'"
                    variant="subtle"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </UCard>
    </div>
  </div>
</template>
