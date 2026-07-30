<template>
  <EbeamRecipeOpenParamPanel
    caption="레시피 원본 폴더에서 읽은 이미지와 빔 · 포커스 조건입니다."
    :pending="pending"
    :error="error"
  >
    <div
      v-if="images.length"
      class="mb-3 grid gap-3"
      :style="{ gridTemplateColumns: `repeat(${images.length}, minmax(0, 1fr))` }"
    >
      <EbeamRecipeOpenImgThumb
        v-for="image in images"
        :key="image.slot"
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
      class="mb-3 sk-meta"
    >
      이 파라미터에는 이미지가 없습니다.
    </p>

    <div class="grid gap-3 md:grid-cols-2">
      <!--
        AF / PR is one FILE and the beam conditions are one per image, so the two
        columns hold different counts on purpose: the settings file left, the
        thumbnails' own conditions stacked right. Sharing one flat grid would
        interleave them and read as five peers.
      -->
      <EbeamRecipeOpenSettingTable
        title="AF / PR (포커스 · 패턴 인식)"
        :block="afPrSettings"
      />
      <div
        v-if="images.length"
        class="flex flex-col gap-3"
      >
        <EbeamRecipeOpenSettingTable
          v-for="image in images"
          :key="`cond-${image.slot}`"
          :title="`${image.stage} 빔 조건`"
          :block="image.cond"
        />
      </div>
    </div>
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
import { IMAGE_SLOTS, splitSequenceSections, type SlotRole } from '~/utils/recipeView'

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

// The AF/PR file minus its two `sequence_*` groups — those list which steps run
// rather than one step's settings, and live on the Sequence tab.
const afPrSettings = computed(() => splitSequenceSections(props.detail?.af_pr ?? null).settings)

const roleOf = (slotKey: string): SlotRole =>
  IMAGE_SLOTS.find(slot => slot.key === slotKey)?.role ?? 'address'

const imageSrc = (name: string) =>
  recipeImageUrl(base, props.toolSlug, props.locator, name)
</script>
