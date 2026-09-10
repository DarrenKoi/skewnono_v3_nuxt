<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
    <div class="flex shrink-0 items-center justify-between gap-3">
      <span class="sk-meta">
        {{ caption }}
      </span>
      <span
        v-if="pending"
        class="sk-meta"
      >불러오는 중…</span>
      <span
        v-else-if="error"
        class="text-xs text-rose-600 dark:text-rose-400"
      >설정을 불러오지 못했습니다.</span>
    </div>

    <div class="min-h-0 flex-1 overflow-auto pr-1">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * The frame shared by every tab backed by the raw-recipe folder — 이미지 + 설정,
 * AMP and Sequence: a caption, the fetch's pending/error state, and a scroll
 * area.
 *
 * ONE fetch feeds all three (see `loadParamDetail` in `RecipeOpenView`), so its
 * status has to read identically on whichever tab happens to be open when the
 * response lands. Repeating the header per tab is how that quietly drifts.
 */
defineProps<{
  /** What this tab is showing, in one line. */
  caption: string
  pending: boolean
  error: boolean
}>()
</script>
