<template>
  <div
    class="min-w-0"
    :aria-busy="lock === 'loading'"
  >
    <p class="mb-1.5 sk-label">
      PARAMETER
    </p>
    <div
      class="flex flex-wrap gap-1.5"
      role="group"
      aria-label="분석할 측정 항목"
    >
      <SkChip
        :active="parameters.length === 0"
        :disabled="lock !== null"
        @click="emit('update:parameters', [])"
      >
        전체
      </SkChip>
      <SkChip
        v-for="name in parameterNames"
        :key="name"
        :active="parameters.includes(name)"
        :disabled="lock !== null"
        @click="emit('update:parameters', parameters.includes(name) ? parameters.filter(p => p !== name) : [...parameters, name])"
      >
        {{ name }}
      </SkChip>
    </div>
    <p class="mt-1.5 sk-field-label leading-relaxed">
      <UIcon
        v-if="lock === 'loading'"
        name="i-lucide-loader-circle"
        class="mr-1 h-3.5 w-3.5 animate-spin"
      />
      <template v-if="lock === 'no-recipe'">
        레시피를 선택하면 측정 항목을 확인할 수 있습니다.
      </template>
      <template v-else-if="lock === 'no-request'">
        데이터를 요청하면 측정 항목이 표시됩니다.
      </template>
      <template v-else-if="lock === 'no-data'">
        선택한 조건에는 측정 데이터가 없습니다.
      </template>
      <template v-else-if="lock === 'loading'">
        측정 항목을 불러오는 중입니다.
      </template>
      <template v-else-if="!parameterNames.length">
        이름 있는 측정 항목이 없어 전체 데이터로 판정합니다.
      </template>
      <template v-else>
        여러 항목을 선택할 수 있으며, 선택한 모든 항목에서 맞는 장비를 그룹으로 묶습니다.
      </template>
    </p>
  </div>
</template>

<script setup lang="ts">
import type { AnalysisLock } from '~/utils/tttmRecipeScope'

defineProps<{
  parameters: string[]
  parameterNames: string[]
  lock: AnalysisLock
}>()

const emit = defineEmits<{
  (e: 'update:parameters', value: string[]): void
}>()
</script>
