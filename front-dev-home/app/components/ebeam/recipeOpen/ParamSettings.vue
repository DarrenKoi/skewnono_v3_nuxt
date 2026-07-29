<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
    <div class="flex shrink-0 items-center justify-between gap-3">
      <span class="sk-meta">
        레시피 원본 폴더에서 읽은 파라미터 설정입니다.
      </span>
      <span
        v-if="pending"
        class="sk-meta"
      >불러오는 중…</span>
      <span
        v-else-if="error"
        class="text-[11px] text-(--sk-danger)"
      >설정을 불러오지 못했습니다.</span>
    </div>

    <div class="min-h-0 flex-1 overflow-auto pr-1">
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
          Two settings files, not five image columns: img_meas2 (PRMS0000) is
          the AMP file itself and img_add2 (PRMP0000 -> ENMP0000) is the
          auto-focus / pattern-recognition condition. Neither names an image.
        -->
        <EbeamRecipeOpenSettingTable
          title="AMP (측정 방법 · amp 설정)"
          :block="detail?.amp ?? null"
        />
        <EbeamRecipeOpenSettingTable
          title="AF / PR (포커스 · 패턴 인식)"
          :block="detail?.af_pr ?? null"
        />
      </div>

      <div
        v-if="images.length"
        class="mt-3 grid gap-3 md:grid-cols-2"
      >
        <EbeamRecipeOpenSettingTable
          v-for="image in images"
          :key="`cond-${image.slot}`"
          :title="`${image.stage} 빔 조건`"
          :block="image.cond"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * One parameter's raw-recipe settings: up to three images with their beam
 * conditions, plus the AMP and AF/PR setting files.
 *
 * Fetched on selection rather than with the recipe — each parameter costs up to
 * five files off the measuring tool's own FTP server, and most parameters are
 * never opened.
 */
import type { ParamImage } from '~/composables/useRecipeParamDetail'
import type { IdpLocator } from '~/composables/useRecipeSearchApi'
import { recipeApiBase, recipeImageUrl } from '~/composables/useRecipeParamDetail'
import { IMAGE_SLOTS, type SlotRole } from '~/utils/recipeView'

const props = defineProps<{
  toolSlug: string
  locator: IdpLocator
  detail: import('~/composables/useRecipeParamDetail').ParamDetail | null
  pending: boolean
  error: boolean
}>()

const emit = defineEmits<{ (e: 'openImage', image: ParamImage): void }>()

const base = recipeApiBase()

const images = computed<ParamImage[]>(() => props.detail?.images ?? [])

const roleOf = (slotKey: string): SlotRole =>
  IMAGE_SLOTS.find(slot => slot.key === slotKey)?.role ?? 'address'

const imageSrc = (name: string) =>
  recipeImageUrl(base, props.toolSlug, props.locator, name)
</script>
