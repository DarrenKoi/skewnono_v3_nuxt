<script setup lang="ts">
// The one back affordance. Before this existed the app spelled "go back to the
// parent screen" five different ways — ghost/sm on the left here, outline/md
// with rounded-full there, outline/sm pinned to the RIGHT on the AFM pages —
// so the same action moved and changed shape as you walked between features.
//
// Look is fixed on purpose: callers pass a destination and a label, never a
// variant. Position is the caller's job, but the convention is LEFT, ahead of
// the title — see EbeamMetaBar's #leading slot, which exists for exactly this.
//
// Not in scope: the skewvoir workspace rail (a saturated sidebar CTA, not a
// header) and empty-state recovery buttons ("Recipe 검색으로 돌아가기"), which are
// error affordances sized to their empty state rather than header navigation.
withDefaults(defineProps<{
  /** Route to return to. Omit and listen for @click when the parent navigates itself. */
  to?: string
  label?: string
}>(), {
  to: undefined,
  label: '돌아가기'
})
</script>

<template>
  <UButton
    size="sm"
    color="neutral"
    variant="ghost"
    icon="i-lucide-arrow-left"
    :label="label"
    :to="to"
    class="font-medium"
  />
</template>
