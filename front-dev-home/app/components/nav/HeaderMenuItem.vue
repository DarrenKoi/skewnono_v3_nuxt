<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'

// One row of a header menu (실험실 / 계정). Both menus share it so the two panels cannot
// drift apart in padding, radius or active treatment — the failure mode that turned the
// old icon row into eight slightly different buttons.
//
// Renders a link when it has a target and a button otherwise ('본인이 아닙니다' is an
// action, not a destination), which is why `to` is what picks the tag rather than a prop
// the caller has to remember to set.
withDefaults(defineProps<{
  label: string
  icon?: string
  description?: string
  to?: RouteLocationRaw
  active?: boolean
  /** Hairline above the row — marks a change of kind inside one menu. */
  separated?: boolean
  /** A row that offers an escape rather than a feature; it should not compete for the eye. */
  muted?: boolean
  loading?: boolean
}>(), {})

defineEmits<{ (e: 'select'): void }>()

const NuxtLink = resolveComponent('NuxtLink')
</script>

<template>
  <div
    v-if="separated"
    class="menu-rule"
    role="presentation"
  />
  <component
    :is="to ? NuxtLink : 'button'"
    :to="to"
    :type="to ? undefined : 'button'"
    :disabled="!to && loading ? true : undefined"
    class="menu-row"
    :class="[active ? 'menu-row--active' : null, muted ? 'menu-row--muted' : null]"
    :aria-current="to && active ? 'page' : undefined"
    @click="$emit('select')"
  >
    <UIcon
      v-if="icon"
      :name="loading ? 'i-lucide-loader-circle' : icon"
      class="menu-row__icon"
      :class="loading ? 'animate-spin' : null"
    />
    <span class="menu-row__body">
      <span class="menu-row__label sk-title">
        {{ label }}
        <slot name="meta" />
      </span>
      <span
        v-if="description || $slots.note"
        class="menu-row__desc sk-meta"
      >
        {{ description }}
        <slot name="note" />
      </span>
    </span>
  </component>
</template>

<style scoped>
/* Radius is `--sk-r-chip` (8px) because a menu row is chip-scale, not nav-pill-scale;
   the panel around it keeps NuxtUI's popover radius, per DESIGN.md §Shapes. */
.menu-row {
  display: flex;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: 0;
  border-radius: var(--sk-r-chip);
  background: transparent;
  font-family: inherit;
  text-align: left;
  text-decoration: none;
  color: var(--sk-ink);
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.menu-row:hover {
  background: var(--sk-muted-surface);
}

.menu-row:disabled {
  cursor: not-allowed;
}

/* The active row wears the crimson left edge — the same 2px inset the FAB sidebar's
   selected row uses (`.sk-fab-active`), restated here without the paper shadow because a
   row inside an already-elevated panel must not cast a second one. Crimson stays trim. */
.menu-row--active {
  background: var(--sk-muted-surface);
  box-shadow: inset 2px 0 0 0 var(--sk-accent);
}

/* An escape hatch, not a feature: it drops from `.sk-title` weight to supporting text so
   it reads as the smallest thing in the panel. */
.menu-row--muted .menu-row__label {
  font-weight: 400;
  color: var(--sk-ink-muted);
}

.menu-row__icon {
  width: 15px;
  height: 15px;
  flex: none;
  margin-top: 2px;
  color: var(--sk-ink-muted);
}

.menu-row__body {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  gap: 1px;
}

/* Type comes from the role classes in the template (`.sk-title`, `.sk-meta`); these rules
   own layout only, so a retone of either role reaches this menu for free. */
.menu-row__label,
.menu-row__desc {
  display: flex;
  align-items: center;
  gap: 6px;
}

.menu-row__desc {
  line-height: 1.45;
}

.menu-rule {
  height: 1px;
  margin: 4px 8px;
  background: var(--sk-border-soft);
}
</style>
