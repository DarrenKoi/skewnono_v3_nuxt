<template>
  <button
    :type="type"
    :class="[
      'sk-btn',
      `sk-btn--${size}`,
      `sk-btn--${kind}`,
      full ? 'sk-btn--full' : null,
      disabled ? 'sk-btn--disabled' : null
    ]"
    :disabled="disabled"
    :aria-label="ariaLabel"
    @click="$emit('click', $event)"
  >
    <UIcon
      v-if="icon"
      :name="icon"
      class="sk-btn__icon"
    />
    <span class="sk-btn__label"><slot>{{ label }}</slot></span>
    <UIcon
      v-if="trailingIcon"
      :name="trailingIcon"
      class="sk-btn__icon"
    />
  </button>
</template>

<script setup lang="ts">
type Size = 'sm' | 'md' | 'lg'
type Kind = 'primary' | 'secondary' | 'brand' | 'ghost'

withDefaults(defineProps<{
  label?: string
  icon?: string
  trailingIcon?: string
  ariaLabel?: string
  kind?: Kind
  size?: Size
  full?: boolean
  disabled?: boolean
  type?: 'button' | 'submit' | 'reset'
}>(), {
  kind: 'secondary',
  size: 'md',
  type: 'button'
})

defineEmits<{ (e: 'click', payload: MouseEvent): void }>()
</script>

<style scoped>
.sk-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border-radius: var(--sk-r-nav);
  border: 1px solid var(--sk-border);
  font-family: inherit;
  font-weight: 600;
  letter-spacing: -0.003em;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  white-space: nowrap;
}

.sk-btn--sm { padding: 6px 10px; font-size: 12px; }
.sk-btn--md { padding: 9px 14px; font-size: 13px; }
.sk-btn--lg { padding: 11px 18px; font-size: 14px; }
.sk-btn--full { width: 100%; }

.sk-btn--primary {
  background: var(--sk-ink);
  color: var(--sk-ink-fg);
  border-color: var(--sk-ink);
}
.sk-btn--secondary {
  background: var(--sk-surface);
  color: var(--sk-ink-muted);
}
.sk-btn--secondary:hover {
  color: var(--sk-ink);
  background: var(--sk-muted-surface);
}
.sk-btn--brand {
  background: var(--sk-brand);
  color: var(--sk-brand-fg);
  border-color: var(--sk-brand);
}
.sk-btn--ghost {
  background: transparent;
  color: var(--sk-ink-muted);
  border-color: transparent;
}
.sk-btn--ghost:hover {
  background: var(--sk-muted-surface);
  color: var(--sk-ink);
}

.sk-btn--disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.sk-btn__icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}
</style>
