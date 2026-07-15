<template>
  <aside class="flex w-60 shrink-0 flex-col gap-5 overflow-y-auto border-r border-(--sk-border) bg-(--sk-surface) px-3 py-4">
    <!-- View modes — the back-to-search escape hatch sits directly above them and
         is the only saturated control here, so it never reads as a view mode. -->
    <section>
      <UButton
        block
        variant="solid"
        icon="i-lucide-arrow-left"
        label="검색으로"
        size="sm"
        class="mb-3 justify-start bg-(--sk-accent) font-semibold text-white shadow-sm ring-1 ring-(--sk-accent-border) hover:bg-(--sk-accent) hover:brightness-110 focus-visible:outline-(--sk-accent)"
        @click="ws.goSearch()"
      />
      <p class="mb-2 px-1 sk-eyebrow">
        WORKSPACE
      </p>
      <ul class="space-y-1">
        <li
          v-for="mode in ws.viewModes"
          :key="mode.kind"
        >
          <button
            type="button"
            class="flex w-full items-center gap-2.5 rounded-(--sk-r-nav) px-2.5 py-2 text-left transition-colors"
            :class="mode.kind === ws.activeKind.value
              ? 'bg-(--sk-ink) text-(--sk-ink-fg)'
              : 'text-zinc-600 hover:bg-zinc-500/10 dark:text-zinc-300'"
            @click="ws.openView(mode.kind)"
          >
            <span
              class="flex h-4 w-4 shrink-0 items-center justify-center rounded-[4px] border"
              :class="mode.kind === ws.activeKind.value
                ? 'border-(--sk-ink-fg)/40 bg-(--sk-ink-fg)/15'
                : 'border-zinc-300 dark:border-zinc-600'"
            >
              <UIcon
                v-if="mode.kind === ws.activeKind.value"
                name="i-lucide-check"
                class="h-3 w-3"
              />
            </span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-[12.5px] font-semibold">{{ mode.label }}</span>
              <span
                class="block truncate text-[11px]"
                :class="mode.kind === ws.activeKind.value ? 'text-(--sk-ink-fg)/70' : 'text-(--sk-ink-muted)'"
              >{{ mode.sub }}</span>
            </span>
            <UKbd
              :value="String(mode.index)"
              size="sm"
              :class="mode.kind === ws.activeKind.value ? 'opacity-80' : 'opacity-60'"
            />
          </button>
        </li>
      </ul>
    </section>

    <!-- Current selection -->
    <section
      v-if="ws.selection.value"
      class="space-y-1.5 border-t border-(--sk-border-soft) pt-4"
    >
      <p class="mb-1 px-1 sk-eyebrow">
        CURRENT SELECTION
      </p>
      <dl class="space-y-1 px-1 text-[12px]">
        <div
          v-for="field in selectionFields"
          :key="field.label"
          class="flex items-baseline justify-between gap-2"
        >
          <dt class="sk-label">
            {{ field.label }}
          </dt>
          <dd
            class="truncate font-mono text-(--sk-ink)"
            :class="{ 'font-semibold': field.strong }"
          >
            {{ field.value }}
          </dd>
        </div>
      </dl>
    </section>

    <!-- Actions — separated from the selection above by its own bordered section -->
    <section
      v-if="ws.selection.value"
      class="border-t border-(--sk-border) pt-4"
    >
      <p class="mb-2 px-1 sk-eyebrow">
        ACTIONS
      </p>
      <div class="space-y-1.5">
        <UButton
          v-for="action in actions"
          :key="action.label"
          block
          color="neutral"
          variant="ghost"
          size="sm"
          class="justify-start"
          :icon="action.icon"
          :label="action.label"
          @click="action.onClick?.()"
        />
      </div>
    </section>
  </aside>
</template>

<script setup lang="ts">
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'
import { recipeDetailRoute } from '~/utils/recipeView'

const props = defineProps<{ ws: SkewvoirWorkspace, fab: string }>()

const toast = useToast()
const router = useRouter()

// Open the current measurement's recipe in the existing "Recipe 열어 보기" page,
// in a new tab. The analysis route isn't fab-scoped, so the fab comes from the
// focus measurement (passed in).
const openRecipe = () => {
  const recipe = props.ws.selection.value?.recipe
  if (!recipe || !props.fab) return
  const route = recipeDetailRoute(props.ws.toolType, props.fab, 'open', recipe)
  window.open(router.resolve(route).href, '_blank', 'noopener')
}

const share = async () => {
  const url = props.ws.shareUrl()
  try {
    await navigator.clipboard.writeText(url)
    toast.add({ title: '링크가 복사되었습니다', description: url, icon: 'i-lucide-link', color: 'success' })
  } catch {
    toast.add({ title: '복사하지 못했습니다', description: url, icon: 'i-lucide-triangle-alert', color: 'warning' })
  }
}

// Recipe 열어보기 + Share work today; Annotate is staged for the feature
// discussion to follow. Excel export lives on the data table, not here.
const actions = [
  { label: '+ Annotate', icon: 'i-lucide-message-square-plus', onClick: undefined as (() => void) | undefined },
  { label: 'Recipe 열어보기', icon: 'i-lucide-file-search', onClick: openRecipe },
  { label: 'Share', icon: 'i-lucide-share-2', onClick: share }
]

const selectionFields = computed(() => {
  const sel = props.ws.selection.value
  if (!sel) return []
  return [
    { label: 'Lot', value: sel.lot, strong: true },
    { label: 'Recipe', value: sel.recipe, strong: false },
    { label: 'EQ', value: sel.eq, strong: false },
    { label: 'MP', value: sel.mp, strong: false },
    { label: 'Captured', value: sel.capturedAt, strong: false }
  ]
})
</script>
