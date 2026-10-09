# 2026-10-09 Skewvoir · AFM 3차 신규 검토

- 범위: `git diff 20b3071e..4cebdbdd` (main의 11개 commit, 34개 파일).
- 기준: CLAUDE.md, BRIEF.md, BRIEF-2.md, BRIEF-3.md 및 명시된 소유자 결정입니다.
- 결과: blocker 2건, should 2건, nit 1건입니다. 코드는 수정하지 않았습니다.

## Skewvoir

### [blocker] 제외된 MSR와 서로 다른 단위가 세트 상관에 들어갑니다

- where: `frontend/app/utils/skewvoirAnalysis/receipt.ts:274`, `frontend/app/utils/skewvoirAnalysis/acrossMsr.ts:196`, `frontend/app/utils/skewvoirAnalysis/receipt.ts:435`
- what: `MSR별 지표`는 포함된 MSR만 출력하지만 새 `세트 상관`은 모든 featureRows로 계산합니다. `세트`에서 단위 불일치로 제외했다고 적은 측정이 상관계수에는 참여하며, 그 사실이나 참여 MSR 목록은 상관 시트에 없습니다. 화면과 같다는 이유만으로 이 계산을 올바른 수치로 볼 수 없습니다.
- failing input / evidence: M1/M2/M3의 Vacc가 각각 1/2/3 V, level이 2 nm / 4 nm / 900 um이고 M3를 `unit-mismatch`로 제외합니다. 실제 `buildReviewReceipt` 실행 결과는 역할 `포함/포함/제외`, 지표 MSR `M1/M2`인데 상관 MSR는 `M1/M2/M3`, n=3, Pearson=0.8669892561705325, Spearman=1입니다. 포함된 두 건만으로는 n<3이므로 계수를 내면 안 됩니다. 900 um도 nm 축에 숫자 900 그대로 들어갑니다.
- suggested fix: 화면과 영수증이 공유하는 상관 입력을 manifest의 포함 집합으로 제한하고 축 단위가 맞는지 확인하며, 상관에 실제 참여한 MSR를 추적 가능하게 남깁니다.

### [blocker] 색 범위의 서로 다른 끝이 같은 숫자로 표시됩니다

- where: `frontend/app/utils/scaleLabel.ts:10`, `frontend/app/components/ebeam/skewvoir/ColorScaleBar.vue:12`
- what: 정밀도를 값의 크기만으로 정하므로 범위 폭을 표현하지 못합니다. 새 helper를 두 곳에 적용해도 실제로 폭이 있는 scale을 폭 0처럼 읽게 하는 문제가 남습니다. 계산 범위 자체를 0으로 바꾸는 오류는 아니지만 사용자가 색 차이를 해석하는 숫자가 틀리게 전달됩니다.
- failing input / evidence: 직접 실행에서 min=0.2231, max=0.2234 모두 `0.223`입니다. ColorScaleBar의 중간값 0.22325도 `0.223`입니다. min=-0.0004, max=0.0004는 모두 `0`입니다. 미세한 원본·잔차 값을 받는 공용 scale에서 재현 가능하며, helper 시험은 오히려 ±0.0004를 모두 0으로 고정합니다. 기존 ColorScaleBar도 끝값을 합치는 문제가 있었으므로 이 부분은 새 회귀라기보다 이번 정밀도 수정에서 남은 결함입니다.
- suggested fix: min/max를 함께 받아 두 끝을 구분할 수 있는 정밀도를 선택하고, 필요하면 지수 표기를 사용하면서 음의 0 제거는 유지합니다.

### [should] σ 수정에서 Distribution의 mean 출처도 바뀌어 정상 mock의 표와 갈립니다

- where: `frontend/app/components/ebeam/skewvoir/dashboard/Distribution.vue:66`, `frontend/app/utils/skewvoirAnalysis/cdu.ts:94`, `frontend/app/components/ebeam/skewvoir/dashboard/ParamSummary.vue:103`
- what: Distribution은 mean까지 원본 행에서 다시 계산하지만 표의 Mean은 backend가 소수점 3자리로 반올림한 값을 다시 2자리로 표시합니다. 동일 모집단에서도 끝 자리 하나가 달라집니다. 심각한 통계 오류는 아니지만 “σ 출처만 통일”보다 넓은 동작 변경이며 화면 안의 수치 일관성은 완성되지 않았습니다.
- failing input / evidence: `get_msr_file("REVIEW3-69", "CD-SEM", 80)`의 EDGE에 정상 측정값만 사용하면 backend mean=30.535, 원본 행 mean=30.53473684210526입니다. Node에서 각각 `toFixed(2)`는 `30.54`와 `30.53`입니다. 음수 MP에 숫자가 남아야만 생기는 불일치가 아닙니다.
- suggested fix: 표의 기술 통계를 같은 client 모집단과 반올림 경로로 통일하거나, 서버 요약임을 표시해 서로 다른 정밀도의 요약이라는 점을 설명합니다.

### [nit] 영수증 구현 기록이 새 시트 세 개를 아직 미구현이라고 설명합니다

- where: `docs/research/2026-10-06-page-value-plans.md:536`, `docs/research/2026-10-06-page-value-plans.md:542`
- what: 바로 위에는 위치 합성 site·반경 fit·세트 상관을 구현한 것으로 적지만, 이어지는 문단에는 “세 가지는 뺐습니다”와 “순수 함수로 옮긴 뒤에 더합니다”가 남아 있습니다. 마지막 시트 목록도 새 세 개를 빠뜨립니다.
- failing input / evidence: 같은 built 기록의 519–535행과 536–543행을 함께 읽으면 서로 모순됩니다.
- suggested fix: 오래된 미구현 문단과 시트 목록을 현재 구현에 맞게 정리합니다.

## AFM

### [should] 단일 숫자 열 블록에서 이전의 X=Y 선택 경로가 사라졌습니다

- where: `frontend/app/components/afm/trend/RelationChart.vue:7`, `frontend/app/components/afm/trend/RelationChart.vue:107`
- what: X 초기값을 Y와 다른 열로만 찾으므로 숫자 열 하나뿐이면 X가 빈 값입니다. 새 empty 조건이 선택기까지 숨겨서 사용자가 X=Y를 선택할 수 없습니다. 자기 상관이 정보를 늘리지는 않지만, empty 문구·범례 수정 외의 기능 축소입니다.
- failing input / evidence: measured=[Height], usage=[], column=Height, COMPLETED·Valid TRUE인 Height 값 1/2/3의 세 행입니다. 초기 Y=Height, X='' → empty이며 두 선택기가 없습니다. 이전 템플릿은 선택기를 제공해서 X=Height를 고르면 n=3, r=1 산점도를 볼 수 있었습니다. 이는 템플릿·watcher 정적 추적이며 브라우저 실행 결과는 아닙니다.
- suggested fix: 초기 선택이 없더라도 선택 가능한 숫자 열이 있으면 선택기를 남기거나, X=Y 제거를 별도 기능 결정으로 명시합니다.

## 직접 질문에 대한 확인

### 합성 맵과 Δ-map

- **단일 wafer MP의 full weight는 이 합성의 정의에서는 수용합니다.** 같은 chip의 MP1을 W1=10, W2=14가 측정하고 MP2는 W1=100만 측정하면 MP 평균은 12/100이고 chip mean은 56입니다. 이 값은 “관측한 MP별 평균들의 동등 가중 합성”이지 기준 대비 이동이 아닙니다. 공통 MP만 남겨야 하는 Δ-map 결함과 같은 판정 규칙을 적용할 이유는 없습니다. 모든 MP에 같은 반복 수가 있다는 해석이나 서로 다른 세트 간 이동 추정에는 사용할 수 없습니다.
- σ는 반복 wafer가 두 개 이상인 MP만 사용합니다. 위 사례의 σ는 MP1의 2.828427이며 MP2를 0으로 넣지 않습니다. 모든 MP가 한 wafer뿐이면 null입니다. 시트의 측정점 수는 전체 MP 수, wafer 수는 chip에 측정값을 낸 MSR 수이며 σ를 산출한 MP 수는 아닙니다.
- 동일 wafer·MP에 10/12 두 행, 다른 wafer에 15 한 행이면 첫 wafer 값은 11로 축약되어 chip mean=13, σ=2.828427, wafers=2입니다. 단일 wafer의 반복 행만으로 wafer 간 σ가 생기지 않습니다.
- PositionStack은 `manifest.included` 중 setFiles에 있는 ID만 사용합니다. 영수증도 제외 역할을 제거한 compared ID를 사용합니다. 두 경로 모두 siteDeltaReady=false이면 합성 숫자를 내지 않고 이유를 표시합니다.
- shared collectChips의 필터·chip 키·MP별 배열을 이전 구현과 비교했습니다. baselineDeltaMap의 공통 MP 차이 평균, 3자리 출력, unpaired chip 합집합 계산은 유지됩니다. 기존 공통 MP 시험과 새 합성 시험이 통과했습니다.

### σ, 모집단 및 서버 요약

- Distribution·파라미터 요약 Std·측정 개요의 σ는 isMeasuredRow와 client sample σ(n−1)를 사용합니다. n<2에서는 Std가 —이며, 숫자 0으로 완전 반복성을 주장하지 않습니다.
- 정상 mock은 음수 MP의 CD를 null로 내므로 Count/Mean/Min/Max와 client Std의 모집단은 같습니다. 그 안에서도 mean은 앞의 should처럼 반올림 경로로 눈에 보이는 불일치가 납니다.
- office가 같은 parameter에 (mp=1, CD=10), (mp=2, CD=14), (mp=-1, CD=100)을 보내고 서버가 세 숫자를 요약한다면 Count=3, Mean≈41.333, Max=100과 client n=2, mean=12, Std≈2.828427이 섞입니다. 이는 정상 mock에서 확인한 현상과 별개의 경계 입력이며 실제 office 발생을 확인하지 않았습니다. mock _summaries도 유한 값만 검사하고 MP를 검사하지 않지만 현재 생성 데이터는 이 입력을 만들지 않습니다.
- Time-Series tooltip은 `std (서버 요약)`으로 구분합니다. 해당 산포 VERDICT가 서버 std를 사용하는 것은 client 수치와의 정밀도·출처 불일치입니다. 정상 mock의 서버도 sample σ를 계산하므로 그것만으로 잘못된 σ 공식이나 잘못된 판정이라고 하지는 않습니다. 잘못된 서버 모집단이면 판정도 잘못될 수 있습니다. 이번 변경의 다른 panel에서 서버 std를 client σ와 같은 값으로 새로 표시하는 경로는 찾지 못했습니다.

### 상관 축과 통계

- 제외 집합 차이는 단순 표시 차이를 넘어 단위가 다른 숫자를 섞을 수 있으므로 blocker입니다. 같은 화면 수치를 내보내는지는 맞지만 의미가 안전해진 것은 아닙니다.
- Y 기본값은 level, 없으면 첫 축입니다. X는 첫 FDC, 없으면 Y와 다른 첫 축, 축이 하나면 그 축입니다. 축이 없으면 둘 다 빈 값입니다.
- 유효한 축 선택은 encode/resolve 왕복에서 유지됩니다. 기본값은 null로 URL에서 지우고, FDC가 없는 경우 X 기본값을 선택한 Y 기준으로 계산합니다. 기존·추가 axis 시험과 직접 2축의 네 조합 왕복을 확인했습니다.
- 현재 세트에 없는 ax는 기본 X로 해석합니다. `ax=removed, ay=level`을 직접 실행하면 `fixed_fdc.Vacc / level`입니다. screen과 receipt 모두 같은 resolver를 호출하므로 이 경우 서로 다른 축으로 계산하지 않습니다. 원래 stale ID 문자열이 URL에 남는 것은 fallback 규칙이며 수치 오류로 보지 않습니다.
- n=2이면 Pearson/Spearman 모두 null과 표본 부족 이유, n=3에서 상수 축이면 둘 다 null과 분산 없음 이유입니다. X=[1,2,3], Y=[1,1,2]에서는 평균 순위를 사용하여 두 계수 모두 0.8660254037844387입니다. 직접 실행했습니다.

### 반경 fit

- RadiusPlot과 receipt는 같은 focus 행·parameter·waferGeo로 radialSamples를 만들고 같은 URL rfit 모델을 analyzeRadialProfile에 넘깁니다. analyzeSpatial도 같은 helper를 사용하며 기존처럼 notch를 sector 이름에만 반영합니다. bottom 기본 sector는 이전 RadiusPlot의 E/N/W/S 분기와 같습니다. notch 차이는 반경·CD·회귀 계수에 영향을 주지 않습니다.
- 표본은 측정된 행 중 stage coordinate를 mm 위치로 변환할 수 있는 행입니다. sequence·좌표·반경·CD 필드가 공유됩니다. 계수는 관측 반경 최소·최대의 중간값과 반폭으로 정규화한 t의 다항식이며 낮은 차수 순서입니다. 기재된 기준은 맞습니다.
- n와 원본 계수·RMSE는 같은 계산값입니다. xlsx는 4자리, RadiusPlot header의 RMSE는 3자리여서 문자열이 byte-identical하지는 않습니다.
- 독립적인 수치 fixture인 반경 20/40/60/80 mm, CD 5/9/13/18에서는 n=4, c0=11.25, c1=6.45, RMSE=0.273861…(sheet 0.2739)가 통과했습니다. 2차 fixture는 c0=3, c1=0, c2=2와 RMSE=0입니다. 좌표 없음·미측정·표본 부족도 제외합니다.

### 색 라벨, AFM 상태 및 범위 변경

| 입력 | 실제 formatScaleLabel 출력 |
| --- | --- |
| 99.95 | 100 |
| 9.995 | 9.99 |
| 0.9995 | 1 |
| −0.0004 | 0 |
| NaN, +Infinity, −Infinity | — |
| 0.2231 / 0.2234 | 0.223 / 0.223 |

- 9.995→9.99는 JavaScript의 이진 부동소수점과 toFixed 결과입니다. 이 경계 반올림 자체는 별도 결함으로 세지 않았습니다. -0 제거와 비유한 값 처리는 맞지만 범위 양 끝 구분은 부족합니다.
- **single-scope에도 변경이 퍼졌습니다.** ColorScaleBar를 쓰는 WaferMap·WaferDetailModal·SpatialLayerMap의 45.0→45, 0.3→0.25(원본 0.25)도 바뀝니다. 공용 scale formatter 적용으로 생긴 의도된 정밀도 개선으로 판단하며 별도 수치 결함으로 세지 않았습니다. 합성 맵만의 변경은 아닙니다.
- RelationChart는 축이 없으면 empty, 축이 있고 n<3이면 few, 그 밖에는 chart입니다. few에서는 선택기·표본 정보만 있고 chart 범례는 없습니다. chart 범례는 실제 samples의 선택/비선택 존재 여부만 따릅니다.
- ProfileOverlay 범례는 실제 overlay.drawn만 검사합니다. 0개이면 두 범례 모두 없고, 비선택만 있으면 “측정”, 선택만 있으면 “선택한 측정”, 둘 다 있으면 두 항목입니다. pending·제외된 프로파일에 가짜 범례가 생기는 경로는 찾지 못했습니다.
- PointRail의 Site Y 큰 쪽이 위, 두 선이 index 0이라는 설명과 siteDots 위치식이 일치합니다. wafer 형상·물리 중심·notch를 주장하지 않습니다. AFM notch는 알 수 없고 추적하지 않는다는 결정은 재검토하지 않았습니다.
- 변경된 화면과 새 sheet에서 Cp/Cpk·spec pass/fail·관계 유의성·원인 확정을 새로 주장하는 문구는 찾지 못했습니다. 관리선/UCL/LCL이 live AFM component/page에 남는지도 검색했으며 발견하지 못했습니다. recommendation의 “요청 시 configurable 관리선”은 허용된 소유자 결정입니다.

## 기준 및 시험의 범위

- 신규 합성·radialSamples·axis·receipt 시험을 읽었습니다. 합성의 56/13/2.828427, fit의 11.25/6.45/0.2739, 상관의 0.9648 등은 production 함수를 다시 호출해 기대값을 만드는 시험이 아닙니다. 같은 helper를 화면과 sheet에서 쓰는 것만으로 공식이 맞다고 주장하지 않았습니다.
- export 없음으로만 red를 보았다는 기록은 구현 오류에도 시험이 실패했다는 증거는 아닙니다. 다만 현 시험에는 MP 풀링·반복 행 가중치·계수 차수·축 fallback을 바꾸면 달라질 독립 기대값이 있어 그 이유만으로 시험을 무효라고 하지는 않습니다. 이번 검토에서는 소스 mutation을 하지 않았습니다.
- 제외 MSR가 상관에 들어가는 fixture, 범위 두 끝을 동시에 구분하는 시험, AFM 실제 선택기 노출을 검증하는 시험은 부족합니다. pure relationState 시험만으로 template 접근 경로까지 검증되지는 않습니다.
- ax/ay는 기존 query patch 경로이며 두 키를 한 번에 replace합니다. 신규 수동 localStorage·cross-page link·hover에 의존하는 chart-option 변경은 발견하지 못했습니다. AFM index 확인 사항은 기존 datatables와 mock의 기록 범위를 확장하지 않습니다. 문서의 한국어 종결은 존댓말 형식을 유지합니다.

## Gate 결과

| 검사 | 결과 |
| --- | --- |
| frontend npm test (nvm Node 24.13.0) | 2,167 pass, 0 fail, 0 skip, 24 suites |
| frontend npm run lint | exit 0, error 0, 기존 ImageViewer.vue prop naming warning 2건 |
| pytest backend/msr_file backend/afm | 226 pass, 2 skip, 61.75초 |
| ruff check . --no-cache | All checks passed |
| git diff 20b3071e..HEAD --check | 통과 |

- sandbox의 임시 파일 제한 때문에 pytest와 heredoc 재현은 승인된 sandbox 밖 실행으로 마쳤습니다. pytest는 `-B -p no:cacheprovider`로 source bytecode·pytest cache 쓰기를 피했습니다. 소스 변경 없이 in-memory Node 재현과 mock 통계 확인을 실행했습니다.
- gate 통과는 위 blocker를 부정하지 않습니다. 확인한 입력이 현재 시험에 없기 때문입니다.

## 검토하지 않은 것

- 요청대로 서버·브라우저를 실행하지 않았습니다. 실제 chart 표시·선택 이벤트·URL navigation·xlsx 다운로드/Excel 열기·시각적 접근성은 검증하지 않았습니다.
- 사내 DB·office adapter·장비·실제 AFM raw 파일과 배포 환경은 실행하지 않았습니다. mock/단위 시험을 사내 검증으로 제시하지 않습니다.
- typecheck·production build·전체 backend suite는 실행하지 않았습니다. 검토 범위 밖 과거 결함과 이미 수용한 소유자 결정은 재개하지 않았습니다.

## Author 응답 (2차 확인 요청)

수정은 브랜치 `work/review3-fix` 의 네 커밋입니다 (`git diff main..work/review3-fix`, worktree `../skewnono-review3-fix`).

- **blocker 1 (제외 MSR 가 세트 상관에):** 수용했습니다. `analysis.comparedFeatureRows`(`manifest.included` 로 거른 featureRows)를 `Correlation.vue` 세트 범위가 쓰고, 영수증도 `compared` 로 거른 뒤 `acrossMsrOutcomeFor` 를 부릅니다. `세트 상관` 과 `MSR별 지표` 가 같은 측정 집합을 씁니다. 지적하신 사례를 테스트로 고정했습니다(제외 1건 → 전체 n 3). 축 단위 일치 검사를 따로 넣지는 않았습니다. 단위·recipe 가 다른 측정은 manifest 가 이미 제외하고, 그 제외를 이제 따르기 때문입니다. 이것으로 부족한 경로가 있으면 지적해 주십시오. 참여 MSR 목록을 시트에 따로 적지도 않았습니다. `MSR별 지표` 시트가 같은 집합의 축 값을 MSR 별로 싣고 있습니다.
- **blocker 2 (색 범위 양 끝):** 수용했습니다. `scaleDecimals(min, max)` 가 크기 규칙에서 시작해 양 끝이 달라질 때까지 자릿수를 늘리고(상한 8), min · mid · max 가 같은 자릿수를 씁니다. 0.2231/0.2234 → `0.2231`/`0.2234`, ±0.0004 → `-0.0004`/`0`/`0.0004`. 지수 표기는 넣지 않았습니다.
- **should (Distribution mean 과 표의 Mean):** 수용했습니다. `paramTableStats` 가 `cduMetrics` 와 같은 measured rows 에서 Count · Mean · Std · Min · Max 를 모두 내고, 파라미터 요약은 서버 요약에서 파라미터 목록과 단위만 가져옵니다.
- **should (AFM X=Y):** 기능은 되살리지 않았습니다. 같은 항목을 양 축에 놓는 것은 정보가 없다고 판단했고, 대신 `docs/afm/feature-summary.md` 에 2026-10-09 에 뺐다고 명시했습니다. 범위 밖 변경이었다는 지적은 맞습니다.
- **nit (문서의 미구현 문단):** 수용했습니다. 문단을 지우고 시트 목록을 현재 구현에 맞췄습니다.

## 2차 확인

검토 범위는 `git diff main..work/review3-fix`의 네 commit(`fa1e93f7`, `d2f01a54`, `b5cd3f72`, `5f6eed0a`)입니다. 수정 worktree HEAD는 `5f6eed0a9617a8c1620978dbee38900263e8ea47`이며, 기존 본문과 Author 응답은 유지했습니다.

### 기존 다섯 지적의 판정

1. **제외 MSR가 세트 상관에 들어가는 문제 — resolved.** Correlation은 `analysis.comparedFeatureRows`(manifest.included로 필터)를 사용하고, receipt는 MSR별 지표와 같은 compared 집합으로 필터합니다. 단위·recipe가 알려진 불일치는 manifest의 기존 비교에서 제외되므로 그 경로에 추가 단위 검사 없이 필터를 따르는 수정은 수용합니다. 새 시험은 기존 네 유효 쌍 중 M4를 제외했을 때 n=3·r=0.982, EQ2 행 없음으로 고정하며 통과했습니다. 원 지적의 “제외된 측정으로 n과 계수를 늘림”은 해결됐습니다. 다만 화면·receipt가 집합을 만드는 방식 자체가 같아진 것은 아니며, 아래 cap 사례에 새 불일치가 있습니다.
2. **색 범위 양 끝이 같은 숫자로 표시되는 문제 — still open.** 원 입력 0.2231/0.2234는 4자리로 서로 구분되고 ±0.0004도 `-0.0004 / 0 / 0.0004`로 고쳐졌습니다. 그러나 `frontend/app/utils/scaleLabel.ts:17`의 MAX_DECIMALS=8에 닿아도 충돌하면 그대로 반환합니다. 직접 실행한 min=0.2231000001, max=0.2231000004는 decimals=8, min/mid/max 모두 `0.2231`입니다. 1e-9/4e-9도 모두 `0`입니다. 입력을 8자리 이하로 제한하는 계약은 이 변경에 없으므로 “양 끝은 절대 같지 않다”는 주장은 아직 성립하지 않습니다. 상한에서 충돌하면 유효숫자·지수 표기 등으로 두 끝을 구분하는 fallback이 필요합니다.
3. **Distribution mean과 표 Mean의 불일치 — resolved.** ParamSummary의 다섯 수치 모두 paramTableStats로 계산하며, 원본 measured rows의 mean·sample std를 사용합니다. 원 실패 입력 `get_msr_file("REVIEW3-69", "CD-SEM", 80)`의 EDGE 행을 수정 helper에 직접 넣은 결과 Count=38, mean=30.534736842105268, 표 Mean=`30.53`, Distribution=`μ 30.53 · 3σ 1.57`입니다. mp=-1에 숫자가 남은 행 제외, 무측정의 null, 한 행의 std=null 시험도 통과했습니다. 파라미터 목록과 단위만 서버에서 가져오는 것은 통계 모집단을 다시 섞지 않습니다.
4. **새 시트를 아직 미구현이라고 적은 문서 — resolved.** `docs/research/2026-10-06-page-value-plans.md`의 “세 가지는 뺐습니다”와 향후 순수 함수 이전 문단이 제거됐고, 최종 시트 목록에도 위치 합성 site·반경 fit·세트 상관이 들어갔습니다.
5. **AFM 단일 숫자 열의 X=Y 선택 경로 제거 — rebuttal accepted.** 기능 복구는 없지만 `docs/afm/feature-summary.md:113`에 단일 숫자 열이고 usage 열도 없을 때 선택기를 숨기는 결정과 날짜를 명시했습니다. 원 suggested fix의 “별도 기능 결정으로 명시”를 충족하며 자기 상관이 정보를 늘리지 않는다는 이유도 수용합니다. Height만 있는 원 입력은 여전히 empty이지만 이제 기록된 의도입니다. 이 수용은 모든 다중 열 블록에서 X=Y 선택이 금지됐다는 뜻은 아닙니다.

### 수정으로 생긴 새 결함

#### [blocker] 30건 cap 밖의 focus를 화면 상관에만 넣습니다

- where: `frontend/app/composables/useSkewvoirAnalysis.ts:777`, `frontend/app/components/ebeam/skewvoir/views/Correlation.vue:208`, `frontend/app/utils/skewvoirAnalysis/receipt.ts:232`, `frontend/app/utils/skewvoirAnalysis/receipt.ts:274`
- what: manifest는 별도로 불러온 focus를 항상 sources에 넣지만 receipt의 compared는 요청 목록 중 setFiles에 있는 측정만 남깁니다. 이번에 receipt 상관에 compared 필터를 적용하면서 화면과 파일의 상관 표본·계수가 달라졌습니다. 이전 상관 경로는 양쪽 모두 featureRows 전체를 써서 이 사례의 상관계수는 같았습니다.
- failing input / evidence: 요청 MSR를 M1…M31 순서로 하고 focus=M31로 둡니다. setFiles는 cap 때문에 M1…M30만 있고 focusFile은 M31이며, 모든 파일의 recipe=R·단위=nm입니다. X(Mi)=i, Y(Mi)=2i, 단 M31의 Y=900입니다. 실제 buildAnalysisManifest와 수정 상관·receipt 함수를 실행한 결과 included=31, excluded=[]; 화면 n=31·Pearson=0.4092621329856736, receipt n=30·Pearson=1입니다. receipt의 M31 역할은 제외이며 receiptReady는 setResolved=30/setLoaded=30·key 일치 상태에서 true입니다.
- suggested fix: 상관 화면과 receipt에 동일한 실제 비교 ID 집합을 전달합니다. cap 밖 focus를 세트 상관에 포함할지 먼저 같은 규칙으로 정하고, receipt를 맞추려고 다른 통계에 focus를 임의 추가하지 않습니다.

#### [should] 한쪽 끝이 큰 범위에서 작은 끝의 기존 정밀도를 잃습니다

- where: `frontend/app/utils/scaleLabel.ts:20`, `frontend/app/components/ebeam/skewvoir/ColorScaleBar.vue:32`
- what: scaleDecimals는 절댓값이 큰 끝의 magnitude만 기준으로 시작합니다. 끝이 서로 다르기만 하면 자릿수를 늘리지 않으므로 기존 formatter가 표시하던 작은 끝의 소수부를 버립니다.
- failing input / evidence: min=0.25, max=100을 직접 실행하면 decimals=0, labels=`0 / 50 / 100`입니다. 기존 min label은 `0.25`였고 실제 최소값은 0이 아닙니다. SpatialLayerMap의 raw/score와 공용 ColorScaleBar는 두 끝이 서로 다른 경우 이 min/max를 그대로 전달하므로 동일 코드 경로에서 재현됩니다.
- suggested fix: 두 끝 각각에 필요한 기본 정밀도를 보존한 뒤, 좁은 범위에서 충돌할 때 추가 정밀도를 늘립니다.

이 밖의 새 실행 결함은 이번 diff에서 발견하지 못했습니다. 새 시험은 원본 fixture의 수치 기대값을 사용하지만 8자리 상한 충돌·양 끝 magnitude 차이·cap 밖 focus의 화면/receipt 동등성은 다루지 않습니다.

### 검증 결과와 한계

- 수정 worktree에서 nvm Node 24.13.0으로 `npm test`: **2,172 pass, 0 fail, 0 skip, 24 suites**입니다.
- 수정 worktree의 `npm run lint`: exit 0, error 0, 기존 ImageViewer.vue prop naming warning 2건입니다.
- `git diff main..work/review3-fix --check`: 통과했습니다. 원 worktree의 `npm run lint:md`도 213파일 검사에서 오류 없이 통과했습니다.
- scale helper·상관 cap fixture·원 mock EDGE 행은 파일을 만들지 않는 Node/Python 실행으로 직접 재현했습니다. 원 worktree와 수정 worktree의 tracked 파일을 바꾸지 않았습니다.
- 서버·브라우저·Excel·사내 데이터·office adapter는 실행하지 않았습니다. typecheck/build와 backend suite는 이번 frontend·문서 수정에서 재실행하지 않았습니다. 통과한 pure-function 시험을 실제 화면·다운로드·사내 검증으로 주장하지 않습니다.

## Author 응답 2 (3차 확인 요청)

커밋 두 개가 `work/review3-fix` 에 더해졌습니다 (`git log --oneline main..work/review3-fix` 의 위 두 개).

- **색 범위 (still open + 새 should):** 둘 다 수용했습니다. `scaleDecimals` 를 `scaleFormatter(min, max)` 로 바꿨습니다. 0 이 아닌 각 끝이 자기 크기에 필요한 자릿수를 유지하고(작은 끝이 기준), 그래도 양 끝이 같으면 8자리까지 늘리며, 8자리에서도 같으면 지수 표기로 넘어가 양 끝이 달라질 때까지 자릿수를 늘립니다. 지적하신 입력을 테스트로 고정했습니다: 0.25/100 → `0.25`/`100`, 0.2231000001/0.2231000004 → `2.231000001e-1`/`2.231000004e-1`, 1e-9/4e-9 → `1e-9`/`4e-9`.
- **새 blocker (cap 밖 focus):** 수용했습니다. `setComparedMembers(included, setFiles, scope)` — set scope 에서는 included 이면서 set files 에 있는 측정 — 를 `curatedSet.ts` 에 두고 화면의 `comparedFeatureRows` 가 씁니다. 영수증의 `compared`(역할이 제외가 아닌 측정 = 파일이 set files 에 있고 manifest 가 제외하지 않은 측정)와 같은 집합입니다. 영수증에 focus 를 더하지 않고 화면에서 뺐습니다. 1차 묶음에서 정한 "set scope 는 set files 만 쓴다" 는 규칙과 같은 방향입니다.

## 3차 확인

`Author 응답 2`를 읽고 최신 두 commit `c74834ba`(scaleFormatter)와 `ae532f47`(setComparedMembers)를 검토했습니다. 수정 worktree HEAD는 `ae532f47215147223ccc869a11bf7ff0614d6d75`입니다.

- **색 라벨 — cap collision: still open.** 기존 실패 입력 0.2231000001/0.2231000004는 이제 `2.231000001e-1 / 2.231000004e-1`, 1e-9/4e-9는 `1e-9 / 4e-9`로 구분됩니다. 다만 `frontend/app/utils/scaleLabel.ts:22`의 MAX_EXP_DIGITS=15에 도달한 뒤에도 충돌 검사가 끝나므로 다른 유한 입력에서 같은 문제가 남습니다. 직접 실행한 min=1, max=1+Number.EPSILON(1.0000000000000002)은 두 끝 모두 `1.000000000000000e+0`입니다. 지수 표기의 15자리 소수부는 16개 유효숫자이며 모든 서로 다른 double을 구분하기에는 부족합니다. 이 최종 상한에서 같은 문자열이면 17개 유효숫자 또는 원본 number의 round-trip 문자열로 fallback해야 합니다.
- **색 라벨 — wide-range precision: resolved.** min=0.25, max=100은 직접 실행에서 `0.25 / 100`입니다. 양 끝 각각의 기본 정밀도 중 큰 자릿수를 선택하므로 작은 끝을 큰 끝의 정밀도에 맞춰 0으로 버리던 회귀는 해결됐습니다. 기존 ±0.0004도 `-0.0004 / 0.0004`를 유지합니다.
- **cap 밖 focus blocker: resolved.** 원 실패 입력(M1…M31 요청, focus=M31, setFiles=M1…M30, X=i, Y=2i이며 M31만 Y=900)을 실제 manifest·setComparedMembers·상관·receipt 함수로 재실행했습니다. manifest included는 31건이지만 화면과 receipt 모두 n=30, Pearson=1, Spearman=1이며 M31은 상관에서 빠집니다. 두 결과의 참여 MSR·좌표·통계가 같은지 assert로 확인했습니다. receipt의 M31 역할은 기존대로 제외이며, 다른 세트 통계에 focus를 추가하지 않았습니다.

### 화면과 영수증의 compared 집합은 같은가

**다운로드 가능한 현재 세트에서는 같은 집합임을 코드로 증명할 수 있습니다.** 요청 ID 집합을 R, 현재 setFiles 키를 S, manifest included를 I, excluded를 E라고 하면 화면은 `I ∩ S`, receipt는 `(R ∩ S) ∖ E`입니다. 현재 loader는 요청 목록을 해석·cap한 측정만 setFiles에 넣으므로 `S ⊆ R`입니다. manifest는 focus와 모든 setFiles를 검사하여 각 S 원소를 I 또는 E로 분할하므로 `I ∩ S = S ∖ E`입니다. 따라서 두 식이 같습니다. 양쪽 모두 같은 featureRows에서 이 집합으로 필터하고 같은 축 resolver와 상관 함수를 사용하므로 축 값이 없는 MSR가 추가로 빠지는 규칙도 같습니다.

이는 임의로 만든 ReceiptInput·stale pool에서도 무조건 같다는 주장은 아닙니다. 이전 pool이 남거나 batch가 실패·진행 중이면 receiptReady의 pending/error/key 검사가 다운로드를 막습니다. 정상 응답이 요청 MSR를 반환한다는 기존 API 계약 아래의 증명입니다. 원 cap fixture의 실제 receipt와 화면을 비교한 검증에 더해, 네 ID의 요청·로드·제외 조합 4,096개에서 이 집합 등식을 assert로 확인했습니다.

### 새 결함 및 검증 범위

- 최신 두 commit에서 위 지수 표기 상한의 **기존 색 라벨 결함 잔존 외에 새 결함은 발견하지 못했습니다.** 원본 입력을 고정한 새 시험은 통과하지만 인접한 double의 지수 라벨 충돌은 다루지 않습니다.
- 수정 worktree의 `npm test`: **2,175 pass, 0 fail, 0 skip, 24 suites**입니다. `git diff work/review3-fix~2..work/review3-fix --check`도 통과했습니다.
- 모든 직접 재현은 파일을 만들지 않는 Node 실행입니다. 이 보고서 외의 파일을 수정하지 않았습니다. 서버·브라우저·Excel·사내 데이터는 확인하지 않았으며 typecheck/build·frontend lint·backend suite는 이번 작은 재확인에서 재실행하지 않았습니다.

## Author 응답 3 (4차 확인 요청)

- **색 라벨 — cap collision:** 수용했습니다. `work/review3-fix` 의 최신 커밋에서, 지수 표기가 15자리에서도 같으면 `String(value)`(double 의 round-trip 문자열)로 넘어갑니다. 서로 다른 두 유한 double 은 round-trip 문자열이 다르므로 더 남는 상한은 없습니다. 지적하신 입력을 테스트로 고정했습니다: 1 / 1+Number.EPSILON → `1` / `1.0000000000000002`.

## 4차 확인

`Author 응답 3`과 최신 commit `7a672283497f431f943a86b1e70b9f9bc67f69ff`의 scaleLabel 변경을 확인했습니다.

- **색 범위 양 끝 충돌 — resolved.** `scaleFormatter(min, max)`는 수치적으로 서로 다른 모든 유한 JavaScript number의 끝 라벨을 구분합니다. 고정 소수점·지수 표기 경로는 양 끝 문자열이 서로 다름을 확인한 뒤 반환하며, 최종 지수 상한에서도 같으면 `String(value + 0)`으로 넘어갑니다. 유한 number의 round-trip 문자열은 다시 그 number로 변환되므로 서로 다른 두 값이 같은 문자열을 가질 수 없습니다. `+ 0`은 음의 0만 양의 0으로 정규화하며 다른 유한 값을 바꾸지 않습니다. 따라서 표본 시험만이 아니라 반환 경로의 조건과 fallback 성질로 종결을 확인했습니다.
- 직접 실행한 이전 실패 입력 1 / 1+Number.EPSILON은 `1 / 1.0000000000000002`입니다. 0.2231000001 / 0.2231000004, 1e-9 / 4e-9, 0.25 / 100도 기존 수정 결과를 유지합니다. 최소 subnormal과 0, ±Number.MAX_VALUE도 서로 구분됐습니다. 임의 비트 패턴으로 만든 인접 유한 double을 양방향으로 넣은 **39,978회** 확인에서 충돌은 없었습니다. 전체 number 공간을 열거한 시험이라는 뜻은 아닙니다.
- `-0`과 `+0`은 모두 `0`입니다. 비트 표현은 다르지만 수치적으로 같은 끝이며 범위 폭도 0이므로, 기존 “음의 0을 표시하지 않는다”는 규칙에 맞습니다. 이 경우를 서로 다른 수치의 충돌로 세지 않습니다.
- **새 결함은 발견하지 못했습니다.** 변경은 최종 충돌 때의 fallback 추가이며 기존 정밀도 선택, 일반 범위 출력, 비유한 값의 — 처리를 유지합니다.
- 수정 worktree의 `node --test app/utils/scaleLabel.test.ts`: **9 pass, 0 fail, 0 skip**입니다. 최신 commit의 `git diff HEAD~1..HEAD --check`도 통과했습니다. 서버·브라우저·전체 suite·사내 데이터는 이번 한 항목 확인에서 재검증하지 않았습니다. 이 보고서 외의 파일은 수정하지 않았습니다.
