<template>
  <div class="flex h-full flex-col items-center justify-center gap-3 py-20 text-center">
    <span class="flex h-12 w-12 items-center justify-center rounded-(--sk-r-card) bg-(--sk-chip-bg) text-zinc-400">
      <UIcon
        :name="mode?.icon ?? 'i-lucide-layout-dashboard'"
        class="h-6 w-6"
      />
    </span>
    <div>
      <p class="text-[14px] font-semibold text-zinc-700 dark:text-zinc-200">
        {{ mode?.label ?? kind }}
      </p>
      <p class="mt-0.5 text-[12px] text-zinc-400">
        {{ mode?.sub }}
      </p>
    </div>
    <p class="max-w-sm text-[12px] text-zinc-400">
      이 뷰는 다음 단계에서 구현됩니다. 워크스페이스 셸이 먼저 자리잡았습니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import type { SkewvoirViewKind } from '~/composables/useSkewvoirWorkspace'
import { SKEWVOIR_VIEW_MODES } from '~/composables/useSkewvoirWorkspace'

const props = defineProps<{ kind: SkewvoirViewKind }>()

const mode = computed(() => SKEWVOIR_VIEW_MODES.find(m => m.kind === props.kind))
</script>
