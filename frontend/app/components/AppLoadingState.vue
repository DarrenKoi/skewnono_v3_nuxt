<template>
  <div
    :class="variant === 'inline'
      ? 'flex items-center justify-center gap-2 px-4 py-12 sk-body'
      : 'dashboard-surface rounded-2xl px-6 py-12'"
    role="status"
    aria-live="polite"
  >
    <template v-if="variant === 'inline'">
      <UIcon
        name="i-lucide-loader-circle"
        class="h-4 w-4 shrink-0 animate-spin text-(--sk-ink-muted)"
      />
      {{ title }}
    </template>

    <div
      v-else
      class="mx-auto max-w-md"
    >
      <UProgress
        animation="carousel"
        size="sm"
      />
      <p class="mt-4 text-center sk-body">
        {{ title }}
      </p>
      <p
        v-if="description"
        class="mt-1 text-center sk-meta"
      >
        {{ description }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
// `block` (default) owns its own card surface — use it where the loading state
// stands in for a whole panel that has not rendered yet. `inline` is a single
// centered row meant to sit *inside* an existing UCard body, where a second
// dashboard-surface would nest a card in a card; it drops `description`
// because there is no room for a second line in that slot.
withDefaults(
  defineProps<{
    title: string
    description?: string
    variant?: 'block' | 'inline'
  }>(),
  { description: undefined, variant: 'block' }
)
</script>
