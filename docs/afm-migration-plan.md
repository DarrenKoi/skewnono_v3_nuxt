# AFM Data Platform 통합 마이그레이션 계획

## 1. 개요

본 문서는 별도 URL에서 동작하는 `afm_data_platform/` (Vue 3 + Vuetify 3 + Flask) 애플리케이션을 SKEWNONO Nuxt 4 + Flask 통합 환경 (`back_dev_home/` + `front-dev-home/`) 으로 흡수하기 위한 마이그레이션 전략입니다.

### 1.1 통합 목적

- 단일 대시보드 경험: 사용자가 E-Beam Metrology 와 AFM Metrology 를 한 사이트에서 이용합니다.
- 3-Phase 배포 전략 정합성: 홈/오피스/프로덕션 어느 단계에서도 단일 Flask 인스턴스가 단일 Nuxt 빌드를 서빙합니다.
- CLAUDE.md 의 feature-sliced 백엔드 패턴을 AFM 에도 동일하게 적용합니다.

### 1.2 백엔드 통합 vs CORS 분리 비교

| 항목 | 통합 (권고) | CORS 분리 유지 |
| --- | --- | --- |
| 프로세스 수 | 1 | 2 |
| CORS 설정 | 불필요 | 영구 필요 |
| Phase 3 운영 | Flask 1개가 Nuxt dist 서빙 | Flask 2개 동시 운영 |
| 쿠키/세션 | 단일 도메인 | 도메인 간 처리 필요 |
| 컨벤션 정합성 | sem_list, tool_inventory 와 동일 | 예외 케이스 |
| 초기 마이그레이션 비용 | 높음 (라우트 이전) | 낮음 |
| 장기 유지보수 비용 | 낮음 | 높음 |

**결론:** 통합 방식을 채택합니다. 다만 단계적 이행을 위해 *프런트엔드 재작성을 먼저* 진행하고, 그 기간 동안만 Nitro proxy 를 통해 별도 Flask 로 임시 라우팅하는 중간 경로를 둘 수 있습니다.

## 2. 현재 구조 요약

### 2.1 AFM 백엔드 (`afm_data_platform/api/`)

| Blueprint | 파일 | Endpoint 수 | 핵심 책임 |
| --- | --- | --- | --- |
| `api_bp` | `routes.py` | 1 | `/health` |
| `afm_bp` | `afm_routes.py` | 3 | 파일 목록·디테일·프로파일 |
| `image_bp` | `image_routes.py` | 5 | 이미지 위치·서빙·다운로드 |
| `activity_bp` | `activity_routes.py` | 5 | 사용자 활동 로그 조회 |

- 데이터 경로: `itc-afm-data-platform-pjt-shared/AFM_DB/{tool}/...` (고정).
- 주요 자료: pickle (`data_dir_pickle/*.pkl`, `profile_dir/*.pkl`), 이미지 (`tiff_dir/*.webp`).
- 로그 시스템: `system / activity / error` 3 종 RotatingFileHandler (50–200 MB, 10–30 백업).
- 인증: 사실상 없음. `LASTUSER` 쿠키만 사용자 식별 용도로 읽습니다.

### 2.2 AFM 프런트엔드 (`afm_data_platform/front-end/`)

| 분류 | 항목 |
| --- | --- |
| 라우트 | `/`, `/about`, `/contact`, `/result/:recipeId/:filename`, `/result/data_trend` |
| 페이지 | `MainPage`, `AboutPage`, `ContactPage`, `ResultPage`, `DataTrendPage` |
| 컴포넌트 | 약 20 개 (charts, common, MainPage, ResultPage, DataTrend, Settings) |
| 상태관리 | Pinia `dataStore.js` (composition API), localStorage 영속화 |
| 데이터 fetch | Axios + Vue Query (`useResultPageQueries.js`) |
| 차트 | ECharts (vue-echarts) |
| UI | Vuetify 3 |
| 빌드 | Vite + unplugin-auto-import + unplugin-vue-components |

## 3. 백엔드 마이그레이션

### 3.1 디렉토리 매핑

| 원본 | 대상 |
| --- | --- |
| `afm_data_platform/api/__init__.py` | (제거; 통합 앱 팩토리에서 등록) |
| `afm_data_platform/api/routes.py` | `back_dev_home/afm/__init__.py` (blueprint export) |
| `afm_data_platform/api/afm_routes.py` | `back_dev_home/afm/routes.py` 의 일부 (files 그룹) |
| `afm_data_platform/api/image_routes.py` | `back_dev_home/afm/routes.py` 의 일부 (image 그룹) |
| `afm_data_platform/api/activity_routes.py` | `back_dev_home/afm/routes.py` 의 일부 (activity 그룹) |
| `afm_data_platform/api/utils/file_parser.py` | `back_dev_home/afm/data.py` (데이터 액세스 레이어) |
| `afm_data_platform/api/utils/app_logger_standard.py` | 표준 `logging` 으로 단순화 |
| `afm_data_platform/api/utils/standard_logger.py` | 제거 |

### 3.2 URL Prefix 재설계

skewnono blueprint 컨벤션 (`/api/sem-list`, `/api/tool-inventory`) 에 맞춰 모든 AFM 엔드포인트는 `/api/afm/` 하위로 재배치합니다.

| 변경 전 | 변경 후 |
| --- | --- |
| `GET /api/afm-files` | `GET /api/afm/files` |
| `GET /api/afm-files/detail/<filename>` | `GET /api/afm/files/<filename>` |
| `GET /api/afm-files/profile/<filename>/<point>` | `GET /api/afm/files/<filename>/profile/<point>` |
| `GET /api/afm-files/image/<filename>/<point>` | `GET /api/afm/files/<filename>/image/<point>` |
| `GET /api/afm-files/image-file/<filename>/<point>` | `GET /api/afm/files/<filename>/image-file/<point>` |
| `GET /api/afm-files/download-raw-image/...` | `GET /api/afm/files/<filename>/download/<point>` |
| `GET /api/user-activities` | `GET /api/afm/activities` |
| `GET /api/my-activities` | `GET /api/afm/activities/me` |
| `GET /api/current-user` | `GET /api/afm/current-user` |
| `GET /api/user-analytics` | `GET /api/afm/analytics` |
| `GET /api/debug/cookies` | (제거 또는 dev 전용 유지) |

### 3.3 데이터 레이어 분리

`back_dev_home/afm/data.py` 가 노출할 함수입니다.

| 함수 | 책임 |
| --- | --- |
| `list_afm_files(tool: str)` | 도구별 측정 목록 (캐시 pickle 우선, fallback 라이브 파싱) |
| `get_afm_file_detail(filename: str)` | 측정 상세 dict + summary/detail records |
| `get_profile_points(filename: str, point: int)` | xyz 좌표 리스트 |
| `resolve_image_path(filename: str, point: int)` | 이미지 파일 경로 (다중 패턴 매칭) |
| `read_image_bytes(filename: str, point: int)` | WebP 바이트 |
| `list_user_activities(user, limit)` | activity log 파싱 결과 |
| `get_user_analytics()` | 일자별 세션·사용자 통계 |

라우트 핸들러는 위 함수만을 호출하며 pickle/파일시스템에 직접 접근하지 않습니다. 이로써 Phase 2/3 로 이행할 때 `data.py` 만 교체하면 OpenSearch 등으로 백엔드를 바꿀 수 있습니다.

### 3.4 데이터 경로의 환경설정화

- 환경변수 `AFM_DB_ROOT` (default: `./itc-afm-data-platform-pjt-shared/AFM_DB`).
- `back_dev_home/afm/data.py` 모듈 로드 시 `os.environ.get("AFM_DB_ROOT", ...)` 로 해석합니다.
- Phase 1 home 환경: 기본값을 사용해 로컬 dummy 데이터를 가리킵니다.
- Phase 2/3: 회사 공유 경로 또는 마운트된 네트워크 드라이브를 가리킵니다.

### 3.5 로깅 단순화

기존 3-RotatingFileHandler 시스템은 Phase 1 mock 환경에 과도합니다.

- 표준 `logging.getLogger("skewnono.afm")` 으로 통일합니다.
- `back_dev_home/_core/` 에 `logging_config.py` 를 두고 모든 feature 가 공유합니다.
- activity 로그는 *파일 파싱 의존*에서 *메모리 또는 SQLite* 기반으로 단계적으로 이전합니다. 마이그레이션 첫 단계에서는 빈 리스트를 돌려주는 stub 으로 두고, 활동 추적 기능은 후속 작업으로 분리합니다.

### 3.6 `LASTUSER` 쿠키 의존성

- skewnono 에는 인증 시스템이 아직 없습니다.
- 단기: 쿠키가 없으면 `"anonymous"` 사용자로 처리합니다.
- 장기: skewnono 자체 인증 도입 시 동일한 사용자 ID 컨벤션으로 통일합니다.

## 4. 프런트엔드 마이그레이션

### 4.1 라우트 매핑

| 원본 (Vue Router) | 대상 (Nuxt 파일 기반) |
| --- | --- |
| `/` (MainPage) | `front-dev-home/app/pages/afm/index.vue` |
| `/about` | `front-dev-home/app/pages/afm/about.vue` (또는 기존 `/information` 으로 흡수) |
| `/contact` | (제거 검토) |
| `/result/:recipeId/:filename` | `front-dev-home/app/pages/afm/result/[recipeId]/[filename].vue` |
| `/result/data_trend` | `front-dev-home/app/pages/afm/result/data-trend.vue` |

### 4.2 페이지·컴포넌트 이전 매핑

| 원본 | 대상 디렉토리 |
| --- | --- |
| `src/components/common/BreadcrumbNav.vue` | `app/components/afm/common/BreadcrumbNav.vue` |
| `src/components/common/LoadingDialog.vue` | `app/components/afm/common/LoadingDialog.vue` |
| `src/components/MainPage/SearchSection.vue` | `app/components/afm/main/SearchSection.vue` |
| `src/components/MainPage/ViewHistoryCard.vue` | `app/components/afm/main/ViewHistoryCard.vue` |
| `src/components/MainPage/DataGroupingCard.vue` | `app/components/afm/main/DataGroupingCard.vue` |
| `src/components/MainPage/SavedGroupsCard.vue` | `app/components/afm/main/SavedGroupsCard.vue` |
| `src/components/ResultPage/MeasurementInfo.vue` | `app/components/afm/result/MeasurementInfo.vue` |
| `src/components/ResultPage/StatisticalInfoByPoints.vue` | `app/components/afm/result/StatisticalInfoByPoints.vue` |
| `src/components/ResultPage/MeasurementPoints.vue` | `app/components/afm/result/MeasurementPoints.vue` |
| `src/components/ResultPage/AdditionalAnalysisImages.vue` | `app/components/afm/result/AdditionalAnalysisImages.vue` |
| `src/components/ResultPage/charts/*` | `app/components/afm/result/charts/*` |
| `src/components/DataTrend/SimplifiedMeasurementCard.vue` | `app/components/afm/trend/SimplifiedMeasurementCard.vue` |
| `src/components/DataTrend/charts/TimeSeriesChart.vue` | `app/components/afm/trend/charts/TimeSeriesChart.vue` |

### 4.3 상태 관리: Pinia 스토어 도입

- 현재 skewnono 는 `useState` 기반이며 Pinia 는 *예정* 단계입니다 (CLAUDE.md).
- AFM 마이그레이션을 계기로 첫 정식 Pinia 스토어를 도입합니다.

| 원본 (`dataStore.js`) | 대상 (`stores/afmData.ts`) |
| --- | --- |
| `viewHistory[]` | 동일 |
| `groupedData[]` | 동일 |
| `groupHistory[]` | 동일 |
| `selectedTool` | 동일 |
| `searchQuery` | 동일 |
| localStorage 키 (`afm_view_history_<tool>`) | 동일 키 유지 → 사용자 데이터 보존 |

### 4.4 데이터 fetch: Vue Query → `useAsyncData`

CLAUDE.md 에 따르면 TanStack Query 는 도입하지 않으며 `useAsyncData(key, fn)` 를 컨벤션으로 합니다.

| 원본 composable | 대상 composable |
| --- | --- |
| `useResultPageQueries.useMeasurementData` | `useAfmFileApi.useAfmFileDetail` |
| `useResultPageQueries.useProfileData` | `useAfmFileApi.useAfmProfile` |
| `useResultPageQueries.useProfileImage` | `useAfmFileApi.useAfmImage` |
| `useResultPageQueries.useWaferData` | `useAfmFileApi.useAfmWaferData` |
| `useSearch.useDebounceSearch` | `useAfmSearch` |
| `usePointSelection` | `useAfmPointSelection` |
| `useDataDownload` | `useAfmDataDownload` |

캐시 키는 `composables/useSemListApi.ts` 의 `useSemList()` 패턴을 따라 리소스당 단일 키 (예: `afm-file-detail:${filename}`) 로 통일해 다중 컴포넌트 간 중복 fetch 를 방지합니다.

### 4.5 Vuetify → NuxtUI 매핑

| Vuetify | NuxtUI / 대안 | 마찰도 |
| --- | --- | --- |
| `v-card` | `UCard` | 낮음 |
| `v-btn` | `UButton` | 낮음 |
| `v-chip` | `UBadge` | 낮음 |
| `v-tabs` / `v-window` | `UTabs` | 낮음 |
| `v-text-field` / `v-textarea` / `v-select` | `UInput` / `UTextarea` / `USelect` | 낮음 |
| `v-alert` | `UAlert` | 낮음 |
| `v-progress-linear` | `UProgress` | 낮음 |
| `v-progress-circular` | Lucide `i-lucide-loader-2` + `animate-spin` | 중간 |
| `v-dialog` | `UModal` | 중간 |
| `v-menu` | `UDropdownMenu` / `UPopover` | 중간 |
| `v-list` / `v-list-item` | Tailwind 시맨틱 마크업 | 중간 |
| `v-tooltip` | `UTooltip` | 낮음 |
| `v-data-table` | **결정 필요** (4.6 절) | 높음 |
| ECharts (vue-echarts) | 동일 사용 | 낮음 |

### 4.6 `v-data-table` 대체 결정

`StatisticalInfoByPoints.vue` 가 핵심 의존처입니다.

| 옵션 | 장점 | 단점 |
| --- | --- | --- |
| NuxtUI `UTable` + 수동 정렬/필터 | 의존성 추가 없음, 컨벤션 일치 | 정렬·필터·페이징 직접 구현 |
| TanStack Table (`@tanstack/vue-table`) | 헤드리스, 강력, 커뮤니티 검증 | 새 라이브러리 학습·셋업 |
| 자체 컴포넌트 | 디자인 자유도 최대 | 구현·유지보수 비용 |

**권고:** 1차로 `UTable` 로 이전하되, AFM 사용자가 정렬·필터·검색을 빈번히 요구하면 후속 PR 에서 TanStack Table 로 교체합니다.

### 4.7 자산 이전

| 원본 | 대상 |
| --- | --- |
| `front-end/src/assets/afm_logo.png` | `front-dev-home/app/assets/afm/afm_logo.png` |
| `front-end/src/assets/custom_logo.png` | `front-dev-home/app/assets/afm/custom_logo.png` |
| `front-end/src/styles/fonts.css` | skewnono 글로벌 스타일에 병합 검토 |
| `front-end/src/styles/settings.scss` | 빈 파일이므로 제거 |

### 4.8 ECharts 통합

- `vue-echarts` 와 ECharts 를 `package.json` 에 추가합니다.
- 차트 컴포넌트는 SSR 미지원이므로 `<ClientOnly>` 로 감싸거나 페이지에 `definePageMeta({ ssr: false })` 를 둡니다 (skewnono 는 이미 `ssr: false`).
- 리사이즈 핸들러 (resizeObserver) 는 그대로 이전합니다.

## 5. 랜딩 페이지·네비 변경

### 5.1 `pages/index.vue`

- 두 카드 구성을 유지합니다: **E-Beam Metrology** + **AFM Metrology** (Thickness 카드는 제거).
- AFM 카드는 `/afm` 으로 이동하는 단일 행으로 시작하고, 향후 하위 기능 (Search, Trend) 을 행으로 추가할 수 있도록 E-Beam 카드와 동일한 nav 패턴을 채택합니다.

### 5.2 `components/nav/AppHeader.vue`

- 카테고리 버튼 배열을 `[{ id: 'ebeam' }, { id: 'afm' }]` 으로 변경합니다.
- `Thickness` 항목은 코드에서 제거합니다 (Phase: 차후 재도입 시 다시 추가).

### 5.3 `stores/navigation.ts`

```text
Category = 'ebeam' | 'afm'
defaultState.category = 'ebeam'
```

`thickness` 는 향후 재도입 시까지 union 에서 제외합니다.

### 5.4 `composables/useNavigation.ts`

- `navigateToCategory('afm')` → `router.push('/afm')` 분기를 추가합니다.
- 기존 `'thickness'` 분기는 제거합니다.

### 5.5 `pages/thickness/index.vue`

- Phase: 향후 재도입을 고려해 파일은 보존하되, 라우트가 nav 어디에서도 노출되지 않도록 합니다. 또는 깔끔하게 삭제하고 git history 에 의존합니다 — 후자를 권장합니다.

## 6. 단계별 실행 순서 (Sequencing)

### Phase A — 백엔드 이전

1. `back_dev_home/afm/__init__.py`, `routes.py`, `data.py` 골격 생성.
2. `afm_data_platform/api/utils/file_parser.py` 의 함수를 `data.py` 로 이전 (시그니처 정리).
3. 라우트 핸들러를 3.2 절의 새 prefix 로 작성.
4. `back_dev_home/__init__.py` 에서 blueprint 등록.
5. `AFM_DB_ROOT` 환경변수 도입 및 dummy 데이터 경로 설정.
6. `curl` / Postman 으로 12 개 엔드포인트 회귀 검증.

### Phase B — Nuxt 스캐폴드 + MainPage

1. `pages/afm/index.vue` 생성, hub 레이아웃 적용.
2. `stores/afmData.ts` Pinia 스토어 작성.
3. `composables/useAfmFileApi.ts` 작성 (`useAsyncData` 기반).
4. `SearchSection`, `ViewHistoryCard`, `DataGroupingCard`, `SavedGroupsCard` 이전.
5. `/afm` → 검색 → 결과 클릭 시 `/afm/result/...` 로 라우팅 동작 확인.

### Phase C — Result 페이지

1. `pages/afm/result/[recipeId]/[filename].vue` 생성.
2. `MeasurementInfo`, `MeasurementPoints`, `AdditionalAnalysisImages` 이전.
3. ECharts 컴포넌트 (`HistogramChart`, `HeatmapChart`, `DataScatterChart`) 이전.
4. `StatisticalInfoByPoints` 를 `UTable` 로 재구현 (4.6 절).
5. `useAfmPointSelection`, `useAfmDataDownload` 이전.

### Phase D — Trend 페이지

1. `pages/afm/result/data-trend.vue` 생성.
2. `SimplifiedMeasurementCard` 이전.
3. `TimeSeriesChart` 이전.
4. 그룹 데이터 로드 흐름 (sessionStorage 또는 스토어) 검증.

### Phase E — 정리

1. `pages/index.vue`, `AppHeader.vue`, `navigation.ts`, `useNavigation.ts` 변경 적용.
2. 랜딩에서 AFM 카드 클릭 → `/afm` 이동 회귀 테스트.
3. `afm_data_platform/` 폴더 archive (`docs/archive/afm_data_platform_legacy/` 또는 별도 브랜치) 후 root 에서 제거.
4. README / CLAUDE.md 의 feature 목록에 AFM 추가.

## 7. 리스크 및 미해결 항목

| 항목 | 영향 | 대응 |
| --- | --- | --- |
| `v-data-table` 대체 라이브러리 결정 | 결과 페이지 사용성 | Phase C 시점에 사용자 피드백 후 결정 |
| `LASTUSER` 쿠키 부재 | 활동 로깅 정확도 | 단기 anonymous, 장기 skewnono 인증 통합 |
| 파일명 다중 패턴 매칭 | 새 데이터 양식 도입 시 깨짐 | 인덱스 테이블 또는 메타 캐시 도입 검토 |
| AFM_DB Phase 1 dummy 데이터 | 홈 환경 동작 검증 곤란 | `afm_data_platform/generate_*.py` 를 `back_dev_home/afm/scripts/` 로 이전·재사용 |
| Vue Query 의 캐시 정책 손실 | 결과 페이지 재방문 시 재요청 | `useAsyncData` 키 공유 + Pinia 캐시로 보완 |
| ECharts 번들 크기 | 초기 로딩 시간 | Nuxt `vite.build.rollupOptions` 청크 분리 |

## 8. 검증 (Verification)

### 8.1 로컬 통합 검증

- `python index.py` (skewnono Flask, port 5000) 단일 기동.
- `npm --prefix front-dev-home run dev` (Nuxt, port 3100 — `nuxt.config.ts` `devServer.port` 기본값).
- 브라우저에서 `http://localhost:3100` 접속, 다음 흐름 수동 확인:
  - 랜딩 → AFM 카드 클릭 → `/afm`
  - 도구 선택 → 검색 → 결과 클릭 → `/afm/result/<recipe>/<filename>`
  - 차트 표시, 포인트 선택, 이미지 로드, CSV 다운로드
  - 결과 → Trend Analysis → 시계열 차트 표시

### 8.2 Playwright MCP 회귀

- `.playwright-mcp/screenshots/afm-landing.png`
- `.playwright-mcp/screenshots/afm-search.png`
- `.playwright-mcp/screenshots/afm-result.png`
- `.playwright-mcp/screenshots/afm-trend.png`

### 8.3 백엔드 단위 검증

- 12 개 엔드포인트의 200 응답 + 응답 shape 확인 (`curl` 또는 pytest 후속 도입).

### 8.4 문서 자체 검증

- `npm run lint:md` 로 본 문서의 markdownlint 통과를 확인합니다.

## 9. 참고 파일

- `back_dev_home/__init__.py` — 통합 앱 팩토리 패턴
- `back_dev_home/sem_list/{routes.py,data.py}` — feature 모범 사례
- `front-dev-home/app/composables/useSemListApi.ts` — `useAsyncData` 패턴
- `front-dev-home/app/pages/index.vue` — 랜딩 카드 구조
- `front-dev-home/app/components/nav/AppHeader.vue` — 카테고리 nav
- `afm_data_platform/api/{__init__.py,routes.py,afm_routes.py,image_routes.py,activity_routes.py,utils/}` — 이전 대상 백엔드
- `afm_data_platform/front-end/src/{router,pages,components,stores,composables}` — 이전 대상 프런트엔드
