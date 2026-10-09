# AFM 후속 변경 검토

검토 범위는 `main`의 `a7d79271..e35186801554206d556241a085b825494a00252e`입니다. BRIEF-2.md와 참조 BRIEF.md의 기준으로 5개 커밋의 변경 및 연결된 화면·유틸·테스트를 확인했습니다. 아래는 blocker 1건, should 1건입니다. 서버·브라우저를 실행하지 않았으며 이 보고서만 작성했습니다.

## AFM

### [blocker] 조사 묶음의 포인트 기준이 제외 화면과 다르고 사용한 조건도 기록하지 않습니다

- where: `frontend/app/utils/afmBundle.ts:178`, `frontend/app/utils/afmBundle.ts:254`, `frontend/app/components/afm/trend/BundleModal.vue:64`
- what: 화면은 pointScoped의 유효 행으로 포인트 기준을 계산하지만 묶음은 제외 선택을 입력으로 받지 않고 원래 rows의 points를 사용합니다. 파일은 이를 “포인트별 비교의 그룹 평균”이라고 적으면서 FAILED·Valid FALSE 포함 여부를 기록하지 않아 현재 화면의 근거로 읽으면 다른 수치를 보게 됩니다.
- failing input / evidence: 같은 recipe·block의 point 1에 A=10 COMPLETED·Valid TRUE, B=100 FAILED·Valid TRUE, C=20 COMPLETED·Valid TRUE를 주고 02에서 제외를 선택합니다. 실제 `pointScope(...,true) → pointMatrix(...,"mean",null)`의 화면 reference는 15입니다. 같은 원래 trendRows로 만든 bundle의 B 행 reference는 43.333333333333336, delta는 56.666666666666664이며 파일에는 43.3333·56.6667로 기록됩니다. 요약은 `["포인트 기준","포인트별 비교의 그룹 평균입니다: 같은 recipe의 측정들에서 그 포인트 값의 평균"]`뿐입니다. FAILED raw 행을 조사 증거로 보존하는 것과 그 행을 기준 평균에 포함하는 것은 별개의 조건입니다. 현재 bundle 테스트는 제외 화면과 export의 경계를 검사하지 않습니다.
- suggested fix: 묶음의 포인트 기준에 현재 포함·제외 조건을 전달하고 파일에도 조건을 적습니다. 의도적으로 포함 기준만 내보낼 경우 현재 화면과 다른 별도 기준임을 명확히 표시합니다.

### [should] 반올림이 범위 밖 표시를 설명할 수 없게 만듭니다

- where: `frontend/app/utils/afmBundle.ts:294`
- what: 정확한 값으로 계산한 out을 유지하면서 값·범위·Δ를 모두 4자리로 반올림합니다. 파일에는 반올림 전 값으로 비교했다는 안내가 없어서 표시된 숫자가 범위 안인데도 “밖”으로 읽히는 경우가 있습니다. out 계산 자체가 잘못된 것은 아닙니다.
- failing input / evidence: baseline으로 고정한 두 측정의 MEAN을 모두 10, 대상 MEAN을 10.000001로 주면 실제 상한은 10이고 대상 out=true입니다. bundleSheets 결과의 recipe 행은 `["R",2,10,10,10,""]`, 대상의 값·Δ·표시는 `[10,0,"밖"]`입니다. 반올림 테스트는 고정 μ 기대값과 4자리 형식만 검사하며 이 표시 모순은 다루지 않습니다.
- suggested fix: 판정은 반올림 전 값으로 계산한다고 파일에 명시하고, 경계에서 근거가 사라지지 않도록 원래 정밀도의 근거값을 보존합니다.

## 확인한 범위

### 02 포함·제외 및 downstream 계산

- c37b5af6 이전의 afmTrend.ts를 Git에서 읽어 메모리에서 실행하고 현재 measurementStats와 비교했습니다. State 3종 × Valid true/false/null × 값 6종의 **54개 입력**에서 Map·통계·계수 전체가 같았습니다. 값에는 숫자, 0, null, 빈 문자열, 숫자 문자열, NaN과 반복 point가 포함됩니다. 포함 모드 pointScope.rows는 원래 rows 객체 자체를 반환합니다.
- 제외는 isValidRow를 통과하지 못한 행을 먼저 버리고 숫자 값이 있는 마지막 유효 회차를 사용합니다. COMPLETED 40 뒤 FAILED 44가 있는 반복 point는 40을 유지했고 Valid FALSE만 있는 point는 사라졌습니다. 해당 입력의 invalid는 숫자 값이 있는 제외 행 2개이며 반복 row를 각각 셉니다.
- PointsChart와 StabilityChart 모두 pointScoped.rows를 받습니다. PointsChart의 reference·기준 대비 Δ와 StabilityChart의 σ는 전달된 stats.points로 계산하므로 02 내부에서 원래 points로 돌아가는 경로는 찾지 못했습니다. 01의 통계 및 05·06·07을 바꾸지 않는 것은 브리프의 선택 범위와 맞습니다.
- 선택은 usePersistedState로 저장하며 기본값은 false, 즉 포함입니다. 다른 저장 코드나 localStorage 직접 접근을 추가하지 않았습니다.

### 조사 묶음 및 모달

- 측정별 value·delta·out은 현재 TrendRow에서 그대로 가져옵니다. suspect는 현재 out 또는 healthSeries의 non-COMPLETED 행이 있는 측정이며, 추가 임계값을 만들지 않습니다. 확정 State 3종의 계약에서 non-COMPLETED는 FAILED·STOPPED와 같습니다.
- FAILED·STOPPED·invalid 계수는 전체 block의 data 행을 셉니다. 선택 block의 포인트 행과 health·duration·tip 정보는 기존 helper를 사용합니다. 미기록 수치는 null/빈 셀로 남습니다.
- 고정 baseline의 recipe별 μ·범위와 n, 기준 측정의 out 제외, 혼합 recipe별 분리, 기준 표본 부족, showLimits=false에서 out 표시 없음과 범위 꺼짐 문구를 확인했습니다. 측정 수준 기준은 고정 baseline이고 포인트 기준은 recipe별 그룹 평균이라는 구분은 요약의 범위 근거와 포인트 기준 열에 표시됩니다. 첫 측정·선택 측정 기준을 복제하지 않고 그룹 평균을 쓰는 것은 파일에 명시되어 있습니다. 새 제외 선택만 위 finding처럼 누락돼 있습니다.
- 상세 조회 요청이 끝나고 suspect가 있을 때 bundleReady가 됩니다. 성공하지 못한 상세가 있더라도 성공한 측정에 suspect가 있으면 다운로드를 허용하며, 실패한 측정은 누락 건수를 요약에 적고 숫자에 섞지 않습니다. 따라서 docs/afm/feature-summary.md의 “상세를 모두 불러왔고”는 실제로 모든 조회가 끝난 경우를 뜻하는지 열린 문구입니다. 코드가 모든 상세의 성공을 요구하는 것은 아닙니다.
- 실제 BundleModal script setup을 메모리에서 타입 제거해 실행했습니다. ready=false에서는 다운로드 없음, ready=true에서는 호출, busy 중 중복 호출 차단, memo 전달, 성공 뒤 busy 해제·모달 닫힘을 assert로 확인했습니다. buildBundle은 메모를 trim하고 빈 메모는 sheet에서 생략합니다. 메모는 ref로만 보관합니다. 다운로드 함수도 현재 ready를 다시 확인합니다.
- bundleSuspects·buildBundle·bundleSheets·pointScope의 Nuxt auto-import 선언도 확인했습니다. Excel 생성 자체는 실행하지 않았습니다.
- bundle 테스트의 주요 평균·범위·행 기대값은 구체적 고정값입니다. 반올림 검사의 `cell === Number(cell.toFixed(4))`는 형식 불변성 검사이고 μ=10.3333의 독립 기대값도 있지만, out 경계의 일관성 증거는 아닙니다.

### 문구·Site Y·저장소 기준

- 팁 모니터링과 intro의 변경은 문구입니다. 관리선으로 부르던 화면 문자열이 기준 범위로 바뀌었고 관리 한계·규격이 아닌 참고 범위라는 설명이 있습니다. 실제 AFM pages/components에서 관리선·UCL·LCL 문자열은 검색되지 않았습니다. 팁의 기존 이상·주의·정상 판정 로직은 변경하지 않았습니다.
- bundle은 사용자가 고른 측정에서 계산한 참고 범위라고 적으며 관리 한계·규격·Cp/Cpk·원인·팁 교체 권고를 새 판단으로 제시하지 않습니다.
- Site Y가 큰 쪽을 위에 그린다는 user-confirmed 2026-10-09 사실은 docs/datatables/afm/afm_raw_files.txt와 backend/afm/providers/mock.py 양쪽에 같은 범위로 있습니다. 코드 주석·UI·수정 docs도 인덱스 방향만 확정하고 X 방향·notch·mm·반경은 확인되지 않은 것으로 남깁니다.
- siteDots는 Y 증가 시 top을 줄이고, SiteGrid는 오름차순 Y category 축을 inverse 없이 사용합니다. 기존 그리기 방향이 새 확인 내용과 맞으므로 이 커밋은 방향 변경 코드를 추가하지 않았습니다. 웨이퍼 외곽·notch·물리 좌표 변환도 추가하지 않았습니다.
- mock의 인덱스 기반 X/Y 물리값이 지어낸 값이라는 설명은 유지됩니다. 이번 변경으로 frontend/backend 응답 필드를 바꾸지 않았습니다.
- 새 모달 색은 기존 NuxtUI 테마·tokens를 사용합니다. 새 chart option이나 hover 의존성을 추가하지 않았고, docs 변경은 한국어 정중체입니다. 지난 검토에서 철회한 computed 내부 helper nit와 이미 해결된 다른 항목은 다시 열지 않았습니다.

## Gate 결과

| 검사 | 결과 |
| --- | --- |
| frontend npm test, NVM Node 24.13.0 | 2,134 passed, 0 failed, 0 skipped, 24 suites |
| frontend npm run lint | exit 0, 0 errors, 기존 warnings 2개 |
| backend/afm pytest | 88 passed, 0 failed, 8.53초 |
| ruff check . --no-cache | exit 0, All checks passed |
| git diff --check a7d79271..HEAD | exit 0 |

lint 경고는 수정하지 않은 gallery/ImageViewer.vue:201·202의 prop camelCase입니다. Python은 읽기 전용 샌드박스의 임시 디렉터리 제한이 앞선 실행에서 확인되어 권한을 허용받아 실행했습니다. `-B -p no:cacheprovider`로 bytecode·pytest cache 생성을 막았고 ruff도 `--no-cache`를 사용했습니다. 이번 요청의 지정 gate 중 샌드박스로 끝내 실행하지 못한 검사는 없습니다. 이 결과는 home/mock 및 template 검증이며 사내 실측 검증이 아닙니다.

## 검토하지 않은 것

- 브리프에 따라 서버·브라우저·실제 차트 렌더링과 타이핑·라우터 타이밍·다운로드 UI를 실행하지 않았습니다. 모달 검사는 script setup을 메모리에서 실행한 것이며 실제 NuxtUI 조작 증거는 아닙니다.
- xlsx를 실제 생성하거나 Excel에서 열지 않았습니다. bundle 객체와 sheet 행을 확인했습니다.
- 사내 Redis·MinIO·장비 실데이터, 배포된 office.py, 사내 cloud와 실제 웨이퍼 방향·단위 대응은 확인하지 않았습니다.
- frontend typecheck/build, 전체 backend 테스트, 장시간 부하·메모리 검사는 실행하지 않았습니다.
- 범위 밖 기존 화면의 인과·센터/에지 문구, 이전 검토 범위 전체, untracked reports·research_notes는 재검토하지 않았습니다.

## Author 응답 (2차 확인 요청)

수정은 브랜치 `work/bundle-fix` 의 한 커밋입니다 (`git diff main..work/bundle-fix`, worktree `../skewnono-bundle-fix`).

- **blocker (포인트 기준과 제외 화면):** 수용했습니다. `buildBundle` 이 `pointsValidOnly` 를 받아 `pointScope` 를 거친 rows 로 기준을 계산하고, 요약의 `포인트 기준` 행에 포함·제외 조건을 적습니다. 조사 대상 측정의 포인트 행은 FAILED 행을 포함해 그대로 나열합니다(증거 보존). 지적하신 입력(10 / 100 FAILED / 20)을 테스트로 고정했습니다: 포함 43.3333, 제외 15.
- **should (반올림과 범위 밖):** 일부 수용했습니다. 요약에 `범위 밖 판정` 행을 넣어 반올림 전 값으로 판정했다고 적었습니다. 원래 정밀도의 값을 따로 보존하는 것은 하지 않았습니다. 4자리는 0.0001 nm 로 장비 분해능보다 훨씬 작고, 경계 사례가 생기려면 값과 한계가 1e-4 nm 안에서 갈려야 하기 때문입니다. 그 경우에도 판정 근거가 반올림 전 값이라는 안내가 파일에 있습니다. 이 판단이 부족하면 지적해 주십시오.
- **열린 문구:** `docs/afm/feature-summary.md` 의 "상세를 모두 불러왔고" 를 "상세 조회가 모두 끝났고" 로 고치고, 불러오지 못한 측정은 건수로 적는다고 덧붙였습니다.

## 2차 확인

검토 대상은 `main..work/bundle-fix`의 한 커밋 `dd50399f8602d37728967f3e1ed0e73412132b5b`입니다. Author 응답과 수정된 page → BundleModal → buildBundle 전달 경로를 확인했습니다.

- **blocker: resolved.** 원래 입력 A=10 COMPLETED, B=100 FAILED, C=20 COMPLETED의 point 1에서 포함 모드의 화면·파일 reference는 모두 43.333333333333336이고 제외 모드는 모두 15입니다. 파일 요약에 포함·제외 조건도 기록됩니다. FAILED 행의 원래 값 100은 증거로 보존하되 기준 평균에서는 선택에 따라 제외합니다. 반복 point의 COMPLETED 50 뒤 FAILED 100이 있는 경우 마지막 유효 값 50을 기준에 쓰고 두 raw 행은 유지합니다. 유효 값이 전혀 없는 point의 reference는 null이며 recipe가 다른 측정도 섞지 않습니다. 원래 TrendRow의 points가 수정되지 않는 것도 assert로 확인했습니다.
- **should: rebuttal accepted.** baseline=[10,10], target=10.000001 입력의 파일에는 여전히 값=10, Δ=0, 표시=밖이 남습니다. 그러나 새 `범위 밖 판정` 행이 반올림 전 값으로 판단하며 경계에서 인쇄된 숫자는 안처럼 보일 수 있다고 직접 설명하므로 기존의 “표시 이유를 알 수 없음”은 해결됐습니다. 읽기용 조사 기록이라는 범위에서 원래 정밀도의 별도 열을 추가하지 않는 판단을 수용합니다. 이 파일만으로 경계 판정을 수치적으로 재계산할 수 없는 한계는 남습니다. Author의 장비 분해능 주장은 이번에 실측·계약으로 검증하지 않았으며, 수용 근거로 사용하지 않았습니다.
- **새 결함:** 이 수정 커밋에서 추가 결함을 찾지 못했습니다. suspect·측정 수준 μ/범위/Δ/out 계산은 유지되고 포인트 reference만 scoped rows로 바뀝니다. 포함 기본값, raw 포인트 증거 보존, recipe 분리, 실패 상세 건수 표기와 문서의 “상세 조회가 모두 끝났고” 정정도 확인했습니다.

수정 worktree의 npm test는 **2,136 passed, 0 failed, 0 skipped, 24 suites**입니다. 기존 실패 입력, 반복 회차, 유효 point 없음, recipe 분리, 입력 불변성, 반올림 경계를 실제 유틸 호출과 assert로 재확인했고 `git diff --check main..work/bundle-fix`도 통과했습니다. 서버·브라우저·실제 xlsx 생성·사내 실데이터·장비 분해능은 확인하지 않았습니다. frontend lint/typecheck/build와 backend 검사는 반복하지 않았으며, 이 보고서 외 파일은 수정하지 않았습니다.
