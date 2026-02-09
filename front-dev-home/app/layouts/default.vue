<script setup lang="ts">
const { category } = useNavigation()
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <NavAppHeader />

    <template v-if="category === 'ebeam'">
      <NavToolTypeTabs />
    </template>

    <div class="flex flex-1">
      <NavFabSidebar />

      <main class="flex-1 flex flex-col overflow-hidden">
        <NavFeatureTabs />

        <div class="flex-1 overflow-auto p-6">
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
