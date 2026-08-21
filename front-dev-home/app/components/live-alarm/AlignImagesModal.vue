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
 * download and parse. Here the file names are computed server-side, so no
 * recipe parse is involved at all.
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

      <div
        v-else-if="data?.images.length"
        class="grid grid-cols-2 gap-3"
      >
        <figure
          v-for="image in data.images"
          :key="image.name"
          class="flex min-w-0 flex-col gap-1"
        >
          <div class="relative mx-auto aspect-square w-full max-w-[280px] overflow-hidden rounded-md border border-zinc-300/70 bg-(--sk-field) dark:border-zinc-700">
            <img
              :src="imageSrc(image.name)"
              :alt="`${image.optic} 정렬 기준 이미지`"
              loading="lazy"
              decoding="async"
              class="h-full w-full object-cover"
            >
            <span class="absolute top-1 left-1 rounded-sm bg-(--sk-ink) px-1.5 py-px font-mono text-[11px] font-bold tracking-wider text-(--sk-ink-fg)">
              {{ image.optic }}
            </span>
          </div>
          <figcaption class="text-center font-mono text-[11px] text-(--sk-ink-muted)">
            P.No {{ image.p_no }} · {{ image.name }}
          </figcaption>
        </figure>
      </div>
    </template>
  </UModal>
</template>
