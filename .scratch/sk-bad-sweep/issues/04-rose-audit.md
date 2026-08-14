# 04 — 남은 `rose-*` 를 뜻으로 분류한다 (조사만, 코드 변경 없음)

Status: open
Spec: [`../spec.md`](../spec.md) · 결정: D3

`front-dev-home/app` 에 `rose-*` 가 **22개 파일**에 있습니다. 이 스펙은 그중
device-statistics ↔ measurement-rules 드리프트만 고칩니다. 나머지를 손대기 전에
**빨강이 각 화면에서 무엇을 뜻하는지** 먼저 적습니다 — 뜻을 확인하지 않고 토큰으로
바꾸는 것은 색을 통일하는 게 아니라 의미를 지우는 것입니다.

**조사 대상 (건수순):**

```
8  components/ebeam/RecipeMeasHistView.vue
4  components/ebeam/RecipeOpenView.vue
4  components/ebeam/RecipeLateralView.vue
4  components/ebeam/recipeCompare/CompareGrouping.vue
4  components/ebeam/HardwareView.vue
3  components/ebeam/RecipeSearchView.vue
3  components/ebeam/RecipeCompareView.vue
2  utils/bmPmMarkers.ts
2  pages/ebeam/cd-sem/device-statistics/index.vue
2  pages/afm/[tool]/[filename].vue
2  pages/activity.vue
2  components/ebeam/StorageView.vue
2  components/ebeam/storage/PpidUnavailablePanel.vue
2  components/ebeam/skewvoir/FdcAnalysis.vue
2  components/ebeam/recipeOpen/ParamPanel.vue
2  components/ebeam/recipeOpen/AlignPopup.vue
2  components/ebeam/MeasurementRulesView.vue
1  components/ebeam/recipeCompare/CompareMatrix.vue
```

(`DrillSlideover` · `LotTable` 은 티켓 02·03 이 처리하고,
`ComplianceTable.vue:25` 와 `comparison.vue:114` 는 아래 참조.)

**각 사용처를 셋 중 하나로 분류합니다:**

| 분류 | 뜻 | 처리 |
| --- | --- | --- |
| 나쁨 | 오류·위반·비정상 상태 | `--sk-bad` 계열로 (후속 티켓) |
| 에러 메시지 줄 | 실패 안내 텍스트 | `DESIGN.md:62` 가 명시적으로 허용 — 그대로 |
| 그 외 | 단순 강조, 차트 계열, 브랜드 무관 장식 | 뜻을 적고 판단 보류 |

**이미 확인된 문서 불일치 하나:**

`DESIGN.md:62` 는 에러 텍스트를 `text-rose-600 dark:text-rose-400` 으로 적었지만
실제 코드는 `dark:text-rose-300` 을 씁니다 (`ComplianceTable.vue:25`,
`comparison.vue:114`). `CLAUDE.md` 규칙상 **코드가 고쳐지는 쪽**이므로 둘을
`rose-400` 으로 맞추거나, 300 이 의도된 값이라면 문서를 고칩니다. 어느 쪽인지는
다크 모드에서 눈으로 보고 정합니다.

**완료 조건:**

- 위 목록의 모든 사용처에 분류와 한 줄 근거가 이 파일에 적혀 있습니다.
- "나쁨" 으로 분류된 것들의 후속 티켓 범위가 정해졌습니다.
- **코드는 바뀌지 않습니다** — 문서 불일치 건 포함, 이 티켓은 조사입니다.
