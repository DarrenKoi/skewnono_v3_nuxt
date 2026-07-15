<script setup lang="ts">
const colorMode = useColorMode()

const colorModeOptions = [
  {
    value: 'light',
    label: 'Light',
    description: 'A bright interface for daytime use.',
    icon: 'i-lucide-sun'
  },
  {
    value: 'dark',
    label: 'Dark',
    description: 'A low-light interface that is easy on the eyes.',
    icon: 'i-lucide-moon'
  },
  {
    value: 'system',
    label: 'System',
    description: 'Automatically match your device appearance.',
    icon: 'i-lucide-monitor'
  }
] as const

const selectedLabel = computed(() =>
  colorModeOptions.find(option => option.value === colorMode.preference)?.label ?? 'System'
)

const resolvedLabel = computed(() => colorMode.value === 'dark' ? 'Dark' : 'Light')
</script>

<template>
  <section class="space-y-3">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div class="min-w-0">
        <p class="font-medium text-zinc-900 dark:text-zinc-100">
          App color mode
        </p>
        <p class="text-sm text-(--sk-ink-muted)">
          Choose how the interface should look on this device.
        </p>
      </div>
      <div class="inline-flex items-center gap-2 self-start rounded-md bg-zinc-100 px-2.5 py-1 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
        <UIcon
          name="i-lucide-circle-half"
          class="h-3.5 w-3.5"
        />
        <span class="whitespace-nowrap">Applied: {{ resolvedLabel }}</span>
      </div>
    </div>

    <div
      role="radiogroup"
      aria-label="App color mode"
      class="grid gap-3 sm:grid-cols-3"
    >
      <button
        v-for="option in colorModeOptions"
        :key="option.value"
        type="button"
        role="radio"
        :aria-checked="colorMode.preference === option.value"
        class="group overflow-hidden rounded-lg border bg-white text-left shadow-sm transition dark:bg-zinc-950"
        :class="colorMode.preference === option.value
          ? 'border-(--sk-accent) ring-2 ring-(--sk-accent)/25'
          : 'border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700'"
        @click="colorMode.preference = option.value"
      >
        <div class="h-20 border-b border-zinc-200 bg-zinc-100 p-3 dark:border-zinc-800 dark:bg-zinc-900">
          <div
            class="relative h-full overflow-hidden rounded-md border border-zinc-200 shadow-sm dark:border-zinc-700"
            :class="{
              'bg-white': option.value === 'light',
              'bg-zinc-950': option.value === 'dark',
              'bg-linear-to-r from-white from-50% to-zinc-950 to-50%': option.value === 'system'
            }"
          >
            <div
              class="absolute inset-x-2 top-2 h-1.5 rounded-full"
              :class="option.value === 'dark' ? 'bg-zinc-700' : option.value === 'light' ? 'bg-zinc-200' : 'bg-linear-to-r from-zinc-200 from-50% to-zinc-700 to-50%'"
            />
            <div
              class="absolute bottom-2 left-2 h-5 w-8 rounded-sm"
              :class="option.value === 'dark' ? 'bg-zinc-800' : 'bg-zinc-200'"
            />
            <div
              class="absolute right-2 bottom-2 h-5 w-10 rounded-sm"
              :class="option.value === 'light' ? 'bg-(--sk-accent)/20' : 'bg-(--sk-accent)/70'"
            />
          </div>
        </div>

        <div class="flex items-start gap-3 p-3.5">
          <UIcon
            :name="option.icon"
            class="mt-0.5 h-4 w-4 shrink-0 text-(--sk-ink-muted)"
          />
          <div class="min-w-0 flex-1">
            <div class="flex items-center justify-between gap-2">
              <span class="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                {{ option.label }}
              </span>
              <UIcon
                v-if="colorMode.preference === option.value"
                name="i-lucide-check"
                class="h-4 w-4 shrink-0 text-(--sk-accent)"
              />
            </div>
            <p class="mt-1 sk-meta">
              {{ option.description }}
            </p>
          </div>
        </div>
      </button>
    </div>

    <p class="sk-meta">
      Selected mode: {{ selectedLabel }}. The choice is saved in this browser.
    </p>
  </section>
</template>
