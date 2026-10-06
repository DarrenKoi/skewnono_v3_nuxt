<template>
  <AfmCard
    icon="i-lucide-info"
    title="측정 정보"
  >
    <div class="space-y-3">
      <div>
        <p class="sk-label">
          Recipe ID
        </p>
        <p class="break-all font-mono text-base font-bold tracking-tight text-(--sk-ink)">
          {{ text(information['Recipe ID']) }}
        </p>
      </div>
      <AfmLotSlotTags
        :lot-id="text(information['Lot ID'])"
        :slot-number="slotNumber"
      />
      <dl class="space-y-1.5">
        <div
          v-for="[key, value] in rest"
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
    </div>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmInformation } from '~/composables/useAfmDetailApi'

const props = defineProps<{
  information: AfmInformation
  slotNumber?: string | number | null
}>()

// The Info section comes in two layouts (13 and 15 keys). Only keys both carry
// are named here, for the headline; everything else is listed as it arrives.
const HEADLINE = ['Recipe ID', 'Lot ID']
const rest = computed(() => Object.entries(props.information).filter(([key]) => !HEADLINE.includes(key)))

const text = (value: unknown) => value === null || value === undefined || value === '' ? '–' : String(value)
</script>
