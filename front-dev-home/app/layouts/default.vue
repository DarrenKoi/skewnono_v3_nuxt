<script setup lang="ts">
const route = useRoute()
const isEbeamRoute = useEbeamRoute()
const showFabSidebar = computed(() => isEbeamRoute.value && route.meta.hideFabSidebar !== true)
const lockDesktopPageScroll = computed(() => route.meta.lockDesktopPageScroll === true)
</script>

<template>
  <div class="relative isolate flex h-screen min-h-0 flex-col overflow-hidden text-zinc-900 dark:text-zinc-100">
    <div
      class="dashboard-bg-layer"
      aria-hidden="true"
    />
    <NavAppHeader />

    <div class="flex min-h-0 flex-1 gap-3 pr-4 md:gap-4 md:pr-6 lg:pr-8">
      <NavFabSidebar v-if="showFabSidebar" />

      <main class="flex-1 flex flex-col overflow-hidden min-w-0">
        <div
          class="min-h-0 flex-1 p-4 md:p-6 lg:p-8"
          :class="lockDesktopPageScroll
            ? 'overflow-auto [scrollbar-gutter:stable] xl:overflow-hidden xl:[scrollbar-gutter:auto]'
            : 'overflow-auto [scrollbar-gutter:stable]'"
        >
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
