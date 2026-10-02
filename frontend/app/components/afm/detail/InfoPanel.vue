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
      <div class="flex flex-wrap items-center gap-1.5">
        <AfmLotSlotTags
          :lot-id="text(information['Lot ID'])"
          :slot-number="slotNumber"
        />
        <UBadge
          v-if="information.Measurement"
          :label="String(information.Measurement)"
          color="neutral"
          variant="outline"
        />
      </div>
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
  // Known only when the measurement was opened from the list.
  slotNumber?: string | number | null
}>()

// The three keys the header already shows are left out of the list below it.
const HEADLINE = ['Recipe ID', 'Lot ID', 'Measurement']
const rest = computed(() => Object.entries(props.information).filter(([key]) => !HEADLINE.includes(key)))

const text = (value: unknown) => value === null || value === undefined || value === '' ? '–' : String(value)
</script>
