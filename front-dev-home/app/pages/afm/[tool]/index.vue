<template>
  <div class="max-w-5xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <section class="dashboard-surface rounded-3xl p-6 md:p-8">
      <p class="text-xs uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
        AFM Metrology
      </p>
      <h1 class="text-2xl md:text-3xl font-semibold tracking-tight">
        {{ toolLabel }}
      </h1>
      <p
        v-if="fabLabel"
        class="text-sm text-zinc-500 dark:text-zinc-400 mt-1"
      >
        {{ fabLabel }}
      </p>
    </section>

    <UCard
      class="dashboard-surface rounded-3xl"
      :ui="{ body: 'p-6' }"
    >
      <div class="flex flex-col items-center justify-center h-40 text-zinc-500">
        <UIcon
          name="i-lucide-construction"
          class="w-12 h-12 mb-2 text-zinc-400"
        />
        <span class="text-sm">
          AFM 데이터 플랫폼 마이그레이션 예정
        </span>
        <NuxtLink
          to="/afm"
          class="mt-4"
        >
          <UButton
            color="neutral"
            variant="outline"
          >
            Tool 목록으로 돌아가기
          </UButton>
        </NuxtLink>
      </div>
    </UCard>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  layout: 'hub'
})

const route = useRoute()
const { setCategory } = useNavigation()
const { fabs } = useAfmToolData()

const toolId = computed(() => String(route.params.tool ?? ''))

const matched = computed(() => {
  for (const fabGroup of fabs) {
    const tool = fabGroup.tools.find(t => t.id === toolId.value)
    if (tool) return { fab: fabGroup.fab, tool }
  }
  return null
})

const toolLabel = computed(() => matched.value?.tool.label ?? toolId.value.toUpperCase())
const fabLabel = computed(() => matched.value?.fab ?? '')

onMounted(() => {
  setCategory('afm')
})
</script>
