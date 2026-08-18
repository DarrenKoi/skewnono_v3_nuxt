<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-6 py-12 text-center">
    <UIcon
      :name="icon"
      class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
    />
    <p class="mt-2 sk-body">
      {{ title }}
    </p>
    <p
      v-if="description"
      class="mt-1 sk-meta"
    >
      {{ description }}
    </p>
    <p
      v-if="hint"
      class="mt-1.5 sk-field-label"
    >
      {{ hint }}
    </p>
  </div>
</template>

<script setup lang="ts">
// "The query succeeded and matched nothing" — the sibling of AppLoadingState,
// with the same block-card geometry so a panel does not shift as it moves from
// loading to empty. Three views had byte-identical copies of this markup
// (전체 요약, and the two 장비별 views that reuse it per the by-equipment specs
// §3.3); the wording differs per view, the shell must not.
//
// `hint` is the third line the two lab pages needed: `description` carries the
// server's own account of WHY there is nothing, and the hint says what the user
// can do about it. They were about to be a fourth and fifth byte-identical copy
// of this shell — the thing this component's existence is meant to prevent.
//
// The radius is stated because `.dashboard-surface` carries none of its own —
// a plain div here would render square corners while the UCards beside it stay
// rounded.
withDefaults(
  defineProps<{
    title: string
    description?: string
    hint?: string
    icon?: string
  }>(),
  { description: undefined, hint: undefined, icon: 'i-lucide-inbox' }
)
</script>
