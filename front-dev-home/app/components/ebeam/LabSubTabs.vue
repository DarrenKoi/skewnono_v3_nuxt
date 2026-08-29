<template>
  <!-- These sub-tabs change the ROUTE, so they are real links (NuxtLink +
       aria-current="page") rather than a client-side toggle — the same
       semantic EbeamEquipmentStatusSubTabs uses for 장비 리스트 / 스토리지, and
       for the same reason: the URL is what the two views are addressed by.
       Here that is load-bearing beyond bookmarking — /tttm and /pm-planning are
       identities, not just paths (`_logging/feature_map.py` files activity under
       the slug, `utils/pageIdentity.ts` carries /pm-tune as an alias of the
       second, and 실험실 lists both). One page, two addresses.

       Skinned from AppViewToggle's tokens rather than copied from
       EquipmentStatusSubTabs' zinc classes: DESIGN.md §Colors is --sk-* only,
       and that older bar predates the rule. -->
  <nav
    aria-label="실험실 분석 sub-view"
    class="inline-flex items-center gap-1 rounded-lg bg-(--sk-muted-surface) p-1 ring-1 ring-(--sk-border-soft) ring-inset"
  >
    <NuxtLink
      v-for="option in options"
      :key="option.value"
      :to="option.to"
      :aria-current="view === option.value ? 'page' : undefined"
      class="inline-flex h-[30px] items-center gap-1.5 rounded-md px-3 text-sm font-semibold transition-colors"
      :class="view === option.value
        ? 'bg-(--sk-surface) text-(--sk-ink) shadow-sm ring-1 ring-(--sk-border)'
        : 'text-(--sk-ink-muted) hover:text-(--sk-ink)'"
    >
      <UIcon
        :name="option.icon"
        class="h-4 w-4"
      />
      {{ option.label }}
    </NuxtLink>
  </nav>
</template>

<script setup lang="ts">
import type { LabViewSlug } from '~/utils/labView'
import { LAB_VIEWS } from '~/utils/labView'

// Which view is showing comes from the PARENT, not from re-parsing the path:
// LabView already has it as a prop (it decides which results to draw with it),
// and a second derivation here is a second thing to fix when routes move.
defineProps<{ view: LabViewSlug }>()

const route = useRoute()

// The sibling route is this one with its last segment swapped, so the pair
// keeps whatever prefix it sits under (/ebeam/cd-sem/<fab>/…) without this
// component knowing the shape. Both slugs are the last segment by construction:
// they are `pages/ebeam/cd-sem/[fab]/{tttm,pm-planning}.vue`.
const base = computed(() => route.path.replace(/\/[^/]+$/, ''))

const options = computed(() =>
  LAB_VIEWS.map(v => ({ ...v, to: `${base.value}/${v.value}` }))
)
</script>
