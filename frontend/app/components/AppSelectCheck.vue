<template>
  <span
    class="flex h-4 w-4 items-center justify-center rounded border"
    :class="checked
      ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
      : 'border-(--sk-border)'"
  >
    <UIcon
      v-if="checked"
      name="i-lucide-check"
      class="h-3 w-3"
    />
  </span>
</template>

<script setup lang="ts">
// The checkbox mark for a multi-select USelectMenu's `#item-leading` slot.
// Pair it with `:ui="{ itemTrailingIcon: 'hidden' }"` on the menu: the mark
// belongs right before the label, not in a far-right column separated from the
// text it applies to.
//
// Presentation only. Whether an item is checked stays with the caller's own
// store or composable — this component never sees the selection, only the
// answer for one row, so extracting it changed no selection behavior.
//
// Three copies (hardware/CompareToolPicker, hardware/ScePanel, the landing
// page's fab dropdown) existed until 2026-08-09, and the landing copy's own
// commit message cited the picker as its source — acknowledged duplication,
// not accident. They had already drifted: ScePanel's copy wrote
// `text-white dark:text-zinc-900` where the others take `--sk-ink-fg`, which
// is the same intent spelled in banned literals. One home, one answer.
defineProps<{ checked: boolean }>()
</script>
