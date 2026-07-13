<script setup lang="ts">
definePageMeta({
  layout: 'hub'
})
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold mb-6">
      Settings
    </h1>

    <div class="space-y-6">
      <UCard class="dashboard-surface rounded-3xl">
        <template #header>
          <h2 class="font-semibold">
            Appearance
          </h2>
        </template>

        <div class="space-y-6">
          <SettingsColorModeSelector />

          <SettingsEchartThemeSelector />
        </div>
      </UCard>

      <div id="api-tokens">
        <SettingsApiTokens />
      </div>

      <UCard class="dashboard-surface rounded-3xl">
        <template #header>
          <h2 class="font-semibold">
            About
          </h2>
        </template>

        <div class="space-y-2 text-sm">
          <p><span class="text-gray-500">Application:</span> SKEWNONO v3</p>
          <p><span class="text-gray-500">Purpose:</span> E-Beam Metrology Dashboard</p>
          <p><span class="text-gray-500">Phase:</span> Development (Phase 1 - Offline)</p>
        </div>
      </UCard>
    </div>
  </div>
</template>
