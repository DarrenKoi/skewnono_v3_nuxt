<script setup lang="ts">
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 py-8">
    <h1 class="sk-page-title mb-6">
      Settings
    </h1>

    <div class="space-y-6">
      <UCard class="dashboard-surface rounded-3xl">
        <template #header>
          <h2 class="sk-title">
            Appearance
          </h2>
        </template>

        <SettingsColorModeSelector />
      </UCard>

      <UCard class="dashboard-surface rounded-3xl">
        <template #header>
          <h2 class="sk-title">
            기본 Fab
          </h2>
        </template>

        <SettingsDefaultFabPicker />
      </UCard>

      <UCard class="dashboard-surface rounded-3xl">
        <template #header>
          <h2 class="sk-title">
            ECharts theme
          </h2>
        </template>

        <SettingsEchartThemeSelector />
      </UCard>

      <div id="api-tokens">
        <SettingsApiTokens />
      </div>
    </div>
  </div>
</template>
