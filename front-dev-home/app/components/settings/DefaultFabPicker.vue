<script setup lang="ts">
import { useNavigationStore } from '~/stores/navigation'
import { extractFabNames } from '~/utils/fab'

const { fabs, setFabs } = useNavigationStore()

// Same source and normalization the fab sidebar and the landing page use. The
// sem list loads client-side only, so pending/error/empty each render a one-line
// hint instead of an empty picker.
const { data: semRows, pending, error } = useSemList()
const fabOptions = computed(() => extractFabNames(semRows.value ?? []))

// Multi-select. setFabs canonicalizes (uppercase, deduped, order preserved) and
// fabs[0] stays the primary fab — identical contract to the landing page picker.
// Persistence is handled by the persist-fab client plugin; this card only reads
// and writes the store.
const selectedFabs = computed<string[]>({
  get: () => [...fabs.value],
  set: value => setFabs(value)
})

const primaryLabel = computed(() => (fabs.value.length > 0 ? fabs.value[0] : '없음'))
</script>

<template>
  <section class="space-y-3">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
      <div class="min-w-0">
        <p class="font-medium text-zinc-900 dark:text-zinc-100">
          Fab 선택
        </p>
        <p class="text-sm text-(--sk-ink-muted)">
          측정·분석 페이지에서 사용할 Fab을 고르세요. 여러 개를 선택하면 첫 번째가 기본 Fab이 됩니다.
        </p>
      </div>
      <div class="inline-flex items-center gap-2 self-start rounded-md bg-zinc-100 px-2.5 py-1 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
        <UIcon
          name="i-lucide-factory"
          class="h-3.5 w-3.5"
        />
        <span class="whitespace-nowrap">기본: {{ primaryLabel }}</span>
      </div>
    </div>

    <div
      v-if="pending"
      class="sk-meta"
    >
      장비 목록을 불러오는 중입니다…
    </div>
    <div
      v-else-if="error"
      class="sk-meta"
    >
      장비 목록을 불러오지 못해 Fab 선택을 표시할 수 없습니다.
    </div>
    <div
      v-else-if="fabOptions.length === 0"
      class="sk-meta"
    >
      선택할 Fab이 없습니다. 장비 목록이 비어 있습니다.
    </div>

    <div
      v-else
      class="flex flex-col gap-3"
    >
      <div class="flex flex-wrap items-center gap-2">
        <!-- Checkbox multi-select, same pattern as the landing page picker:
             leading checkbox, default trailing check hidden. The fab list is
             short, so the search input is off. -->
        <USelectMenu
          id="default-fab-select"
          v-model="selectedFabs"
          multiple
          class="w-52"
          size="md"
          color="neutral"
          variant="subtle"
          icon="i-lucide-factory"
          placeholder="Fab 선택"
          :items="fabOptions"
          :search-input="false"
          :ui="{ itemTrailingIcon: 'hidden' }"
        >
          <template #item-leading="{ item }">
            <AppSelectCheck :checked="selectedFabs.includes(item)" />
          </template>
        </USelectMenu>

        <UButton
          size="sm"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          :disabled="fabs.length === 0"
          @click="setFabs([])"
        >
          선택 해제
        </UButton>
      </div>

      <div
        v-if="fabs.length > 0"
        class="flex flex-wrap items-center gap-1.5"
      >
        <span
          v-for="fab in fabs"
          :key="fab"
          class="inline-flex items-center gap-1 rounded-[var(--sk-r-chip)] bg-(--sk-brand-soft) px-2.5 py-1 text-xs font-semibold text-(--sk-brand-ink)"
        >
          <span>{{ fab }}</span>
          <button
            type="button"
            :aria-label="`${fab} 선택 해제`"
            class="rounded-full opacity-60 hover:opacity-100"
            @click="setFabs(fabs.filter(f => f !== fab))"
          >
            <UIcon
              name="i-lucide-x"
              class="h-3 w-3"
            />
          </button>
        </span>
        <span
          v-if="fabs.length > 1"
          class="sk-meta"
        >
          첫 번째가 기본 Fab입니다.
        </span>
      </div>
    </div>

    <p class="sk-meta">
      선택한 Fab은 이 브라우저에 저장됩니다. 방문할 때마다 복원되며, 모든 도구 페이지에서 동일하게 적용됩니다.
    </p>
  </section>
</template>
