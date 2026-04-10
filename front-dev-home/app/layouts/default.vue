<script setup lang="ts">
const { category } = useNavigation()
</script>

<template>
  <div class="relative isolate min-h-screen flex flex-col text-zinc-900 dark:text-zinc-100">
    <div
      class="dashboard-bg-layer"
      aria-hidden="true"
    />
    <NavAppHeader />

    <template v-if="category === 'ebeam'">
      <NavToolTypeTabs />
    </template>

    <div class="flex flex-1">
      <NavFabSidebar />

      <main class="flex-1 flex flex-col overflow-hidden">
        <NavFeatureTabs />

        <div class="flex-1 overflow-auto p-4 md:p-6 lg:p-8">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
