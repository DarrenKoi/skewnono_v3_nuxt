# Skewvoir 분석 대시보드 — 테이블 키보드 탐색 + 측정점 다중선택

- **날짜:** 2026-07-25
- **대상 페이지:** `/ebeam/{cd-sem,hv-sem}/skewvoir/analysis`
- **대상 컴포넌트:** `MeasurementPoints.vue`, `ParamSummary.vue`,
  `dashboard/WaferMap.vue`, `dashboard/RadiusPlot.vue`(+ 하위 차트),
  `composables/useSkewvoirAnalysis.ts`
- **상태:** 설계 승인 완료
- **구성:** Part A(키보드 상하 탐색) + Part B(Measurement Points 체크박스 다중선택)

## 배경 / 문제

분석 대시보드의 **Measurement Points**와 **파라미터 요약** 테이블은 현재
행을 마우스로 클릭해야만 포커스가 바뀝니다. 여러 측정점/파라미터를 연속으로
훑어보려면 매번 클릭해야 해서 번거롭습니다. 사용자는 한 행을 선택한 뒤
**키보드 위/아래 화살표로 다른 데이터·이미지를 넘겨보기**를 원합니다.

현재 상태(확인 완료):

- 두 테이블 모두 순수 `<table>` + `<tr @click>` 핸들러만 있고 키보드 핸들러 없음.
- 스큐보이어 내 키보드 리스너는 이미지 모달류(`ImageLightbox`, `gallery/ImageViewer`,
  `dashboard/AlignImages`, `dashboard/RadiusAnalysisDialog`)에만 존재.
- `MeasurementPoints.vue:89` — 행 클릭 → `analysis.setFocusedSequence(p.seq)`;
  포커스 하이라이트는 `:87`, `SemImage.vue`가 `focusedSequence`를 읽어 이미지 갱신.
- `ParamSummary.vue:48` — 행 클릭 → `analysis.toggleParam(param, additive)`
  (⌘/Ctrl/⇧ = 비교 대상 다중선택 토글).
- 공유 포커스 상태는 `useState` 단일 값(`useSkewvoirAnalysis.ts:251` `focusedSequence`),
  파라미터 선택은 `activeParam`(URL `mp`) + `extraParams`(비교셋)로 구성
  (`:189`, `:203`, `:207`, `:216`).

## 목표

1. **(Part A)** 두 테이블에서 위/아래 화살표로 행 커서를 이동하면 **즉시** 관련
   데이터·이미지가 반응한다.
2. **(Part B)** Measurement Points에서 체크박스로 여러 측정점을 다중선택하면,
   그 집합이 웨이퍼 맵·Radius Plot에 함께 강조되고 복사/Excel 내보내기 대상이 된다.
3. 기존 마우스 클릭 동작을 유지한다(회귀 없음).
4. 접근성 기본을 지킨다(포커스 가능, 페이지 스크롤 방지, 포커스 행 자동 스크롤).

## 비목표 (YAGNI)

- 좌/우 화살표 탐색, 마우스 hover 프리뷰, 가상 스크롤.
- 파라미터 요약에서 화살표로 비교셋(extras) 자체를 이동/편집(→ 기존 Space/Enter 토글로 충분).
- Part B: SEM 이미지 갤러리 비교, 선택 항목 드래그, 선택 상태 URL 영속.

## 컴퓨팅 부담 분석 (설계 근거)

- **Measurement Points**: 화살표 이동은 `focusedSequence`(useState 값 하나)만 갱신.
  SEM 이미지가 그 값을 읽어 소스를 바꾸는 정도 → 매우 가벼움. **추가 최적화 불필요.**
- **파라미터 요약**: `activeParam` 변경 시 `activeOverview = overviewSites(siteRows,
  param, cfg)`(`:311`) 재계산 + Distribution/WaferMap 재채색/SEM redraw 발생.
  데이터 계산은 O(site 수) = 수 ms로 작지만, ECharts redraw가 실제 비용.
  - 한 번 누름 → 한 번 캐스케이드는 문제없음.
  - 유일한 리스크: 화살표 **키 리피트**(초당 30~60회). 각 keydown이 별도 task라
    Vue 배칭으로 뭉쳐지지 않아 redraw가 쌓여 순간 버벅일 수 있음.
  - 대응: 선택 상태·하이라이트는 즉시 갱신하되, **무거운 소비자 갱신만 필요 시
    `requestAnimationFrame`으로 coalesce**(중간 프레임 버림). debounce로 반응을
    늦추지 않는다. **먼저 순수 반응형으로 구현 → `/verify`에서 실제 버벅임 확인 후
    필요할 때만 rAF 도입** (YAGNI).

## 설계

### 공통 상호작용 규약 (두 테이블 동일)

- 스크롤 컨테이너(`overflow-auto` div)에 `tabindex="0"` + `@keydown` 부여.
- 행 클릭 시 그 컨테이너에 포커스를 준다 → 이후 화살표가 동작.
- 키 처리:
  - `ArrowDown` / `ArrowUp` → `preventDefault()` 후 커서 ±1.
  - `Home` / `End` → 첫/마지막 행.
  - 경계에서 더 이동 불가(래핑 없음).
- 커서가 이동한 행이 뷰포트 밖이면 해당 `<tr>`에 `scrollIntoView({ block: 'nearest' })`.
- 접근성: 컨테이너 `role="grid"`, 포커스된 `<tr>`에 `aria-selected="true"`.
- 커서 이동은 즉시(반응형) — 별도 커밋 단계 없음.

### Measurement Points

- **커서 대상**: 화면에 보이는 `rows` computed(정렬·필터 적용, `:241`)의 인덱스.
  화살표는 이 배열 순서대로 이동(사용자가 보는 순서와 일치).
- **커서 식별**: 행의 고유 `p.key`로 추적 → 정렬/필터 변경 시에도 안정.
  현재 커서 인덱스는 `rows`에서 `p.key === cursorKey`를 `findIndex`로 재도출.
- **이동 효과**: `analysis.setFocusedSequence(row.seq)` 호출. 기존 하이라이트(`:87`)와
  `SemImage`가 자동 반응.
- **동기화**: `focusedSequence`와 커서를 양방향 정합.
  - 외부에서 `focusedSequence`가 바뀌면(예: 다른 패널이 seq 설정) 커서를
    그 seq의 첫 매칭 행으로 맞춤.
  - `rows`가 바뀌어 현재 커서 key가 사라지면 커서를 클램프(가까운 유효 인덱스).
- **다중 파라미터 주의(기존 한계 계승)**: multiParam 모드에서 seq는 파라미터 간
  중복 가능. 하이라이트는 이미 seq 전역 매칭이므로, 화살표는 `rows` 인덱스 기준으로
  이동하고 `setFocusedSequence(row.seq)`를 설정한다. 이 동작을 스펙에 명시(새 한계 아님).

### 파라미터 요약 (선택: "기본 파라미터만 이동")

- **커서 대상**: 표시된 `summaries` 배열(`:96`)의 인덱스.
- **이동 효과**: `ws.setParam(next)` 직접 호출로 `activeParam`을 그 순서로 이동.
  기존 `extraParams`(비교셋)는 **보존**한다(비우지 않음).
  - 결과적으로 `selectedParams` = extras ∪ 새 activeParam. 이전 activeParam은
    extras에 없었다면 선택에서 빠짐(= "기본 포인터 이동"의 의미, 승인된 동작).
- **선택 토글**: `Space` / `Enter` → `analysis.toggleParam(activeParam, true)`
  (현재 활성 행을 비교셋에 추가/제거). `Space`는 페이지 스크롤 방지 위해 `preventDefault`.
- **커서-activeParam 정합**: 커서는 항상 `activeParam` 행을 가리킨다. 외부에서
  activeParam이 바뀌면 커서도 그 행으로 이동.
- **compute**: 위 "컴퓨팅 부담 분석"의 rAF coalescing 원칙 적용(우선 순수 반응형).

### Part B: Measurement Points 체크박스 다중선택

**새 공유 상태** (`useSkewvoirAnalysis.ts`):

- `selectedSequences`: `useState<number[]>` (또는 Set을 감싼 ref) — 체크된 측정점
  sequence 집합. 리마운트 생존 위해 `useState` 기반, `focusedSequence`와 동일 규약.
- 조작 API: `toggleSelectedSequence(seq)`, `setSelectedSequences(list)`,
  `clearSelectedSequences()`.
- **리셋 규칙**: 포커스 MSR(웨이퍼)이 바뀌면 비움. **activeParam 변경 시엔 유지**
  (선택이 파라미터를 걸칠 수 있고, 활성 파라미터에 없는 seq는 그냥 강조되지 않음).
- `focusedSequence`(단일 커서 = SEM 이미지 구동)와 **독립**.

**Measurement Points 테이블 변경**:

- **MP 열 바로 오른쪽에 체크박스 열** 추가. 클릭 → `toggleSelectedSequence(p.seq)`.
  행 자체 클릭(포커스)과 체크박스 클릭이 겹치지 않도록 체크박스 `@click.stop`.
- **헤더 전체 선택/해제 체크박스**: 현재 필터로 보이는 `rows`의 seq 전체를 토글.
  일부만 선택된 상태는 indeterminate 표시.
- **키보드 시너지 (Part A와 통합)**: 화살표는 커서(`focusedSequence`) 이동,
  **`Space` = 포커스 행의 체크박스 토글**(`toggleSelectedSequence(focusedSeq)`).
  → 키보드만으로 훑으며 다중선택 가능. 파라미터 요약의 Space 패턴과 통일.
- **복사/Excel 범위**: 선택이 비어있지 않으면 **체크된 행만**(보이는 rows ∩ 선택),
  비어있으면 기존대로 보이는 전체 `rows`. `pointsTable()`가 대상 rows를 받도록 조정.
- **meta 표시**: 선택이 있으면 "N개 선택"을 meta에 덧붙임.

**웨이퍼 맵 + Radius Plot 강조**:

- `WaferMap.vue`/`RadiusPlot.vue`에서 기존 `:outlier-seqs` 옆에 `:selected-seqs`
  prop을 추가해 하위 차트로 전달:
  - `WaferMap.vue` → `WaferHeatChart`(main), `WaferDetailModal`.
  - `RadiusPlot.vue` → `RadiusChart`, `RadiusAnalysisDialog`.
- 하위 차트는 이미 `focused-sequence`(단일)와 `outlier-seqs`(집합)를 렌더링하므로,
  `selected-seqs`(집합)를 동일 패턴으로 받아 **포커스(단일)·이상(◎)과 구분되는
  스타일**(예: 외곽선/헤일로)로 표시. 정확한 시각은 구현 단계에서 확정하되
  세 상태(focus/outlier/selected)가 겹쳐도 판별 가능해야 함.
- 웨이퍼 맵은 activeParam site만 그리므로, 선택 집합 중 activeParam에 존재하는
  seq만 강조됨(의도된 동작).

## 구현 구조 / 격리

- 키보드 커서 로직은 **순수 함수로 추출**해 단위 테스트 가능하게 한다. 예:
  `utils/tableCursor.ts`(가칭) — `nextIndex(current, len, key, { home, end })` 같은
  경계·클램프 계산을 담당. 컴포넌트는 이 함수를 호출하고 부작용(포커스 상태 갱신,
  scrollIntoView)만 담당.
- 두 컴포넌트가 공통 규약(tabindex, keydown 분기, scrollIntoView)을 공유하므로,
  가능하면 얇은 컴포저블/유틸로 공통화하되 과설계는 피한다(각 테이블의 "이동 효과"는
  서로 다르므로 콜백으로 주입).

## 에러/엣지 케이스

- 빈 테이블(행 0개): 화살표 무시.
- 필터로 rows가 줄어 커서 key 소실: 가장 가까운 유효 인덱스로 클램프.
- 첫/끝 경계: 이동하지 않음(래핑 없음).
- multiParam seq 중복: `rows` 인덱스 기준 이동으로 결정적 동작 보장.
- 포커스가 테이블 밖(예: 검색 입력)일 때: 화살표는 해당 테이블에 영향 없음
  (keydown이 컨테이너 스코프에 한정되므로 자연히 격리).
- (Part B) 선택된 seq가 현재 activeParam site에 없을 때: 테이블/export에는 남되
  웨이퍼 맵에는 강조되지 않음(리셋 아님).
- (Part B) 필터가 '이상·실패'로 바뀌어 체크된 행이 화면에서 사라져도 선택 집합은
  유지. 헤더 전체 선택/해제·export는 "보이는 rows" 기준으로 동작.
- (Part B) MSR 전환 시 선택 집합 비움.

## 테스트 전략

- `useSkewvoirAnalysis.focusCache.test.ts` 패턴을 따른다.
- 커서 유틸 단위 테스트: 다음/이전/Home/End, 경계 클램프, 빈 배열, len 축소 시 클램프.
- (Part B) 선택 집합 조작 단위 테스트: toggle(추가/제거), setSelectedSequences,
  clear, MSR 전환 시 리셋, activeParam 전환 시 유지.
- (Part B) export 대상 rows 선택 로직: 선택 있음 → 체크된 행만, 선택 없음 → 전체.
- (가능 시) 컴포넌트 로직 테스트: 화살표 → `setFocusedSequence` 호출 인자,
  파라미터 요약 화살표 → `setParam` 호출, Space(요약) → `toggleParam(param, true)`,
  Space(MP) → `toggleSelectedSequence(seq)`, 체크박스 클릭 → 선택 토글.
- 검증(`/verify`): 실제 앱에서 상하 이동 시 SEM 이미지/차트가 즉시 반응하는지,
  체크 시 웨이퍼 맵·Radius Plot에 강조되고 export 범위가 좁혀지는지,
  키 리피트로 버벅이는지 확인 → 버벅이면 rAF coalescing 도입.

## 산출물 체크리스트

**Part A (키보드 탐색)**

- [ ] 커서 유틸(순수 함수) + 단위 테스트
- [ ] `MeasurementPoints.vue` 키보드 탐색 + focusedSequence 동기화
- [ ] `ParamSummary.vue` 키보드 탐색(기본 파라미터 이동 + Space/Enter 토글)
- [ ] 접근성 속성(tabindex/role/aria)

**Part B (측정점 다중선택)**

- [ ] `useSkewvoirAnalysis.ts` 선택 집합 상태 + API + 리셋 규칙 + 단위 테스트
- [ ] `MeasurementPoints.vue` 체크박스 열 + 헤더 전체선택 + Space 토글 + export 범위
- [ ] `WaferMap.vue`/`RadiusPlot.vue`(+하위 차트) `selected-seqs` 강조 렌더
- [ ] Space(MP)와 화살표 커서의 시너지 동작 확인

**공통**

- [ ] `/verify`로 반응성·강조·export 범위·부드러움 확인, 필요 시 rAF coalescing
- [ ] `npm run lint` / `npm run lint:md` / 관련 테스트 통과
