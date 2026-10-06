<template>
  <AfmCard
    icon="i-lucide-info"
    title="측정 정보"
  >
    <dl class="space-y-1.5">
      <div
        v-for="(value, key) in information"
        :key="key"
        class="flex items-baseline justify-between gap-3 border-b border-(--sk-border-soft) pb-1.5"
      >
        <dt class="whitespace-nowrap sk-label">
          {{ key }}
        </dt>
        <dd
          class="truncate text-right sk-value-num"
          :title="text(value)"
        >
          {{ text(value) }}
        </dd>
      </div>
    </dl>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmInformation } from '~/composables/useAfmDetailApi'

// No key is named here: the Info section comes in more than one layout, so the
// panel lists whatever keys the file has. (They arrive A–Z: Flask sorts JSON keys.)
defineProps<{ information: AfmInformation }>()

const text = (value: unknown) => value === null || value === undefined || value === '' ? '–' : String(value)
</script>
