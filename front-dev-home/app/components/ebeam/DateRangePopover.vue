<template>
  <UPopover :content="{ align: 'start' }">
    <UButton
      :icon="icon"
      color="neutral"
      variant="outline"
      size="sm"
      :class="['font-medium tabular-nums', triggerClass]"
    >
      <span>{{ startLabel }}</span>
      <span class="text-(--sk-ink-subtle)">~</span>
      <span>{{ endLabel }}</span>
    </UButton>

    <template #content>
      <div class="flex flex-col gap-3 p-3 sm:flex-row">
        <div class="flex flex-row gap-1 sm:flex-col sm:min-w-[120px]">
          <UButton
            v-for="preset in presets"
            :key="preset.label"
            size="xs"
            variant="ghost"
            color="neutral"
            class="justify-start"
            @click="applyPreset(preset.days)"
          >
            {{ preset.label }}
          </UButton>
        </div>
        <div class="border-l border-zinc-200 dark:border-zinc-800 hidden sm:block" />
        <UCalendar
          v-model="range"
          range
          :number-of-months="2"
          :max-value="anchorValue"
          :placeholder="anchorValue"
          size="sm"
        />
      </div>
    </template>
  </UPopover>
</template>

<script setup lang="ts">
import { CalendarDate, getLocalTimeZone, today } from '@internationalized/date'
import type { DateValue } from '@internationalized/date'

// ModelValue is a pair of ISO YYYY-MM-DD strings.
interface ModelValue {
  start: string
  end: string
}

const props = defineProps<{
  modelValue: ModelValue
  icon?: string
  // Extra classes merged onto the trigger button — lets a caller enlarge the
  // hit target (e.g. match a page's h-9 toggle row) without changing the
  // shared default sizing used by other pages.
  triggerClass?: string
  // Optional ISO YYYY-MM-DD anchor. When provided, presets ("Last 7 days",
  // etc.) and the calendar's max-value resolve relative to this date instead
  // of wall-clock today. Used by callers tied to mock data with a fixed
  // ceiling — without it presets land outside the data window.
  anchorDate?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: ModelValue]
}>()

const icon = computed(() => props.icon ?? 'i-lucide-calendar-range')
const tz = getLocalTimeZone()
const wallToday = computed(() => today(tz))

const parseIsoToCalendarDate = (iso: string): CalendarDate => {
  const [y, m, d] = iso.split('-').map(Number)
  return new CalendarDate(y || wallToday.value.year, m || 1, d || 1)
}

const anchorValue = computed(() => {
  if (props.anchorDate) return parseIsoToCalendarDate(props.anchorDate)
  return wallToday.value
})

const formatCalendarDate = (value: DateValue): string => {
  const y = value.year.toString().padStart(4, '0')
  const m = value.month.toString().padStart(2, '0')
  const d = value.day.toString().padStart(2, '0')
  return `${y}-${m}-${d}`
}

// Bridge ISO string ModelValue <-> DateRange used by UCalendar.
const range = computed({
  get: () => ({
    start: parseIsoToCalendarDate(props.modelValue.start),
    end: parseIsoToCalendarDate(props.modelValue.end)
  }),
  set: (value) => {
    if (!value?.start || !value?.end) return
    emit('update:modelValue', {
      start: formatCalendarDate(value.start),
      end: formatCalendarDate(value.end)
    })
  }
})

const startLabel = computed(() => props.modelValue.start || '----/--/--')
const endLabel = computed(() => props.modelValue.end || '----/--/--')

const presets = [
  { label: 'Today', days: 0 },
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 90 days', days: 90 }
]

const applyPreset = (days: number) => {
  const end = anchorValue.value
  const start = days === 0 ? end : end.subtract({ days })
  emit('update:modelValue', {
    start: formatCalendarDate(start),
    end: formatCalendarDate(end)
  })
}
</script>
