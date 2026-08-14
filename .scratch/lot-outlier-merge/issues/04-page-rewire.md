# 04 — outlier 배지를 모달로 돌리고 슬라이드오버를 뗀다

Status: resolved
Plan: [`../plan.md`](../plan.md) · Spec: [`../spec.md`](../spec.md)
Blocked by: 03

표의 outlier 배지가 슬라이드오버 대신 **같은 모달**을 `초과만` 으로 엽니다.
이 티켓이 끝나면 디바이스 비교 페이지에 오버레이는 하나뿐입니다.

`DrillSlideover.vue` 도 `deviceDrill.ts` 도 지우지 않습니다 —
`components/ebeam/rules/ComplianceTable.vue:82` 가 cap 위반 쪽에서 계속 쓰고,
`toOutlierDrill` 은 모달이 계속 씁니다 (D3).

**Files:**

- Modify: `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/comparison.vue`
  (204-216 오버레이, 637-674 핸들러, 232-233 import)
- Modify: `front-dev-home/app/components/cdsem/comparison/LotTable.vue`
  (408-409 안내 문구)

**Interfaces:**

- Consumes: `LotDetailModal` 의 `drill` · `outlier` prop 과 `filter` 모델 (02·03)
- Produces: 없음 — 이 티켓 뒤로 `comparison.vue` 는 `drillOpen` / `activeDrill`
  을 갖지 않습니다.

**단위 테스트가 없는 티켓입니다.** 페이지 배선이라 순수 함수로 뺄 것이 없습니다.
검증은 타입체크 + 린트 + 05 의 브라우저 확인입니다.

---

- [ ] **Step 1: 모달 태그를 완성하고 슬라이드오버를 걷어낸다**

`comparison.vue` 204-216행을 다음으로 바꿉니다:

```vue
        <CdsemComparisonLotDetailModal
          v-model:open="lotModalOpen"
          v-model:filter="lotModalFilter"
          :row="selectedLotRow"
          :bucket="selectedBucket"
          :recipe-rows="recipeRowsForBucket"
          :recipe-params="selectedLotParams"
          :drill="selectedLotDrill"
          :outlier="selectedLotOutlier"
          :trend="trend ?? null"
        />
```

`<EbeamDevstatDrillSlideover ... />` 블록은 지웁니다.

- [ ] **Step 2: 핸들러를 바꾼다**

637-674행을 다음으로 바꿉니다:

```ts
const lotModalOpen = ref(false)
const selectedLotRow = ref<HealthAugmentedRow | null>(null)

// 필터의 초기 상태를 **진입점이** 정합니다 (D1). 행을 눌러 들어온 사람은 "이
// device 가 무엇을 재는가" 를 물었고, outlier 배지를 눌러 들어온 사람은 "무엇이
// 규칙을 어겼는가" 를 물었습니다 — 클릭이 이미 말한 것을 화면이 되묻지 않습니다.
const lotModalFilter = ref<StepFilter>('all')

const openLotDetail = (row: HealthAugmentedRow) => {
  selectedLotRow.value = row
  lotModalFilter.value = 'all'
  lotModalOpen.value = true
}

// 표의 outlier 배지. 예전에는 별도 슬라이드오버를 열었습니다 — 같은 lot 의 같은
// 버킷 범위의 같은 recipe 를 다른 열로 한 번 더 그리는 화면이라, 스텝과 초과
// recipe 를 대조하려면 두 오버레이를 왕복해야 했습니다.
const openLotOutliers = (lot_cd: string) => {
  const row = profiledRows.value.find(r => r.lot_cd === lot_cd)
  if (!row) return
  selectedLotRow.value = row
  lotModalFilter.value = 'flagged'
  lotModalOpen.value = true
}

// 모달의 CSV 내보내기가 쓰는 파라미터. 이미 버킷 범위로 좁혀진 recipesByLot 에서
// 꺼내므로, 파일이 화면의 health·outlier 와 다른 모집단을 말할 수 없습니다.
const selectedLotParams = computed<RecipeInput[]>(() => {
  const lotCd = selectedLotRow.value?.lot_cd
  return lotCd ? recipesByLot.value.get(lotCd) ?? [] : []
})

const selectedLotOutlier = computed(() => {
  const lotCd = selectedLotRow.value?.lot_cd
  return lotCd ? deviceOutliers.value.get(lotCd) ?? null : null
})

// 모달이 그리는 outlier. 슬라이드오버가 쓰던 것과 **같은 어댑터**입니다 —
// 분석 제외 꼬리표 두 층과 dropLeadingHelperParams 정합성이 여기 들어 있고
// utils/deviceDrill.test.ts 가 그것을 지킵니다.
const selectedLotDrill = computed<DrillDevice | null>(() => {
  const lotCd = selectedLotRow.value?.lot_cd
  if (!lotCd) return null
  const recipes = recipesByLot.value.get(lotCd) ?? []
  const result = selectedLotOutlier.value
  return result ? toOutlierDrill(lotCd, recipes[0]?.ctn_desc ?? '', recipes, result) : null
})

// 버킷이 바뀌면 열려 있던 모달을 닫습니다 — 중앙값·초과까지 버킷 범위로
// 계산하므로(2026-08-04) 열어 둔 채로 두면 이전 버킷의 숫자를 계속 보여 줍니다.
watch(selectedBucket, () => {
  lotModalOpen.value = false
})
```

(02·03 에서 넣어 둔 `selectedLotDrill` / `selectedLotParams` 는 여기 판으로
대체됩니다 — 중복 선언이 남지 않게 하십시오.)

- [ ] **Step 3: import 를 맞춘다**

232-233행 근처:

```ts
import { toOutlierDrill, type DrillDevice } from '~/utils/deviceDrill'
import type { StepFilter } from '~/utils/lotOutlierSteps'
```

`toOutlierDrill` 은 계속 씁니다. 지우지 마십시오.

- [ ] **Step 4: 표의 이벤트 이름을 그대로 두고 수신부만 바꾼다**

201-202행:

```vue
          @select-lot="openLotDetail"
          @open-outliers="openLotOutliers"
```

`LotTable.vue` 는 마크업도 emit 이름도 손대지 않습니다 — 표는 "이 lot 의
outlier 를 보고 싶다" 고 말할 뿐, 그것을 무엇으로 여는지는 페이지의 결정입니다.

- [ ] **Step 5: 안내 문구를 사실에 맞춘다**

`LotTable.vue` 408-409행:

```ts
  subtitleCards: '카드를 클릭하면 recipe 상세와 추이를, outlier 를 클릭하면 같은 팝업이 초과 recipe 만 추려 열립니다.',
  subtitleTable: '행을 클릭하면 recipe 상세와 추이를, outlier 를 클릭하면 같은 팝업이 초과 recipe 만 추려 열립니다.',
```

- [ ] **Step 6: 슬라이드오버의 다른 호출처가 멀쩡한지 확인한다**

Run: `grep -rn "DrillSlideover" front-dev-home/app`
Expected: `components/ebeam/devstat/DrillSlideover.vue` 자신과
`components/ebeam/rules/ComplianceTable.vue` 두 곳만. `comparison.vue` 는 없어야
합니다.

- [ ] **Step 7: 정적 게이트**

Run: `npm run typecheck && npm run lint && npm test 2>&1 | tail -5`
Expected: 셋 다 clean. `toOutlierDrill` 미사용 경고가 없어야 합니다.

- [ ] **Step 8: 커밋**

```bash
git commit -- front-dev-home/app/pages/ebeam/cd-sem/device-statistics/comparison.vue \
  front-dev-home/app/components/cdsem/comparison/LotTable.vue \
  -m "feat(device-statistics): outlier badge opens the lot modal, not a slideover

같은 lot 의 같은 버킷을 두 오버레이가 나눠 그리던 것을 하나로 합칩니다. 배지는
모달을 '초과만' 으로 열고, 행 클릭은 '전체' 로 엽니다 — 진입점이 필터의 초기
상태를 정합니다. DrillSlideover 와 deviceDrill 은 그대로 둡니다: 전자는
measurement-rules 의 cap 위반 쪽이 계속 쓰고, 후자는 이 모달이 계속 씁니다."
```
