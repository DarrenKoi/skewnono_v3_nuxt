# Recipe Compare 개선 — 설계 (Design)

- **Date:** 2026-06-14
- **Status:** 구현 완료 (Implemented), E2E 검증 완료
- **관련:** [[2026-06-14-recipe-comparison-design]] (compare 뷰 본체), [[2026-06-14-recipe-switcher-design]]
- **대상 화면:** `ebeam/<tool>/<fab>/recipe-search/compare` (`RecipeCompareView.vue`)

---

## 1. 목적 (Purpose)

Recipe 비교 화면(`recipe-search/compare`)에 대한 세 가지 사용성 개선입니다.

1. **"+recipe 추가" 인라인 입력 제거** — set bar 안의 인라인 검색/자동완성으로 비교 대상을 추가하는 UI를 없앱니다.
2. **"Recipe 검색으로" 돌아가기 버튼 추가** — 비교 대상을 더 넣고 싶을 때 검색 페이지로 돌아가도록 안내합니다. (추가/제거는 검색 페이지의 체크박스로 일원화.)
3. **Excel 다운로드 시 셀 이미지 삽입** — 현재 화면(활성 슬롯 + 활성 파라미터)의 SEM 썸네일을 Excel 셀에 실제 이미지로 넣습니다.

---

## 2. 배경 제약 (Constraints discovered)

- **현재 Excel 엔진(SheetJS / `xlsx` 무료판)은 셀 이미지 삽입을 지원하지 않습니다.** 이미지 삽입에는 `exceljs`(무료, `worksheet.addImage`)가 필요합니다.
- **Phase 1 mock에는 실제 이미지 바이트가 없습니다.** 화면의 썸네일은 `EbeamRecipeOpenSemNoise`가 그리는 **절차적 SEM 노이즈 placeholder**이고, 데이터에는 파일명 문자열만 있습니다. (`recipeCompare.ts`의 `imageFilenames`는 파일명만 반환.)
- `SemNoise`의 텍스처는 `#23201B` 배경 + 고정 CSS 그라디언트로 **결정적·동일**합니다(파일명별 랜덤 아님). → canvas로 재현해 role별 1장씩만 만들어 재사용 가능.
- `buildCompareWorkbook`은 `node --test`로 검증되는 **순수 함수**입니다(65 cases). 이 함수의 시그니처·반환 구조는 바꾸지 않습니다.

---

## 3. 결정 사항 (Decisions)

| ID | 결정 |
| --- | --- |
| D1 | `RecipeSetBar.vue`의 인라인 "+recipe 추가" 입력·자동완성·관련 상태/emit/import를 제거한다. |
| D2 | chip의 remove(×) 버튼은 유지한다(비교 대상에서 제거는 그대로). |
| D3 | `RecipeSetBar`에 `backRoute: string` prop을 추가하고, "비교 대상 recipe" 레이블 옆에 outline back 버튼(`i-lucide-arrow-left`, "Recipe 검색")을 둔다. |
| D4 | 비교 Excel export만 `xlsx` → `exceljs`로 교체한다. `xlsx` 패키지는 제거하지 않는다(타 기능 영향 차단). |
| D5 | `buildCompareWorkbook`(순수)은 변경하지 않는다. 이미지/엔진 변경은 `downloadCompareWorkbook`(writer) 및 신규 브라우저 전용 헬퍼에 격리한다. |
| D6 | 이미지 PNG는 canvas로 `SemNoise` 텍스처를 재현한다. 활성 슬롯은 단일 role이므로 export당 PNG 1장만 만들어 recipe 셀들에 재사용한다(헬퍼는 role 인자로 ADDR/MEAS 모두 그릴 수 있음). 추가 의존성(html2canvas 등) 없음. |
| D7 | Excel 이미지 범위는 **활성 슬롯 + 활성 파라미터**의 한 행(recipe별 썸네일)만. 나머지 표(시트)는 기존대로 전체 유지. |
| D8 | 활성 슬롯에 해당하는 시트 상단(헤더 아래)에 이미지 블록을 삽입한다: `이미지 · <activeParam>` 레이블 행 + recipe 컬럼(C열~)에 anchor한 이미지 행 + 빈 행. |
| D9 | canvas/ExcelJS 코드는 단위 테스트하지 않는다. 검증은 typecheck + lint + Playwright(다운로드 산출물 확인). |

---

## 4. 컴포넌트 / 데이터 흐름

### 4.1 `RecipeSetBar.vue` (수정)

제거: 인라인 `<input type="search">` + 자동완성 드롭다운, `addQuery` ref, `suggestions` computed, `pick`, catalog `useAsyncData`, `add` emit, `useRecipeSearchApi` import.

추가: `backRoute: string` prop. 레이블 행에 back 버튼:

```vue
<UButton
  size="xs"
  color="neutral"
  variant="outline"
  icon="i-lucide-arrow-left"
  label="Recipe 검색"
  :to="backRoute"
/>
```

유지: `selected` chips + remove(×), `canExport` Excel 다운로드 버튼.

### 4.2 `RecipeCompareView.vue` (수정)

- `useRecipeSelectionSet`에서 `add` 구조분해 제거(remove는 유지).
- `EbeamRecipeCompareRecipeSetBar`에서 `@add` 바인딩 제거, `:back-route="backRoute"` 추가.
- `downloadExcel`가 `activeParam`·`activeSlot`을 writer에 전달.

### 4.3 `utils/recipeCompare.ts` (수정)

- `buildCompareWorkbook` — 변경 없음.
- `downloadCompareWorkbook` — ExcelJS 기반으로 재작성. 시그니처 확장:

```ts
async function downloadCompareWorkbook(
  workbook: CompareWorkbook,
  filename: string,
  imageBlock?: {
    sheetName: string        // 활성 슬롯의 stage 이름 (예: 'Measure 1')
    parameter: string        // 활성 파라미터
    images: (string | null)[] // recipe별 이미지 파일명(없으면 null) — 빈 셀 판정용
    pngDataUrl: string        // view(브라우저)에서 미리 렌더한 SEM 노이즈 PNG data URL
  }
): Promise<void>
```

동작: 각 `sheet.rows`를 `worksheet.addRow`로 기록. `imageBlock`이 있고 `sheet.name === imageBlock.sheetName`이면, 헤더 아래에 레이블 행 + 이미지 행 + 빈 행을 `spliceRows`로 삽입하고, `book.addImage({ base64: imageBlock.pngDataUrl, extension: 'png' })`로 한 번 등록한 이미지 id를 recipe 컬럼마다 `images[i]`가 non-null인 셀에 `worksheet.addImage`로 anchor(재사용). PNG 렌더(`renderSemNoisePng`)는 view에서 수행하고 writer는 받은 `pngDataUrl`만 사용한다(canvas 코드가 `node --test` 대상 `recipeCompare.ts`에 들어가지 않게).

### 4.4 신규 브라우저 전용 헬퍼 (canvas → PNG)

`utils/recipeCompare.ts`와 분리(순수성 보존). 위치 후보: 같은 파일 내 별도 함수지만 `node --test`에서 import되지 않게 하거나, 신규 `app/utils/semNoiseImage.ts`(브라우저 전용). **결정: 신규 `app/utils/semNoiseImage.ts`.**

```ts
// 브라우저 전용. node --test 대상 아님.
export function renderSemNoisePng(role: 'address' | 'measure', size = 180): string
```

내용: offscreen `<canvas>`에 `#23201B` 채우기 → 대각선 반복선(45° 밝은선, -30° 어두운선) → 두 개의 부드러운 radial 하이라이트 → 좌상단 MEAS/ADDR 뱃지. `canvas.toDataURL('image/png')` 반환. SemNoise CSS의 시각적 재현(픽셀 일치 아님).

---

## 5. 검증 (Testing)

- `node --test`(기존 `recipeCompare` 순수 함수 테스트) — 회귀 없음 확인.
- `nuxt typecheck` 클린.
- `npx eslint` 변경 파일 클린.
- `npm run lint:md`(이 문서 포함) 클린.
- Playwright E2E:
  1. compare 진입(working-set ≥ 2) → set bar에 "+recipe 추가" 입력 **없음**, "Recipe 검색" back 버튼 **있음**.
  2. back 버튼 클릭 → `recipe-search`로 이동.
  3. 활성 슬롯/파라미터 선택 후 Excel 다운로드 → `.xlsx` 생성. 파일 열어 활성 슬롯 시트 상단에 이미지가 삽입됐는지 확인(가능하면 ExcelJS로 재파싱하여 media 존재 검증).

---

## 6. 영향 범위 / 비범위 (Scope)

**범위:** `RecipeSetBar.vue`, `RecipeCompareView.vue`, `utils/recipeCompare.ts`, 신규 `utils/semNoiseImage.ts`, `exceljs` 의존성 추가.

**비범위:** 실제 이미지 바이트 백엔드 제공(office 단계), 전체 슬롯/파라미터 이미지 출력(D7로 활성 화면만), `xlsx` 제거, compare 외 다른 화면.
