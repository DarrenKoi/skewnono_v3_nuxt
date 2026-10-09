# Skewvoir · AFM 4차 리팩터링 검토

검토 범위는 `806c41c960de402152403e875dea1baf9d0ab7a5..85bc3dea48910a0ada86a1112dd157b6d6f6a507`입니다. BRIEF-4.md의 두 커밋, 19개 파일과 관련 호출 경로를 읽었습니다. 이전 세 리뷰에서 해결·수용한 사항은 다시 finding으로 올리지 않았습니다.

Part A는 blocker 0건, should 0건, nit 1건입니다. Part B는 기존 should 2건과 수치 내보내기 방어의 nit 1건입니다. Part B의 기존 문제는 두 리팩터링이 만든 회귀가 아닙니다.

## Part A. 동작 보존 여부

### [nit] 임계값의 미완성 초안이 다른 URL 항목 변경 뒤에도 남습니다

- 위치: `frontend/app/composables/useSkewvoirRoute.ts:90`, `frontend/app/components/ebeam/skewvoir/workspace/AnomalyThresholds.vue:64`.
- 입력: URL이 `anom=range:10:20&mp=A`인 상태에서 주의 임계값을 `0`으로 바꾸고, 같은 컴포넌트가 유지되는 동안 `mp=B`로 query를 교체합니다. `anom`은 그대로 둡니다.
- 결과: 이전 코드는 새로운 cfg 객체를 만들어 props watcher가 초안을 `10/20`으로 복원합니다. 변경 후에는 `anomRaw`가 같아 cfg 객체도 유지되고 초안은 `0/20`, valid=false로 남습니다. 실제 AnomalyThresholds SFC script를 메모리에서 타입 제거하고 Vue computed/watch/nextTick으로 실행해 확인했습니다. 양쪽 모두 emit은 0회이고 URL 및 판정 임계값은 `10/20`입니다.
- 의미: 실제 화면 초안과 검증 안내의 차이이므로 엄밀한 “visible change 없음”은 성립하지 않습니다. 사용자의 입력을 보존하는 쪽이 합리적이며 판정 오류나 stale 설정은 아닙니다.
- 최소 조치: 초안 보존을 의도한 동작 변화로 커밋 설명에 명시합니다. 기존 복원까지 반드시 보존해야 한다면 중간 `anomRaw` computed를 제거해 직접 파싱하는 원래 식으로 돌아갑니다. 새로운 재설정 이벤트는 이 문제만을 위해 추가할 필요가 없습니다.

### 나머지 Part A 확인

- `afmPoints.ts:22`, `afmTrend.ts:52`: blockRows는 이동 전 함수 및 prepareEntries의 루프와 동일합니다. fallback, 최초 등장 순서와 행 순서를 유지합니다. 빈 Summary, Site 없는 행, 빈 Site, 반복 point, 빈 data를 포함한 9개 조합에서 이전 prepareEntries와 결과가 같았습니다.
- `afmTrend.ts:219`, `afmBundle.ts:226`: centre.n의 values는 동일 recipe, 값이 null이 아닌 행, 고정 기준이 있으면 baseline 역할만 남긴 집합입니다. 기존 bundle의 rows.filter 조건과 같습니다. 6개 pin 조합에서 pinned/unpinned, 혼합 recipe, 값 없는 recipe, group 밖 pin을 비교했습니다. centre의 나머지 필드와 TrendRow도 이전 구현과 같았습니다.
- `afmBundle.ts:32`, `pages/afm/[tool]/see-together.vue:353`: trendRows는 entries.map으로 한 행씩 만들며 정렬·제외를 하지 않습니다. 따라서 rows[i].entry === entries[i]입니다. page의 healthSeries(entries), bundle의 healthSeries(rows.map(...))는 같은 순서입니다. 실제 값 비교도 통과했습니다. 이 추가 인자의 임의 외부 오용을 현재 호출 경로의 회귀로 세지 않습니다.
- `pages/afm/[tool]/see-together.vue:379`, `:389`: pointRows는 같은 rows에서 pointRecipe만으로 필터합니다. relationEntries도 entries에 같은 조건을 적용하므로 측정값의 존재, baseline 역할, validOnly 선택과 무관하게 같은 entry를 같은 순서로 받습니다.
- `afmExport.ts:41`, `afmRelation.ts:23`: localeCompare와 Intl.Collator는 모두 locale=undefined, numeric=true, sensitivity=base입니다. 안정 정렬의 동률 순서도 유지됩니다.
- `useSkewvoirRoute.ts:90`: qstr은 첫 query 값 또는 undefined를 반환하며 재적용해도 같습니다. parseAnomalyCfg도 원래 qstr을 호출했습니다. 실제 anom 문자열 변경은 cfg를 다시 계산합니다. props watcher에 의존하는 로직은 초안 동기화이며, 위 nit 외에 모든 URL patch마다 다시 실행되어야 할 판정·저장 동작은 찾지 못했습니다.
- `useSkewvoirRoute.ts:96`: baseline은 항상 전체 route.query를 파싱하므로 msrs·base 변경을 모두 읽습니다. parseBaseline의 반환 원소는 comma로 분리한 토큰이므로 원소 안에 comma가 없습니다. 빈 토큰도 정상 세트에 들어갈 수 없습니다. 따라서 join 비교가 서로 다른 정상 baseline 목록을 같은 목록으로 보아 stale 값을 반환하는 경로는 없습니다.
- `useSkewvoirAnalysis.ts:777`, `views/PositionStack.vue:156`: set scope에서 comparedMembers는 기존 included.filter(setFiles.has)와 같습니다. single scope에서 unfiltered included를 반환하지만 includedIds/waferCount/sites의 소비는 single의 v-if에 대응하는 set 분기 안에만 있습니다. lazy computed가 single 화면에서 잘못된 집계를 노출하지 않습니다.
- `skewvoirAnalysis/routeQuery.ts:234`: thresholdPair는 기존 두 분기 식 그대로입니다. encode·receipt는 active method를 읽고, AnomalyThresholds의 method 전환은 명시한 다른 method를 읽습니다.
- `skewvoirAnalysis/receipt.ts:233`, `dateTime.ts:68`: 유효한 Date는 toISOString 후 다시 Date로 읽어도 같은 시각이므로 local getter 값과 문자열이 같습니다. 월말·KST 자정·연말·윤일 4개 입력도 같았습니다. receiptFilename의 날짜 부분도 유지됩니다. Invalid Date는 이제 toISOString에서 throw하지만, 실제 호출자는 new Date()를 전달합니다. 이전의 NaN 날짜 문자열 출력을 보존해야 할 사용자 동작으로 판단하지 않았습니다.
- `skewvoirAnalysis/cdu.ts:70`, `dashboard/ParamSummary.vue:105`: paramValues의 gate와 순서는 기존 filter/filter/map과 같습니다. 표의 숫자는 변경 전에도 statsOf의 client 통계였습니다. 서버 count/mean/std/min/max 덮어쓰기는 이 커밋에서 새로 통계 출처를 바꾼 것이 아닙니다. 선택·키보드 이동은 계속 summaries를 읽고, 새로운 rows 소비자는 표 렌더링뿐입니다. null은 기존 NaN 대체와 같이 —로 표시됩니다.
- `position/SpatialLayerMap.vue:20`, `WaferHeatChart.vue:50`: 생략한 hint/why는 같은 label/SHORT로 복원됩니다. scaleLabel은 option 선언 전에 있으며, formatter 호출 시 현재 computed 값에 접근합니다. setup 순서 오류는 없습니다.
- entryTimeText와 receipt의 comparedRows·axisLabel 추출도 원래 식과 조건·순서를 유지합니다.

## Part B. 정리 중 제기된 질문

### 1. [should] 로딩되지 않은 focus를 파라미터 값이 없어 제외했다고 설명합니다

- 위치: `frontend/app/composables/useSkewvoirAnalysis.ts:723`, `frontend/app/utils/skewvoirAnalysis/baselineCompare.ts:80`, `frontend/app/components/ebeam/skewvoir/timeseries/BaselineBlock.vue:132`.
- 입력: `msrs=M1,...,M31&msr=M31&base=M1&scope=set`이고 모두 같은 recipe·parameter·unit으로 호환됩니다. 30건 cap으로 setFiles에는 M1~M30만 있고, focus M31은 별도로 로딩되어 manifest.included에 있습니다.
- 결과: baselineGroups.target에는 M2~M31의 30건이 들어가지만 실제 기여 측정은 M2~M30의 29건입니다. baselineComparison 직접 호출에서 requested=30, msrs.length=29입니다. UI는 “대상 30건 중 1건은 이 파라미터의 측정값이 없어 빠졌습니다.”라고 출력합니다. M31의 값은 존재하지만 이 계산의 파일 집합에 없는 것입니다.
- 최소 수정: splitBaseline의 included 인자로 setComparedMembers가 반환한 로딩된 호환 집합을 사용합니다. 기존 cap 안내를 유지하면 파라미터 값 없음과 cap 제외를 구분할 수 있습니다. comparedMembers 선언이 현재 baselineGroups보다 아래이므로 선언을 먼저 두거나 같은 순수 helper를 그 자리에서 호출합니다.
- 이 finding은 이전 리뷰의 상관·영수증 수치 불일치를 다시 여는 것이 아닙니다. 현재 수치는 로딩된 파일만으로 계산되며, 여기서는 BaselineBlock의 누락 사유만 잘못 설명합니다.

### 2. [should] AFM의 색 범위 라벨이 실제 범위를 표현하지 못합니다

- 위치: `frontend/app/components/afm/detail/SiteGrid.vue:45`, `:160`, `frontend/app/components/afm/detail/HeatmapChart.vue:152`.
- 입력과 결과: SiteGrid의 서로 다른 두 유효 cell 값이 0.220, 0.224이면 실제 폭은 0.004지만 fmt2는 양쪽 모두 `0.22`를 출력합니다. HeatmapChart의 Z 범위가 -0.3~0.3이면 calculable handle 라벨은 `-0 / 0`입니다. 설치된 ECharts의 VisualMapModel.formatValueText를 precision=0으로 직접 호출해 후자를 확인했습니다. 소스의 기본 precision도 0입니다.
- 최소 수정: 현재 공용 scaleFormatter(min,max)를 사용합니다. SiteGrid의 설명과 visualMap.text에는 그 formatter로 양 끝을 출력하고, HeatmapChart에는 같은 범위로 만든 formatter를 지정합니다. 전자는 text를 별도로 쓰므로 formatter만 추가해서는 두 위치가 모두 해결되지 않습니다.
- tooltip의 읽기용 소수 2자리 표시는 이 질문의 수정 범위에 포함할 필요가 없습니다. 공용 helper의 이전 결함은 해결된 상태이며, 이번 문제는 아직 그 helper를 쓰지 않는 두 AFM 화면입니다.

### 3. not a defect. 서로 다른 분석 맵의 자동 범위 정책입니다

- 위치: `frontend/app/components/ebeam/skewvoir/WaferHeatChart.vue:39`, `frontend/app/components/ebeam/skewvoir/position/SpatialLayerMap.vue:175`.
- 확인 입력: 값 [-0.3,0.3]이면 전자는 [-0.3,0.3], 후자는 [-0.5,0.5]입니다. 각 화면의 범위 라벨은 자기 범위를 설명합니다.
- WaferHeatChart의 symmetric 사용자는 PositionStack의 대상−기준 Δ이며, SpatialLayerMap은 단일 측정의 Centered/Residual입니다. 같은 관측값에 반드시 같은 색을 써야 한다는 계약이나 0.5 nm를 공통 바닥으로 써야 한다는 근거는 찾지 못했습니다. 어느 하나가 확정 의도라고 단정할 수 없습니다.
- 최소 수정은 없습니다. 정책 통일을 별도로 선택한다면 비영점 데이터의 최대 절댓값으로 범위를 잡고 0일 때만 fallback을 사용하는 기존 WaferHeatChart 식을 재사용할 수 있습니다. 이는 이번 회귀 수정이 아니라 동작 선택입니다.

### 4. not a defect. 마지막 유효 회차와 마지막 회차는 명시된 서로 다른 규칙입니다

- 위치: `frontend/app/utils/afmTrend.ts:123`, `frontend/app/utils/afmSiteGrid.ts:65`, `frontend/app/components/afm/detail/SiteGrid.vue:62`.
- 확인 입력: 같은 point·Site 좌표에서 첫 행이 COMPLETED/Valid=true/H=10, 마지막 행이 FAILED/H=20이면 validOnly의 pointValues는 10을 남기고 siteGrid의 cell.value는 null입니다. 실제 helper 호출로 확인했습니다.
- `docs/afm/feature-summary.md:112`는 제외 선택의 마지막 유효 회차를 명시합니다. 상세 격자는 `:82` 및 화면 안내에서 마지막 회차를 명시하고 FAILED는 값으로 칠하지 않습니다. 값 차이는 이 두 규칙의 결과입니다.
- 최소 수정은 없습니다. 이미 수용한 제외 정책을 바꾸지 않습니다. 선택 옆에 “마지막 유효 회차”를 더 보여 주는 문구 개선은 가능하지만 필수 결함 수정은 아닙니다.

### 5. [nit] −0은 시트 배열에 도달하고, 비유한 값 방어도 빠져 있습니다

- 위치: `frontend/app/utils/afmBundle.ts:191`, `:301`.
- 확인 입력: FAILED point의 값이 -0.000001이면 bundleSheets의 측정값은 Object.is(cell,-0)=true입니다. 그러나 ExcelJS의 실제 XML은 `<v>0</v>`이므로 이 −0 자체가 사용자에게 잘못 보이는 결함은 아닙니다.
- 원래 측정값과 health 숫자는 summaryNumber가 비유한 입력을 거릅니다. 다만 두 측정의 유한한 Summary MEAN을 각각 1e308로 주면 centre.mu=Infinity, lcl=NaN이 됩니다. 이 계산 결과는 round와 toSheetRows를 통과합니다. raw Site X=NaN도 cell이 그대로 허용하지만, 이것은 정상 JSON 응답으로 전달되는 입력이라는 증거가 없어 별도 실제 발생 사례로 세지 않습니다.
- ExcelJS를 디스크 파일 없이 메모리에서 실행한 결과 NaN/Infinity는 각각 `<v>NaN</v>`, `<v>Infinity</v>`로 기록됩니다. 비유한 계산 결과가 있다면 정상 숫자 셀로 내보낼 수 없습니다. 1e308 nm는 물리적으로 현실적인 측정은 아니므로 이 경계는 nit로 분류합니다.
- 최소 수정: 숫자 셀을 round에서 Number.isFinite로 검사해 비유한 값은 빈 칸으로 만들고, 유한 소수는 Number(cell.toFixed(4))+0으로 정규화합니다. 문자열·정수·기존 반올림 정책은 유지합니다. NaN이 정상 사내 자료에서 관측됐다는 주장은 하지 않습니다.

### 6. not a defect. 타이핑과 캐시는 현재 근거로 필수 변경하지 않습니다

- 위치: `frontend/app/components/ebeam/skewvoir/workspace/AnomalyThresholds.vue:74`, `frontend/app/composables/useSkewvoirRoute.ts:166`, `frontend/app/components/afm/trend/ProfileOverlay.vue:133`.
- 임계값은 유효한 입력마다 emit하며 URL은 router.replace로 갱신합니다. 숫자 값이 같으면 emit하지 않고, invalid draft는 판정에 쓰지 않습니다. `12.5`의 중간 값들이 유효하면 여러 번 재판정하는 것은 사실이지만 history 누적이나 잘못된 최종 임계값은 확인하지 못했습니다. 지연을 측정하지 않은 상태에서 debounce·Apply 버튼을 필수 수정으로 추가할 근거는 없습니다.
- profileCache는 tool/file/point별로 SPA 수명 동안 보관하므로 현재 그룹 20건은 누적 캐시 크기의 상한이 아닙니다. FHD도 이를 제한하지 않습니다. “한 줄 약 1 MB”는 실측하지 않았으며, 장시간 여러 point·group을 순회하면 메모리가 누적되는 한계는 분명히 있습니다.
- 이전 `codex-review.md:70`이 이 제한을 수용하고 LRU를 요구하지 않았으므로 이번에도 새 should로 다시 올리지 않습니다. 최소 수정은 없습니다. 실제 장시간 사용에서 메모리 압박이 확인되면 활성 profile을 보호하는 제한된 캐시를 검토합니다. 현재 크기에서 반드시 문제없다는 성능 보증은 아닙니다.

## 검증과 한계

- frontend npm test: Node 24.13.0, 2,176 pass, 0 fail, 0 skip, 24 suites입니다.
- 이전 AFM 모듈을 git show로 읽고 메모리에서 실행한 15개 grouping·pin 조합이 동등했습니다. 관련 현재 helper, baseline 누락 계수, 회차 차이, 날짜, ECharts 라벨 및 ExcelJS 숫자 XML도 직접 확인했습니다.
- `git diff --check 806c41c9..HEAD`는 통과했습니다.
- heredoc 직접 검사는 읽기 전용 샌드박스의 임시 파일 제한으로 시작하지 못했습니다. 파일을 만들지 않는 node -e 방식으로 같은 검사를 실행했습니다.
- 서버·브라우저·사내 자료·실제 Excel UI·장시간 메모리/타이핑 성능은 확인하지 않았습니다. frontend lint/typecheck/build와 backend 테스트는 이 frontend 리팩터링 검토에서 재실행하지 않았습니다. Part A의 초안 차이는 Vue script 실행 증거이며 브라우저 조작 증거는 아닙니다.
- 소스·테스트·설정·Git 상태를 변경하지 않았습니다. 작성한 파일은 이 리뷰 하나입니다.

판정: 두 커밋은 현재 상태로 병합해도 됩니다. 임계값 초안 보존은 의도한 화면 변화로 명시하고, Part B의 기존 should 2건은 후속 수정합니다.

## Author 응답 (2026-10-09)

- **Part A nit (임계값 초안 보존):** 받아들입니다. 다른 URL 항목이 바뀌어도 미완성 초안이 남는 것은 의도한 변화로 둡니다. 판정에 쓰이는 값과 URL은 그대로입니다.
- **B1 (should):** 수정했습니다. `baselineGroups`가 `comparedMembers`(호환 + 로딩된 멤버)로 좁혀집니다.
- **B2 (should):** 수정했습니다. `SiteGrid.vue`의 색 범위 문구·visualMap text와 `HeatmapChart.vue`의 visualMap 라벨이 `scaleFormatter`를 거칩니다. 툴팁의 소수 2자리는 그대로입니다.
- **B5 (nit):** 수정했습니다. `afmBundle.ts`의 `round`가 비유한 값을 빈 칸으로, −0을 0으로 씁니다.
- **B3, B4, B6:** 결함 아님 판정을 따라 바꾸지 않았습니다.
- 검증: frontend `npm test` 2176 pass, typecheck·lint clean. :3101 worktree 서버에서 세트 위치 비교·Time-Series 기준 블록·상관·측정 개요, 임계값 편집과 Back 복원, AFM 시계열 비교·측정 상세 Site 격자(`색 범위 63.1 – 68.2`)를 브라우저로 확인했습니다.
