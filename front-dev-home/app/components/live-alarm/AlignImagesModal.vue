<script setup lang="ts">
/**
 * The recipe's align reference images (OM and SEM) for one ALIGNMENT FAIL.
 *
 * Answers "was the tool ever going to find this target" — it shows what the
 * recipe told the tool to look for, not what the tool saw when it failed (no
 * source for the latter is known). Fetched on open rather than with the board:
 * most alarms are never opened, and every fetch is an FTP session to a tool
 * that is, by definition, already having trouble.
 *
 * A separate component from `recipeOpen/AlignPopup.vue` on purpose — that one
 * takes `wafer_align_info` rows as a prop, which only exist after a full .idp
 * download and parse. Here the file names come from a listing of the tool's
 * raw folder, so no recipe parse is involved at all.
 *
 * THREE OUTCOMES, and they are not the same thing. The tool could not be
 * reached (503 -> the failed branch); the folder was read and holds no align
 * images (empty list); the folder holds some (rendered). Until 2026-08-22 the
 * server computed the names instead of reading them, so the middle case
 * arrived disguised as the last one — two <img> tags pointing at files that
 * were not there, which showed up as 404s in production.
 */
import { fetchAlignImages, recipeApiBase, recipeImageUrl } from '~/composables/useRecipeParamDetail'
import type { AlignImages } from '~/composables/useRecipeParamDetail'
import { toolSlug } from '~/utils/toolType'
import type { ToolType } from '~/utils/toolType'

const open = defineModel<boolean>('open', { required: true })

const props = defineProps<{
  /** The ROUTE spelling ("cd-sem"), which is what the board carries. */
  toolType: ToolType
  fab: string
  recipeId: string
  eqpId: string
}>()

// `/api/<slug>/...` uses the hyphen-less spelling, a Hitachi legacy the whole
// app carries (utils/toolType.ts). Converted here rather than at the call site
// so the board keeps passing the one slug it has.
const apiSlug = computed(() => toolSlug(props.toolType))

const data = ref<AlignImages | null>(null)
const pending = ref(false)
const failed = ref(false)

// What `data` currently holds images FOR. A plain null check would re-fetch on
// every open when a recipe legitimately has none, and would never notice the
// alarm underneath the modal changing.
const loadedFor = ref('')
const wantKey = computed(() => `${props.toolType}|${props.fab}|${props.recipeId}|${props.eqpId}`)

// The tool's crosshair / white box over each image, from its cond.txt. The
// same preference recipe-open's modals use; the toggle only appears when at
// least one sidecar located a mark.
const showMarks = useCondCrosshair()
const hasMarks = computed(() => (data.value?.images ?? []).some(img => img.marks))

const base = recipeApiBase()
const imageSrc = (name: string) =>
  data.value ? recipeImageUrl(base, apiSlug.value, data.value.locator, name) : ''

async function load() {
  const key = wantKey.value
  pending.value = true
  failed.value = false
  try {
    data.value = await fetchAlignImages(apiSlug.value, props.recipeId, props.fab, props.eqpId)
    loadedFor.value = key
  } catch {
    failed.value = true
    data.value = null
  } finally {
    pending.value = false
  }
}

watch(open, (isOpen) => {
  if (!isOpen) return
  if (loadedFor.value !== wantKey.value && !pending.value) void load()
})
</script>

<template>
  <UModal
    v-model:open="open"
    :ui="{ content: 'w-[88vw] sm:max-w-[760px]' }"
  >
    <template #header>
      <div class="px-1 py-1 pe-8">
        <p class="sk-eyebrow text-(--sk-brand)">
          ALIGN REFERENCE
        </p>
        <p class="mt-1 sk-heading">
          정렬 기준 이미지
        </p>
        <p class="mt-1 sk-meta">
          {{ recipeId }} · {{ eqpId }} 이 정렬하려던 대상입니다. 실패 순간의 화면이 아니라 레시피가 지정한 기준 이미지입니다.
        </p>
      </div>
      <UButton
        icon="i-lucide-x"
        color="neutral"
        variant="ghost"
        aria-label="닫기"
        class="absolute end-4 top-4"
        @click="open = false"
      />
    </template>

    <template #body>
      <!-- The substitution disclosure. A sibling tool's copy of the recipe can
           differ from the alarming tool's, so judging "the target looks fine"
           against the wrong file is the failure this line exists to prevent. -->
      <UAlert
        v-if="data && !data.from_requested_tool"
        color="warning"
        variant="subtle"
        icon="i-lucide-triangle-alert"
        class="mb-4"
        :title="`${data.eqp_id} 의 사본입니다`"
        :description="`${data.requested_eqp_id} 의 레시피 파일에 접근할 수 없어 같은 레시피를 가진 다른 장비에서 가져왔습니다. 장비마다 레시피 버전이 다를 수 있습니다.`"
      />

      <p
        v-if="pending"
        class="sk-meta"
      >
        불러오는 중…
      </p>
      <p
        v-else-if="failed"
        class="text-xs text-rose-600 dark:text-rose-400"
      >
        정렬 기준 이미지를 불러오지 못했습니다. 레시피 위치를 찾을 수 없거나 장비에 연결할 수 없습니다.
      </p>

      <p
        v-else-if="data && !data.images.length"
        class="sk-meta"
      >
        이 레시피에는 정렬 기준 이미지가 없습니다. 장비의 레시피 폴더를 읽었으나 IMAP 파일이 없었습니다.
      </p>

      <div v-else-if="data?.images.length">
        <div
          v-if="hasMarks"
          class="mb-2 flex justify-end"
        >
          <EbeamRecipeOpenCondMarksToggle
            v-model="showMarks"
            label="정렬점 십자선"
            variant="bar"
          />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <figure
            v-for="image in data.images"
            :key="image.name"
            class="flex min-w-0 flex-col gap-1"
          >
            <div class="relative mx-auto aspect-square w-full max-w-[280px] overflow-hidden rounded-md border border-zinc-300/70 bg-(--sk-field) dark:border-zinc-700">
              <img
                :src="imageSrc(image.name)"
                :alt="`${image.optic || `P.No ${image.p_no}`} 정렬 기준 이미지`"
                loading="lazy"
                decoding="async"
                class="h-full w-full object-cover"
              >
              <EbeamRecipeOpenCondMarks
                v-if="showMarks"
                :marks="image.marks"
                fit="cover"
              />
              <!-- Blank for a P.No the office has never described. The server
                 will not name an optic it cannot know, and a badge reading
                 "SEM" over an OM image is worse than no badge. -->
              <span
                v-if="image.optic"
                class="absolute top-1 left-1 rounded-sm bg-(--sk-ink) px-1.5 py-px font-mono text-xs font-bold tracking-wider text-(--sk-ink-fg)"
              >
                {{ image.optic }}
              </span>
            </div>
            <figcaption class="text-center font-mono text-xs text-(--sk-ink-muted)">
              P.No {{ image.p_no }} · {{ image.name }}
            </figcaption>
          </figure>
        </div>
      </div>
    </template>
  </UModal>
</template>
