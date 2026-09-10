<template>
  <UModal
    v-model:open="open"
    :ui="{ content: 'w-[92vw] sm:max-w-[1080px]', body: 'p-0' }"
  >
    <template #content>
      <div
        v-if="open && data"
        class="grid h-full max-h-[88vh] grid-cols-1 gap-4 p-4 md:grid-cols-[1.4fr_320px]"
      >
        <div class="relative mx-auto flex aspect-square w-full max-w-[min(100%,78vh)] items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-(--sk-field)">
          <!-- No `loading="lazy"` here: the user has already asked for this one. -->
          <img
            v-if="!failed"
            :src="data.src"
            :alt="`${data.stage} (${data.name})`"
            decoding="async"
            class="h-full w-full object-contain"
            @error="failed = true"
          >
          <div
            v-else
            class="px-6 text-center font-mono text-[12px] text-white/45"
          >
            이미지를 불러오지 못했습니다
          </div>
          <EbeamRecipeOpenCondMarks
            v-if="!failed && showMarks"
            :marks="data.marks"
          />
          <div class="absolute top-3.5 left-3.5 flex items-center gap-2">
            <span
              class="rounded px-2 py-0.5 font-mono text-xs font-bold tracking-wider"
              :class="isMeas
                ? 'bg-(--sk-brand) text-(--sk-brand-fg)'
                : 'bg-(--sk-ink) text-(--sk-ink-fg)'"
            >{{ data.stage.toUpperCase() }}</span>
            <span class="font-mono text-xs text-white/60">{{ data.name }}</span>
          </div>
          <!-- Overriding #content drops UModal's own ✕, so carry one here.
               Over the image, not the dialog corner, which holds 빔 조건. -->
          <div class="absolute top-3 right-3 flex items-center gap-1.5">
            <EbeamRecipeOpenCondMarksToggle
              v-if="data.marks"
              v-model="showMarks"
              label="측정점 십자선 표시"
            />
            <button
              type="button"
              class="rounded-(--sk-r-nav) bg-black/50 p-1.5 text-white transition-colors duration-200 hover:bg-black/70"
              aria-label="닫기"
              @click="open = false"
            >
              <UIcon
                name="i-lucide-x"
                class="h-4 w-4"
              />
            </button>
          </div>
        </div>

        <div class="max-h-[88vh] overflow-auto rounded-xl bg-zinc-50/60 px-4 py-3 dark:bg-zinc-900/40">
          <p class="sk-meta text-(--sk-brand)">
            빔 조건 — {{ data.stage.toUpperCase() }}
          </p>
          <p class="mt-0.5 sk-title">
            {{ data.slot }}
          </p>
          <p
            v-if="!data.cond"
            class="mt-2.5 text-xs text-(--sk-ink-muted)"
          >
            파일 없음
          </p>
          <div
            v-else
            class="mt-2.5"
          >
            <p class="mb-1.5 font-mono text-xs text-(--sk-ink-subtle)">
              {{ data.cond.source }}
            </p>
            <div
              v-for="setting in data.cond.rows"
              :key="setting.key"
              class="flex items-baseline justify-between gap-3 border-b border-zinc-100 py-1.5 dark:border-zinc-800/60"
            >
              <span class="sk-label">{{ setting.key }}</span>
              <span class="text-right sk-value-num">
                {{ formatSettingValue(setting.value) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
/**
 * One raw-recipe image at full size, beside the beam condition parsed from its
 * `.{name}/cond.txt` sidecar.
 */
import type { CursorMarks, SettingBlock } from '~/composables/useRecipeParamDetail'
import { formatSettingValue, type SlotRole } from '~/utils/recipeView'

export interface LightboxData {
  /** Column name, e.g. `img_meas1`. */
  slot: string
  stage: string
  name: string
  src: string
  role: SlotRole
  cond: SettingBlock | null
  marks?: CursorMarks | null
}

const open = defineModel<boolean>('open', { required: true })

const props = defineProps<{
  data: LightboxData | null
}>()

const isMeas = computed(() => props.data?.role === 'measure')

// The tool's crosshair / white-box centre over the image; the toggle only
// appears when the sidecar actually located a mark.
const showMarks = useCondCrosshair()

const failed = ref(false)
watch(() => props.data?.src, () => {
  failed.value = false
})
</script>
