<template>
  <section class="dashboard-surface rounded-2xl">
    <header class="flex items-center justify-between border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
      <div class="flex items-center gap-2">
        <UIcon name="i-lucide-layers" class="h-4 w-4 text-zinc-500" />
        <h3 class="text-sm font-semibold">
          Data Grouping
        </h3>
        <UBadge :label="String(items.length)" color="primary" size="xs" variant="subtle" />
      </div>
      <UButton
        v-if="items.length > 0"
        size="xs"
        color="neutral"
        variant="ghost"
        @click="$emit('clear')"
      >
        Clear All
      </UButton>
    </header>

    <ul
      v-if="items.length > 0"
      class="divide-y divide-zinc-200 dark:divide-zinc-800"
    >
      <li
        v-for="item in sortedItems"
        :key="item.filename"
        class="group flex items-start gap-2 px-4 py-2.5"
      >
        <div class="min-w-0 flex-1">
          <p class="truncate text-xs font-medium">
            {{ item.formattedDate }} • {{ item.recipeName }} • {{ item.lotId }}
          </p>
          <p class="truncate text-[11px] text-zinc-500">
            Slot {{ item.slotNumber }} · {{ item.measuredInfo }}
          </p>
        </div>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          aria-label="Remove from group"
          class="opacity-0 transition group-hover:opacity-100"
          @click="$emit('remove', item.filename)"
        />
      </li>
    </ul>
    <p
      v-else
      class="px-4 py-6 text-center text-xs text-zinc-500"
    >
      No grouped data yet
    </p>

    <footer
      v-if="items.length > 0"
      class="flex flex-wrap items-center gap-2 border-t border-zinc-200 px-4 py-3 dark:border-zinc-800"
    >
      <UTooltip text="Trend analysis page is not yet ported">
        <span class="inline-flex">
          <UButton
            size="xs"
            color="primary"
            variant="solid"
            icon="i-lucide-line-chart"
            disabled
            class="pointer-events-none"
          >
            See Together
          </UButton>
        </span>
      </UTooltip>
      <UButton
        v-if="items.length > 1"
        size="xs"
        color="neutral"
        variant="outline"
        icon="i-lucide-save"
        @click="openSaveDialog"
      >
        Save Group
      </UButton>
    </footer>

    <UModal v-model:open="showSaveDialog">
      <template #content>
        <div class="space-y-4 p-6">
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-save" class="h-5 w-5 text-primary-500" />
            <h3 class="text-base font-semibold">
              Save Data Group
            </h3>
          </div>

          <UFormField label="Group name" required>
            <UInput
              v-model="groupName"
              placeholder="Enter a name for this group"
              maxlength="50"
              autofocus
            />
          </UFormField>

          <UFormField label="Description">
            <UTextarea
              v-model="groupDescription"
              placeholder="Optional description"
              :rows="3"
              maxlength="200"
            />
          </UFormField>

          <div class="rounded-lg bg-zinc-100 px-3 py-2 text-xs text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
            <strong>Group contains:</strong> {{ items.length }} measurements
          </div>

          <div class="flex justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              @click="closeSaveDialog"
            >
              Cancel
            </UButton>
            <UButton
              color="primary"
              variant="solid"
              icon="i-lucide-save"
              :disabled="!groupName.trim()"
              @click="confirmSave"
            >
              Save Group
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </section>
</template>

<script setup lang="ts">
import type { AfmGroupedEntry } from '~/composables/useAfmCart'

const props = defineProps<{
  items: AfmGroupedEntry[]
}>()

const emit = defineEmits<{
  (event: 'remove', filename: string): void
  (event: 'clear'): void
  (event: 'save', payload: { name: string, description: string }): void
}>()

const sortedItems = computed(() =>
  [...props.items].sort((a, b) => b.addedAt.localeCompare(a.addedAt))
)

const showSaveDialog = ref(false)
const groupName = ref('')
const groupDescription = ref('')

const openSaveDialog = () => {
  const stamp = new Date()
  const dateStr = stamp.toLocaleDateString()
  const timeStr = stamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  groupName.value = `Group ${dateStr} ${timeStr}`
  groupDescription.value = ''
  showSaveDialog.value = true
}

const closeSaveDialog = () => {
  showSaveDialog.value = false
  groupName.value = ''
  groupDescription.value = ''
}

const confirmSave = () => {
  if (!groupName.value.trim()) return
  emit('save', { name: groupName.value.trim(), description: groupDescription.value.trim() })
  closeSaveDialog()
}
</script>
