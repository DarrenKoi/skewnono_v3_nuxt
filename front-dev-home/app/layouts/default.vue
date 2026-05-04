<script setup lang="ts">
const route = useRoute()

const isEbeamRoute = computed(() => route.path === '/ebeam' || route.path.startsWith('/ebeam/'))
const showFabSidebar = computed(() => isEbeamRoute.value && route.meta.hideFabSidebar !== true)
</script>

<template>
  <div class="relative isolate min-h-screen flex flex-col text-zinc-900 dark:text-zinc-100">
    <div
      class="dashboard-bg-layer"
      aria-hidden="true"
    />
    <NavAppHeader />

    <template v-if="isEbeamRoute">
      <NavToolTypeTabs />
    </template>

    <div class="flex flex-1 gap-3 md:gap-4 pr-4 md:pr-6 lg:pr-8">
      <NavFabSidebar v-if="showFabSidebar" />

      <main class="flex-1 flex flex-col overflow-hidden min-w-0">
        <NavFeatureTabs />

        <div class="flex-1 overflow-auto p-4 md:p-6 lg:p-8">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
