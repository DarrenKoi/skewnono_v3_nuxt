<script setup lang="ts">
const { selectedTheme, resolvedThemeName, themeOptions } = useEchartsTheme()

const appliedLabel = computed(() => {
  const option = themeOptions.find(item => item.value === resolvedThemeName.value)
  return option?.label ?? resolvedThemeName.value
})

const selectedLabel = computed(() =>
  themeOptions.find(option => option.value === selectedTheme.value)?.label ?? 'Default'
)
</script>

<template>
  <section class="space-y-3">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div class="min-w-0">
        <p class="font-medium text-zinc-900 dark:text-zinc-100">
          ECharts theme
        </p>
        <p class="text-sm text-(--sk-ink-muted)">
          대시보드 차트에 사용할 색상과 모양을 선택하세요.
        </p>
      </div>
      <div class="inline-flex items-center gap-2 self-start rounded-md bg-zinc-100 px-2.5 py-1 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
        <UIcon
          name="i-lucide-palette"
          class="h-3.5 w-3.5"
        />
        <span class="whitespace-nowrap">적용 중: {{ appliedLabel }}</span>
      </div>
    </div>

    <div
      role="radiogroup"
      aria-label="ECharts theme"
      class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
    >
      <button
        v-for="option in themeOptions"
        :key="option.value"
        type="button"
        role="radio"
        :aria-checked="selectedTheme === option.value"
        class="group flex min-h-[12rem] flex-col overflow-hidden rounded-lg border bg-white text-left shadow-sm transition dark:bg-zinc-950"
        :class="selectedTheme === option.value
          ? 'border-(--sk-accent) ring-2 ring-(--sk-accent)/25'
          : 'border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700'"
        @click="selectedTheme = option.value"
      >
        <div
          class="relative h-24 border-b border-black/5 px-4 py-3 dark:border-white/10"
          :style="{ backgroundColor: option.backgroundColor, color: option.textColor }"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold">
                {{ option.label }}
              </p>
              <p class="mt-0.5 truncate font-mono text-[10px] opacity-70">
                {{ option.fileName }}
              </p>
            </div>
            <UIcon
              v-if="selectedTheme === option.value"
              name="i-lucide-check"
              class="h-4 w-4 shrink-0"
            />
          </div>

          <div class="absolute inset-x-4 bottom-3 flex items-end gap-1.5">
            <span
              v-for="(color, index) in option.colors.slice(0, 5)"
              :key="`${option.value}-${color}`"
              class="w-full rounded-sm"
              :style="{
                height: `${18 + (index % 3) * 9}px`,
                backgroundColor: color
              }"
            />
          </div>
        </div>

        <div class="flex flex-1 flex-col gap-3 p-3.5">
          <p class="text-sm leading-5 text-zinc-600 dark:text-zinc-300">
            {{ option.description }}
          </p>
          <div class="mt-auto flex items-center gap-1.5">
            <span
              v-for="color in option.colors"
              :key="`${option.value}-swatch-${color}`"
              class="h-4 w-4 rounded-full ring-1 ring-black/10 dark:ring-white/20"
              :style="{ backgroundColor: color }"
            />
          </div>
        </div>
      </button>
    </div>

    <p class="sk-meta">
      선택한 테마: {{ selectedLabel }}. 이 설정은 이 브라우저에 저장됩니다.
    </p>
  </section>
</template>
