# 디바이스 통계 구현 계획

## 목적

CD-SEM `디바이스 통계` 탭에서 R3 / M-fab의 lot 단위 디바이스 목록을 조회하고, 선택한 lot에 대해 recipe 파라미터 분포와 운용 레시피수를 분석합니다. Phase 1에서는 Flask mock backend(`back_dev_home/ebeam/cdsem/device_statistics/`)가 모든 데이터를 in-memory 로 생성합니다.

## 현재 구성 한눈에 보기

| 파일 | 역할 |
| --- | --- |
| `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/index.vue` | 디바이스 선택 화면 (Step 1 ~ 3) |
| `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/comparison.vue` | 선택된 lot 분석 화면 (요약 + 트렌드) |
| `front-dev-home/app/composables/useDeviceStatisticsApi.ts` | `r3-device-grp`, `device-desc` fetcher |
| `front-dev-home/app/composables/useRecipeStatisticsApi.ts` | `recipe-statistics`, `recipe-trend` fetcher + bucket 타입 |
| `front-dev-home/app/composables/useDeviceCart.ts` | 두 페이지가 공유하는 lot 카트 (useState + localStorage) |
| `front-dev-home/app/composables/useDevicePresets.ts` | lot 묶음 프리셋 저장/적용 |
| `front-dev-home/app/components/ebeam/CompareCart.vue` | Step 3 카트 UI (선택 탭 / 프리셋 탭) |
| `front-dev-home/app/components/ebeam/CompareDeviceChips.vue` | 분석 화면 상단 lot chip strip |
| `front-dev-home/app/components/ebeam/CompareTrendCharts.vue` | 기간별 트렌드 차트 (날짜 범위 + 표시 필터) |
| `front-dev-home/app/components/ebeam/RecipeDetailSlideover.vue` | lot 클릭 시 recipe 상세 패널 |
| `back_dev_home/ebeam/cdsem/device_statistics/routes.py` | 4개 endpoint 등록 |
| `back_dev_home/ebeam/cdsem/device_statistics/data.py` | `R3DeviceGrpRow`, `DeviceDescRow` 생성 및 공개 표면 |
| `back_dev_home/ebeam/cdsem/device_statistics/statistics.py` | recipe summary / trend mock (data.py 가 재노출) |

라우팅은 `FeatureTabs.vue`의 `device-statistics` 항목이 `cd-sem` toolType에서만 노출되며, 분석 화면은 같은 폴더의 하위 page 라우트라 URL은 `/ebeam/cd-sem/device-statistics`와 `/ebeam/cd-sem/device-statistics/comparison` 두 개입니다. route 파일명은 `comparison.vue`이지만 사용자에게는 단일 lot 분석과 여러 lot 비교를 모두 포함하는 `디바이스 분석` 화면으로 표현합니다. 두 페이지 모두 `definePageMeta({ hideFabSidebar: true })`로 fab 사이드바를 숨겨 디바이스 선택에 집중하도록 합니다.

## 페이지 흐름

1. 사용자가 `디바이스 통계` 탭을 누르면 `index.vue`가 로드됩니다.
2. `index.vue`는 Step 1 ~ Step 3을 한 화면에 보여 줍니다.
    - **Step 1 — 빠른 필터**: `selectedFab`이 `R3`면 `prod_catg_cd` chip + `lot_cd` chip strip(검색창 포함), `M*`이면 `tech_nm` chip strip(검색창 포함)을 노출합니다. chip strip은 `STEP1_LOT_CHIP_BUDGET=24` 한도로 잘라 보여 주고 초과분은 `+N`으로 표시합니다.
    - **Step 2 — 디바이스 선택**: `UTable`로 정렬·검색·CSV 다운로드·페이지네이션(25/50/100)을 제공합니다. 체크박스로 행 단위 선택, 헤더 체크박스로 페이지 단위 토글이 가능합니다.
    - **Step 3 — 분석 + 이동(`CompareCart.vue`)**: 선택된 lot 목록과 프리셋 탭을 보여 주고, CTA(`디바이스 분석 보기` / `N개 분석 페이지로`)를 누르면 `proceed` 이벤트가 발생해 `comparison.vue`로 navigate 합니다. 프리셋 적용 시에는 `applyPreset` 이벤트가 호출되어 fab 전환 후 누락 lot을 toast로 알려 줍니다.
3. `comparison.vue`는 `useDeviceCart`에서 `selectedDeviceLots`를 그대로 읽어 `/api/cdsem/device-statistics/recipe-statistics`를 호출합니다. 1개 lot만 선택해도 단일 lot 분석 화면으로 동작하고, 2개 이상이면 여러 lot을 나란히 비교하는 분석 화면이 됩니다.
    - 상단: `bucket` 라디오(`all_summary` / `only_normal_summary` / `mother_normal_summary` / `only_sample_summary`)와 `sort` 라디오(이름순 / 파라미터 / 운용 레시피수).
    - 메인: `CompareDeviceChips`로 lot 칩, ECharts 두 패널(파라미터 스택 + 운용 레시피수, 평균/±1σ markLine 포함).
    - 하단: `CompareTrendCharts`가 `/recipe-trend`를 호출해 날짜 범위·표시 필터(전체 / 상위 N개 등) 기반 시계열 차트를 그립니다.
    - lot chip이나 막대 클릭 시 `RecipeDetailSlideover`가 열려 해당 lot의 recipe-info row를 보여 줍니다.
4. `돌아가기` 버튼은 `/ebeam/cd-sem/device-statistics`로 navigate 합니다. 카트는 그대로 유지되어 같은 선택으로 재진입할 수 있습니다.

## 상태 흐름

- **Fab 선택 (`selectedFab`)**: `localStorage` key `skewnono:deviceStatistics.selectedFab`. 기본값은 `R3`.
- **빠른 필터 선택**: `selectedProdCategories`, `selectedLots`, `selectedTechs`도 각각 localStorage에 persist 합니다. fab 전환 후 backend 응답이 도착하면 현재 옵션과 교집합만 남기도록 `syncSelectionWithOptions`로 prune 합니다 (단, 빠른 R3↔M 왕복 보존을 위해 R3 옵션은 R3일 때만, tech_nm은 M-fab일 때만 prune).
- **카트 (`useDeviceCart`)**: `useState('device-cart:selectedLots')` + localStorage key `skewnono:deviceStatistics.selectedDeviceLots`. persistence watcher는 `effectScope(true)`에 등록되어 페이지 unmount에도 살아남습니다.
- **fab 전환 시 카트**: `watch(selectedFab)`가 카트를 비웁니다. fab은 1개 단위로 다루는 UI이므로 다른 fab의 lot을 carry over 하지 않습니다. 초기 로드 시 카트와 옵션 불일치는 `[sortedRows, pending]` watcher가 정리합니다.
- **프리셋 (`useDevicePresets`)**: 같은 패턴으로 `skewnono:deviceStatistics.presets`에 저장. preset에는 `fab`이 함께 저장되어 적용 시 자동으로 fab을 전환합니다. 적용 후 누락된 lot이 있으면 `useToast`로 안내합니다.

## API 구성

`back_dev_home/__init__.py`가 `cdsem_device_statistics` blueprint를 `/api` 아래에 등록합니다. 모든 endpoint는 `data.py`의 함수만 호출하므로 office 환경에서는 `data.py`만 교체하면 됩니다.

| Method | Path | Query | 반환 |
| --- | --- | --- | --- |
| GET | `/api/cdsem/device-statistics/r3-device-grp` | 없음 | R3 lot 2,000 row |
| GET | `/api/cdsem/device-statistics/device-desc` | `fac_id` (comma-separated, optional) | M-fab lot row (필터 적용) |
| GET | `/api/cdsem/device-statistics/recipe-statistics` | `lot_cds` (comma-separated, required) | `{ date, buckets }` 최신 1주차 요약 + recipe info |
| GET | `/api/cdsem/device-statistics/recipe-trend` | `lot_cds`, `start_date?`, `end_date?` | `{ dates, trend }` 주차별 summary buckets |

응답 형식과 enum은 `docs/api-contracts/cdsem-device-statistics.yaml`에 고정되어 있습니다. 통계 endpoint는 `get_weekly_trend_data`가 생성한 결과를 그대로 분기해 사용하므로 같은 ISO 날짜 + lot 조합은 항상 같은 값을 반환합니다 (`_seed_for(lot_cd, point_index)` 기준 결정적).

## Mock 데이터 기준

- `r3_device_grp`는 fab `R3` 전용, 2,000 row를 `_generate_r3_device_grp`가 `random.Random(20260426)` 시드로 1회 생성합니다.
- `device_desc`는 fab `M11`, `M12`, `M14`, `M15`, `M16`을 균등 분배하여 총 2,000 row(`M_ROW_COUNT // 5 = 400 row/fab`)를 `random.Random(20260427)`으로 생성합니다.
- 모든 도메인 컬럼 값은 string이며, 빈 값은 `""`로 채웁니다.
- R 계열은 `fac_id -> prod_catg_cd -> lot_cd` 순서로 탐색합니다.
- M 계열은 `fac_id -> tech_nm` 순서로 탐색합니다.
- `lot_cd`는 R 계열이 `R<base36 3-digit>`, M 계열이 `<fac-prefix><base36 2 or 3-digit>` 형식이며 카트·preset·통계 endpoint의 join key로 사용됩니다.

## 검증 계획

- `GET /api/cdsem/device-statistics/r3-device-grp`가 2,000개 R3 row를 반환하는지 확인합니다.
- `GET /api/cdsem/device-statistics/device-desc?fac_id=M11,M14`가 해당 두 fab row만 반환하는지 확인합니다.
- `GET /api/cdsem/device-statistics/recipe-statistics?lot_cds=R001,R002`가 `date`와 `buckets` 4개 summary + 4개 recipe-info를 반환하는지 확인합니다.
- `GET /api/cdsem/device-statistics/recipe-trend?lot_cds=R001&start_date=...`가 `dates`와 `trend`만 반환하고 recipe-info를 포함하지 않는지 확인합니다.
- `front-dev-home/`에서 `npm.cmd run lint`와 `npm.cmd run typecheck`를 실행합니다.
- repo root에서 `npm.cmd run lint:md`를 실행합니다.
