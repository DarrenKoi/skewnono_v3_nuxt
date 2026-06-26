# 스큐보아(Skewvoir) — 검색/분석 분리 + 샘플 스타일 적용 설계

- 작성일: 2026-06-27
- 상태: **설계 확정 (승인됨)** — 다음 단계는 구현 계획(plan) 작성
- 대상: 엔지니어용 측정 결과 분석 뷰어 `ebeam/{cd-sem,hv-sem}/skewvoir`
- 참고: `docs/skewvoir_sample1.html`(렌더 목업), `docs/issues/skewvoir/brainstorm-note.md`(중단된 2026-05-31 브레인스토밍), 메모리 `project_skewvoir_design`
- 이번 패스 범위: **재스타일 + 구조만**. 패널 내부 차트 연결은 후속 패스로 분리합니다.

## 1. 배경 및 현재 상태 (코드 확인 결과)

- 페이지 `app/pages/ebeam/{cd-sem,hv-sem}/skewvoir.vue` 는 현재 **구버전**
  `EbeamSkewvoirView`(`components/ebeam/SkewvoirView.vue`)를 마운트합니다.
  이는 `MsrPicker → AnalyzePanel` 흐름으로, 실제 mock(`useMeasHistApi`) 데이터로
  4개 차트(다중 MSR 시계열, wafer map, 히스토그램, sequence 추이)를 렌더하는
  **동작하는** 구현입니다.
- `components/ebeam/skewvoir/Workspace.vue`(IDE 셸: TopBar + LeftRail +
  StatusBar)는 **고아 상태**입니다. 어떤 페이지도 이를 마운트하지 않으며,
  selection/filters/health 는 모두 하드코딩된 데모 `useState` 값입니다.
- 즉 구현이 둘로 갈라져 있습니다: **동작하는 분석(셸 밖)** vs **잘 만든 빈
  셸(마운트 안 됨)**. 이번 설계가 셸을 정식 홈으로 확정하고, 검색과 분석을 분리해
  그 분기를 해소합니다.

## 2. 핵심 결정 사항 (브레인스토밍 합의)

| 항목 | 결정 |
| --- | --- |
| 검색/분석 분리 형태 | **검색 랜딩 → 분석 워크스페이스** (라우트 기반, 형제 라우트) |
| 공유 방식 | **라이브 재조회(live re-query)** 공유 링크 — URL이 선택을 운반, 열면 재조회 |
| 저장 뷰 | Phase 1 `localStorage` 영속화, Phase 2/3 `saved_views` 블루프린트로 스왑 |
| 이번 패스 범위 | **재스타일 + 구조만** (패널은 placeholder, 실제 차트는 후속) |
| view 모델 | 검색은 랜딩으로 분리, 분석 레일은 **5개 분석 sub-view** 유지 |
| AI Anomaly 카드 | 이번 패스 제외 |
| 패널 분해 | **패널별 sub-vue 파일**로 분해 (코드량 대비, 900줄 임계/폴더 prefix 규칙 준수) |

## 3. 아키텍처 — 형제 라우트 2개

leaf 파일 `skewvoir.vue` 를 폴더로 전환합니다 (cd-sem · hv-sem 모두):

| 라우트 | 파일 | 역할 |
| --- | --- | --- |
| `…/skewvoir` | `pages/ebeam/<tool>/skewvoir/index.vue` | **검색 랜딩** — 검색 바 + 필터 + 결과 타임라인/quick-stats/latest-lots |
| `…/skewvoir/analysis` | `pages/ebeam/<tool>/skewvoir/analysis.vue` | **분석 워크스페이스** — 셸(TopBar+LeftRail+StatusBar), 선택은 URL query 기반 |

- 형제 라우트(중첩 아님)이므로 `<NuxtPage>` 배선이 불필요합니다.
- 두 페이지 모두 얇은 wrapper이며 `tool-label`/`tool-type` prop만 내려줍니다
  (기존 `skewvoir.vue` 패턴 유지, `definePageMeta({ hideFabSidebar: true })`,
  `useNavigation().setToolType(...)` 호출 포함).

## 4. URL 상태 = 공유 가능성 (라이브 재조회)

- 분석 라우트는 선택을 query에서 읽습니다:
  `…/analysis?lot=RK2W016.13&recipe=RK2A_DSVTEOSETCLN&eq=MCD026&mp=WAFER&view=dashboard`
- 신규 composable `useSkewvoirRoute(toolType)`:
  - `selection`(lot/recipe/eq/mp) ↔ query 직렬화/역직렬화
  - `view`(활성 sub-view kind) ↔ query
  - `navigateTo({ path, query })` 헬퍼, 그리고 현재 URL 반환 헬퍼
- 검색 결과 "열기" → `navigateTo` 로 분석 라우트 이동(query 포함).
- **Share** 버튼 → `location.href` 복사(clipboard). 라이브: 분석 화면은 매 로드 시
  query로부터 mock fetch를 재실행합니다.
- 빈 query로 분석 라우트 직접 진입 시: "검색에서 측정을 선택하세요" 빈 상태 표시
  + 검색 랜딩 링크.

## 5. 저장 뷰 (Saved Views)

- 신규 composable `useSkewvoirSavedViews(toolType)`:
  - 레코드: `{ id, name, toolType, query, createdAt, createdBy }`
  - Phase 1: `localStorage` 키 `skewvoir-saved-views`(전 tool 공유, toolType로 필터)
  - Phase 2/3: 동일 composable 인터페이스 유지, 내부만 `saved_views` Flask
    블루프린트(`back_dev_home/saved_views/{routes,data}.py`) 호출로 스왑 →
    프론트 코드 무변경(크로스-페이즈 원칙)
- UI 배선: 검색 랜딩의 "Saved" 버튼(저장 뷰 목록 열기) + 분석 TopBar의
  "Save view" 버튼(현재 query 이름 붙여 저장). 목록은 간단한 드롭다운/슬라이드오버.
- **createdBy 출처**: 기존 사용자 식별 메커니즘 재사용. 없으면 Phase 1 한정
  `'me'` 고정값으로 두고 Phase 2/3에서 실제 사용자로 대체(주석으로 명시).

## 6. 컴포넌트 분해

### 6.1 워크스페이스 상태 (`useSkewvoirWorkspace` 개편)

- `SkewvoirViewKind` 에서 `'search'` 제거 → **5개 분석 kind**:
  `dashboard | position-stack | time-series | correlation | gallery`.
- 탭/데모 `useState` 흐름 제거. 활성 view는 URL `view` param이 단일 출처(source of
  truth). selection/filters/health 는 query + mock에서 시드(하드코딩 제거).
- `openView(kind)` → `view` query 갱신(`navigateTo`)으로 변경. 단축키 1-5 유지.
- health/filters 는 당분간 mock 시드값 유지하되, 하드코딩 데모 selection은
  query 우선으로 대체.

### 6.2 컴포넌트 트리

```text
components/ebeam/skewvoir/
  Workspace.vue                 # 분석 셸: TopBar + LeftRail + 활성 view + StatusBar
  SearchLanding.vue             # 검색 랜딩(기존 workspace/SearchView 승격)
  PanelFrame.vue                # 재사용 패널 크롬(타이틀 + 인라인 세그먼트 토글)
  workspace/                    # 기존 크롬
    TopBar.vue                  # Share / Save view / 액션, breadcrumb
    LeftRail.vue                # 5개 분석 view + "← 검색" 복귀 + 선택/필터/Health
    StatusBar.vue
  views/
    Dashboard.vue               # <EbeamSkewvoirViewsDashboard>
    PositionStack.vue
    TimeSeries.vue
    Correlation.vue
    Gallery.vue
  dashboard/                    # Dashboard 패널(파일당 1개)
    WaferMap.vue                # <EbeamSkewvoirDashboardWaferMap>
    DataSummary.vue
    RadiusPlot.vue
    SemImage.vue
    MeasurementPoints.vue
    Distribution.vue
    Acquisition.vue
  # timeSeries/, correlation/ 등 패널 폴더는 해당 view를 채울 때 추가
```

- 폴더명이 auto-import prefix를 공급하므로 파일명은 prefix 이후 깔끔히 읽히게
  명명합니다(`dashboard/WaferMap.vue` → `<EbeamSkewvoirDashboardWaferMap>`,
  `Panel` 접미사로 stutter 만들지 않음).
- `Workspace.vue` 는 URL `view` 값에 따라 `views/*` 중 하나를 렌더합니다.
- 각 `views/*` 는 자기 패널 폴더에서 패널을 조합합니다. **이번 패스는 Dashboard
  view의 패널 7개를 우선 생성**(샘플이 완전히 명세하는 유일한 view).

### 6.3 패널 = PanelFrame placeholder

- 모든 패널은 이번 패스에서 `PanelFrame` 기반의 얇은 placeholder로 출하하되
  **각자 자기 파일**을 가집니다. 후속 "차트 연결" 패스가 `AnalyzePanel`의 실제
  차트를 각 leaf 내부로 이주합니다.
- `PanelFrame` props: `title`, `meta`(우측 보조 텍스트), `toggles`(세그먼트 옵션
  배열, 예: Cell/Dot, Hist/Box/Violin), 기본 슬롯(본문).

## 7. 재스타일 (생각보다 가벼움)

- 기존 `--sk-*` 토큰계가 이미 **웜 크림 + 다크 잉크 + 테라코타** 에디토리얼
  팔레트입니다. 샘플의 *크롬*은 이와 사실상 일치합니다 — 전면 팔레트 교체 불필요.
- 샘플의 navy/red 는 주로 **데이터 시각화**(diverging wafer 컬러맵 + 히스토그램)에
  존재. 따라서 신규 **데이터 스케일 토큰**만 추가합니다(이번 패스에선 정의만,
  실제 사용은 차트 연결 패스):
  - `--sk-scale-low`(navy `#2752a8`) → `--sk-scale-mid`(웜 탄) → `--sk-scale-high`(red `#b21f24`)
  - light/dark 양쪽 `main.css` 의 `--sk-*` 블록에 대응 정의.
- 시각 디테일: 더 조밀한 타이포, 대문자 mono 섹션 라벨, hairline 패널 프레이밍을
  `PanelFrame` 으로 일관 적용. 뮤트 텍스트는 raw `text-zinc-*` 대신 `--sk-ink-*`
  시맨틱 토큰 사용(다크모드 적응). NuxtUI `USelect` 사용 시 빈 문자열 value 금지.
- 토글 등 인터랙티브 칩은 Tailwind v4 canonical 클래스/간격 토큰 사용.

## 8. 유지(삭제 금지)

- 구버전 `components/ebeam/SkewvoirView.vue` · `MsrPicker.vue` ·
  `AnalyzePanel.vue`(및 하위 차트들)는 **삭제하지 않습니다**. 후속 패스에서 셸
  내부로 이주할 실제 데이터 분석 자산입니다.
- 기존 `workspace/SearchView.vue` 는 `SearchLanding.vue` 로 승격/이동하며 원본은
  제거(중복 방지). `PlaceholderView.vue`/`PanelStub.vue` 는 PanelFrame 도입 후
  사용처가 없으면 정리.

## 9. 검증

- `npm run dev` (Flask :5050 + Nuxt :3000 은 사용자가 PyCharm에서 구동) +
  Playwright:
  1. 검색 랜딩 렌더링 확인
  2. 결과 "열기" → `…/analysis?…` URL에 query 반영 확인
  3. Share → URL 클립보드 복사 확인
  4. 해당 URL 재진입 → 동일 화면 재구성(라이브 재조회) 확인
  5. Save view → `localStorage` 영속 + 목록 재노출 확인
  6. 5개 sub-view 전환(레일/단축키 1-5) 동작 확인
  7. 검색 ↔ 분석 라우트 왕복 확인
- 스크린샷: 두 라우트 × light/dark, `.playwright-mcp/screenshots/` 하위 저장.
- `npm run lint:md` (이 문서 등 md 편집 후).

## 10. 파일 변경 요약

신규:
- `pages/ebeam/{cd-sem,hv-sem}/skewvoir/index.vue`, `…/skewvoir/analysis.vue`
- `components/ebeam/skewvoir/SearchLanding.vue`, `PanelFrame.vue`
- `components/ebeam/skewvoir/views/{Dashboard,PositionStack,TimeSeries,Correlation,Gallery}.vue`
- `components/ebeam/skewvoir/dashboard/{WaferMap,DataSummary,RadiusPlot,SemImage,MeasurementPoints,Distribution,Acquisition}.vue`
- `composables/useSkewvoirRoute.ts`, `composables/useSkewvoirSavedViews.ts`

수정:
- `composables/useSkewvoirWorkspace.ts`(URL 기반, 5 view), `Workspace.vue`,
  `workspace/{TopBar,LeftRail,StatusBar}.vue`, `assets/css/main.css`(스케일 토큰)

삭제/이동:
- leaf `pages/ebeam/{cd-sem,hv-sem}/skewvoir.vue` → 폴더로 대체
- `workspace/SearchView.vue` → `SearchLanding.vue` 로 승격

## 11. 비범위(이번 패스 제외)

- 패널 내부 실제 차트 연결(후속 패스)
- AI Anomaly Summary 카드
- 백엔드 `saved_views` 블루프린트(Phase 2/3) — 이번엔 localStorage만
- mock 데이터 모델 확장(spec 한계선/radius/nested 키) — 차트 연결 패스에서 논의
