<template>
  <div
    class="overflow-hidden rounded-xl bg-(--sk-surface) ring-1"
    :class="[
      flagged ? 'ring-(--sk-bad-border)' : 'ring-(--sk-border-soft)',
      step.para_all === 0 ? 'opacity-60' : ''
    ]"
  >
    <!-- 펼칠 것이 있을 때만 button 이 됩니다. 파라미터가 없는 스텝까지 눌리게
         해 두면 눌러도 아무 일이 없는 카드가 목록에 섞입니다. -->
    <component
      :is="expandable ? 'button' : 'div'"
      :type="expandable ? 'button' : undefined"
      :aria-expanded="expandable ? expanded : undefined"
      class="flex w-full flex-wrap items-start gap-x-5 gap-y-3 px-4 py-3 text-left"
      @click="expandable && emit('toggle')"
    >
      <!-- 카드의 주어는 **스텝(oper_desc)** 입니다. recipe_id 가 아닙니다 —
           이 목록을 읽는 질문이 "이 device 는 어느 공정에서 무엇을 재는가"
           이고, recipe 이름은 그 스텝을 재는 job 의 이름일 뿐입니다. -->
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <span class="flex min-w-0 items-center gap-1.5">
            <UIcon
              v-if="expandable"
              :name="expanded ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
              class="h-4 w-4 flex-none text-(--sk-ink-subtle)"
            />
            <span class="sk-card-id">{{ step.oper_desc || '—' }}</span>
          </span>
          <span class="sk-field-label">
            oper_seq <span class="sk-field-value font-semibold text-(--sk-ink)">{{ step.oper_seq }}</span>
          </span>
        </div>
        <div class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          <span class="sk-field-value">{{ step.recipe_id }}</span>
          <span class="sk-badge bg-(--sk-muted-surface) text-(--sk-ink-muted) ring-1 ring-(--sk-border) ring-inset">{{ step.oper_id }}</span>
          <span class="sk-field-label">
            samp_seq <span class="sk-field-value">{{ step.samp_seq }}</span>
          </span>

          <EbeamDevstatDrillFlagBadge
            v-if="card.drill?.exempt"
            variant="exempt"
          />
          <EbeamDevstatDrillFlagBadge
            v-else-if="flagged"
            variant="flagged"
            :count="card.drill?.flagged_count"
          />

          <!-- 같은 recipe 가 스텝 여럿에서 돕니다. 말해 두지 않으면 같은 배지가
               카드 두 장에 붙은 것이 중복 집계로 읽힙니다. -->
          <span
            v-if="card.stepSpan > 1"
            class="sk-field-label"
            :title="SPAN_TITLE"
          >스텝 {{ card.stepSpan }}곳</span>
        </div>
      </div>

      <div class="w-50 flex-none">
        <div class="mb-1.5 flex items-baseline justify-between gap-2">
          <span class="sk-field-label">para 분포</span>
          <span class="sk-field-value font-semibold text-(--sk-ink)">{{ step.para_all }}</span>
        </div>
        <CdsemComparisonStackedBar
          v-if="step.para_all > 0"
          :row="step"
          :label="step.recipe_id"
          :height="18"
          :normalize="false"
          :max-total="maxTotal"
        />
        <p
          v-else
          class="sk-field-label"
        >
          파라미터 없음
        </p>
      </div>
    </component>

    <EbeamDevstatDrillParamRows
      v-if="expanded && card.drill"
      :parameters="card.drill.parameters"
      dense
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { isFlaggedStep, type StepOutlier } from '~/utils/lotOutlierSteps'

// 판정하지 않는 카드입니다. flagged 도 note 도 toOutlierDrill 이 이미 정한
// 값을 그대로 읽습니다 (utils/deviceDrill.ts) — 여기서 다시 계산하면 그쪽
// 테스트가 지키던 제외 규칙 두 층이 화면에서만 풀립니다.
const props = defineProps<{
  card: StepOutlier
  /** lot 안의 최대 para_all. 카드마다 제 합계로 정규화하면 3개짜리와 40개짜리 막대가 똑같이 꽉 차 보입니다. */
  maxTotal: number
  expanded: boolean
}>()

const emit = defineEmits<{ toggle: [] }>()

const SPAN_TITLE = '같은 recipe 를 여러 공정 스텝에서 돌립니다. 초과는 recipe 단위 사실이라 '
  + '각 스텝 카드에 같은 값이 붙습니다 — 중복 집계가 아닙니다.'

const step = computed(() => props.card.step)
const flagged = computed(() => isFlaggedStep(props.card))
const expandable = computed(() => (props.card.drill?.parameters.length ?? 0) > 0)
</script>
