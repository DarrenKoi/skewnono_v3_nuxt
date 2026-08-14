# 03 — 전체 / 초과만 토글과 기준선 표시

Status: resolved
Plan: [`../plan.md`](../plan.md) · Spec: [`../spec.md`](../spec.md)
Blocked by: 02

모달 안에서 `전체 / 초과만` 을 토글합니다. 기본은 **전체** 입니다 (D1). 그리고
초과 개수 옆에 그 판정의 기준선(중앙값 · 문턱)을 둡니다 — 지금은 "40 point 인데
왜 초과가 아닌가" 를 답해 줄 숫자가 화면에 없습니다.

**Files:**

- Modify: `front-dev-home/app/components/cdsem/comparison/LotDetailModal.vue`
  (44-67 헤더 메타줄, 107-159 recipe 헤더줄, 224-229 빈 상태, script 전반)
- Modify: `front-dev-home/app/utils/lotParamExport.ts` (71-74)
- Modify: `front-dev-home/app/utils/lotParamExport.test.ts` (파일 끝에 추가)

**Interfaces:**

- Consumes: `filterStepOutliers`, `flaggedStepCount`, `StepFilter` (01)
- Produces:
  - `LotDetailModal.vue` 의 `filter` 모델 — `defineModel<StepFilter>('filter', { default: 'all' })`
  - `LotDetailModal.vue` 의 새 prop `outlier: DeviceOutlierResult | null`
  - `lotParamFileName(lotCd, bucket, flagged?)`

---

- [ ] **Step 1: 파일 이름의 실패하는 테스트를 먼저 쓴다**

`app/utils/lotParamExport.test.ts` 끝에 붙입니다:

```ts
test('초과만 상태의 내보내기는 파일 이름으로 구별된다', () => {
  // 같은 lot·같은 버킷에서 두 번 내려받으면 전체 파일과 초과 파일이 한
  // 폴더에 섞입니다. 행 수는 파일을 열어야 보이므로 이름이 말해야 합니다.
  assert.equal(lotParamFileName('R123', 'only_normal_summary'), 'R123_only_normal_params.csv')
  assert.equal(lotParamFileName('R123', 'only_normal_summary', true), 'R123_only_normal_params_flagged.csv')
  assert.equal(lotParamFileName('R123', 'only_normal_summary', false), 'R123_only_normal_params.csv')
})
```

- [ ] **Step 2: 실패를 확인한다**

Run: `npm test 2>&1 | tail -20`
Expected: FAIL — `'R123_only_normal_params.csv' !== 'R123_only_normal_params_flagged.csv'`

- [ ] **Step 3: `lotParamFileName` 을 고친다**

`app/utils/lotParamExport.ts` 71-74행을 바꿉니다:

```ts
/**
 * 내보내기 파일 이름. `flagged` 는 화면이 초과만 보여 주는 상태에서 받은
 * 파일이라는 표시입니다 — 행 수는 파일을 열어야 보이므로 이름이 말합니다.
 */
export const lotParamFileName = (lotCd: string, bucket: string, flagged = false): string => {
  const safe = (value: string) => (value || 'unknown').replace(/[^\w.-]+/g, '_')
  const suffix = flagged ? '_flagged' : ''
  return `${safe(lotCd)}_${safe(bucket.replace(/_summary$/, ''))}_params${suffix}.csv`
}
```

- [ ] **Step 4: 통과를 확인한다**

Run: `npm test 2>&1 | tail -10`
Expected: 전부 pass

- [ ] **Step 5: 모달에 필터 모델과 기준선 prop 을 더한다**

`LotDetailModal.vue` `<script setup>`:

```ts
import { filterStepOutliers, flaggedStepCount, type StepFilter } from '~/utils/lotOutlierSteps'
import type { DeviceOutlierResult } from '~/utils/outlierDetect'
```

props 에 (02 에서 더한 `drill` 아래):

```ts
  /** 이 lot 의 중앙값·문턱·초과 총계. 초과 개수와 그 기준선은 같은 화면에 있어야 합니다. */
  outlier: DeviceOutlierResult | null
```

모델과 파생값 (02 의 `stepCards` 아래):

```ts
// 필터는 **페이지가 갖습니다**. 진입점이 초기 상태를 정하기 때문입니다 — 행을
// 누르면 전체, outlier 배지를 누르면 초과만 (D1). 모달이 자기 안에 두면 배지로
// 들어온 사람에게 한 번 더 클릭을 시키게 됩니다.
const filter = defineModel<StepFilter>('filter', { default: 'all' })

const visibleCards = computed(() => filterStepOutliers(stepCards.value, filter.value))
const flaggedCards = computed(() => flaggedStepCount(stepCards.value))

const filterOptions = [
  { label: '전체', value: 'all' },
  { label: '초과만', value: 'flagged' }
] as const satisfies readonly { label: string, value: StepFilter }[]
```

02 의 카드 루프에서 `stepCards` 를 `visibleCards` 로 바꿉니다 (`v-if` 도 함께).

- [ ] **Step 6: 헤더에 기준선을 넣는다**

`LotDetailModal.vue` 44-67행 메타줄의 `recipeRatio` 항목 뒤에 더합니다:

```vue
              <span
                v-if="outlier && outlier.outlier_count > 0"
                class="sk-field-label"
              >
                {{ text.outlierCount }}
                <span class="sk-field-value font-semibold text-rose-700 dark:text-rose-300">{{ outlier.outlier_count }}</span>
              </span>
              <span
                v-if="outlier && outlier.median > 0"
                class="sk-field-label"
                :title="text.baselineHint"
              >
                {{ text.baseline }}
                <span class="sk-field-value">{{ outlier.median }} · &gt; {{ outlier.threshold }}</span>
              </span>
```

`text` 상수에 더합니다:

```ts
  outlierCount: '과다 측정',
  baseline: '중앙값 · 문턱',
  baselineHint: '이 디바이스가 이 버킷에서 재는 모든 파라미터 point 수의 중앙값과, '
    + '그 2배인 초과 문턱입니다. CDU 계열·FULL/HALF/MTX job 과 선두 Dummy/Align 파라미터는 '
    + '기준선에서도 초과 판정에서도 빠집니다.',
  filterLabel: 'recipe 필터',
  emptyFlagged: '이 lot 에는 초과로 잡힌 recipe 가 없습니다.',
```

**총계는 `outlier.outlier_count` 입니다.** 카드 배지를 더하지 마십시오 — 한
recipe 가 여러 스텝에서 돌면 중복 집계됩니다 (D2).

- [ ] **Step 7: 정렬 칩 옆에 필터 칩을 놓는다**

`LotDetailModal.vue` 119행 `<div class="ml-auto flex items-center gap-2">` 안,
정렬 `role="radiogroup"` **앞**에 넣습니다. 초과가 없는 lot 에서는 아예 그리지
않습니다 — 눌러도 빈 목록만 나오는 칩이기 때문입니다.

```vue
              <div
                v-if="flaggedCards > 0"
                role="radiogroup"
                :aria-label="text.filterLabel"
                class="flex items-center gap-1.5"
              >
                <button
                  v-for="option in filterOptions"
                  :key="option.value"
                  type="button"
                  role="radio"
                  :aria-checked="filter === option.value"
                  :class="[CHIP_BASE, chipClass(filter === option.value)]"
                  @click="filter = option.value"
                >
                  {{ option.label }}
                  <span
                    v-if="option.value === 'flagged'"
                    class="tabular-nums opacity-70"
                  >{{ flaggedCards }}</span>
                </button>
              </div>
```

- [ ] **Step 8: 빈 상태와 건수 표시를 필터에 맞춘다**

113행의 `{{ lotRecipes.length }}건` 을 다음으로 바꿉니다 — 필터가 걸린 상태에서
전체 건수를 말하면 화면과 숫자가 어긋납니다.

```vue
            <span class="sk-field-label">{{ visibleCards.length }}건</span>
```

224-229행의 빈 상태를 바꿉니다:

```vue
          <p
            v-else
            class="py-2 text-center sk-body text-(--sk-ink-muted)"
          >
            {{ filter === 'flagged' ? text.emptyFlagged : text.recipeEmpty }}
          </p>
```

- [ ] **Step 9: 내보내기를 화면에 맞춘다**

352행의 `paramRows` 와 359행의 `downloadParamTable` 을 바꿉니다. 정렬 칩이
파일 순서를 바꾸는 것과 같은 규약입니다 (D4).

```ts
// 파일은 화면이 보여 주는 것을 그대로 담습니다 — 정렬도, 필터도. 버튼 옆의
// `N행` 이 무엇을 받는지 미리 말해 주고, 파일 이름의 _flagged 가 받은 뒤에도
// 말해 줍니다.
const paramRows = computed(() =>
  buildLotParamRows(visibleCards.value.map(card => card.step), props.recipeParams)
)
```

```ts
const downloadParamTable = () => {
  if (!props.row) return
  downloadCsv(
    lotParamFileName(props.row.lot_cd, props.bucket, filter.value === 'flagged'),
    headers,
    paramRows.value
  )
}
```

- [ ] **Step 10: 호출처가 컴파일되게 prop 을 넘긴다**

`comparison.vue` 의 모달 태그에 더합니다 (배선은 04):

```vue
          :outlier="selectedLotRow ? deviceOutliers.get(selectedLotRow.lot_cd) ?? null : null"
```

- [ ] **Step 11: 정적 게이트**

Run: `npm run typecheck && npm run lint && npm test 2>&1 | tail -5`
Expected: 셋 다 clean

- [ ] **Step 12: 커밋**

```bash
git commit -- front-dev-home/app/components/cdsem/comparison/LotDetailModal.vue \
  front-dev-home/app/utils/lotParamExport.ts \
  front-dev-home/app/utils/lotParamExport.test.ts \
  front-dev-home/app/pages/ebeam/cd-sem/device-statistics/comparison.vue \
  -m "feat(device-statistics): add 전체/초과만 filter and outlier baseline to lot modal

기본은 전체이고 초과만은 토글입니다 — 이 목록을 여는 질문이 '이 device 가
공정을 따라가며 무엇을 재는가' 라서 기본 정렬이 공정순인 것과 같은 이유입니다.
중앙값·문턱을 초과 개수 옆에 두어 '40 point 인데 왜 초과가 아닌가' 를 같은
화면에서 답합니다. 내보내기는 화면을 따라가고 파일 이름에 _flagged 가 붙습니다."
```
