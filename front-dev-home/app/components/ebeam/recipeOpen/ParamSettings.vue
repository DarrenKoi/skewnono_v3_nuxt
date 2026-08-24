<template>
  <EbeamRecipeOpenParamPanel
    caption="레시피 원본 폴더에서 읽은 이미지와 빔 · 포커스 조건입니다."
    :pending="pending"
    :error="error"
  >
    <div class="grid gap-3 md:grid-cols-2 md:items-start">
      <section
        v-for="lane in lanes"
        :key="lane.key"
        class="flex min-w-0 flex-col gap-3 rounded-xl border border-zinc-200/70 p-3 dark:border-zinc-800/60"
      >
        <div class="flex items-center justify-between gap-2">
          <span class="text-xs font-bold tracking-wide text-zinc-900 dark:text-zinc-100">
            {{ lane.title }}
          </span>
          <span class="font-mono text-[10px] text-(--sk-ink-muted)">
            {{ lane.images.length }} image
          </span>
        </div>

        <div
          v-if="lane.images.length"
          class="grid gap-3"
          :style="{ gridTemplateColumns: `repeat(${lane.images.length}, minmax(0, 1fr))` }"
        >
          <!-- Keyed on (slot, name): an HV-SEM slot expands to several
               stem-suffixed files (2026-08-08), so `slot` alone would collide
               and Vue would silently drop the extra thumbnails. -->
          <EbeamRecipeOpenImgThumb
            v-for="image in lane.images"
            :key="`${image.slot}:${image.name}`"
            :label="image.slot"
            :stage="image.stage"
            :name="image.name"
            :src="imageSrc(image.name)"
            :role="roleOf(image.slot)"
            @open="emit('openImage', image)"
          />
        </div>
        <p
          v-else-if="!pending"
          class="sk-meta"
        >
          {{ lane.title }} 이미지가 없습니다.
        </p>

        <EbeamRecipeOpenSettingTable
          title="AF / PR (포커스 · 패턴 인식)"
          :block="lane.afPr"
        />

        <EbeamRecipeOpenSettingTable
          v-for="image in lane.images"
          :key="`cond-${image.slot}:${image.name}`"
          :title="condTitle(image, lane.images)"
          :block="image.cond"
        />
      </section>
    </div>

    <EbeamRecipeOpenSettingTable
      v-if="groupedAfPr.other?.rows.length"
      class="mt-3"
      title="기타 AF / PR"
      :block="groupedAfPr.other"
    />
  </EbeamRecipeOpenParamPanel>
</template>

<script setup lang="ts">
/**
 * One parameter's images with their beam conditions, plus the focus / pattern
 * recognition settings that go with them.
 *
 * Fetched on selection rather than with the recipe — each parameter costs up to
 * five files off the measuring tool's own FTP server, and most parameters are
 * never opened. Two of those five name no image: `img_meas2` (`PRMS0000`) is the
 * AMP file, which has its own tab, and `img_add2` (`PRMP0000` → `ENMP0000`) is
 * the AF/PR file below.
 */
import type { ParamDetail, ParamImage } from '~/composables/useRecipeParamDetail'
import type { IdpLocator } from '~/composables/useRecipeSearchApi'
import { recipeApiBase, recipeImageUrl } from '~/composables/useRecipeParamDetail'
import { imageVariantLabels } from '~/utils/imageKind'
import {
  IMAGE_SLOTS,
  splitAfPrSectionsByDomain,
  splitSequenceSections,
  type SlotRole
} from '~/utils/recipeView'

const props = defineProps<{
  toolSlug: string
  locator: IdpLocator
  detail: ParamDetail | null
  pending: boolean
  error: boolean
}>()

const emit = defineEmits<{ (e: 'openImage', image: ParamImage): void }>()

const base = recipeApiBase()

const images = computed<ParamImage[]>(() => props.detail?.images ?? [])

const groupedAfPr = computed(() => splitAfPrSectionsByDomain(
  splitSequenceSections(props.detail?.af_pr ?? null).settings
))

const lanes = computed(() => [
  {
    key: 'address',
    title: 'Addressing',
    images: images.value.filter(image => roleOf(image.slot) === 'address'),
    afPr: groupedAfPr.value.addressing
  },
  {
    key: 'measure',
    title: 'Measurement',
    images: images.value.filter(image => roleOf(image.slot) === 'measure'),
    afPr: groupedAfPr.value.measurement
  }
] as const)

const roleOf = (slotKey: string): SlotRole =>
  IMAGE_SLOTS.find(slot => slot.key === slotKey)?.role ?? 'address'

// A slot that expanded to several files (HV-SEM) repeats its stage, so the
// cond-table titles carry the variant label to stay tellable apart —
// list-aware, because a sub-position listed under two extensions would
// otherwise title two different cond tables identically.
const condTitle = (image: ParamImage, all: readonly ParamImage[]): string => {
  const siblings = all.filter(other => other.slot === image.slot)
  if (siblings.length <= 1) return `${image.stage} 빔 조건`
  const labels = imageVariantLabels(siblings.map(sibling => sibling.name))
  return `${image.stage} 빔 조건 — ${labels[siblings.indexOf(image)]}`
}

// Display rendition: a TIFF raw file converts to WebP server-side; the JPEGs
// recipe folders have been observed to hold pass through byte-identical.
const imageSrc = (name: string) =>
  recipeImageUrl(base, props.toolSlug, props.locator, name, { preview: true })
</script>
