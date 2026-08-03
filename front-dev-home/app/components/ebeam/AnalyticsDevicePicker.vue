<template>
  <div class="dashboard-surface rounded-(--sk-r-card) px-3.5 py-2.5">
    <div class="mb-2 flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <h3 class="sk-title">
          디바이스 선택
        </h3>
        <span class="sk-meta">
          {{ filteredDevices.length }} / {{ devices.length }}개의 디바이스
        </span>
      </div>
      <UButton
        size="xs"
        color="neutral"
        variant="ghost"
        icon="i-lucide-rotate-ccw"
        label="초기화"
        :disabled="!selectedLot && !lotSearch && selectedCategories.length === 0"
        @click="reset"
      />
    </div>

    <div
      v-if="categoryField && categoryOptions.length"
      class="mb-6 flex min-w-0 flex-wrap items-start gap-2 border-b border-(--sk-border-soft) pb-4"
    >
      <span class="mt-1.5 shrink-0 font-mono text-[10px] text-(--sk-ink-muted)">{{ categoryField }}</span>
      <div class="flex min-w-0 flex-wrap items-center gap-1">
        <button
          v-for="category in categoryOptions"
          :key="category"
          type="button"
          class="inline-flex h-6 items-center gap-1 rounded-md px-2 text-[11px] font-medium ring-1 transition-colors"
          :class="chipClass(selectedCategories.includes(category))"
          @click="toggleCategory(category)"
        >
          {{ category }}
        </button>
      </div>
    </div>

    <div class="flex min-w-0 flex-wrap items-start gap-x-3 gap-y-2">
      <span class="mt-1.5 shrink-0 font-mono text-[10px] text-(--sk-ink-muted)">lot_cd</span>
      <UInput
        v-model="lotSearch"
        class="w-44 shrink-0"
        size="xs"
        color="neutral"
        variant="subtle"
        icon="i-lucide-search"
        placeholder="디바이스 검색"
      />
      <div class="flex max-h-28 min-w-0 flex-1 flex-wrap items-center gap-1.5 overflow-y-auto border-l border-(--sk-border-soft) pl-3">
        <button
          v-for="device in chipStrip"
          :key="device.lot_cd"
          type="button"
          class="inline-flex h-7 shrink-0 items-center gap-1 rounded-md px-2 font-mono text-[11px] font-medium ring-1 transition-colors"
          :class="chipClass(selectedLot === device.lot_cd)"
          :title="getTitle?.(device)"
          @click="toggleLot(device.lot_cd)"
        >
          {{ device.lot_cd }}
        </button>
        <span
          v-if="!devices.length"
          class="text-[11px] text-(--sk-ink-muted)"
        >
          {{ emptyMessage }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts" generic="T extends AnalyticsDevice">
import { chipClass } from '~/utils/chipClass'

export interface AnalyticsDevice {
  lot_cd: string
  exec_count: number
  prod_catg_cd: string | null
  tech_nm: string | null
}

const props = withDefaults(defineProps<{
  devices: readonly T[]
  getTitle?: (device: T) => string
  emptyMessage?: string
  resetKey?: unknown
}>(), {
  getTitle: undefined,
  emptyMessage: '이 기간에 측정된 디바이스가 없습니다.'
})

const selectedLot = defineModel<string | null>('selectedLot', { required: true })
const lotSearch = ref('')
const selectedCategories = ref<string[]>([])

const categoryField = computed<'prod_catg_cd' | 'tech_nm' | null>(() => {
  if (props.devices.some(device => device.prod_catg_cd)) return 'prod_catg_cd'
  if (props.devices.some(device => device.tech_nm)) return 'tech_nm'
  return null
})

const categoryOptions = computed(() => {
  const field = categoryField.value
  if (!field) return []
  return [...new Set(
    props.devices
      .map(device => device[field])
      .filter((value): value is string => Boolean(value))
  )].sort()
})

const filteredDevices = computed(() => {
  const field = categoryField.value
  if (!field || selectedCategories.value.length === 0) return props.devices
  const allowed = new Set(selectedCategories.value)
  return props.devices.filter((device) => {
    const value = device[field]
    return value !== null && allowed.has(value)
  })
})

const chipStrip = computed(() => {
  const query = lotSearch.value.trim().toLowerCase()
  const matches = query
    ? filteredDevices.value.filter(device => device.lot_cd.toLowerCase().includes(query))
    : filteredDevices.value

  if (!selectedLot.value || matches.some(device => device.lot_cd === selectedLot.value)) {
    return matches
  }

  const selected = props.devices.find(device => device.lot_cd === selectedLot.value)
  return selected ? [selected, ...matches] : matches
})

const toggleLot = (lot: string) => {
  selectedLot.value = selectedLot.value === lot ? null : lot
}

const toggleCategory = (category: string) => {
  selectedCategories.value = selectedCategories.value.includes(category)
    ? selectedCategories.value.filter(value => value !== category)
    : [...selectedCategories.value, category]
}

const reset = () => {
  selectedLot.value = null
  lotSearch.value = ''
  selectedCategories.value = []
}

watch(() => props.resetKey, reset)
</script>
