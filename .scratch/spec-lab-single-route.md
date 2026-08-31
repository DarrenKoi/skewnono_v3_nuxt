# Spec: /pm-planning 라우트를 /tttm 으로 흡수 (실험실 단일 페이지)

Status: approved (design by manager session, 2026-09-01)
Worktree: `../skewnono-lab-single` (branch `work/lab-single`)

## 배경 / 목표

2026-08-30 머지로 두 페이지는 이미 한 컴포넌트(`LabView.vue`)가 되었고, 두
라우트는 패널 프리셋일 뿐이다. `pm` 패널 칩이 켜지면 튜닝할 장비 바가 이미
나타난다(`v-if="has('pm')"`). 이제 라우트도 하나로: **`/tttm` 만 남기고
`/pm-planning` 라우트·서브탭·프리셋 축을 제거**한다. PM 튜닝은 "다른 화면"이
아니라 "켜는 분석 칩"이 된다.

선례: recipe-tat / fail-issue → recipe-status 병합 (redirect 스텁 페이지 +
FEATURE_SLUGS 에서 슬러그 제거 + pageIdentity 는 유지).

## 범위

**Frontend only.** `back_dev_home/` 는 한 글자도 바꾸지 않는다 — `pm_planning`
API 는 pm 칩의 데이터원으로 그대로 쓰이고, `_logging/feature_map.py` 의 API
경로 매핑이 활동을 계속 `pm_planning` 슬러그로 기록한다.

## 변경 목록 (파일별)

### 1. `pages/ebeam/cd-sem/[fab]/pm-planning.vue` — redirect 스텁으로 교체

`fail-issue.vue` 와 같은 모양: `definePageMeta` route middleware 에서
`navigateTo({ path: \`/ebeam/cd-sem/${to.params.fab}/tttm\` }, { replace: true })`.
query 는 넘길 것 없음(두 화면이 query 를 쓰지 않음). 주석 한 줄: 병합 사실 +
북마크 보존 목적.

skipped: redirect 가 pm 칩을 자동으로 켜는 `?panel=pm` 축 — 칩 피커가 화면에
보이므로 불필요. 사용자가 원하면 나중에.

### 2. `components/ebeam/LabSubTabs.vue` — 삭제

`LabView.vue` 의 MetaBar `#toggle` 슬롯 사용처와 함께 제거.

### 3. `utils/labView.ts` — 뷰 축 삭제, 패널 축만 남김

- 삭제: `LabViewSlug`, `LabViewDef`, `LAB_VIEWS`, `labViewBySlug`.
- 유지: `LabPanel`, `LAB_PANELS`(5칩 그대로 — pm 칩 포함), `normalizePanels`
  (정렬 복원 로직 그대로).
- 추가: `DEFAULT_PANELS: LabPanel[] = ['verdict', 'map', 'matrix', 'trend']`
  — 구 tttm 프리셋. **pm 은 기본 꺼짐**: PM 튜닝 칩을 켜야 튜닝할 장비가
  나타난다(요구사항의 핵심).
- 파일 머리 주석 재작성: 한 페이지 한 라우트(2026-09-01), pm-planning 은 칩,
  백엔드 슬러그 `pm_planning` 은 API 매핑으로 계속 살아 있음, redirect 스텁
  존재. 기존 주석의 "두 라우트가 살아남은 이유" 문단은 삭제(더는 사실 아님).

### 4. `composables/useLabPanels.ts` — 슬러그 축 제거, 단일 선택

- `useLabPanels()` 인자 없음. `panels`/`has`/`setPanels` 시그니처 유지.
- 저장 키 `'lab-panels'` 유지. **마이그레이션 제약**: 기존 사용자의 저장값은
  `{"tttm": [...], "pm-planning": [...]}` 형태 — `tttm` 키의 선택은 살리고,
  `pm-planning` 키는 버린다. 새 저장 형태는 구현자 재량(평평한 배열 권장:
  normalize 가 배열이면 그대로, 객체면 `.tttm` 을 읽는 한 줄 이행).
- 빈 배열(모두 끔)은 여전히 적법한 저장값.

### 5. `components/ebeam/LabView.vue`

- props 에서 `slug` 제거, `view` computed 제거.
- MetaBar: `#toggle` 슬롯(서브탭) 제거. `title="장비간 스큐 관리"` 하드코드,
  subtitle 은 구 tttm subtitle 유지.
- 구 PM 플래닝 subtitle 의 설명("하드웨어를 만질 기회는 PM 창뿐입니다 — …")은
  버리지 말 것: `EbeamPmPlanningToolPicker` 의 캡션이 이미 그 내용을 담고
  있는지 확인하고, 없으면 그 바(또는 PM 카드 묶음)의 캡션으로 이동.
- `useLabPanels()` 호출 인자 제거.
- "두 화면이 함께 씁니다" 힌트 2곳(ScopeBar, ToolGroupBar) — 화면이 하나이므로
  문구 수정(예: "이 설정은 이 브라우저에 저장됩니다").
- 파일 내 라우트/뷰 언급 주석 갱신(setup 머리 doc, showsPickedTool 주석,
  pm fleet fetch 주석의 "두 뷰" 표현 등). 로직은 전부 그대로 — `has('pm')`
  게이트, pm fleet 을 항상 fetch 하는 결정, metaStats 의 has('pm') 분기 유지.

### 6. `pages/ebeam/cd-sem/[fab]/tttm.vue`

- `slug` prop 제거(LabView 시그니처 변경 반영), 주석의 "두 라우트" 문단 갱신.
- `:key="primaryFab"` 와 그 이유 주석은 유지.

### 7. `utils/headerNav.ts`

- PM 플래닝 행 삭제. TTTM 행 description 을 병합 반영해 갱신
  (예: `'장비끼리 얼마나 맞는지 비교 · PM 튜닝 목표'`). TTTM 행 위 주석에서
  "두 플래그는 함께 내려갑니다" 등 PM 행을 전제한 문장 정리.
- `scope` 유니언에서 `'pm-planning'` 제거.

### 8. `utils/features.ts`

- `FEATURE_SLUGS` 에서 `'pm-planning'` 제거 — recipe-tat 선례 그대로(redirect
  스텁이 layout 관측 전에 경로를 바꾸므로 슬러그는 route.path 에 안 나타남).
  그 선례를 설명하는 기존 주석에 pm-planning 을 추가.
- `SINGLE_FAB_FEATURES`, `FEATURE_TOOL_TYPES` 에서 제거. 주변 주석 갱신.

### 9. `utils/pageIdentity.ts` — **변경 없음**

`/pm-planning`, `/pm-tune` 항목은 역사적 identity 로 유지(recipe-tat 선례).
과거 활동 로그 라벨링이 이 항목에 걸려 있다.

### 10. `pages/intro.vue`

pm-planning 카드 제거, tttm 카드 description 에 PM 튜닝 흡수를 한 줄 반영.

### 11. 주석-only 정리 (로직 불변)

`LabMenu.vue`, `useNavigation.ts`, `useFabRoute.ts`, `FabSidebar.vue`,
`FeatureTabs.vue`, `useTttmSettings.ts`, `tttm/FleetMap.vue` — pm-planning
페이지를 현재형으로 언급하는 주석만 갱신. LabMenu 의 scope 로직은
`FEATURE_TOOL_TYPES` 테이블 파생이므로 코드 변경 불필요(행이 사라지면 끝).

### 12. 테스트

- `utils/labView.test.ts`: LAB_VIEWS/labViewBySlug 케이스 제거, DEFAULT_PANELS
  와 normalizePanels 케이스 유지·보강.
- `utils/features.test.ts`: pm-planning 제거 반영.
- 새 동작(useLabPanels 마이그레이션 한 줄)에 최소 테스트 1개.

## 게이트 (전부 통과해야 완료)

worktree 준비: `ln -s` 로 main 체크아웃의 `node_modules` 연결 후
`npx nuxi prepare` (worktree 에는 `.nuxt` 가 없음).

1. `npm run typecheck` (front-dev-home)
2. `npm test`
3. `npm run lint`
4. `grep -rn "pm-planning" app/` 잔존이 다음뿐일 것: redirect 스텁,
   `usePmPlanningApi.ts` 의 API 경로, `pageIdentity.ts`, `pmPlanning`
   컴포넌트/유틸 파일명·import, 역사 서술 주석.
5. 커밋: `refactor(lab): pm-planning 라우트를 tttm 으로 흡수합니다 — PM 튜닝은 칩` 류의
   type(scope) 형식, 본문에 무엇이/왜.

## 하지 말 것

- `back_dev_home/` 수정 금지. `pageIdentity.ts` 수정 금지.
- `pmPlanning/` 컴포넌트·`usePmPlanningApi`·`pmAdmission`·`pmTuningTarget`
  이름 변경 금지(파일명은 API·도메인 이름이지 라우트가 아님).
- `git add -A` / `git add .` 금지 — 편집한 파일만 명시 pathspec 으로.
