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
        <div class="relative flex min-h-[360px] items-center justify-center overflow-hidden rounded-xl border border-white/10 bg-[#1A1813]">
          <EbeamRecipeOpenSemNoise />
          <div class="relative font-mono text-[80px] font-bold tracking-widest text-white/10">
            SEM
          </div>
          <div class="absolute top-3.5 left-3.5 flex items-center gap-2">
            <span
              class="rounded px-2 py-0.5 font-mono text-[10px] font-bold tracking-wider"
              :class="isMeas
                ? 'bg-(--sk-brand) text-(--sk-brand-fg)'
                : 'bg-(--sk-ink) text-(--sk-ink-fg)'"
            >{{ data.slot.stage.toUpperCase() }}</span>
            <span class="font-mono text-[11px] text-white/60">{{ data.filename }}</span>
          </div>
        </div>

        <div class="max-h-[88vh] overflow-auto rounded-xl bg-zinc-50/60 px-4 py-3 dark:bg-zinc-900/40">
          <p class="font-mono text-[10px] font-bold tracking-wider text-(--sk-brand) uppercase">
            AMP — {{ data.slot.stage.toUpperCase() }}
          </p>
          <p class="mt-0.5 font-mono text-[15px] font-bold text-zinc-900 dark:text-zinc-100">
            {{ data.slot.label }}
          </p>
          <div class="mt-2.5">
            <div
              v-for="field in fields"
              :key="field.key"
              class="flex items-baseline justify-between gap-3 border-b border-zinc-100 py-1.5 dark:border-zinc-800/60"
            >
              <span class="font-mono text-[11px] tracking-wide text-(--sk-ink-muted)">
                {{ field.label }}<span
                  v-if="field.unit"
                  class="ml-1 text-zinc-400"
                >({{ field.unit }})</span>
              </span>
              <span class="text-right font-mono text-[13px] font-medium text-zinc-900 dark:text-zinc-100">
                {{ formatAmpValue(data?.ampRow?.[field.key]) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { AmpRow } from '~/composables/useRecipeSearchApi'
import { ampFieldsForRole, formatAmpValue, type ImageSlot } from '~/utils/recipeView'

export interface LightboxData {
  slot: ImageSlot
  filename: string
  ampRow: AmpRow | null
}

const open = defineModel<boolean>('open', { required: true })

const props = defineProps<{
  data: LightboxData | null
}>()

const isMeas = computed(() => props.data?.slot.role === 'measure')
const fields = computed(() => (props.data ? ampFieldsForRole(props.data.slot.role) : []))
</script>
