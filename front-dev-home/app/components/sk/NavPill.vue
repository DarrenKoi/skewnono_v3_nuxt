<template>
  <component
    :is="resolvedTag"
    v-bind="rootAttrs"
    :class="[
      'sk-nav-pill',
      `sk-nav-pill--${size}`,
      active ? 'sk-nav-pill--active' : 'sk-nav-pill--rest',
      disabled ? 'sk-nav-pill--disabled' : null
    ]"
    :aria-pressed="ariaPressed"
    :aria-disabled="disabled || undefined"
    :aria-current="to && active ? 'page' : undefined"
  >
    <UIcon
      v-if="icon"
      :name="icon"
      class="sk-nav-pill__icon"
    />
    <span
      class="sk-nav-pill__label"
      :class="labelClass"
    ><slot>{{ label }}</slot></span>
    <span
      v-if="count != null"
      class="sk-nav-pill__count"
      :class="countTone === 'brand' ? 'sk-nav-pill__count--brand' : null"
    >{{ count }}</span>
    <UIcon
      v-if="trailingIcon"
      :name="trailingIcon"
      class="sk-nav-pill__trailing"
    />
  </component>
</template>

<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'

type Size = 'sm' | 'md' | 'lg'

const props = withDefaults(defineProps<{
  label?: string
  icon?: string
  trailingIcon?: string
  count?: number | string | null
  countTone?: 'neutral' | 'brand'
  active?: boolean
  disabled?: boolean
  size?: Size
  to?: RouteLocationRaw
  ariaLabel?: string
  labelClass?: string
}>(), {
  size: 'md',
  countTone: 'neutral'
})

const emit = defineEmits<{ (e: 'click', payload: MouseEvent): void }>()

const NuxtLink = resolveComponent('NuxtLink')

const resolvedTag = computed(() => {
  if (props.disabled || !props.to) return 'button'
  return NuxtLink
})

const rootAttrs = computed(() => {
  const base: Record<string, unknown> = {
    'aria-label': props.ariaLabel,
    'onClick': (event: MouseEvent) => emit('click', event)
  }

  if (resolvedTag.value === 'button') {
    base.type = 'button'
    if (props.disabled) base.disabled = true
  } else {
    base.to = props.to
  }

  return base
})

const ariaPressed = computed(() => {
  if (props.to) return undefined
  if (props.disabled) return undefined
  return props.active
})
</script>

<style scoped>
.sk-nav-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  border-radius: var(--sk-r-nav);
  border: 1px solid var(--sk-border);
  font-family: inherit;
  font-weight: 500;
  letter-spacing: -0.005em;
  cursor: pointer;
  transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  white-space: nowrap;
  text-decoration: none;
}

.sk-nav-pill--sm { padding: 6px 12px; font-size: 13px; }
.sk-nav-pill--md { padding: 9px 16px; font-size: 14px; }
.sk-nav-pill--lg { padding: 11px 22px; font-size: 15px; }

.sk-nav-pill--rest {
  background: transparent;
  color: var(--sk-ink-muted);
}
.sk-nav-pill--rest:hover {
  background: var(--sk-muted-surface);
  color: var(--sk-ink);
  border-color: var(--sk-border);
}

.sk-nav-pill--active {
  background: var(--sk-ink);
  color: var(--sk-ink-fg);
  border-color: var(--sk-ink);
  font-weight: 600;
}

.sk-nav-pill--disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.sk-nav-pill--disabled:hover {
  background: transparent;
  color: var(--sk-ink-muted);
}

.sk-nav-pill__icon,
.sk-nav-pill__trailing {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.sk-nav-pill__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 18px;
  padding: 0 6px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 5px;
  background: var(--sk-border-soft);
  color: var(--sk-ink-subtle);
  font-variant-numeric: tabular-nums;
}

.sk-nav-pill--active .sk-nav-pill__count {
  background: rgba(255, 255, 255, 0.14);
  color: rgba(232, 225, 210, 0.95);
}
.dark .sk-nav-pill--active .sk-nav-pill__count {
  background: rgba(21, 17, 13, 0.18);
  color: rgba(21, 17, 13, 0.9);
}

.sk-nav-pill__count--brand {
  background: var(--sk-brand-soft);
  color: var(--sk-brand-ink);
}
</style>
