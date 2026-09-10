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
      :class="countClass"
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

// A brand-toned count keeps its own palette. Otherwise, once the pill is
// active the count sits on the `--sk-ink` fill and takes the shared
// `.sk-count-on-ink` treatment (main.css) — the same rule SkChip's ink-toned
// count uses, so a retone of `--sk-ink-fg` reaches both.
const countClass = computed(() => {
  if (props.countTone === 'brand') return 'sk-nav-pill__count--brand'
  return props.active ? 'sk-count-on-ink' : null
})
</script>

<style scoped>
/* The pill's geometry and states live in main.css, not here: DESIGN.md
   describes `sk-nav-pill` as a ROLE CLASS, and a second consumer already
   needs it — skewvoir's Time-Series lens tabs, which cannot use this
   component (it hardcodes `aria-pressed`, invalid on `role="tab"`) but must
   not drift from its look. The parts below stay scoped because they are this
   component's internals; nothing outside renders them. */

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
  font-size: 12px;
  font-weight: 600;
  border-radius: 5px;
  background: var(--sk-border-soft);
  color: var(--sk-ink-subtle);
  font-variant-numeric: tabular-nums;
}

/* The active count's colours come from `.sk-count-on-ink` (main.css), applied
   in the template — one rule shared with SkChip, derived from `--sk-ink-fg` so
   it follows the theme instead of being written out per mode. */

.sk-nav-pill__count--brand {
  background: var(--sk-brand-soft);
  color: var(--sk-brand-ink);
}
</style>
