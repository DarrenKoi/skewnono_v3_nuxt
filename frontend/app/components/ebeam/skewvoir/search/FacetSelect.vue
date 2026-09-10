<template>
  <UPopover :content="{ align: 'start' }">
    <button
      type="button"
      :disabled="disabled"
      class="inline-flex h-7 items-center gap-1.5 rounded-(--sk-r-chip) border border-(--sk-border) bg-(--sk-surface) px-2.5 text-[12px] text-zinc-600 hover:bg-zinc-500/5 disabled:cursor-not-allowed disabled:opacity-50 dark:text-zinc-300"
      :class="{ 'border-(--sk-brand)': modelValue.length > 0 }"
    >
      <span class="text-(--sk-ink-muted)">{{ label }}:</span>
      <span class="font-medium text-zinc-800 dark:text-zinc-100">
        {{ summary }}
      </span>
      <UIcon
        name="i-lucide-chevron-down"
        class="h-3 w-3 opacity-50"
      />
    </button>

    <template #content>
      <div class="w-64 p-2">
        <UInput
          v-if="searchable"
          v-model="filterText"
          size="xs"
          icon="i-lucide-search"
          placeholder="검색"
          class="mb-1.5 w-full"
        />
        <p
          v-if="!visibleOptions.length"
          class="px-2 py-3 sk-body"
        >
          값이 없습니다.
        </p>
        <ul
          v-else
          class="max-h-64 space-y-0.5 overflow-y-auto"
        >
          <li
            v-for="opt in visibleOptions"
            :key="opt.value"
            class="flex items-center gap-2 rounded-(--sk-r-nav) px-2 py-1 hover:bg-zinc-500/10"
          >
            <UCheckbox
              :model-value="modelValue.includes(opt.value)"
              @update:model-value="toggle(opt.value)"
            />
            <button
              type="button"
              class="flex min-w-0 flex-1 items-baseline justify-between gap-2 text-left"
              @click="toggle(opt.value)"
            >
              <span class="truncate font-mono text-xs text-zinc-700 dark:text-zinc-200">{{ opt.value }}</span>
              <span class="shrink-0 font-mono text-xs text-(--sk-ink-subtle)">{{ opt.count }}</span>
            </button>
          </li>
        </ul>
        <div
          v-if="modelValue.length"
          class="mt-1.5 border-t border-(--sk-border-soft) pt-1.5"
        >
          <UButton
            color="neutral"
            variant="ghost"
            size="xs"
            label="선택 해제"
            block
            @click="emit('update:modelValue', [])"
          />
        </div>
      </div>
    </template>
  </UPopover>
</template>

<script setup lang="ts">
import type { MeasHistFacetValue } from '~/composables/useMeasHistApi'

const props = defineProps<{
  label: string
  options: MeasHistFacetValue[]
  modelValue: string[]
  // EQ lists run to hundreds in the office index — type to narrow. (There is
  // no RECIPE facet: recipes are found via the search bar only, see §6.3.)
  searchable?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const filterText = ref('')

const visibleOptions = computed(() => {
  const needle = filterText.value.trim().toLowerCase()
  if (!needle) return props.options
  return props.options.filter(o => o.value.toLowerCase().includes(needle))
})

const summary = computed(() => {
  if (!props.modelValue.length) return 'ALL'
  if (props.modelValue.length === 1) return props.modelValue[0]
  return `${props.modelValue.length}개`
})

const toggle = (value: string) => {
  const next = props.modelValue.includes(value)
    ? props.modelValue.filter(v => v !== value)
    : [...props.modelValue, value]
  emit('update:modelValue', next)
}
</script>
