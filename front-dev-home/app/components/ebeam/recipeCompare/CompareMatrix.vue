<template>
  <div class="flex min-h-0 flex-col gap-3">
    <!-- IDP block -->
    <div class="overflow-x-auto rounded-lg border border-zinc-200/70 dark:border-zinc-800/70">
      <table class="w-full border-collapse font-mono text-[11px]">
        <caption class="px-2.5 py-1.5 text-left text-[10px] font-bold tracking-wider text-(--sk-brand) uppercase">
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
              v-for="id in recipeIds"
              :key="id"
              class="px-2.5 py-2 text-left font-medium"
              :title="id"
            >
              {{ shortId(id) }}
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
                v-if="file"
                :image-slot="slotDescriptor"
                :filename="file"
                @open="openLightbox(i, file)"
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
                class="ml-1 text-zinc-400"
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
import { buildAmpRows, buildIdpRows, imageFilenames, findParameter } from '~/utils/recipeCompare'
import { IMAGE_SLOTS, type ImageSlotKey } from '~/utils/recipeView'
import type { LightboxData } from '~/components/ebeam/recipeOpen/ImageLightbox.vue'

const props = defineProps<{
  recipes: CompareRecipe[]
  parameter: string
  slotKey: ImageSlotKey
  diffOnly: boolean
}>()

const recipeIds = computed(() => props.recipes.map(r => r.recipe_id))
const slotDescriptor = computed(() => IMAGE_SLOTS.find(s => s.key === props.slotKey) ?? IMAGE_SLOTS[0]!)
const slotLabel = computed(() => slotDescriptor.value.stage)

const idpRows = computed(() => buildIdpRows(props.recipes, props.parameter))
const ampRows = computed(() => buildAmpRows(props.recipes, props.parameter, props.slotKey))
const images = computed(() => imageFilenames(props.recipes, props.parameter, props.slotKey))

const visibleIdpRows = computed(() => props.diffOnly ? idpRows.value.filter(r => r.differs) : idpRows.value)
const visibleAmpRows = computed(() => props.diffOnly ? ampRows.value.filter(r => r.differs) : ampRows.value)

const shortId = (id: string) => (id.length > 12 ? `…${id.slice(-10)}` : id)

const lightboxOpen = ref(false)
const lightboxData = ref<LightboxData | null>(null)

const openLightbox = (recipeIndex: number, filename: string) => {
  const recipe = props.recipes[recipeIndex]
  const param = recipe ? findParameter(recipe, props.parameter) : null
  const ampRow = param?.amp.find(a => a.slot === props.slotKey) ?? null
  lightboxData.value = { slot: slotDescriptor.value, filename, ampRow }
  lightboxOpen.value = true
}
</script>
