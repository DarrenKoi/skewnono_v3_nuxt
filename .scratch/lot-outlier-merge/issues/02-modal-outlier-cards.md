# 02 — 스텝 카드에 초과 배지와 파라미터 펼침

Status: resolved
Plan: [`../plan.md`](../plan.md) · Spec: [`../spec.md`](../spec.md)
Blocked by: 01

모달의 recipe 카드에 `초과 N` / `분석 제외` 배지를 달고, 펼치면 파라미터별
point_count 와 꼬리표가 나오게 합니다. 슬라이드오버에서 옮겨 오는 내용이지
새로 판정하는 것이 아닙니다.

카드를 컴포넌트로 뺍니다. `LotDetailModal.vue` 가 이미 372줄이고 여기에 펼침
상태·배지·파라미터 행이 더해지면 한 화면에 안 들어옵니다.

**Files:**

- Create: `front-dev-home/app/components/cdsem/comparison/StepOutlierCard.vue`
- Modify: `front-dev-home/app/components/cdsem/comparison/LotDetailModal.vue`
  (161-223 카드 루프, 236-254 import, props 255-268, 301-331 computed)

**Interfaces:**

- Consumes: `StepOutlier`, `buildStepOutliers` (01), `recipeStepKey`/`sortSteps`
  (`~/utils/recipeStepSort`), `DrillDevice` (type, `~/utils/deviceDrill`)
- Produces:
  - `StepOutlierCard.vue` — props `{ card: StepOutlier, maxTotal: number, expanded: boolean }`,
    emit `toggle`
  - `LotDetailModal.vue` 의 새 prop `drill: DrillDevice | null`
  - `LotDetailModal.vue` 의 `stepCards` computed (03 이 필터를 얹을 자리)

**단위 테스트가 없는 티켓입니다.** `.vue` 를 마운트할 하네스가 저장소에
없습니다(컴포넌트 테스트도 Playwright 설정도 없음). 검증은 01 의 테스트 무회귀
+ 타입체크 + 린트 + 05 의 브라우저 확인입니다. 로직을 이 파일에 두지 않는 것이
그 대가를 갚는 방법입니다 — 조인·필터는 전부 01 에 있습니다.

---

- [ ] **Step 1: 카드 컴포넌트를 만든다**

Create `app/components/cdsem/comparison/StepOutlierCard.vue`:

```vue
<template>
  <div
    class="overflow-hidden rounded-xl bg-(--sk-surface) ring-1"
    :class="[
      flagged ? 'ring-rose-200 dark:ring-rose-900/60' : 'ring-(--sk-border-soft)',
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

          <!-- 설계상 웨이퍼 전면을 훑는 job 입니다. 이 배지가 없으면 큰 숫자가
               초과 표시 없이 놓인 것이 규칙 고장으로 읽힙니다. -->
          <span
            v-if="card.drill?.exempt"
            class="sk-badge bg-(--sk-muted-surface) font-semibold text-(--sk-ink-muted) ring-1 ring-(--sk-border) ring-inset"
            :title="EXEMPT_TITLE"
          >{{ EXEMPT_BADGE }}</span>
          <span
            v-else-if="flagged"
            class="sk-badge sk-badge-lg bg-rose-100 font-bold text-rose-700 dark:bg-rose-950/50 dark:text-rose-300"
          >초과 {{ card.drill?.flagged_count }}</span>

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
          <span class="sk-field-value text-[15px] font-semibold text-(--sk-ink)">{{ step.para_all }}</span>
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

    <!-- 표가 아니라 라벨 달린 행입니다 — 열이 셋뿐이고 헤더도 없어서 <table>
         이 주는 정렬 이점보다 작은 글자의 대가가 큽니다 (DrillSlideover 에서
         같은 이유로 같은 모양을 씁니다). -->
    <div
      v-if="expanded && card.drill"
      class="border-t border-(--sk-border)"
    >
      <div
        v-for="param in card.drill.parameters"
        :key="param.name"
        class="px-4 py-1.5"
        :class="param.flagged ? 'bg-rose-100/50 dark:bg-rose-950/30' : ''"
      >
        <div class="flex max-w-2xl items-center gap-3">
          <span class="min-w-0 flex-1 font-mono text-[15px] text-(--sk-ink)">{{ param.name }}</span>
          <span class="w-16 flex-none text-right font-mono text-base font-semibold tabular-nums text-(--sk-ink)">{{ param.point_count }}</span>
          <span class="w-28 flex-none text-right sk-field-label tabular-nums">{{ param.note ?? '' }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { StepOutlier } from '~/utils/lotOutlierSteps'

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

const EXEMPT_BADGE = '분석 제외'
const EXEMPT_TITLE = 'CDU 계열(_*CDU)·full/half-map·matrix 측정 job(_FULL/_HALF/_MTX)입니다. '
  + '설계상 측정 규모가 정상 recipe 와 달라 중앙값 기준선과 초과 판정에서 모두 빠집니다.'
const SPAN_TITLE = '같은 recipe 를 여러 공정 스텝에서 돌립니다. 초과는 recipe 단위 사실이라 '
  + '각 스텝 카드에 같은 값이 붙습니다 — 중복 집계가 아닙니다.'

const step = computed(() => props.card.step)
const flagged = computed(() => props.card.drill?.flagged === true)
const expandable = computed(() => (props.card.drill?.parameters.length ?? 0) > 0)
</script>
```

- [ ] **Step 2: 모달이 카드 컴포넌트를 쓰도록 바꾼다**

`LotDetailModal.vue` 의 `<script setup>` 에서 import 를 더합니다 (241행 근처):

```ts
import { buildStepOutliers } from '~/utils/lotOutlierSteps'
import type { DrillDevice } from '~/utils/deviceDrill'
```

props 에 `drill` 을 더합니다 (267행 `trend` 아래):

```ts
  /**
   * 이 lot 의 과다 측정 결과 — 페이지가 toOutlierDrill 로 만든 것입니다.
   * 모달이 직접 판정하지 않는 이유는 recipeParams 를 좁히지 않는 이유와
   * 같습니다: 화면 하나가 두 경로로 같은 사실을 계산하면 언젠가 갈립니다.
   */
  drill: DrillDevice | null
```

`sortedRecipes`(326행) 아래에 카드 목록을 더합니다:

```ts
// 정렬 -> 조인 순서입니다. buildStepOutliers 는 순서를 보존하므로 정렬 칩이
// 그대로 카드 순서가 됩니다.
const stepCards = computed(() => buildStepOutliers(sortedRecipes.value, props.drill))
```

- [ ] **Step 3: 카드 루프를 교체한다**

`LotDetailModal.vue` 161-223행의 `<div v-if="sortedRecipes.length > 0">` 블록
안에서, 카드 `div` v-for(171-218행) 전체를 지우고 다음으로 바꿉니다.

```vue
            <CdsemComparisonStepOutlierCard
              v-for="card in stepCards"
              :key="recipeStepKey(card.step)"
              :card="card"
              :max-total="maxRecipeParaTotal"
              :expanded="expandedSteps.has(recipeStepKey(card.step))"
              @toggle="toggleStep(recipeStepKey(card.step))"
            />
```

`v-if="sortedRecipes.length > 0"` 는 `v-if="stepCards.length > 0"` 로 바꿉니다.

- [ ] **Step 4: 펼침 상태를 모달이 갖는다**

`<script setup>` 끝(371행 근처)에 더합니다:

```ts
// 펼침 상태의 키는 카드의 키와 같아야 합니다 — recipe_id 로 잡으면 같은
// recipe 를 쓰는 두 스텝이 함께 펼쳐집니다(그리고 접힙니다).
const expandedSteps = ref<Set<string>>(new Set())

const toggleStep = (key: string) => {
  const next = new Set(expandedSteps.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedSteps.value = next
}

// lot 이 바뀌면 모두 접습니다. 모달은 unmount 되지 않으므로 두면 이전 lot 의
// 펼침이 남습니다.
watch(() => props.row?.lot_cd, () => {
  expandedSteps.value = new Set()
})
```

- [ ] **Step 5: 호출처가 컴파일되게 새 prop 을 넘긴다**

`comparison.vue:204-211` 의 모달 태그에 한 줄 더합니다. (진입점 배선은 04 의
일이고, 여기서는 타입만 맞춥니다.)

```vue
          :drill="selectedLotDrill"
```

그리고 `comparison.vue` 의 `selectedLotParams`(649-652행) 아래에:

```ts
// 모달이 그리는 outlier. 슬라이드오버가 쓰던 것과 **같은 어댑터**입니다 —
// 화면이 둘로 갈렸을 때 두 벌로 계산하지 않으려고 만든 것이 toOutlierDrill
// 이므로, 화면을 하나로 합치면서 그것을 버릴 이유가 없습니다.
const selectedLotDrill = computed<DrillDevice | null>(() => {
  const lotCd = selectedLotRow.value?.lot_cd
  if (!lotCd) return null
  const recipes = recipesByLot.value.get(lotCd) ?? []
  const result = deviceOutliers.value.get(lotCd)
  return result ? toOutlierDrill(lotCd, recipes[0]?.ctn_desc ?? '', recipes, result) : null
})
```

- [ ] **Step 6: 정적 게이트**

Run: `npm run typecheck && npm run lint && npm test 2>&1 | tail -5`
Expected: 셋 다 clean, 테스트 무회귀

- [ ] **Step 7: 눈으로 한 번 본다**

`verify` 스킬로 Flask(:5050) + Nuxt(:3000) 를 띄우고
`/ebeam/cd-sem/device-statistics/comparison` 에서 lot 하나를 엽니다.
초과가 있는 스텝에 rose 배지가 보이고, 눌러서 펼치면 파라미터 행이 나오는지
확인합니다. (전체 확인 목록은 05 입니다.)

- [ ] **Step 8: 커밋**

```bash
git add front-dev-home/app/components/cdsem/comparison/StepOutlierCard.vue
git commit -- front-dev-home/app/components/cdsem/comparison/StepOutlierCard.vue \
  front-dev-home/app/components/cdsem/comparison/LotDetailModal.vue \
  front-dev-home/app/pages/ebeam/cd-sem/device-statistics/comparison.vue \
  -m "feat(device-statistics): show outlier badges and params on lot step cards

Lot 상세 팝업의 스텝 카드를 StepOutlierCard 로 빼고, 초과 배지·분석 제외
배지·파라미터 펼침을 붙였습니다. 슬라이드오버에서 옮겨 온 표시일 뿐 판정은
toOutlierDrill 이 그대로 합니다. 카드 키와 펼침 키는 recipeStepKey 로,
recipe_id 를 쓰면 같은 recipe 를 쓰는 스텝이 함께 접힙니다."
```
