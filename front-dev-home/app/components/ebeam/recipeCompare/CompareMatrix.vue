<template>
  <div class="flex min-h-0 flex-col gap-3">
    <!-- IDP block -->
    <div class="overflow-x-auto rounded-lg border border-zinc-200/70 dark:border-zinc-800/70">
      <table class="w-full border-collapse font-mono text-[11px]">
        <caption class="px-2.5 py-1.5 text-left sk-eyebrow text-(--sk-brand)">
          IDP · 파라미터 단위
        </caption>
        <tbody>
          <tr
            v-for="row in visibleIdpRows"
            :key="row.key"
            :class="row.differs ? 'bg-amber-400/10' : ''"
          >
            <td class="sticky left-0 z-10 bg-inherit px-2.5 py-1.5 font-medium text-(--sk-ink-muted)">
              {{ row.label }}
            </td>
            <td
              v-for="(value, i) in row.values"
              :key="i"
              class="px-2.5 py-1.5 text-zinc-900 dark:text-zinc-100"
              :class="row.differs ? 'font-bold' : ''"
            >
              {{ value }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- AMP block for active slot -->
    <div class="overflow-x-auto rounded-lg border border-zinc-200/70 dark:border-zinc-800/70">
      <table class="w-full border-collapse font-mono text-[11px]">
        <thead>
          <tr class="bg-zinc-50/80 text-left dark:bg-zinc-900/60">
            <th class="sticky left-0 z-10 bg-inherit px-2.5 py-2 font-medium text-(--sk-ink-muted)">
              {{ slotLabel }}
            </th>
            <th
              v-for="col in columns"
              :key="recipePairKey(col.fab_name, col.recipe_id)"
              class="px-2.5 py-2 text-left font-medium"
              :title="col.recipe_id"
            >
              {{ shortId(col.recipe_id) }}
              <span
                v-if="multiFab"
                class="sk-fab-badge"
              >
                {{ col.fab_name }}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="sticky left-0 z-10 bg-inherit px-2.5 py-2 text-(--sk-ink-muted)">
              이미지
            </td>
            <td
              v-for="(file, i) in images"
              :key="i"
              class="px-2 py-2 align-top"
            >
              <EbeamRecipeOpenImgThumb
                v-if="file && slotDescriptor.hasImage"
                :label="slotDescriptor.label"
                :stage="slotDescriptor.stage"
                :name="imageFileName(i)"
                :src="imageSrc(i)"
                :role="slotDescriptor.role"
                :variant="variantOf(i)?.label"
                :variant-total="variantOf(i)?.total"
                @open="openLightbox(i)"
              />
              <span
                v-else
                class="text-rose-500"
              >없음</span>
            </td>
          </tr>
          <tr
            v-for="row in visibleAmpRows"
            :key="row.key"
            :class="row.differs ? 'bg-amber-400/10' : ''"
          >
            <td class="sticky left-0 z-10 bg-inherit px-2.5 py-1.5 font-medium text-(--sk-ink-muted)">
              {{ row.label }}<span
                v-if="row.unit"
                class="ml-1 text-(--sk-ink-subtle)"
              >({{ row.unit }})</span>
            </td>
            <td
              v-for="(value, i) in row.values"
              :key="i"
              class="px-2.5 py-1.5 text-zinc-900 dark:text-zinc-100"
              :class="row.differs ? 'font-bold' : ''"
            >
              {{ value }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <EbeamRecipeOpenImageLightbox
      v-model:open="lightboxOpen"
      :data="lightboxData"
    />
  </div>
</template>

<script setup lang="ts">
import type { CompareRecipe } from '~/composables/useRecipeCompareApi'
import type { CompareColumn, CompareParamDetail } from '~/utils/recipeCompare'
import { blockForSlot, buildSettingRows, buildIdpRows, displayedVariant, imageFilenames, spansFabs } from '~/utils/recipeCompare'
import { recipePairKey } from '~/utils/recipePair'
import { recipeApiBase, recipeImageUrl } from '~/composables/useRecipeParamDetail'
import { IMAGE_SLOTS, type ImageSlotKey } from '~/utils/recipeView'
import type { LightboxData } from '~/components/ebeam/recipeOpen/ImageLightbox.vue'

const props = defineProps<{
  recipes: CompareRecipe[]
  parameter: string
  slotKey: ImageSlotKey
  diffOnly: boolean
  /** Aligned with `recipes` by index — the visible cell's settings per recipe. */
  details: (CompareParamDetail | null)[]
  toolSlug: string
}>()

const base = recipeApiBase()

// recipe_id alone collides when the same recipe name is compared across two
// fabs, so the header needs the pair to stay keyed correctly and to attribute
// each column to its fab.
const columns = computed<CompareColumn[]>(
  () => props.recipes.map(r => ({ recipe_id: r.recipe_id, fab_name: r.fab_name })))
const multiFab = computed(() => spansFabs(props.recipes))
const slotDescriptor = computed(() => IMAGE_SLOTS.find(s => s.key === props.slotKey) ?? IMAGE_SLOTS[0]!)
const slotLabel = computed(() => slotDescriptor.value.stage)

const idpRows = computed(() => buildIdpRows(props.recipes, props.parameter))
const ampRows = computed(() => buildSettingRows(props.details, props.slotKey))
const images = computed(() => imageFilenames(props.recipes, props.parameter, props.slotKey))

const visibleIdpRows = computed(() => props.diffOnly ? idpRows.value.filter(r => r.differs) : idpRows.value)
const visibleAmpRows = computed(() => props.diffOnly ? ampRows.value.filter(r => r.differs) : ampRows.value)

const shortId = (id: string) => (id.length > 12 ? `…${id.slice(-10)}` : id)

const lightboxOpen = ref(false)
const lightboxData = ref<LightboxData | null>(null)

// The filename comes from the SERVER (ParamDetail.images[].name), never from
// re-appending ".jpeg" here — that rule lives in rawfiles.py and a second
// client-side implementation could disagree with it.
const imageFileName = (recipeIndex: number) =>
  props.details[recipeIndex]?.images.find(i => i.slot === props.slotKey)?.name ?? ''

// The cell renders one thumbnail per recipe, so an HV-SEM slot's extra files
// have nowhere to go — the chip names the one that IS showing rather than
// letting two recipes that differ in a hidden variant look identical.
const variantOf = (recipeIndex: number) =>
  displayedVariant(props.details[recipeIndex], props.slotKey)

const imageSrc = (recipeIndex: number) => {
  const locator = props.recipes[recipeIndex]?.locator
  const name = imageFileName(recipeIndex)
  return locator && name ? recipeImageUrl(base, props.toolSlug, locator, name) : ''
}

const openLightbox = (recipeIndex: number) => {
  const name = imageFileName(recipeIndex)
  const detail = props.details[recipeIndex] ?? null
  lightboxData.value = {
    slot: slotDescriptor.value.key,
    stage: slotDescriptor.value.stage,
    name,
    src: imageSrc(recipeIndex),
    role: slotDescriptor.value.role,
    cond: blockForSlot(detail, props.slotKey)
  }
  lightboxOpen.value = true
}
</script>
