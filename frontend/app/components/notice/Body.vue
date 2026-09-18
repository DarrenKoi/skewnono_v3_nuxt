<script setup lang="ts">
import type { Notice } from '~/data/notices'

// A notice's opened body: each area over its bulleted changes. The timeline cards set
// area and list side by side; the pinned card, a banner rather than a rail entry, stacks them.
defineProps<{ notice: Notice, stacked?: boolean }>()
</script>

<template>
  <div class="flex flex-col gap-4 border-t border-(--sk-border-soft) px-[18px] pt-4 pb-5">
    <section
      v-for="section in notice.sections"
      :key="section.area"
      :class="stacked ? '' : 'grid items-start gap-x-4 gap-y-1.5 sm:grid-cols-[148px_minmax(0,1fr)]'"
    >
      <h3 class="text-[13px] leading-[1.45] font-semibold text-(--sk-ink-muted)">
        {{ section.area }}
      </h3>
      <ul
        class="list-disc space-y-1 pl-5 marker:text-(--sk-ink-subtle)"
        :class="{ 'mt-1.5': stacked }"
      >
        <li
          v-for="(item, index) in section.items"
          :key="index"
          class="sk-body"
        >
          {{ item }}
        </li>
      </ul>
    </section>
  </div>
</template>
