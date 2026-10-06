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
          <!-- A value wraps instead of clipping (Data Save Location is a long
               path), and a click copies it whole. -->
          <dd class="min-w-0">
            <button
              type="button"
              class="cursor-pointer break-all rounded-sm text-right sk-value-num transition-colors duration-200 hover:bg-(--sk-muted-surface)"
              :title="`${key} 복사`"
              @click="copy(key, value)"
            >
              {{ shown(key, value) }}
            </button>
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

const toast = useToast()
const copy = async (key: string, value: unknown) => {
  const copied = await copyTextToClipboard(shown(key, value))
  toast.add(copied
    ? { title: `${key} 값을 복사했습니다`, icon: 'i-lucide-clipboard-check', color: 'success' }
    : { title: '복사하지 못했습니다', icon: 'i-lucide-triangle-alert', color: 'warning' })
}

// A Tip Width that is stated but is not a number (the office's 'NaN') reads
// 측정 없음, by the same rule the trend page counts it with.
const shown = (key: string, value: unknown) =>
  key === 'Tip Width' && text(value) !== '–' && tipWidthOf(props.information) === null ? '측정 없음' : text(value)

const text = (value: unknown) => value === null || value === undefined || value === '' ? '–' : String(value)
</script>
