# 「오늘 데이터」 토글을 페이지 헤더로 승격

Status: shipped
브라우저 확인: 2026-08-11 (M14A HV-SEM, 3탭 × 3모드)
작성일: 2026-08-11

## 배경

`recipe-status` 페이지의 세 탭(TAT / Align / Meas)은 각각 세 개의 뷰 모드를
가집니다 — 전체 요약 / 디바이스별 / 장비별.

「오늘 데이터」 토글(`includeToday`)은 `RecipeStatusView.vue`가 소유하고
`RecipeTatView` · `FailIssueView`에 내려주지만, 정작 스위치 위젯은 **일별 추이
차트 카드의 헤더 안**에 박혀 있습니다.

- `RecipeTatView.vue` — 트렌드 카드 헤더에 1개
- `FailIssueView.vue` — align 카드와 meas 카드에 각각 1개, 총 2개

이 배치가 만드는 문제는 두 가지입니다.

1. **찾기 어렵습니다.** 페이지 전체의 데이터 기간에 관한 설정인데 특정 차트의
   옵션처럼 보입니다. 뷰 모드를 바꾸면 위치가 달라지거나 사라집니다.
2. **장비별에는 아예 없습니다.** 전체 요약과 디바이스별은 같은
   `<template v-else>` 본문을 공유해서 우연히 둘 다 동작하지만, 장비별은
   `EbeamRecipeTatEquipmentView` / `EbeamFailIssueEquipmentView`라는 별도
   컴포넌트 트리라 `includeToday`가 도달하지 못합니다. 그 트리의 비교 패널에도
   일별 추이 차트가 있는데 오늘 데이터가 항상 포함됩니다.

## 목표

- 토글을 **「데이터 기준」 배지 바로 옆**, 페이지 헤더 한 곳으로 옮깁니다.
- 세 탭(TAT / Align / Meas) × 세 뷰 모드(전체 요약 / 디바이스별 / 장비별)
  **전부**에서 같은 자리에 보이고 같은 상태를 공유합니다.
- 장비별 비교 패널의 일별 추이 차트가 실제로 토글을 따르게 배선합니다.

## 범위 밖 (Non-goals)

- **백엔드 변경 없음.** 토글은 이미 받아온 응답을 프런트에서 거르는
  표시 옵션이며, `end_date`를 흔들어 서버를 재조회하지 않습니다.
- **차트 이외의 것은 거르지 않습니다.** 요약 숫자, 랭킹 표, 플릿 표,
  레시피 매트릭스는 전 기간 데이터를 그대로 유지합니다.
- **Excel 내보내기 무변경.** 장비별 워크북의 「일별추이」 시트는 토글과
  무관하게 전 기간을 담습니다. 한 파일 안에서 시트마다 기준일이 달라지는
  쪽이 더 나쁜 거짓말이기 때문입니다.
- **지속성 무변경.** `includeToday`는 지금처럼 `ref(false)`로 남아 페이지
  방문 단위로만 유지되고 새로고침 시 리셋됩니다.

## 설계

### 1. 새 위치 — MetaBar의 `#actions` 슬롯

`EbeamMetaBar`는 **손대지 않습니다.** 오른쪽 클러스터가 이미

```text
[stats] → [EbeamDataFreshness] → <slot name="actions" />
```

순서라, `#actions`에 스위치를 넣으면 그대로 「데이터 기준」 배지 오른쪽에
붙습니다. `RecipeTatView` · `FailIssueView` 둘 다 현재 이 슬롯을 쓰지 않아
충돌이 없습니다.

```text
[Recipe TAT] │ [전체요약|디바이스별|장비별] [기간▾] … [◉ 데이터 기준 07-28 · 1시간 주기] [오늘 데이터 ⬤]
```

토글은 뷰 모드 · 로딩 · 빈 상태와 무관하게 **항상** 렌더합니다. 헤더 요소가
상태에 따라 나타났다 사라지면 그 줄의 폭이 흔들립니다.

기존 스위치 3개(`RecipeTatView` 1개, `FailIssueView` 2개)는 카드 헤더에서
제거하고 제목만 남깁니다.

### 2. 장비별 배선

`anchor_date`는 `summary`에 있고, `summary`는 뷰 모드와 무관하게 페치되므로
prop 두 개를 내려보내면 됩니다.

```text
RecipeTatView (summary.anchor_date, includeToday)
  └─ RecipeTatEquipmentView       :anchor-date :include-today   ← 통과만
       └─ RecipeTatEquipmentCompare                              ← 여기서 필터
```

FailIssue 쪽도 같은 모양입니다.

비교 패널에 `visibleTrends` computed를 하나 두고, x축 `dates`와 `series`
**둘 다** 거기서 파생시킵니다.

```ts
const visibleTrends = computed(() => trends.value.map(series => ({
  ...series,
  points: filterRecipeStatusTrendPoints(series.points, props.anchorDate, props.includeToday)
})))
```

지금 코드는 `dates`를 `trends.value[0]?.points`에서 따로 뽑습니다. 그대로 두고
시리즈만 거르면 **축과 데이터가 하루씩 어긋납니다** — 두 곳 모두
`visibleTrends`를 보게 하는 것이 이 변경의 핵심입니다.

`emit('loaded', …)`는 필터 이전의 `data`를 그대로 올려보내므로 Excel은
영향받지 않습니다(Non-goals).

### 3. 필터 함수

`utils/recipeStatusTrend.ts`의 `filterRecipeStatusTrendPoints`를 그대로
재사용합니다. 로직 변경 없음, 호출 지점만 늘어납니다.

## 변경 파일

| 파일 | 변경 |
| --- | --- |
| `components/ebeam/RecipeTatView.vue` | 스위치를 카드→`#actions`로 이동, 장비별에 prop 2개 전달 |
| `components/ebeam/FailIssueView.vue` | 스위치 2개 제거 후 `#actions`에 1개, 장비별에 prop 2개 전달 |
| `components/ebeam/RecipeTatEquipmentView.vue` | prop 2개 받아 비교 패널로 통과 |
| `components/ebeam/FailIssueEquipmentView.vue` | 위와 동일 |
| `components/ebeam/RecipeTatEquipmentCompare.vue` | `visibleTrends`로 축·시리즈 필터 |
| `components/ebeam/FailIssueEquipmentCompare.vue` | 위와 동일 |

`EbeamMetaBar`, `EbeamDataFreshness`, `utils/recipeStatusTrend.ts`,
`utils/equipmentExport.ts`, 백엔드는 **무변경**입니다.

## 검증

변경이 전부 `.vue` 배선이고 이 저장소에는 컴포넌트 마운트 하네스가 없으므로
**새 단위 테스트는 생기지 않습니다.** `recipeStatusTrend.test.ts`가 이미
필터 함수를 덮고 있고 그 로직은 바뀌지 않습니다.

정적 게이트: `npm run lint`, `npm run typecheck`, `npm test`.

브라우저 확인(`verify` 스킬):

- TAT / Align / Meas 3탭 × 전체요약 · 디바이스별 · 장비별 3모드 = 9개 화면에서
  토글이 「데이터 기준」 옆 같은 자리에 보이는지
- 탭·모드를 오가도 토글 상태가 유지되는지 (`RecipeStatusView`가 소유)
- 장비 2대 선택 후 토글 → 비교 차트의 마지막 날짜 점이 사라지고 x축 라벨
  개수도 함께 줄어드는지
- 장비별 Excel 「일별추이」 시트는 토글과 무관하게 전 기간인지
- 콘솔 에러 0
