<template>
  <div class="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
    <div class="flex shrink-0 items-center justify-between gap-3">
      <div class="flex gap-1">
        <SkNavPill
          size="sm"
          label="측정"
          :count="measSlots.length"
          :active="activeRole === 'measure'"
          @click="activeRole = 'measure'"
        />
        <SkNavPill
          size="sm"
          label="어드레싱"
          :count="addrSlots.length"
          :active="activeRole === 'address'"
          @click="activeRole = 'address'"
        />
      </div>
      <span class="font-mono text-[10.5px] text-zinc-500">
        {{ activeRole === 'measure'
          ? '실측 단계 — CD/Edge 측정'
          : '패턴 매칭 단계 — 측정 위치 찾기' }}
      </span>
    </div>

    <div class="min-h-0 flex-1 overflow-auto pr-1">
      <EbeamRecipeOpenAmpBlock
        v-if="activeRole === 'measure'"
        :image-slots="measSlots"
        :fields="AMP_FIELDS_MEAS"
        :amp-rows="measAmp"
        :idp-row="row"
        @open-image="(slotKey) => emit('openImage', slotKey)"
      />
      <EbeamRecipeOpenAmpBlock
        v-else
        :image-slots="addrSlots"
        :fields="AMP_FIELDS_ADDR"
        :amp-rows="addrAmp"
        :idp-row="row"
        @open-image="(slotKey) => emit('openImage', slotKey)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { AmpRole, AmpRow, IdpImageInfoRow } from '~/composables/useRecipeSearchApi'
import {
  AMP_FIELDS_ADDR,
  AMP_FIELDS_MEAS,
  IMAGE_SLOTS,
  type ImageSlotKey
} from '~/utils/recipeView'

const props = defineProps<{
  row: IdpImageInfoRow
  ampRows: AmpRow[]
}>()

const emit = defineEmits<{ (e: 'openImage', slotKey: ImageSlotKey): void }>()

const activeRole = ref<AmpRole>('measure')

const addrSlots = computed(() => IMAGE_SLOTS.filter(s => s.role === 'address'))
const measSlots = computed(() => IMAGE_SLOTS.filter(s => s.role === 'measure'))

const addrAmp = computed(() => props.ampRows.filter(a => a.role === 'address'))
const measAmp = computed(() => props.ampRows.filter(a => a.role === 'measure'))
</script>
