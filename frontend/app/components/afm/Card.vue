<template>
  <UCard
    class="dashboard-surface"
    :ui="{
      header: 'px-4 py-3 sm:px-4',
      body: flush ? 'p-0 sm:p-0' : 'p-4 sm:p-4',
      footer: 'px-4 py-3 sm:px-4'
    }"
  >
    <template #header>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <UIcon
            :name="icon"
            class="size-4 text-(--sk-ink-muted)"
          />
          <h2 class="sk-title">
            {{ title }}
          </h2>
          <UBadge
            v-if="count != null"
            :label="String(count)"
            color="neutral"
            variant="subtle"
          />
        </div>
        <slot name="actions" />
      </div>
    </template>

    <slot />

    <template
      v-if="$slots.footer"
      #footer
    >
      <slot name="footer" />
    </template>
  </UCard>
</template>

<script setup lang="ts">
// The one card shell on the AFM pages: icon + title (+ count badge) on the left,
// actions on the right. `flush` drops the body padding for lists and tables that
// run edge to edge.
defineProps<{
  icon: string
  title: string
  count?: number
  flush?: boolean
}>()
</script>
