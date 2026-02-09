<script setup lang="ts">
definePageMeta({
  layout: 'hub'
})
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <h1 class="text-2xl font-bold mb-6">Settings</h1>

    <div class="space-y-6">
      <UCard>
        <template #header>
          <h2 class="font-semibold">Appearance</h2>
        </template>

        <div class="flex items-center justify-between">
          <div>
            <p class="font-medium">Theme</p>
            <p class="text-sm text-gray-500">Select your preferred color theme</p>
          </div>
          <UColorModeSelect />
        </div>
      </UCard>

      <UCard>
        <template #header>
          <h2 class="font-semibold">Notifications</h2>
        </template>

        <div class="flex flex-col items-center justify-center py-8 text-gray-500">
          <UIcon name="i-lucide-bell" class="w-12 h-12 mb-4 text-gray-300" />
          <p class="text-sm">Notification settings coming soon</p>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <h2 class="font-semibold">About</h2>
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
