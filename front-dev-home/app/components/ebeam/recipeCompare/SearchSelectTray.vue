<template>
  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="translate-y-4 opacity-0"
    leave-active-class="transition duration-150 ease-in"
    leave-to-class="translate-y-4 opacity-0"
  >
    <div
      v-if="selected.length"
      class="fixed inset-x-0 bottom-4 z-40 mx-auto w-full max-w-[1100px] px-4"
    >
      <div class="dashboard-surface flex flex-col gap-3 rounded-2xl border border-(--sk-brand)/40 p-3 shadow-lg sm:flex-row sm:items-center">
        <div class="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
          <span class="flex shrink-0 items-center gap-1 text-[11px] font-semibold text-(--sk-brand)">
            <UIcon
              name="i-lucide-shopping-basket"
              class="h-3.5 w-3.5"
            />
            작업 세트 · {{ selected.length }}
          </span>
          <span
            v-for="name in selected"
            :key="name"
            class="inline-flex max-w-[220px] items-center gap-1 rounded-[var(--sk-r-chip)] bg-(--sk-brand-soft)/60 py-1 pl-2.5 pr-1 font-mono text-[10.5px] text-(--sk-ink)"
          >
            <span class="truncate">{{ name }}</span>
            <button
              type="button"
              class="rounded-md p-0.5 text-(--sk-ink-muted) transition hover:bg-zinc-300 hover:text-(--sk-ink) dark:hover:bg-zinc-600"
              :aria-label="`Remove ${name}`"
              @click="emit('remove', name)"
            >
              <UIcon
                name="i-lucide-x"
                class="h-3 w-3"
              />
            </button>
          </span>
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-trash-2"
            label="선택 비우기"
            @click="emit('clear')"
          />
        </div>

        <div class="flex shrink-0 flex-wrap items-center gap-2">
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-file-search"
            label="열어보기"
            @click="emit('open')"
          />
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-network"
            label="횡전개"
            @click="emit('lateral')"
          />
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-history"
            label="측정이력"
            @click="emit('measHist')"
          />
          <UButton
            size="sm"
            color="primary"
            variant="solid"
            icon="i-lucide-scale"
            label="비교하기"
            @click="emit('compare')"
          />
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
defineProps<{
  selected: string[]
}>()

const emit = defineEmits<{
  remove: [name: string]
  clear: []
  open: []
  lateral: []
  measHist: []
  compare: []
}>()
</script>
