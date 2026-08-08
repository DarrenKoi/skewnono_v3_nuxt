<template>
  <button
    type="button"
    :class="[
      'sk-chip',
      `sk-chip--${size}`,
      active ? `sk-chip--active sk-chip--${tone}` : 'sk-chip--rest',
      disabled ? 'sk-chip--disabled' : null
    ]"
    :aria-pressed="active"
    :aria-disabled="disabled || undefined"
    :disabled="disabled"
    @click="$emit('click', $event)"
  >
    <UIcon
      v-if="icon"
      :name="icon"
      class="sk-chip__icon"
    />
    <span><slot>{{ label }}</slot></span>
    <span
      v-if="count != null"
      class="sk-chip__count"
      :class="active && tone === 'ink' ? 'sk-count-on-ink' : null"
    >{{ count }}</span>
  </button>
</template>

<script setup lang="ts">
type Size = 'sm' | 'md'
type Tone = 'brand' | 'ink'

withDefaults(defineProps<{
  label?: string
  icon?: string
  count?: number | string | null
  active?: boolean
  disabled?: boolean
  size?: Size
  tone?: Tone
}>(), {
  size: 'md',
  tone: 'brand'
})

defineEmits<{ (e: 'click', payload: MouseEvent): void }>()
</script>

<style scoped>
.sk-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: var(--sk-r-chip);
  border: 1px solid var(--sk-border);
  font-family: inherit;
  font-weight: 500;
  letter-spacing: -0.003em;
  cursor: pointer;
  transition: background-color 0.12s ease, color 0.12s ease, border-color 0.12s ease;
  white-space: nowrap;
}

.sk-chip--sm { padding: 5px 9px; font-size: 12px; }
.sk-chip--md { padding: 7px 12px; font-size: 13px; }

.sk-chip--rest {
  background: var(--sk-surface);
  color: var(--sk-ink-muted);
}
.sk-chip--rest:hover {
  background: var(--sk-muted-surface);
  color: var(--sk-ink);
}

.sk-chip--active {
  font-weight: 600;
}
.sk-chip--active.sk-chip--brand {
  background: var(--sk-brand);
  color: var(--sk-brand-fg);
  border-color: var(--sk-brand);
}
.sk-chip--active.sk-chip--ink {
  background: var(--sk-ink);
  color: var(--sk-ink-fg);
  border-color: var(--sk-ink);
}

.sk-chip--disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.sk-chip__icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

/* 12px, not 10px: this badge holds a NUMBER the reader is meant to read — a
   tool count, a zero-family size, a coverage fraction — and DESIGN.md's floor is
   that a data value never renders below 12px. 10px is reserved for mono
   uppercase eyebrows, which this is not. */
.sk-chip__count {
  font-size: 12px;
  font-weight: 600;
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--sk-muted-surface);
  color: var(--sk-ink-subtle);
  font-variant-numeric: tabular-nums;
}
/* The BRAND fill only. `--sk-brand` is dark in both themes, so its count keeps
   a near-white foreground that must NOT invert — which is exactly why this
   cannot be folded into the shared rule below. */
.sk-chip--active.sk-chip--brand .sk-chip__count {
  background: rgba(255, 255, 255, 0.18);
  color: rgba(255, 237, 223, 0.95);
}

/* The INK fill inverts with the theme (near-black in light, cream in dark), so
   a fixed near-white count is legible in light mode and invisible in dark.
   The fix is `.sk-count-on-ink` (main.css), applied in the template and shared
   with SkNavPill: both colours derive from `--sk-ink-fg`, which inverts along
   with the fill. It replaced a hand-resolved `rgba(21, 17, 13, …)` — dark
   mode's token value written out by hand — that lived in a `.dark` override
   here and, byte-for-byte, in NavPill.vue. */
</style>
