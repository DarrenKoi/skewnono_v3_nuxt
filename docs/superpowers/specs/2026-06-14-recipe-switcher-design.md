# Recipe Switcher — 설계 (Design)

- **Date:** 2026-06-14
- **Status:** 설계 승인 대기 → 구현 예정
- **관련:** [[2026-06-14-recipe-comparison-design]] (작업 세트 `useRecipeSelectionSet` 의 fast-follow, 빌드 저널 §6.5)
- **승인된 접근:** Approach A — URL `recipe_name` 쿼리 구동 방식

---

## 1. 목적 (Purpose)

검색 페이지에서 **작업 세트(`useRecipeSelectionSet`)** 에 여러 recipe를 담은 뒤, 하단 트레이의
**열어보기 / 횡전개 / 측정이력** 버튼으로 진입하면, 해당 화면 상단에 작업 세트를 **탭**으로 띄워
recipe 사이를 전환할 수 있게 합니다. 현재는 세 버튼 모두 `selected[0]`(첫 번째) recipe 하나만 열며,
이 전환기는 그 보류분(빌드 저널 §6.5의 "recipe switcher")을 구현하는 것입니다.

**비교하기(`compare`)** 는 이미 세트 전체를 소비하므로 이 설계의 대상이 아닙니다.

## 2. 결정 사항 (Decisions)

| # | 질문 | 결정 |
| --- | --- | --- |
| D1 | 탭에 어떤 recipe가 보이나 | **진입 경로에 따라 다름.** 트레이 진입 → 작업 세트가 탭으로 표시. 행(行) 버튼 진입 → 탭 없음(기존 단일 화면 그대로). |
| D2 | 진입 경로 구분 방법 | 트레이 네비게이션에만 쿼리 플래그 `set=1` 을 부여. 행 버튼은 플래그 없음. |
| D3 | 탭 제거(×) 기능 | **없음.** 읽기 전용 전환기. 세트 편집(추가/제거)은 검색 페이지 트레이·비교 페이지에서만. |
| D4 | 전환 구동 방식 | Approach A — 탭 클릭이 `route.query.recipe_name` 을 재작성. 세 뷰가 이미 이 쿼리에 반응해 refetch. |
| D5 | 활성 탭 | `route.query.recipe_name` 과 이름이 일치하는 탭. |
| D6 | 컴포넌트 형태 | 세 뷰가 공유하는 단일 컴포넌트 1개(option 2). |
| D7 | 위치 | 각 뷰 본문 **최상단**(기존 헤더: 목록으로 버튼 + 제목 + 통계 **위**). |

## 3. 전제 (Verified premise)

`RecipeOpenView` · `RecipeLateralView` · `RecipeMeasHistView` 세 뷰 모두 동일 패턴입니다.

```ts
const recipeName = computed(() => readRecipeNameQuery(route))   // route.query.recipe_name
const cacheKey  = computed(() => `<view>:${toolType}:${fab||'ALL'}:${recipeName.value}`)
const { data, pending, error, refresh } = await useAsyncData(
  () => cacheKey.value,
  () => recipeName.value ? fetch(...) : Promise.resolve(null),
  { watch: [cacheKey], ... }
)
```

따라서 `recipe_name` 쿼리만 바꾸면 모든 뷰가 자동으로 데이터를 다시 불러오고, 뷰별 하위 상태(선택된 IDP
인덱스, 서브탭 등)는 기존 `watch(cacheKey)` 로직이 리셋합니다. **뷰의 데이터 패칭 코드는 손대지 않습니다.**

세 뷰 모두 `{ fab, toolLabel, toolType }` props 를 받습니다.

## 4. 컴포넌트 설계 (Component)

### `app/components/ebeam/RecipeSwitcher.vue`

- **Auto-import 이름:** `EbeamRecipeSwitcher` (폴더 접두사 규칙 — `ebeam/` → `Ebeam` 1회만).
- **Props:** `{ toolType: RecipeSearchToolType, fab: string }`.
- **Emits:** 없음 (라우터를 직접 조작).
- **의존:** `useRecipeSelectionSet(toolType, fab)`, `useRoute()`, `useRouter()`, `SkNavPill`.

**가시성 (자기 완결적).** 다음을 **모두** 만족할 때만 렌더, 아니면 아무것도 렌더하지 않음:

1. `route.query.set` 가 truthy(`'1'`), **그리고**
2. 작업 세트(`selected`) 길이 ≥ 2.

이 자기 완결성 덕분에 부모 뷰는 위치에 한 줄만 추가하면 되고, 단일 진입 화면은 오늘과 동일하게 보입니다.

**탭.** `selected`(삽입 순서)를 `SkNavPill` 로 렌더. `SkNavPill` 은 §3.5 **BLACK = NAVIGATE** 가족 —
탭 클릭이 "보는 대상"을 바꾸므로 nav 가 맞습니다. 긴 recipe id 는 잘라서 표시하고 `:title` 로 전체 노출.

```text
활성 탭:  name === route.query.recipe_name
```

**전환.** 탭 클릭 →

```ts
router.replace({ query: { ...route.query, recipe_name: name } })
```

- `replace` (not `push`): 뒤로가기 버튼이 탭 순환이 아니라 목록으로 향하도록.
- `set` 플래그를 포함한 기존 쿼리를 **보존**(`...route.query`).
- 활성 탭을 다시 눌러도 무해(같은 쿼리).

**엣지.** `recipe_name` 이 세트에 없으면(사용자가 URL 직접 편집 등) 활성 표시 없음 — 드문 경우, 허용.

## 5. 트레이 와이어링 (RecipeSearchView.vue)

세트 진입 핸들러 3개에 `set: '1'` 쿼리를 추가합니다. 행 버튼 핸들러는 **변경 없음**.

```ts
// 변경: 트레이 → 세트 모드 진입
const openSetDetail   = () => { if (firstSelected.value) router.push({ ...getRecipeDetailRoute(firstSelected.value), query: { recipe_name: firstSelected.value, set: '1' } }) }
const openSetLateral  = () => { if (firstSelected.value) router.push({ ...getLateralRoute(firstSelected.value),   query: { recipe_name: firstSelected.value, set: '1' } }) }
const openSetMeasHist = () => { if (firstSelected.value) router.push({ ...getMeasHistRoute(firstSelected.value),  query: { recipe_name: firstSelected.value, set: '1' } }) }
```

> 구현 시 `getRecipeDetailRoute` 등 헬퍼에 선택적 `extraQuery` 인자를 추가하는 방식으로 중복을 줄일 수 있습니다(구현 계획에서 확정).

초기 활성 탭은 기존과 동일하게 `firstSelected`. 세트가 1개뿐이면 §4 가시성 조건(≥2)에 막혀 전환기는 숨겨지고
단일 화면이 됩니다.

## 6. 뷰 통합 (View integration)

세 뷰(`RecipeOpenView`, `RecipeLateralView`, `RecipeMeasHistView`) 본문 최상단에 한 줄 추가:

```vue
<EbeamRecipeSwitcher :tool-type="toolType" :fab="fab" />
<!-- ↓ 기존 헤더(목록으로 + 제목 + 통계)와 본문은 그대로 -->
```

전환기가 자기 완결적으로 숨으므로 그 외 변경은 없습니다. 큰 제목(`<h1>`)은 활성 recipe를 그대로 반영합니다.

## 7. DESIGN.md 준수

- 탭: `SkNavPill` (NAVIGATE/BLACK, §3.5 / §7.0). `rounded-full`·이모지 금지(§3.6/§9) 준수.
- 라벨 한국어, 식별자 영어(§11). recipe id 는 데이터 값이므로 `--sk-ink` 계열(§3.7).
- `max-w-[1440px]`/`max-w-7xl` 등 각 뷰의 기존 컨테이너 폭 안쪽에 위치(§5).

## 8. 테스트 / 검증

- `nuxt typecheck` clean, `npm run lint` clean.
- Playwright E2E: 검색 → 2개+ 체크 → 트레이 **열어보기** → 상단 탭 표시 → 다른 탭 클릭 시 내용 교체 →
  **횡전개**·**측정이력** 동일 동작 확인 → 행 버튼 단일 진입 시 탭 미표시 확인 → 새로고침 후 탭 유지(세트는
  localStorage 영속) 확인.
- 순수 로직이 사실상 없으므로(쿼리 재작성) 별도 단위 테스트는 두지 않음. (repo 컨벤션: `.vue`/composable 은
  typecheck + E2E 로 검증.)

## 9. 범위 밖 (Out of scope / YAGNI)

- 탭에서의 세트 편집(추가/제거)·드래그 정렬.
- 비교 페이지 변경(이미 세트 전체 소비).
- 탭별 독립 스크롤 상태 보존 등 고급 상태 관리.

## 10. 영향 파일 (Touched files)

| 파일 | 변경 |
| --- | --- |
| `app/components/ebeam/RecipeSwitcher.vue` | **신규** — 공용 전환기. |
| `app/components/ebeam/RecipeSearchView.vue` | 트레이 세트 핸들러 3개에 `set=1` 추가. |
| `app/components/ebeam/RecipeOpenView.vue` | 본문 최상단 `<EbeamRecipeSwitcher>` 1줄. |
| `app/components/ebeam/RecipeLateralView.vue` | 동일 1줄. |
| `app/components/ebeam/RecipeMeasHistView.vue` | 동일 1줄. |
