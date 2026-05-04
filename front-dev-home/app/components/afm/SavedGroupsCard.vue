<template>
  <section class="dashboard-surface rounded-2xl">
    <header class="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
      <div class="flex items-center gap-2">
        <UIcon name="i-lucide-folder-open" class="h-4 w-4 text-zinc-500" />
        <h3 class="text-sm font-semibold">
          Saved Groups
        </h3>
        <UBadge :label="String(groups.length)" color="neutral" size="xs" variant="subtle" />
      </div>
      <UButton
        v-if="groups.length > 0"
        size="xs"
        color="neutral"
        variant="ghost"
        @click="$emit('clear')"
      >
        Clear All
      </UButton>
    </header>

    <ul
      v-if="groups.length > 0"
      class="divide-y divide-zinc-200 dark:divide-zinc-800"
    >
      <li
        v-for="group in groups"
        :key="group.id"
        class="group flex items-start gap-2 px-4 py-2.5"
      >
        <button
          type="button"
          class="min-w-0 flex-1 cursor-pointer text-left"
          @click="$emit('load', group.id)"
        >
          <p class="truncate text-xs font-semibold">
            {{ group.name }}
          </p>
          <p
            v-if="group.description"
            class="truncate text-[11px] text-zinc-500"
          >
            {{ group.description }}
          </p>
          <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-zinc-500">
            <span>{{ group.itemCount }} items</span>
            <span>•</span>
            <span>{{ formatDate(group.createdAt) }}</span>
            <UBadge
              v-for="tool in group.tools"
              :key="tool"
              :label="tool"
              size="xs"
              color="primary"
              variant="soft"
            />
          </div>
        </button>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          aria-label="Remove saved group"
          class="opacity-0 transition group-hover:opacity-100"
          @click="$emit('remove', group.id)"
        />
      </li>
    </ul>
    <p
      v-else
      class="px-4 py-6 text-center text-xs text-zinc-500"
    >
      No saved groups yet
    </p>
  </section>
</template>

<script setup lang="ts">
import type { AfmSavedGroup } from '~/composables/useAfmCart'

defineProps<{
  groups: AfmSavedGroup[]
}>()

defineEmits<{
  (event: 'load' | 'remove', groupId: string): void
  (event: 'clear'): void
}>()

const formatDate = (iso: string) => {
  try {
    return new Date(iso).toLocaleDateString()
  } catch {
    return iso
  }
}
</script>
