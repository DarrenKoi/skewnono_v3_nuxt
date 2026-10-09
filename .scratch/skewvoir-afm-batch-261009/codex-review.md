# 2026-10-09 변경 검토

검토 범위는 `main`의 `a49931d8..ea463854d2d14f7ba2379f87db25a3d333239583`입니다. 브리프의 13개 커밋, 66개 변경 파일과 관련 호출 경로를 읽었습니다. 소스 수정, Git 상태 변경, 서버·브라우저 실행은 하지 않았습니다.

결과는 blocker 3건, should 2건, nit 1건입니다. 아래 수치 재현은 실제 유틸 함수를 Node 24.13.0에서 직접 호출한 결과입니다. Vue 선택 상태 재현은 SFC의 script setup을 메모리에서 타입 제거한 뒤 실제 Vue 반응성 API로 실행했습니다. 브라우저 검증은 아닙니다.

## Skewvoir

### [blocker] 1. 위치 호환성이 없는 측정도 같은 site의 Δ로 표시합니다

- where: `frontend/app/components/ebeam/skewvoir/views/PositionStack.vue:160`, `frontend/app/utils/skewvoirAnalysis/baselineCompare.ts:136`
- what: 새 Δ 맵은 `manifest.included`만 적용하며 `manifest.readiness.multiMsrDelta`를 확인하지 않습니다. 포함 여부는 좌표계 충돌을 모두 거르지 않으므로 같은 chip 인덱스가 다른 물리 위치를 뜻해도 같은 위치의 변화량으로 표시합니다. 영수증의 `기준 대비 site`에도 같은 값이 들어갑니다.
- failing input / evidence: B와 T의 recipe=R, parameter=CD, unit=nm, chip=`1,1`, MP=1을 같게 하고 layout hash는 생략합니다. chip pitch만 B=`1000000,1000000`, T=`2000000,2000000`으로 다르게 합니다. CD는 각각 10, 20입니다. `buildAnalysisManifest → splitBaseline → baselineDeltaMap`의 실제 결과는 `included=["B","T"]`, `readiness={status:"unavailable",reasons:["layout-mismatch"]}`인데도 `points=[[1,1,10]], unpaired=0`입니다. B와 T는 같은 물리 위치의 관측이 아닙니다. 기존 baseline 테스트는 이 readiness 경계를 다루지 않습니다.
- suggested fix: 화면과 영수증이 같은 readiness 조건을 적용해 위치 비교 불가 시 Δ 맵을 계산·내보내지 않도록 합니다.

### [blocker] 2. 실패한 세트 교체 후 이전 파일 개수로 영수증 다운로드를 허용합니다

- where: `frontend/app/utils/skewvoirAnalysis/receipt.ts:357`, `frontend/app/components/ebeam/skewvoir/workspace/LeftRail.vue:608`
- what: `receiptReady`는 현재 세트의 파일인지 확인하지 않고 loaded 개수만 비교합니다. `loadSet`은 실패 시 이전 map을 유지하므로 현재 선택의 자료가 준비되지 않았는데도 영수증 버튼이 켜집니다. 다운로드 함수도 모달을 연 뒤 바뀐 준비 상태를 다시 확인하지 않습니다.
- failing input / evidence: A·B 2건을 읽은 뒤 C·D 2건으로 세트를 바꾸고 새 batch를 실패시킵니다. focus C는 독립 경로로 로딩되어 있고, `setRows=[C,D]`, `setFiles={A,B}`, `setError=true`, `setPending=false`가 됩니다. 실제 `receiptReady({scope:"set",focusLoaded:true,setResolved:2,setLoaded:2,setPending:false})` 결과는 `true`입니다. 파일의 세트 시트에는 focus fallback으로 C만 포함하고 D는 로딩 실패로 적힙니다. 화면·URL의 세트가 완전히 준비되었다는 다운로드 조건을 충족하지 않습니다. 현재 테스트도 개수만 바꿔 검사하여 이전 키/현재 키가 다른 사례를 놓칩니다.
- suggested fix: 이미 있는 `isSetPoolComplete`의 키·개수 검증을 공유하고 setError 및 다운로드 시점의 준비 상태도 확인합니다.

### [blocker] 3. 세트에 없는 focus 파일을 영수증만 기준 통계에 추가합니다

- where: `frontend/app/utils/skewvoirAnalysis/receipt.ts:130`, `frontend/app/utils/skewvoirAnalysis/receipt.ts:174`
- what: 영수증은 scope와 무관하게 focus 파일을 setFiles에 추가한 뒤 기준 통계를 계산합니다. 화면의 BaselineBlock과 Δ 맵은 setFiles만 사용하므로 같은 상태에서 화면은 평가 불가인데 영수증은 숫자를 기록할 수 있습니다.
- failing input / evidence: `msrs=M1,...,M31`, `msr=M31`, `base=M31`이면 30건 상한으로 setFiles에는 M1~M30만 있습니다. focus M31은 별도로 로딩되며 manifest의 included에는 들어갑니다. 따라서 baselineGroups.base에는 M31이 있지만 화면 통계의 base 파일은 없습니다. 이를 축소해 focus F의 값=[10,12], setFiles의 T 값=[20,22], base=[F], target=[T]로 직접 실행한 결과는 `screen.comparison=null`, `receipt.comparison.shift=10`입니다. 영수증은 기준 3σ 대비 2.3570배, 산포 배율 1까지 기록합니다. 상한 notice는 M31이 분석에 들어가지 않았다고 설명하므로 이 결과와도 어긋납니다.
- suggested fix: set scope의 영수증과 화면에 동일한 파일 집합을 사용하고, focus 보충은 single scope에만 적용합니다.

### 확인한 범위

- pooled 평균·표본 표준편차·3σ·range, 0인 기준 σ의 배율 공란, 양쪽 최소 표본, dominance의 60% 초과 경계, 한쪽에만 값이 있는 chip의 unpaired 계산을 확인했습니다. 계산식 자체에서는 추가 결함을 찾지 못했습니다.
- `anom`의 유효한 active-method pair 인코딩·파싱, 비활성 방식의 기본값 복귀, `base`의 중복 제거·세트 교집합, `rfit` 공유 경로를 확인했습니다. threshold draft의 변경 순서와 emit 동등성 가드를 읽었으며 일반적인 유효 값에서 반복 emit 경로는 찾지 못했습니다. 숫자 입력 위젯의 실제 타이핑 동작은 확인하지 않았습니다.
- `loadSet/retrySet`의 빈 키 초기화, incremental carry, 다른 키의 늦은 응답·예외·finally 가드를 확인했습니다. 다른 키로 이동한 요청의 setError가 현재 키에 남는 경로는 찾지 못했습니다.
- quality는 별도 feature family와 별도 `spatialScorePoints`로 전달됩니다. 실제 판정 코드인 `utils/anomaly/*`, `verdict.ts`, `overview.ts`, Time-Series 계산·roll-up은 quality 값을 읽지 않습니다. score 변경 불변성 테스트와 판정 모듈 읽기 금지 검사도 통과했습니다.
- ObjectSEM·VRD는 schema의 기존 표기와 맞고 새 계약 테스트는 문서에 없는 catalog key를 검출합니다. score 척도·방향과 alignment offset 해석의 OFFICE-VERIFY는 schema 문서와 mock docstring 양쪽에 있습니다. 새 quality 입력은 nullable score와 비숫자/빈 offset을 거릅니다. 새 frontend 타입과 backend 계약 사이의 추가 불일치는 찾지 못했습니다.
- 새 Score 레이어는 판정 ramp와 다른 순차 chart palette를 사용하며, 척도 미확인 문구와 mock 안내가 있습니다. Cp/Cpk, spec 판정, AFM↔e-beam 연결을 추가한 경로는 찾지 못했습니다.

## AFM

### [should] 4. 기준 토글이나 그룹 갱신이 사용자가 고른 Y축을 초기화합니다

- where: `frontend/app/components/afm/trend/RelationChart.vue:80`
- what: columns 또는 상위 column이 바뀔 때마다 Y를 상위 측정 항목으로 무조건 덮어씁니다. 기준 토글은 trendRows와 relationEntries를 다시 만들기 때문에 항목 목록이 동일해도 사용자의 유효한 Y 선택이 사라집니다.
- failing input / evidence: measured columns=[A (nm), B (nm), C (nm)], 상위 column=B (nm)에서 Y를 C (nm)로 선택합니다. SFC의 실제 watcher를 Vue로 실행하고 entries만 동일한 내용의 새 배열로 바꾸면 `chosen_y C (nm)` 뒤 `same_columns_after_entries_change_y B (nm)`가 출력됩니다. 페이지에서는 기준 토글·측정 추가/제거가 이 갱신을 일으킵니다. 순수 관계 테스트는 이 선택 상태를 검사하지 않습니다.
- suggested fix: 상위 column이 실제로 바뀔 때만 따라가고, columns 갱신 시에는 현재 Y가 목록에서 사라졌을 때만 대체합니다.

### [should] 5. 첫 블록에 좌표가 없으면 좌표가 있는 다른 블록을 선택할 수 없습니다

- where: `frontend/app/components/afm/detail/SiteGrid.vue:8`
- what: 블록 선택기 전체를 현재 grid에 cell이 있을 때만 표시합니다. 처음 선택된 블록에 좌표가 없으면 다른 블록의 격자가 존재해도 선택기를 사용할 수 없습니다.
- failing input / evidence: data 첫 행은 `Site=A, Site X=null, Site Y=null, H (nm)=10`, 다음 행은 `Site=B, Site X=1, Site Y=1, H (nm)=20`이고 서로 다른 measurement_point를 줍니다. 실제 blockRows/siteGrid 결과는 `blocks=["A","B"], defaultBlockCells=0, secondBlockCells=1`입니다. block watcher가 A를 고르고, template의 `v-if="grid.cells.length"`가 B로 전환할 선택기를 감춥니다. null 좌표는 기존 siteGrid 테스트도 지원하는 입력입니다.
- suggested fix: blockItems가 있을 때 블록 선택기를 보여 주고, 격자 없는 안내는 현재 블록 범위로 표시합니다.

### [nit] 6. 새 차트의 축 helper가 option computed 내부에 있습니다

- where: `frontend/app/components/afm/detail/SiteGrid.vue:128`, `frontend/app/components/afm/trend/RelationChart.vue:99`, `frontend/app/components/afm/trend/ProfileOverlay.vue:259`
- what: 브리프가 명시한 “helpers must be declared above the option computed” 규칙과 달리 세 컴포넌트가 axis helper를 option computed 안에서 선언합니다. 현재 계산 오류나 hover 의존성은 확인하지 못했습니다.
- failing input / evidence: 세 chartOption computed 본문 안의 `const axis = ...` 선언을 직접 확인했습니다. 이는 런타임 결함이 아닌 명시된 검토 기준 위반입니다.
- suggested fix: axis helper를 chartOption 앞에 선언합니다.

### 확인한 범위

- 고정 기준은 loaded entry에 속한 baseline만으로 recipe별 μ와 범위를 만들고 기준 측정은 out 판정에서 제외합니다. 다른 recipe에 기준 표본이 없을 때 다른 recipe의 기준을 빌리지 않는 경로를 확인했습니다. 그룹 삭제·교체·비우기는 setGroup을 거쳐 baseline을 prune하며 usePersistedState를 사용합니다. cart의 저장·삭제 lifecycle은 실제 앱에서 실행하지 않았습니다.
- Lot·Slot 숫자 선행 0 정규화, 빈 Lot·Slot의 연결 거부, 시간순·파일명 tie-break, 같은 recipe 기본 필터, 그룹 잔여 자리와 기존 포함 항목 제외를 확인했습니다. “가까운 순”은 실제 시간 간격이 아니라 문서화된 시간순 인덱스 거리로 구현되어 있습니다.
- 관계는 같은 행의 두 값을 pairing하며 반복 lap을 독립 행으로 유지합니다. State·Valid gate, 결측·Valid 미상 계수, 최소 n=3 및 상수 축 r=null을 확인했습니다. 항목 간 차이와 원인 판정을 내지 않습니다.
- seconds per point는 가장 큰 block의 전체 행 수로 나눕니다. 반복·FAILED·STOPPED 행 포함, data 없는 경우 공란, recipe별 per-point 중앙값을 확인했습니다. 블록별 재스캔 여부는 문서가 미확인으로 남겨 두므로 실제 포인트당 스캔 시간으로 확인된 값은 아닙니다.
- Site 격자는 정수 인덱스만 사용하고 같은 point의 마지막 행을 채택합니다. 같은 cell의 여러 유효 point 평균, 실패·중단·무효 표시, 선택 point 연동 코드를 확인했습니다. wafer 외곽·notch·mm·Y 방향 확정 주장은 추가하지 않았습니다.
- 프로파일의 DataSize 우선 1D 분류, 단위 없는 결과 제외, 단위 별칭 비교, 동일 recipe 범위, 최소제곱 직선 제거와 X 불변성을 확인했습니다. 캐시 키는 tool·filename·point이며 과거 point의 응답은 그 키에 저장됩니다. 화면은 현재 point 키만 읽으므로 point 변경 뒤 과거 point의 값이 현재 값으로 표시되는 경로는 찾지 못했습니다.
- 프로파일 캐시의 세션 동안 무제한 보관은 기존 ponytail 제한 주석으로 명시되어 있습니다. LRU 추가는 이 검토에서 요구하지 않습니다. 2D anchor 선조회, failed 재조회, 나머지 병렬 조회 경로는 소스 수준에서 확인했습니다.
- 새 band 문구는 관리 한계·규격이 아닌 참고 범위라고 명시합니다. 가동률·OEE를 계산하거나 확정하는 새 경로는 찾지 못했습니다. 새 차트 색은 tokens/chart palette를 사용하며 hover 상태를 chart option 입력으로 추가하지 않았습니다.
- 같은 Lot 후보 상세·함께 보기 링크는 실제로 추가되었습니다. 이는 요청된 후보 확인·시계열 비교 이동 범위이며 다른 도메인 간 연결은 아닙니다. 브리프의 “no cross-page links added”를 같은 AFM 내부 이동까지 금지하는 뜻으로 적용하면 이 부분은 규칙 예외 확인이 필요합니다.
- 새 유틸 테스트의 주요 수치 기대값은 구체적인 고정값이며 구현 결과로 기대값을 다시 만드는 동어반복은 찾지 못했습니다. 위 두 should 사례, cart baseline prune, SFC threshold/cache 비동기 lifecycle을 직접 검증하는 새 테스트는 이 diff에 없습니다.

## Gate 결과

| 검사 | 결과 |
| --- | --- |
| frontend npm test | 2,116 passed, 0 failed, 0 skipped, 24 suites |
| frontend npm run lint | exit 0, 0 errors, 2 warnings |
| backend/msr_file pytest | 138 passed, 2 skipped, 59.12초 |
| ruff check . --no-cache | exit 0, All checks passed |
| git diff --check a49931d8..HEAD | exit 0 |
| npm run lint:md | exit 0, 215 files, 0 issues |

frontend lint 경고 2개는 변경하지 않은 `gallery/ImageViewer.vue:201`과 `:202`의 prop camelCase 경고입니다.

기본 Homebrew Node로 npm test/lint를 실행하면 `libllhttp.9.3.dylib` 누락으로 exit 134가 발생했습니다. 설치되어 있는 NVM Node 24.13.0을 PATH 앞에 놓고 재실행한 위 결과입니다.

pytest는 최초 샌드박스 실행에서 `No usable temporary directory found`로 수집 전에 중단됐습니다. 권한이 허용된 재실행은 bytecode·pytest cache 생성을 막는 `-B -p no:cacheprovider`를 붙여 통과했습니다. ruff에도 `--no-cache`를 사용했습니다. 위 gate는 home/mock 및 office template 단위 검증이며 실제 사내 서비스 연결 증거가 아닙니다. skip은 office provider 부재에 따른 template 비교와 mock의 layout metadata gate입니다.

## 검토하지 않은 것

- 브리프에 따라 서버 실행, 브라우저, 차트 실제 렌더링·hover·키보드 조작, 반응형 배치, 라우터의 실제 입력 타이밍을 검증하지 않았습니다.
- Excel 파일을 실제 생성하거나 Excel에서 열지 않았습니다. receipt 객체·sheet 행 계산과 UI에서 넘기는 입력을 검토했습니다.
- 사내 Redis·MinIO·pickle 실데이터, 배포된 gitignored office.py, 사내 네트워크 및 cloud 실행, AFM 실제 장비의 블록별 재스캔·좌표 방향·score 척도는 확인하지 않았습니다.
- 전체 backend pytest, frontend typecheck/build, 메모리 장시간 측정은 실행하지 않았습니다.
- 지정 범위 밖 기존 결함과 기존 문서 전체, untracked BRIEF·reports·research_notes는 변경 검토 대상에 포함하지 않았습니다.

## Author 응답 (2차 확인 요청)

수정은 브랜치 `work/review-fixes` 의 두 커밋입니다 (`git diff main..work/review-fixes`).

- **1 (Δ 맵 위치 호환성):** 수용했습니다. `analysis.siteDeltaReady`(`manifest.readiness.multiMsrDelta.status !== 'unavailable'`)를 화면과 영수증이 함께 봅니다. `limited` 는 공통 site 부분집합이 있다는 뜻이라 짝짓기를 허용했습니다. 이 판단이 틀렸으면 지적해 주십시오. 기존 Composite Mean / Site Variability 맵도 readiness 를 보지 않는데, 이번 diff 이전부터 그랬으므로 손대지 않았습니다.
- **2 (receiptReady):** 수용했습니다. `isSetPoolComplete` 의 키 검증을 공유하고 `setError` 를 거부 조건에 넣었으며, 내려받기 시점에 다시 확인하고 버튼도 비활성으로 만듭니다.
- **3 (focus 보충):** 수용했습니다. focus 파일 보충은 single scope 에만 적용합니다.
- **4 (Y축 초기화):** 수용했습니다. 페이지 측정 항목이 바뀔 때만 따라가고, 목록 갱신 때는 현재 Y 가 사라졌을 때만 바꿉니다.
- **5 (블록 선택기):** 수용했습니다. 블록이 둘 이상이면 선택기를 항상 보여 줍니다.
- **6 (axis helper 위치):** 반려합니다. 이 저장소의 규칙이 막으려는 것은 option computed **아래** 모듈 범위에 선언된 helper 가 setup 시점에 TDZ 로 터지는 경우입니다. computed 본문 안에 선언된 `const axis` 는 호출 전에 초기화되므로 해당하지 않습니다. 브리프의 문구가 부정확했습니다.

## 2차 확인

검토 대상은 `main..work/review-fixes`의 `9536af3e`, `1ed87fb5` 두 커밋이며, worktree HEAD는 `1ed87fb51e6bf9387e57bf94f9fd2034cff40250`입니다. Author 응답을 읽고 원래 실패 입력과 수정된 호출 경로를 다시 확인했습니다.

1. **still open**: 원래 chip pitch 충돌 사례는 화면·영수증의 readiness gate로 해결됐습니다. 다만 `limited`일 때 같은 chip의 서로 다른 MP까지 섞습니다. 같은 geometry에서 기준 B=`(chip 1,1 / MP1 / CD10), (chip 1,1 / MP2 / CD100)`, 대상 T=`(chip 1,1 / MP1 / CD20), (chip 2,2 / MP3 / CD30)`이면 readiness는 `limited, common-coverage:1`이고 공통 MP1의 Δ는 +10인데, 실제 맵은 `[[1,1,-35]]`를 출력합니다. “공통 site 부분집합을 짝짓는다”는 해석대로 계산하지 않습니다.
2. **resolved**: A·B의 map을 유지한 C·D 로딩 실패 입력에서 키 불일치 또는 setError가 있으면 receiptReady=false입니다. 정상 키·정상 로딩에서만 true이며, 모달 버튼 비활성화와 downloadReceipt 진입 시 재검증도 확인했습니다.
3. **resolved**: focus F=[10,12], setFiles T=[20,22], base=[F], target=[T]의 set scope에서 영수증 comparison=null이고 F는 제외입니다. single scope의 focus 보충은 유지됩니다. 새 회귀 테스트와 전체 테스트가 통과했습니다.
4. **resolved**: 실제 SFC watcher를 Vue로 실행해 Y=C (nm)가 동일 항목의 entries 재생성 뒤에도 유지됨을 확인했습니다. 상위 column을 A (nm)로 바꾸면 Y가 따라가고, 현재 Y 항목을 목록에서 제거하면 유효 항목으로 대체됩니다.
5. **resolved**: 첫 블록 A에 좌표가 없고 B에 좌표가 있는 원래 입력에서 블록 선택기를 숨기던 조건이 제거됐습니다. 수정된 실제 template을 Vue SSR로 렌더링해 `aria-label="블록"` 선택기와 “이 블록의 행에는” 안내가 함께 존재함을 확인했습니다.
6. **rebuttal accepted**: computed 내부의 axis는 해당 본문에서 호출하기 전에 초기화되므로 모듈 범위 helper의 TDZ 문제에 해당하지 않습니다. Author가 브리프의 규칙 의도를 명확히 했으므로 기존 nit를 철회합니다. helper 이동은 필요하지 않습니다.

### limited readiness에 대한 답변

`limited` 자체를 전부 거부할 필요는 없습니다. 현재 layoutReadiness는 알려진 좌표계 충돌이 없고 공통 canonical site가 존재할 때 이를 반환하므로, 확인된 공통 부분만 비교하는 데는 사용할 수 있습니다. 그러나 이 상태는 허용 조건이지 pairing 작업을 대신하지 않습니다.

현재 canonical key는 `chip_number + mp_number`인 반면 baselineDeltaMap은 chip만으로 묶고 그 chip의 모든 행을 평균합니다. 따라서 위 1번처럼 공통 MP와 기준에만 있는 MP가 섞이면 비교 대상 구성의 차이가 수치 이동으로 나타납니다. Author의 “limited이므로 공통 site 부분집합을 짝짓기를 허용했다”는 설명은 **현 구현에 대해서는 수용하지 않습니다**. 공통 canonical site만 짝지은 뒤 동일 MP 구성을 chip별로 합치거나, MP 구성이 다른 chip의 Δ를 보류해야 합니다. 이 문제는 두 수정 커밋이 새로 만든 계산식 결함은 아니며, 이번에 요청한 limited 경계 확인에서 드러난 기존 Δ 계산의 미해결 조건입니다.

### 수정으로 생긴 새 결함

**새 안내 문구가 unavailable의 모든 원인을 확정된 배치 불일치로 설명합니다.** 위치는 수정 브랜치의 `frontend/app/components/ebeam/skewvoir/views/PositionStack.vue:66`과 `frontend/app/utils/skewvoirAnalysis/receipt.ts:312`입니다.

같은 recipe·unit·wafer_size·chip_array·chip_pitch·map_origin을 가진 B와 T에서 layout hash는 생략하고, B는 chip 1,1과 2,2를, T는 chip 3,3과 4,4를 각각 측정하게 합니다. 값은 B=[10,12], T=[20,22]입니다. 실제 readiness는 `unavailable, reasons=["layout-unknown"]`인데 영수증 행은 `["site별 비교","세트의 wafer 배치가 서로 달라 site 단위로 비교하지 않았습니다"]`입니다. 배치는 같고 관측 site가 겹치지 않는 사례를 “배치가 다르다”로 확정합니다. recipe 불일치로 included가 1건뿐일 때의 `needs-multiple-msrs`도 같은 화면 문구로 설명됩니다.

readiness reason에 따라 사유를 구분하거나 “같은 위치임을 확인할 수 없어 site 단위로 비교하지 않았습니다”처럼 확인 불가로 표현하는 것이 맞습니다. 위 1번의 MP pairing 조건과 이 새 사유 문구 외에는 두 수정 커밋에서 추가 결함을 찾지 못했습니다. 기존 Composite Mean / Site Variability 맵은 요청대로 이번 수정 검토를 확장하지 않았습니다.

### 2차 검증 및 한계

- 수정 worktree에서 NVM Node 24.13.0으로 npm test를 실행했습니다. **2,120 passed, 0 failed, 0 skipped, 24 suites**입니다.
- 같은 worktree의 npm run lint는 exit 0이며, 수정하지 않은 ImageViewer.vue의 기존 경고 2개만 남았습니다. `git diff --check main..work/review-fixes`도 통과했습니다.
- 키·오류 readiness, geometry 충돌, limited MP pairing, 동일 geometry의 비공통 site를 실제 유틸 호출로 확인했습니다. Y watcher는 실제 SFC script setup을 메모리에서 타입 제거해 실행했고, SiteGrid는 실제 template을 컴파일해 SSR로 확인했습니다. 검증용 파일은 생성하지 않았습니다.
- 서버·브라우저·Excel 파일 생성·사내 실데이터 검증은 하지 않았습니다. frontend-only 수정이므로 backend 검사는 반복하지 않았고 typecheck/build도 실행하지 않았습니다. 수정 worktree와 소스·테스트 파일은 변경하지 않았습니다.

## Author 응답 2 (3차 확인 요청)

커밋 `ee34cc5a` (`git show ee34cc5a`, 브랜치 `work/review-fixes`) 입니다.

- **1 잔여 (MP pairing):** 수용했습니다. `baselineDeltaMap` 이 chip 안에서 양쪽이 모두 측정한 MP 끼리만 차이를 내고 그 평균을 chip 값으로 씁니다. 공통 MP 가 없는 chip 은 짝 없음으로 셉니다. 지적하신 입력은 테스트로 고정했습니다(+10, 짝 없음 1).
- **새 결함 (사유 문구):** 수용했습니다. "같은 위치임을 확인할 수 없어" 로 바꾸고 화면은 분석 준비 상태를 가리킵니다. 짝 없음 라벨도 "공통 측정점이 없는 chip" 으로 바꿨습니다.

## 3차 확인

검토 범위는 `work/review-fixes`의 `ee34cc5a5d5e6ef587b587ac2d3c0c5e3ff52058` 한 커밋입니다. Author 응답 2와 `git show ee34cc5a`를 읽고 수정 worktree에서 두 잔여 항목만 재확인했습니다.

- **MP pairing: resolved.** 기존 실패 입력 B=`(chip 1,1 / MP1 / CD10), (chip 1,1 / MP2 / CD100)`, T=`(chip 1,1 / MP1 / CD20), (chip 2,2 / MP3 / CD30)`의 실제 결과는 `points=[[1,1,10]], unpaired=1`입니다. 같은 chip에서 MP가 서로 다르면 `points=[], unpaired=1`이며 0으로 그리지 않습니다. 여러 MSR에 걸쳐 MP별 관측 수가 다르고 공통 MP가 둘인 사례도 확인했습니다. MP1의 기준 평균 20·대상 평균 40, MP2의 기준 평균 100·대상 평균 140이면 chip Δ는 두 MP 차이의 평균인 30입니다. null CD·음수 MP는 제외됩니다. 화면과 영수증은 같은 baselineDeltaMap을 호출합니다.
- **사유 문구: resolved.** 같은 geometry에서 B가 chip 1,1·2,2, T가 chip 3,3·4,4를 측정한 기존 실패 입력은 여전히 `unavailable, layout-unknown`이지만 영수증 행은 이제 `["site별 비교","같은 위치임을 확인할 수 없어 site 단위로 비교하지 않았습니다"]`입니다. 화면도 “같은 위치를 쟀는지 확인할 수 없어”라고 표현하고 분석 준비 상태로 사유를 안내합니다. 배치 불일치를 확정하지 않으므로 표본 부족·비공통 site에도 거짓 원인을 제시하지 않습니다. 짝 없음의 영수증 라벨도 “공통 측정점이 없는 chip”으로 바뀌었습니다.
- **새 결함:** 이 커밋에서 추가 결함을 찾지 못했습니다. MP별 차이를 구한 뒤 공통 MP에 같은 가중치를 주는 계산과 chip 합집합에서 짝지어진 chip을 뺀 unpaired 계수를 확인했습니다. 이제 limited에서 공통 MP만 비교한다는 Author의 설명을 수용합니다.

검증은 수정 worktree의 baselineCompare·receipt 테스트 **32 passed, 0 failed, 0 skipped**, 위 입력의 직접 assert 검사, `git diff --check ee34cc5a^ ee34cc5a` 통과입니다. 전체 테스트·lint·typecheck는 반복하지 않았고 서버·브라우저·Excel 파일 생성·사내 실데이터는 확인하지 않았습니다. 이 보고서 외 파일은 수정하지 않았습니다.
