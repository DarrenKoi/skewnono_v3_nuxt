<template>
  <div class="flex shrink-0 flex-col overflow-hidden rounded-xl border border-zinc-200/70 bg-zinc-50/40 dark:border-zinc-800/60 dark:bg-zinc-900/30">
    <div
      class="grid gap-2 px-3.5 py-2.5"
      :style="{ gridTemplateColumns: `110px repeat(${imageSlots.length}, minmax(0, 1fr))` }"
    >
      <div class="flex items-end pb-1 font-mono text-[10px] tracking-wide text-(--sk-ink-muted)">
        AMP ↓ / Image →
      </div>
      <EbeamRecipeOpenImgThumb
        v-for="slot in imageSlots"
        :key="slot.key"
        :image-slot="slot"
        :filename="idpRow[slot.key]"
        @open="emit('openImage', slot.key)"
      />
    </div>

    <div class="overflow-auto">
      <table class="w-full border-collapse font-mono text-[11.5px]">
        <tbody>
          <tr
            v-for="(field, fi) in fields"
            :key="field.key"
            :class="fi % 2 ? 'bg-black/[0.014] dark:bg-white/[0.02]' : ''"
          >
            <td class="w-[110px] border-b border-zinc-100 px-3.5 py-1.5 text-[10.5px] font-semibold whitespace-nowrap text-zinc-700 dark:border-zinc-800/60 dark:text-zinc-300">
              {{ field.label }}
              <span
                v-if="field.unit"
                class="ml-1 font-normal text-(--sk-ink-muted)"
              >({{ field.unit }})</span>
            </td>
            <td
              v-for="(amp, ci) in ampRows"
              :key="`${field.key}-${ci}`"
              class="border-b border-zinc-100 px-2.5 py-1.5 text-right whitespace-nowrap dark:border-zinc-800/60"
              :class="formatAmpValue(amp[field.key]) === '—'
                ? 'text-(--sk-ink-muted)'
                : 'text-zinc-900 dark:text-zinc-100'"
            >
              {{ formatAmpValue(amp[field.key]) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AmpRow, IdpImageInfoRow } from '~/composables/useRecipeSearchApi'
import {
  formatAmpValue,
  type AmpFieldDescriptor,
  type ImageSlot,
  type ImageSlotKey
} from '~/utils/recipeView'

defineProps<{
  imageSlots: readonly ImageSlot[]
  fields: readonly AmpFieldDescriptor[]
  ampRows: AmpRow[]
  idpRow: IdpImageInfoRow
}>()

const emit = defineEmits<{ (e: 'openImage', slotKey: ImageSlotKey): void }>()
</script>
