<template>
  <UCard
    class="dashboard-surface flex flex-col"
    :ui="{
      header: 'px-4 py-3 sm:px-4',
      body: flush ? 'flex-1 p-0 sm:p-0' : 'flex-1 p-4 sm:p-4',
      footer: 'px-4 py-3 sm:px-4'
    }"
  >
    <template #header>
      <div class="flex min-h-8 flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <div class="flex min-w-0 items-center gap-2">
          <UIcon
            :name="icon"
            class="size-[18px] shrink-0 text-(--sk-ink-muted)"
          />
          <h2 class="whitespace-nowrap sk-panel-title">
            {{ title }}
          </h2>
          <UBadge
            v-if="count != null"
            :label="String(count)"
            color="neutral"
            variant="subtle"
            class="font-mono tabular-nums"
          />
          <!-- The subject this card is computed for (a point, a site), so a card
               far from its picker still names what it shows. -->
          <span
            v-if="subject"
            class="sk-badge min-w-0 truncate border border-(--sk-border) bg-(--sk-muted-surface) text-(--sk-ink)"
            :title="subject"
          >
            {{ subject }}
          </span>
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
// The one card shell on the AFM pages: icon + title (+ count badge, + the subject
// it is computed for) on the left, actions on the right. `flush` drops the body
// padding for lists and tables that run edge to edge. The root is a flex column
// so cards sharing a grid row stretch to one height.
defineProps<{
  icon: string
  title: string
  count?: number
  subject?: string
  flush?: boolean
}>()
</script>
