# 화면별 가치 추가 계획 — 9개 항목을 어떻게 진행할 것인가

- 작성일: 2026-10-06
- 바탕: [`2026-10-05-page-value-brainstorm.md`](2026-10-05-page-value-brainstorm.md)
  의 합의 목록. 10번이던 포인트 축소 민감도(S15)는 사용자 결정으로 제외했고,
  남은 9개와 동반 항목 5개(S16·S17 링크, 장비 목록 → H/W 링크 교체, S10, S11)를
  다룹니다.
- 방법: 항목마다 닿는 코드를 파일·함수 단위로 다시 읽고 계획을 적었습니다.
  **사내 DB 와 브라우저 화면은 보지 않았고, 어떤 항목도 아직 구현하지
  않았습니다.** 파일 위치와 줄 번호는 2026-10-06 `main`(`5b869d1d`) 기준입니다.

## 요약

### 가치 판단: 진행하되 등급을 나눕니다

9개 모두 만들 가치가 있습니다. 다만 "엔지니어가 바로 체감하는가"로 보면 세
등급으로 갈립니다.

| 등급 | 항목 | 왜 그런가 |
| --- | --- | --- |
| 바로 체감 | S2, S5, S1, S3 | 현장에서 매일 나오는 질문("이 실행의 원본은", "왜 이 cap 인가", "장비 문제인가 recipe 문제인가", "지난 기간보다 나빠졌나")에 답하고, 각각 하루 이틀이면 끝납니다. |
| 조건이 붙음 | S4, S7, S13 | S4 는 장비당 표본이 작으면 P90 이 의미가 없어 표본 수를 함께 보여야 합니다. S7 은 기준을 손으로 나누는 사람이 있어야 쓰입니다. S13 은 룰 변경 자체가 드물어 쓰는 횟수는 적지만, 한 번의 결정이 무겁습니다. |
| 지금은 가치가 미뤄짐 | S6, S8 | S6 은 AFM 사내 어댑터가 아직 stub 이라(`backend/afm/providers/office_example.py` 의 모든 함수가 `NotImplementedError`) 사내에서도 mock 을 봅니다. 실데이터가 흐르기 전에는 효용이 없습니다. S8 은 결론을 남기는 습관에 달려 있고, 더 큰 의미는 나중 채팅 결합 보고서(S18)의 입력 형태를 미리 정하는 데 있습니다. |

솔직하게 적어야 할 한계가 둘 있습니다.

1. **이 목록은 두 모델이 코드만 읽고 고른 것입니다.** 사용 로그도, 엔지니어
   인터뷰도 근거에 없습니다. 그래서 S 규모 네 개를 먼저 내고, 사용 통계와
   피드백으로 M 규모의 순서를 다시 정하는 편이 맞습니다.
2. **아홉 개 모두 "이미 받은 데이터를 다시 계산"합니다.** 새 사실을 만들지는
   않고, 있는 사실을 보이게 합니다. 그것만으로도 지금 화면의 "따져 보기" 공백은
   메워지지만, "더 깊은 분석"의 상한은 여기까지입니다. 사내 데이터를 더
   끌어오는 일(S9, S19 류)은 그 뒤의 과제입니다.

### 순서

| 묶음 | 순서 | 규모 | 비고 |
| --- | --- | --- | --- |
| 1 | S2 → S5 → S3 → S4 | 각 S, 합쳐 1~2주 | 모두 한 기능 안, 백엔드 변경 없음. S2 가 링크 계약 테스트의 본보기가 됩니다. |
| 확인 | 1묶음 배포 뒤 1~2주 | — | 아래 "확인 방법" |
| 2 | S1(+S17) → S7 → S13 → S8 | S1 은 S/M, 나머지 M | S1 과 S17 은 같은 화면이라 한 worktree 로 묶습니다. S8 은 S7 뒤에 와야 기준·대상 수치를 담을 수 있습니다. |
| 보류 | S6 | M | AFM 사내 어댑터가 생긴 뒤. 그 전에 만들어도 되지만 엔지니어 가치는 어댑터 뒤에 생깁니다. |
| 동반 | 장비 목록 → H/W, S16, S10, S11 | 각 S | 각 화면을 다음에 손댈 때 같이. |

브레인스톰의 1~4위 순서(S3, S4, S5, S2)를 S2, S5, S3, S4 로 바꿨습니다.
S2 는 네 개 중 가장 작고(검색 랜딩에 같은 변환이 이미 있습니다) 링크 정책의
테스트 묶음을 처음 만드는 일이라, 먼저 두는 편이 뒤의 링크 세 개에 유리합니다.

### 확인 방법

- `/activity` 의 기능별 조회 수(`meas_hist`, `skewvoir`, `live_alarm`,
  `recipe_tat`, `device_statistics`)를 1묶음 배포 전후로 봅니다. 기능 단위
  집계라 "새 블록을 봤는가"까지는 모릅니다. 하위 기능별 비콘은 인덱스 변경이
  필요하므로 만들지 않습니다.
- 그래서 직접 묻는 질문 세 개를 정해 둡니다. "측정 이력에서 MSR 을 열어 본
  적이 있는가", "판정 근거 블록이 질문을 줄였는가", "이전 기간 대비 숫자를
  보고 행동이 달라진 적이 있는가". 셋 중 둘이 '아니오'면 2묶음 순서를 다시
  봅니다.

## 공통 규칙

- **한 항목 = 한 worktree = 한 커밋 묶음.** 다음 항목은 앞 항목이 `main` 에
  오른 뒤 시작합니다.
- **백엔드 변경 없음.** 아홉 개 모두 프런트에서 끝납니다(S3 도 기존 요약
  엔드포인트에 날짜만 바꿔 한 번 더 부릅니다). 백엔드를 고치고 싶어지면 그
  항목의 범위가 틀린 것입니다.
- **순수 함수 먼저, 컴포넌트는 그리기만.** 계산은 `frontend/app/utils/` 의
  Nuxt 의존 없는 파일에 두고 옆에 `.test.ts` 를 둡니다(`node --test`, 파일
  머리의 `// Run:` 주석 관례). 컴포넌트에는 계산을 넣지 않습니다.
- **링크는 브레인스톰 1.3절 정책대로.** 대상 화면이 소유한 빌더가
  `{ path, query }` 를 돌려주고, 만들기 → 읽기 왕복, `/` 가 든 이름, 빈 식별자,
  두 계열(cd-sem, hv-sem)을 테스트하며, 브라우저에서 새 탭·새로고침·뒤로 가기·
  기억된 값과의 충돌·같은 화면 재진입을 확인합니다.
- **표현.** "원시 변화"(S3), "20분 창에서 관측된 범위"(S1), "이 세트 안에서
  손으로 나눈 기준"(S7), "저장되지 않음"(S13), "생성 시각 기준 수치"(S8).
  "악화", "원인", "추천", "공식 기준", "안전"은 쓰지 않습니다.
- **시각 언어.** `DESIGN.md` 대로 `--sk-*` 토큰만 씁니다. 보기를 바꾸는
  컨트롤은 ink `sk-nav-pill`, 데이터를 좁히거나 역할을 지정하는 컨트롤은
  terracotta `sk-chip`, 상태 표시는 `UBadge`. 숫자는 `font-mono tabular-nums`.
- **완료 기준.** `npm run typecheck`, `npm run lint`, `npm test` 가 깨끗하고,
  브라우저 확인 항목을 실제로 봤고(`browser-verify` 스킬), 바뀐 문서가 있으면
  `npm run lint:md` 를 돌린 뒤 `main` 에 올리고 worktree 를 지웁니다.

## 1묶음

### S2. 측정 이력 행 → 스큐보아 분석 (S)

**질문.** 이 실행의 원본 측정은 무엇인가.

**지금 코드.**

- 측정 이력 표의 `msr` 열은 `accessorKey: 'msr_check'` 로 Yes/No `UBadge` 만
  그립니다(`components/ebeam/RecipeMeasHistView.vue` 의 columns). 행에는
  `msr`, `lot_id`, `recipe_name`, `eqp_id`, `timestamp` 가 모두 있습니다
  (`composables/useMeasHistApi.ts:9-37`).
- 스큐보아 검색 랜딩이 **같은 변환을 이미 갖고 있습니다.**
  `skewvoir/SearchLanding.vue:161-168` 의 `toSelection(row)` 가 행을
  `SkewvoirSelection` 으로 바꾸고 `ws.openAnalysis(sel)` 로 엽니다. S2 는 이
  함수를 꺼내 쓰는 일입니다.
- 진입 계약: `utils/skewvoirAnalysis/routeQuery.ts:89-100` 의 `parseSelection`
  은 `lot` 만 필수이고, `mp` 는 `WAFER` 기본값, `cap` 은 표시용입니다.
  `toAnalysisQuery`(186-203)가 `msrs` 를 `[msr]` 로 채워 단일 범위가 됩니다.
  경로는 `/ebeam/{cd-sem|hv-sem}/skewvoir/analysis` (`useSkewvoirRoute.ts`).
- `msr` 이 빈 행이 있습니다. mock 은 `msr_check` No 인 8% 가 빈 문자열이고,
  사내는 21,474행에서 `msr` 이 없었다고 mock 의 docstring 이 적고 있습니다
  (`backend/meas_hist/providers/mock.py:270-285`).

**변경.**

1. `utils/skewvoirLinks.ts` 에 `skewvoirAnalysisRouteForRow(toolType, row)` 를
   더합니다. 안에서 `toSelection` 과 `toAnalysisQuery` 를 써서 `{ path, query }`
   를 돌려주고, `row.msr` 이 비면 `null` 입니다. `SearchLanding.vue` 의
   `toSelection` 은 이 모듈로 옮겨 두 벌을 두지 않습니다.
2. `RecipeMeasHistView.vue` 의 `msr` 열: `msr` 이 있으면 `NuxtLink` 로 MSR id
   앞 8자와 `i-lucide-telescope` 아이콘(선례 `RecipeRowActions.vue:56-65`),
   없으면 지금의 No 배지를 그대로 둡니다. 헤더는 그대로, 툴팁은 "스큐보아에서
   열기".

**테스트** (`skewvoirLinks.test.ts` 에 추가).

- 행 → 경로 → `parseSelection` 왕복에서 lot, recipe, eq, msr, cap 이 보존된다.
- `msr === ''` 이면 `null` 이다.
- `recipe_name` 에 `/` 가 있어도 query 값은 원문이다(인코딩은 라우터 몫).
- hv-sem 은 hv-sem 경로로 간다.
- `msrs` 는 `[msr]` 하나이고 `scope` 는 single 로 읽힌다.

**브라우저 확인.** 새 탭으로 열기, 분석 화면 새로고침, 뒤로 가기로 표 복귀,
최근 본 목록(기억된 값)과 충돌 없음, 세트 보기 중 다른 행으로 재진입.

**주의.** 분석 화면은 계열 전체의 30일 측정 이력을 fab 없이 받아 `focusRow` 를
찾습니다(`useSkewvoirAnalysis.ts:60-68`). 행이 그 집합 밖이면 백엔드가
`class_name` 을 스스로 풀어 파일은 열리지만 캡처 시각 같은 보조 정보가 빕니다.
61일이 지난 파일은 410 이고, 이는 지금 분석 화면이 이미 다루는 경우입니다.

**하지 않는 것.** `/meas-hist/search?msr=` 폴백, 표 전체를 세트로 한 번에 열기.

### S5. 계측 룰 판정 근거 설명 (S)

**질문.** 왜 이 recipe 가 이 cap 으로 판정됐는가.

**지금 코드.**

- `utils/ruleEngine.ts` 는 이유를 **계산은 하지만 결과에 남기지 않습니다.**
  `resolveRuleCell`(:326-331)은 `{kind:'cell', cell} | {kind:'gray', gray:'A'|'B',
  reason}` 을, `resolveCap`(:134-158)은 `{cap, source:'type'|'name'|'fallback'}`
  을 돌려주는데, `evaluateRecipe` 가 만드는 `ParamResult`(:349)에는 `cap` 과
  `over_cap` 불리언만 남고 출처와 매칭 셀이 빠집니다. `effectiveCap`(:271)이
  son 의 fallback 을 mother 의 cap 으로 바꾸는 상속도 결과에서 보이지 않습니다.
- recipe 단위로 결과를 보는 곳은 하나뿐입니다. `ComplianceTable.vue` 의
  자세히 → `devstat/DrillSlideover.vue` → `DrillParamRows`("cap 9" 메모 수준).
- 룰 매트릭스(`MeasurementRulesView.vue`)는 R3 고정이고 셀 클릭이 없습니다.

**변경.**

1. `ruleEngine.ts` 의 결과 타입을 넓힙니다. `ParamResult` 에
   `cap_source: 'type'|'name'|'fallback'|'inherited'|'exempt'` 와
   `over_by: number|null` 을, `RecipeResult` 에 `cell_id: string|null` 을
   더합니다. 값은 이미 손에 있으므로 저장만 추가합니다. **기존 54개 테스트가
   그대로 통과하는 것이 조건입니다.**
2. 새 순수 함수 `explainRecipe(recipe, result, cell)` (`utils/ruleExplain.ts`).
   입력(제품군, phase 또는 yield_check, memory_class 와 그 출처 auto/annotation,
   recipe_class, 이름 예외 적용 여부), 선택된 셀(id 와 selector), gray 사유,
   파라미터별 (이름, 타입, point_count, cap, 출처, 초과분)을 한국어 문장과 표
   행으로 만듭니다. **엔진 로직을 다시 쓰지 않고 엔진의 출력을 배열만 합니다.**
3. 화면: `DrillSlideover` 의 recipe 머리에 "판정 근거" 접기 블록을 두고,
   파라미터 표에 출처 열을 더합니다. 매트릭스에서 해당 셀을 강조하는 이동은
   2단계로 미룹니다.

**테스트** (`ruleExplain.test.ts`). `_other` fallback, 이름 예외로 면제(null),
son 이 mother cap 을 상속, Pool 이 phase 를 이기는 사례(`CONTEXT.md:91`),
gray A 와 B.

**브라우저 확인.** R3 lot 하나 자세히 → recipe 펼침 → 근거 블록. `judgeSons`
토글에 따라 상속 표기가 바뀌는지.

**하지 않는 것.** 룰 엔진 두 벌, 룰 편집, 매트릭스 클릭 이동.

### S3. Recipe 현황 이전 동일 기간 대비 (S)

**질문.** 지난 기간보다 무엇이 변했는가.

**지금 코드.**

- 탭은 `tat | align | meas` 이고 URL `?tab=` 이 진실입니다
  (`RecipeStatusView.vue:81-109`).
- 기간은 `DateRangePopover` 의 프리셋(오늘, 7, 14, 30, 60, 90일)이나 자유
  범위이고, 로컬 `userDateRange` 에만 있습니다(`RecipeTatView.vue:236`,
  `FailIssueView.vue:316`). 비어 있으면 서버가 기준일 기준 14일을 쓰고, 실제로
  쓴 창을 `summary.start_date`/`end_date` 로 돌려줍니다.
- 요약 엔드포인트가 `start_date`/`end_date` 를 그대로 받고 상한이 없습니다
  (`backend/ebeam/_analytics_routes.py:48-83`). 응답은 recipe_tat 이
  `total_tat_seconds, total_recipes, total_executions, avg_meastime`, fail_issue
  가 `total_executions, align_fail_count/rate, meas_fail_count/rate, …` 이며
  rate 는 0..1 소수입니다. **백엔드 변경이 필요 없습니다.**
- KPI 는 타일이 아니라 `RecipeStatusInlineSummary.vue` 의 `<dl>` 스트립이고,
  항목 타입은 `RecipeStatusSummaryItem { label, value, tone? }`
  (`utils/recipeStatusSummary.ts:1-5`)입니다.
- 두 블루프린트는 rate-limit 면제라 요청 하나를 더해도 됩니다
  (`backend/__init__.py` 의 `_EXEMPT_BLUEPRINTS`).
- 장비 지수(`tat_index`, `align_index`, Byar 구간)는 `/equipments` 쪽 백엔드
  계산이며 `/summary` 와 무관합니다. 건드리지 않습니다.

**변경.**

1. `utils/recipeStatusDelta.ts`.
   - `previousWindow(start, end)` → 같은 길이로 바로 앞 구간
     `{ start: start − len, end: start − 1일 }`.
   - `tatDelta(cur, prev)`, `failDelta(cur, prev, section)` → 항목마다
     `{ delta: string, tone: 'ok'|'bad'|'neutral'|'none', title: string }`.
     실행 수는 방향이 없으므로 neutral. 실행당 시간과 실패율은 감소가 ok.
     실패율 차이는 %p = (cur − prev) × 100, 실행당 시간은 초 차이와 %.
     이전 기간 실행이 0이면 "이전 기간 없음"(tone none).
   - `title` 에 양쪽 분모를 넣습니다. "이전 14일(09-08~09-21) 1,204건 대비".
2. `RecipeStatusSummaryItem` 에 `delta?` 를 더하고 `RecipeStatusInlineSummary.vue`
   가 값 옆에 `text-xs font-mono` 로 그립니다. 색은 `--sk-ok` / `--sk-bad` /
   `--sk-ink`.
3. 두 뷰에 두 번째 `useAsyncData`(`recipe-tat:prev:…`, `fail-issue:prev:…`).
   같은 fetch 함수에 옮긴 날짜를 넣습니다. **유효 창이 echo 된 뒤에만** 부릅니다
   (`userDateRange` 가 비어 있으면 `summary.start_date/end_date` 를 씁니다).
4. 라벨은 "이전 동일 기간 대비(원시 변화)". 현재 창의 끝이 기준일이면
   "기준일 포함" 힌트를 붙입니다.

**결정.** 기준일(진행 중인 하루)은 **표시 중인 창 그대로 비교하고 힌트로
알립니다.** 양쪽에서 기준일을 빼면 화면의 총량과 비교 분모가 어긋나 더
헷갈립니다. 브레인스톰의 "완결된 기간" 조건은 이전 구간 쪽에서 지켜집니다.

**테스트.** `previousWindow` 의 월말·1일 창·윤년, 분모 0, 부호와 tone, %p
소수 자리, 실행 수 neutral.

**브라우저 확인.** 프리셋 7일 ↔ 30일 전환에 delta 가 따라오는지, 범위를
비웠을 때 echo 창으로 계산되는지, KeepAlive 탭 전환에서 중복 요청이 없는지,
다중 fab.

**하지 않는 것.** 변화 분해, 급변 목록(S3 다음), 추세 차트 위 이전 기간 선.

### S4. 측정 이력 장비별 꼬리 분해 (S)

**질문.** 전반적으로 느린가, 몇 건이 느린가.

**지금 코드.**

- `GET /meas-hist` 는 30일, 페이지 없음. 사내는 `size=10000` 상한이라
  `total` 보다 `rows` 가 적을 수 있고 `capped` 플래그가 없습니다
  (`backend/meas_hist/providers/office_example.py:403-407`).
- 행의 `meastime` 은 초 단위 정수, `align_fail` 은 Pass/Fail/NA, `fail_ratio`
  는 0..100 이며 뷰의 임계는 `MEAS_FAIL_THRESHOLD = 15` 입니다.
  **`msr_check` 가 No 인 행은 `meastime` 이 0 입니다**(mock.py:241-250, 사내도
  `_int(None)` 이 0). 분위수에서 빼지 않으면 P50 이 내려갑니다.
- 집계는 전체 한 줄뿐입니다(뷰의 `aggregates`). `meastime` 헤더 정렬은 이미
  있습니다.
- 분위수 함수가 있습니다. `utils/stats.ts:27-33` `quantileSorted(sorted, p)`
  (R-7 선형보간, 호출자가 정렬과 유한값 필터를 맡음).
- 요청이 `tool_type + fab_name + recipe_name` 이라 행은 이미 단일 fab·단일
  계열입니다. `eqp_id` 로 묶어도 mock 의 중복 id 가 섞이지 않습니다. `fab` 이
  비는 드문 경우만 `fab_name + eqp_id` 로 묶습니다.

**변경.**

1. `utils/measHistTails.ts` 의 `equipmentTails(rows, { failThreshold })`.
   장비별 `{ eqpId, n, excludedZero, p50, p90, max, slowest: { timestamp, lot_id,
   msr, meastime }, alignFail, measFail }` 과 "전체" 한 줄. 정렬은 p90
   내림차순. `n < 5` 면 p90 은 계산하되 화면에는 "—" 로 두고 "표본 부족"을
   적습니다.
2. 화면: 표 위에 접이식 "장비별 분포" 블록. 열은 장비 / n / P50 / P90 / 최대 /
   Align Fail / 측정 실패(≥15%) / 가장 느린 실행. 가장 느린 실행 칸은 S2 의
   링크를 그대로 씁니다. 캡션: "반환된 {rows.length}건(총 {total}건), 최근
   30일, meastime 0 인 {k}건 제외".
3. `total > rows.length` 이면 "표본이 잘렸습니다" 경고를 캡션에 붙입니다.

**테스트.** 0 제외, `n < 5` 표기, R-7 값이 고정 사례와 일치, Fail 분리 수,
정렬.

**브라우저 확인.** mock 은 recipe 당 8~20행을 합성하므로 표본이 작습니다.
"표본 부족" 표기가 실제로 보이는지, 기존 헤더 정렬과 함께 동작하는지.

**하지 않는 것.** 서버 집계, 전수 주장, 재시도 추정.

## 2묶음

### S1. 라이브 알람 사건 범위 (S/M)

**질문.** 장비 문제인가, recipe 문제인가, lot 문제인가.

**지금 코드.**

- `LiveAlarmView.vue` 는 20분 창의 모든 이벤트(`events`, align + meas)와
  `counts` 를 이미 갖고 있습니다. 폴링은 15초 ± 3초
  (`useLiveAlarmFeed.ts:9-10`)이고 응답이 보드 전체를 교체하므로 클라이언트
  누적 상태가 없습니다.
- 묶기는 순수 함수입니다. `utils/liveAlarm.ts:120-165` `groupMeasEvents` 가
  meas 만 `[eqp_id, ppid]` 로 묶고, `distinctLotCount` 는 빈 lot 을 무시합니다.
  테스트는 `liveAlarm.test.ts` 의 `describe('groupMeasEvents')` 형태입니다.
- 이벤트 필드는 null 이 없고 빈 값은 `""` 입니다. `kind` 는 align|meas,
  `alid` 는 9006(align), 9007·9035(meas), `recipe_id == ppid`.
- 레이아웃은 MetaBar → UAlert → 보드 패널 → 각주이고, 세 탭은 한 패널에
  묶인 모델이라 네 번째 탭을 더하면 안 됩니다.
- 수집은 누가 보고 있을 때만 일어납니다(`backend/ebeam/live_alarm/refresh.py`).
  빈 구간은 기존 동작입니다.

**변경.**

1. `liveAlarm.ts` 에 `scopeGroups(events)` 를 더합니다. 돌려주는 것은
   `recipeAcrossTools`, `toolAcrossRecipes`, `lotAcrossTools` 세 목록이고,
   원소는 `{ key, label, eventCount, toolCount, recipeCount, lotCount,
   firstEpoch, lastEpoch, kinds: { align, meas }, alids: Record<string, number> }`
   입니다.
   - 둘 이상(장비 2+, recipe 2+)일 때만 목록에 둡니다.
   - 빈 recipe·lot 은 묶지 않고 `omitted` 수로 보고합니다.
   - align 과 meas 를 함께 셉니다. 범위 질문은 kind 와 무관하고, 구성은
     `kinds` 로 보입니다. `groupMeasEvents` 의 meas 필터를 재사용하지 않습니다.
   - 정렬은 범위 수 → 이벤트 수 → 최근 순.
2. `components/live-alarm/ScopePanel.vue`: UAlert 와 보드 사이에 3열(한 recipe
   · 여러 장비 / 한 장비 · 여러 recipe / 한 lot · 여러 장비). 열마다 최대 3개와
   "외 n", 행은 라벨, "장비 3 · lot 2 · 7건", 시간 폭(`formatElapsed`), alid
   칩. 비면 "해당 없음". 이벤트가 없거나 `not_configured` 면 패널을 숨깁니다.
   캡션: "최근 20분 창에서 관측된 범위입니다. 원인이나 해결을 뜻하지
   않습니다."
3. `metaStats` 에 고유 장비 수를 더하는 것은 선택입니다.
4. **새 요청도 새 상태도 없습니다.** 그룹을 눌러 필터를 거는 일은 상태가
   생기므로 2단계입니다.

**테스트** (`describe('scopeGroups')`). 장비 2대 이상만 남는다, 빈 ppid 는
`omitted` 로 간다, align + meas 혼합의 kinds 분리, 시간 폭, 정렬, 한 lot 이
여러 장비에서.

**브라우저 확인.** mock 보드에 "한 recipe 가 여러 장비"가 실제로 생기는지.
생기지 않으면 `live_alarm/providers/mock.py` 에 그 패턴을 더하고 docstring 에
`OFFICE-VERIFY` 로 적습니다. 폴링마다 패널이 깜빡이지 않는지(키 안정),
다중 fab 배지.

**하지 않는 것.** 만성·신규 배지, 측정 이력 조인, 확인·해결 흐름.

### S17. 알람 → 스큐보아 검색 (S, S1 과 한 worktree)

- `components/live-alarm/AlarmRow.vue:61-116` 머리줄에 ghost
  `i-lucide-telescope` `UButton` 을 둡니다(선례 `RecipeRowActions.vue:56-65`).
  `:to` 는 `skewvoirSearchRoute(toolType, { eq: event.eqp_id, recipe:
  event.recipe_id, fab: event.fab_name })`. `hasSkewvoir(toolType)` 이고
  `eqp_id` 가 비어 있지 않을 때만 보입니다. **`fab` 은 경로의 `fabSegment`
  ("r3,r4") 가 아니라 이벤트의 `fab_name` 입니다.**
- `MeasGroup.vue` 의 머리는 펼치기 `<button>` 이라 액션은 그 바깥에 둡니다.
- `recipe_id` 에 공백이 있으면 검색어가 쪼개집니다(`utils/measHistQuery.ts:56`).
  그 경우 recipe 를 빼고 eq 만 넘깁니다. 이 분기는 순수 함수
  `alarmSkewvoirTarget(event)` 로 빼서 테스트합니다.
- 폴링 중 측정 이력을 부르지 않습니다. 링크일 뿐입니다.
- 손으로 조립된 recipe-search 경로(`AlarmRow.vue:22-26`)는 이번에 고치지
  않습니다. 빌더가 없는 화면에 빌더를 새로 두는 일은 S16 과 함께 봅니다.
- **사내 확인.** 알람 `recipe_id` 가 class 접두를 포함하는지 문서에 없습니다.
  어느 쪽이든 검색은 부분 일치라 되지만, 그래서 상세 화면 링크는 만들지
  않습니다.

### S7. 스큐보아 기준·대상 고정 비교 (M)

> 2026-10-09 구현했습니다. 아래는 당시 계획 그대로이며, 달라진 점은 다음
> 네 가지입니다.
>
> - "기준 대비" 블록은 Dashboard 가 아니라 Time-Series 뷰의 파라미터 목록
>   아래에 있습니다. Dashboard 는 세트 파일을 불러오지 않는 것이 테스트로
>   고정된 불변식(`shouldLoadSet`)이고, 이를 깨면 활성 파라미터 선택 규칙까지
>   세트 기준으로 바뀝니다.
> - "기준" 토글은 세트 편집 모달이 아니라 좌측 레일의 비교 세트 행에
>   있습니다. 모달에는 MSR 행이 없고, 분석 대상을 바꾸는 컨트롤은 레일에
>   둔다는 `DESIGN.md` 의 레일 규칙을 따랐습니다.
> - `baselineComparison` 은 `setRows` 를 받지 않으며, 측별 통계는 `cduMetrics`
>   결과(`pooled`)를 그대로 돌려줍니다. 호환되지 않는 측정은 `splitBaseline`
>   이 `manifest.included` 로 걸러 냅니다.
> - 계획에 없던 것 하나를 더했습니다. 위치 비교의 세트 화면에 site 별
>   `대상 − 기준` 맵(`baselineDeltaMap`)이 세 번째 패널로 나옵니다. 한쪽
>   그룹만 측정한 site 는 0 이 아니라 빈 자리로 둡니다.
>
> 같은 날 위치 맵의 규칙을 세 맵에 똑같이 맞췄습니다. site 는 (chip,
> 측정점)이고, chip 에 그리는 값은 측정점별 통계를 같은 비중으로 평균한
> 값입니다. `Composite Mean` 과 `Site Variability (σ)` 도
> `compositeSiteMap` 으로 계산하며, σ 는 같은 측정점을 두 wafer 이상이 측정했을
> 때만 값이 있습니다. `analysis.siteDeltaReady` 가 거짓이면 세 맵 모두 그리지
> 않고 같은 위치임을 확인할 수 없다고 적습니다.

**질문.** 고정된 기준 집단보다 얼마나 움직였는가.

**지금 코드.**

- 세트는 URL `msrs`(최대 `TREND_LIMIT = 30`), 포커스는 `msr`.
  `useSkewvoirAnalysis.ts` 가 `setFiles: Map<msr, MsrFileResponse>`(파라미터별
  `count/mean/std/min/max` 와 포인트 행), `setRows`(측정 이력 행: lot, eqp,
  timestamp, recipe), `manifest`(included / excluded + 사유)를 듭니다.
- 판정은 자기 비교입니다(`utils/skewvoirAnalysis/verdict.ts:8-13`). 렌더는
  `skewvoir/overview/VerdictBlock.vue`, Dashboard 뷰.
- 이름이 이미 쓰입니다. `tsb`(시계열 resid 기준선), `ref`(참조 파라미터). 새
  키는 **`base`** 로 둡니다.
- 상태 패턴은 `routeQuery.ts` 의 parse/encode 쌍 → `useSkewvoirRoute` 의
  computed → `ws.patchQuery` 입니다. 세트 편집 UI 는
  `SelectionDetailModal.vue:80` 의 "세트 편집" → `ws.setMsrs`.
- 통계는 `utils/skewvoirAnalysis/cdu.ts:64` `cduMetrics(rows, parameter, unit)`
  → `n, missing, level{mean, median}, spread{std, threeSigma, madSigma,
  range}`. 포인트 값은 `utils/msrRows.ts` 의 `paramValues`.

**변경.**

1. `routeQuery.ts` 에 `base=id,id` parse/encode. 읽을 때 `msrs` 와 교집합을
   취하므로 세트에서 빠진 id 는 자동으로 떨어집니다. `ws.baseline` 과
   `ws.setBaseline(list)`.
2. 세트 편집 모달의 MSR 행마다 "기준" `sk-chip` 토글(역할 지정이므로
   terracotta). 기준이 비어 있으면 화면은 지금과 같습니다.
3. 순수 함수 `baselineComparison(setFiles, setRows, baseIds, targetIds,
   parameter, unit)` (`utils/skewvoirAnalysis/baselineCompare.ts`).
   - 측마다 MSR 단위 `cduMetrics` 와, 모든 포인트를 합친 풀링 통계
     `{ msrCount, pointCount, mean, median, threeSigma, range }`.
   - 비교 `{ shift: target.mean − base.mean, shiftInBaseSigma: shift /
     base.threeSigma, threeSigmaRatio, rangeDelta }`.
   - 포함 범위 `{ baseMsrs, targetMsrs, excluded: manifest.excluded }`.
   - 측당 MSR 1개 이상, 포인트 2개 이상이 아니면 `insufficient` 와 사유.
   - 풀링은 포인트를 같은 가중치로 합치므로 포인트가 많은 MSR 하나가
     지배할 수 있습니다. 최대 MSR 의 포인트 비율을 `dominance` 로 함께
     돌려주고 0.6 을 넘으면 화면에 적습니다.
4. Dashboard 에 "기준 대비" 블록(VerdictBlock 아래). 표 하나와 문장 하나.
   "기준 3건보다 대상 2건의 평균이 +0.42 nm(기준 3σ 의 0.3배) 이동했고 3σ 는
   1.1배입니다." 색은 중립, 라벨은 "이 세트 안에서 손으로 나눈 기준이며 공식
   기준선이 아닙니다". `verdict.ts` 는 건드리지 않습니다.
5. 시계열 뷰에서 기준 MSR 을 음영으로 구분하는 것은 2단계입니다.

**테스트.** `base` parse/encode 왕복과 `msrs` 교집합, 비교 수치 고정 사례,
표본 부족, dominance. 단위 불일치는 manifest 가 이미 제외하므로 들어오지
않는다는 가정을 테스트 이름으로 남깁니다.

**브라우저 확인.** 기준 지정 후 공유 URL 을 새 탭에서 열어 같은 결과,
세트 편집으로 기준 MSR 을 빼면 자동 탈락, 포커스를 바꿔도 기준 유지.

**하지 않는 것.** 자동 집단 탐색, 저장되는 공식 기준, Cp/Cpk, 판정 색.

### S13. 계측 룰 cap 가정 계산 (M)

**질문.** 룰을 바꾸면 어떤 recipe 와 lot 이 영향을 받는가.

**지금 코드와 이미 있는 설계.**

- what-if 는 **설계가 이미 있습니다.** `docs/issues/ground_rules/grilling-log.md`
  의 D17·D18 과 `rule-editor-structure.md` §5·§8-bis: `draft` ↔ `applied`
  분리, 명시적 "적용" 버튼, **cap 만** 대상이고 신호등 threshold 는 제외,
  저장은 D12 로 폐기. 이 계획은 그 설계에서 저장을 뺀 부분을 구현합니다.
- 판정은 전부 클라이언트입니다. `ComplianceTable.vue:128` 이
  `evaluateLot(lot, recipes, cells, { judgeSons })` 를 부르고 `cells` 가
  인자이므로 복제한 셀을 그대로 넣을 수 있습니다. 백엔드에는 compliance
  엔드포인트도 cap override 도 없습니다.
- recipe-params 는 장바구니 lot(`useDeviceCart().selectedDeviceLots`)만
  받습니다. 빈 목록은 전체(약 522 MB)라 금지입니다. 그래서 "영향받는 lot" 은
  **장바구니 lot 범위**입니다.
- 룰 페이지는 R3 고정입니다. D17 의 `useMeasurementMonitor` 는 계획만 있고
  파일이 없으며, `ComplianceTable` 이 이미 데이터를 들고 있으므로 만들지
  않습니다.
- `ToleranceKnob.vue` 는 TTTM 의 nm 슬라이더라 무관합니다.

**변경.**

1. `utils/ruleWhatIf.ts`.
   - `applyCapDraft(cells, edits: { cellId, column, cap: number|null }[])` →
     불변 복제된 `RuleCell[]`.
   - `diffCompliance(before: LotHealth[], after: LotHealth[])` →
     `{ recipes: { lot_cd, recipe_id, from, to, changedParams }[], lots: { lot_cd,
     violationBefore, violationAfter, healthBefore, healthAfter }[], summary }`.
     `from/to` 는 pass | fail | gray.
2. `MeasurementRulesView.vue`: 매트릭스 `CapCell` 을 draft 입력으로 바꾸고
   "적용"·"되돌리기" 버튼을 둡니다. 적용하면 `appliedCells` 가
   `ComplianceTable` 에 prop 으로 내려가 재계산합니다. **저장 버튼은 없고
   새로고침하면 사라집니다.** cap 을 비우는 것과 면제(null)는 뜻이 다르므로
   면제는 명시 토글로 둡니다.
3. 영향 패널: 새로 위반 / 해소된 recipe 목록, lot 별 위반 수와 신호등 변화
   (threshold 는 저장본 고정). 캡션: "장바구니 lot {n}개 범위입니다. 저장되지
   않으며, 룰 변경은 `rules.py` 배포로만 반영됩니다."
4. draft 가 저장본과 다른 셀은 `--sk-warn-soft` 로 칠하고, 적용 상태에서는
   화면 위에 노란 띠를 둡니다. 임원과 담당자가 같은 URL 을 쓰므로 가정 상태임이
   한눈에 보여야 합니다.

**테스트.** `applyCapDraft` 가 원본을 바꾸지 않는다, diff 분류(pass→fail,
fail→pass, gray 불변, son 상속 영향), 적용 전후 `judgeSons` 가 같은 값으로
들어간다.

**브라우저 확인.** 장바구니가 비었을 때 안내, 셀 수정 → 적용 → 표 재색,
되돌리기, 새로고침 후 초기화, 적용 띠.

**하지 않는 것.** 저장·이력·rollback, threshold what-if, fab 전체 lot 조회.

### S8. 스큐보아 검토 영수증 (S/M, S7 뒤)

> 2026-10-09 구현했습니다. 아래는 당시 계획 그대로이며, 달라진 점은 다음
> 여섯 가지입니다.
>
> - 판정 문장과 `outlierShare` 는 넣지 않았습니다. `measurementVerdict` 는
>   "정상 / 확인 필요" 배지를 함께 내는 판정이고 입력을 `VerdictBlock.vue` 가
>   조립합니다. 영수증은 차이와 표본 수만 적으므로, 설정한 기준으로 센
>   주의·이상 site 수와 그 목록(`overviewSites`)만 담습니다. 목록은 focus 만이
>   아니라 포함된 측정 전부를 적습니다.
> - `afmExport.ts` 의 `buildCombinedSheets` 는 쓰지 않았습니다.
>   `receiptSheets` 가 `WorkbookSheet[]` 를 직접 만들고 `downloadWorkbook` 에
>   넘깁니다. 내보내기 유틸은 고치지 않았습니다.
> - 세트 범위에서는 세트 파일을 모두 불러온 화면에서만 버튼이 켜집니다
>   (`receiptReady`). 측정 개요는 세트 파일을 불러오지 않으므로
>   (`shouldLoadSet`) 거기서 받으면 focus 외의 측정이 모두 "불러오지 못함"으로
>   적히기 때문입니다. 단일 측정 범위에서는 모든 화면에서 켜집니다.
> - 분석 URL 은 단축 링크가 아니라 전체 주소를 적습니다. 전체 주소는 무엇을
>   보고 있었는지를 스스로 담고 있고, 단축 링크는 서버 저장소가 살아 있어야
>   풀립니다.
> - 제외 사유의 한글 이름은 `compatibility.ts` 의 `EXCLUSION_REASON_LABEL`
>   로 옮겨 분석 준비 상태 모달과 영수증이 같은 표를 읽습니다.
> - 계획에 없던 시트를 더했습니다. 내보낼 방법이 없던 표 가운데 계산이 이미
>   컴포저블이나 export 된 순수 함수에 있는 것만 데이터가 있을 때 시트가
>   됩니다. `장비 skew`(`analysis.toolSkew`), `MSR별 지표`(`featureRows` 를
>   `acrossMsrAxes` 축으로 펼친 것), `기준 대비 site`(`baselineDeltaMap`)입니다.
>
> 같은 날 계산이 컴포넌트 안에 있어 빠졌던 표 셋을 더했습니다. 각 계산을
> export 된 순수 함수로 옮겨 화면과 영수증이 같은 함수를 부릅니다. 현재 시트는
> 다음과 같고, `요약` 과 `세트` 외에는 데이터가 있을 때만 씁니다.
>
> | 시트 | 내용 | 계산 |
> | --- | --- | --- |
> | `요약` | 선택, 설정, 메모, 주의, 분석 URL | 입력 그대로 |
> | `세트` | 측정별 역할과 수준 · 산포 | `cduMetrics`, `overviewSites` |
> | `기준 대비` | 기준 · 대상의 pooled 통계와 차이 | `baselineComparison` |
> | `기준 대비 site` | chip 별 대상 − 기준 | `baselineDeltaMap` |
> | `위치 합성 site` | chip 별 측정점 수, wafer 수, mean, σ | `compositeSiteMap` |
> | `반경 fit` | focus 측정의 모델, n, RMSE, 반경 범위, 계수 | `radialSamples`, `analyzeRadialProfile` |
> | `장비 skew` | 장비별 n, 평균, 기준 대비, σ | `analysis.toolSkew` |
> | `MSR별 지표` | 측정별 축 값 | `acrossMsrAxes` |
> | `세트 상관` | 전체 · 장비별 Pearson r, Spearman ρ, MSR n | `acrossMsrOutcomeFor` |
> | `주의·이상·실패 site` | 설정한 기준으로 센 site 목록 | `overviewSites` |
>
> - `위치 합성 site` 는 세트 범위에서만 씁니다. 같은 위치임을 확인할 수 없으면
>   쓰지 않고 `요약` 에 그 사실을 적습니다.
> - `반경 fit` 의 차수는 URL `rfit` 값이며, 계수는 정규화 반경
>   t = (반경 − 중간 반경) / 반폭 기준으로 낮은 차수부터 적습니다.
> - `세트 상관` 의 축은 화면에서 고른 축입니다. 세트 범위 상관 화면의 X · Y
>   선택을 URL `ax` · `ay` 로 옮겼고, 기본 축이면 키를 쓰지 않습니다. 계수와
>   표본 수만 적으며 관계가 있다는 판정은 적지 않습니다.
> - 집에서는 mock 이 CD · FDC · 품질 score 를 같은 값 하나에서 만들기 때문에
>   `요약` 의 주의와 `세트 상관` 시트에 데모 데이터 문구가 붙습니다. 사내
>   데이터에는 붙지 않습니다.
>
> 시트는 `요약`, `세트`, 기준을 지정했을 때 `기준 대비` 와 `기준 대비 site`,
> 데이터가 있을 때 `위치 합성 site`, `반경 fit`, `장비 skew`, `MSR별 지표`,
> `세트 상관`, `주의·이상·실패 site` 입니다. `세트 상관` 과 `MSR별 지표` 는 모두
> 비교에 포함된 측정만 씁니다(제외된 측정은 계수에 들어가지 않습니다).

**질문.** 이 결론과 근거를 어떻게 남기는가.

**지금 코드.**

- 내보내기 유틸이 있습니다. `utils/xlsx.ts:65` `downloadWorkbook(filename,
  sheets)`, `utils/afmExport.ts` `buildCombinedSheets(sections)`(섹션 → 시트,
  AFM 이름이지만 범용), `utils/tableExport.ts:40` `downloadBlob`,
  `composables/useTableDownload.ts`(실패 토스트).
- 스큐보아의 내보내기는 포커스 MSR 의 raw/pkl 다운로드와 "요약 복사"
  (`utils/skewvoirAnalysis/summary.ts` `formatSelectionSummary`)뿐입니다
  (`skewvoir/workspace/LeftRail.vue:471-503`).
- 메모는 없습니다. per-MSR 어노테이션 티켓
  (`.scratch/skewvoir-annotation/issues/01-per-msr-annotation.md`)이
  needs-triage 로 서버 저장을 전제하고 있어 이번에 건드리지 않습니다.
- 담을 수 있는 것: `ws.selection`, `ws.msrList`, `ws.scope`, `ws.shareUrl`,
  `activeParam/activeUnit`, `anomalyCfg`(method, range 10/20%, stddev 2k/3k),
  `ws.tsView/tsAxis/tsBaseline`, `manifest`, `cduMetrics` 출력,
  `measurementVerdict` 출력(문장, outlierShare), `siteVerdicts` 의 이상치
  목록, S7 의 `baselineComparison`.

**변경.**

1. 순수 함수 `buildReviewReceipt(input): ReviewReceipt`
   (`utils/skewvoirAnalysis/receipt.ts`). 섹션은 선택, 설정, 세트(MSR 별 lot ·
   eqp · timestamp · recipe · 포함/제외 사유 · 기준/대상 역할), 근거(cduMetrics
   의 n/missing/total/mean/median/std/3σ/madσ/range, 판정 문장, outlierShare,
   이상치 사이트, S7 수치), 메모, 주의("원본 파일은 61일 뒤 삭제됩니다. URL 은
   다시 계산하는 주소이며 수치는 생성 시각 기준입니다"). 사용자 식별자는 넣지
   않습니다.
2. `receiptSheets(receipt): WorkbookSheet[]` →
   `downloadWorkbook('skewvoir-receipt-<msr>-<YYYYMMDD>.xlsx', …)`.
3. LeftRail 액션에 "검토 영수증". 작은 `UModal` 에 메모 textarea(세션 한정,
   저장하지 않음)와 내려받기 버튼.
4. JSON 은 S18 이 필요로 할 때 `JSON.stringify(receipt)` 한 줄로 더합니다.
   지금은 만들지 않습니다. 영수증 **객체**가 S18 의 입력 형태이고, 파일 형식은
   그 뒤의 문제입니다.

**테스트.** 영수증 객체의 필드 존재와 수치 일치(스냅샷이 아니라 명시 비교),
빈 세트와 판정 없음, 시트 행 수.

**브라우저 확인.** 내려받은 파일을 열어 섹션 확인, 단일 모드와 세트 모드,
exceljs 로드 실패 시 토스트.

**하지 않는 것.** 서버 저장, 공유 DB, PDF, 메모 영속.

## 보류: S6. AFM 고정 기준 비교 (M)

> 2026-10-09 구현했습니다. AFM 사내 어댑터가 2026-10-07 사내에서 동작해 보류
> 조건이 풀렸습니다. 아래는 당시 계획 그대로이며, 띠 이름은 관리선 대신
> `그룹 기준 범위` / `고정 기준 범위`로 바꿨습니다.

**질문.** 독립된 기준에서 얼마나 벗어났는가.

**지금 코드.**

- `utils/afmTrend.ts:190-205` `trendRows(entries, block, column, stat,
  showLimits)` 가 recipe 별 `centres = { mu, limits: controlLimits(values) }` 를
  **카트 전체**에서 계산합니다. σ 는 MAD 기반 `robustSd`(:89) 이고 μ ± 3σ 가
  관리선입니다. 바꿀 이음매는 이 `centres` 한 곳입니다.
- 측정의 identity 는 tool + filename 입니다. 카트는 `useAfmCart(toolId)` 의
  `usePersistedState` 슬라이스 네 개(`StorageKind`)입니다.
- 페이지 `pages/afm/[tool]/see-together.vue` 는 로컬 상태 `block, column,
  stat, showLimits, selected` 를 갖고 KPI "관리선 밖"을 보여 줍니다.
- `PointBaseline = 'mean'|'first'|'selected'` 는 포인트 Δ 전용이라 관리선과는
  다른 개념입니다.
- **사내 어댑터가 stub 입니다.** `backend/afm/providers/office_example.py` 의
  모든 함수가 `NotImplementedError` 라 사내에서도 mock 을 봅니다.

**변경.**

1. `useAfmCart` 에 `baseline` 슬라이스(filename 목록, tool 별 영속). normalize
   에서 카트와 교집합을 취해 카트에서 빠진 항목은 자동 탈락합니다.
2. `trendRows(…, baselineKeys?: Set<string>)`. 주어지면 recipe 별 `centres` 를
   기준 항목만으로 계산합니다. recipe 당 기준이 2건 미만이면 limits 는 null
   이고 "기준 표본 부족" 사유를 돌려줍니다. 기준 항목 자신은 `out` 판정에서
   빠지고 `role: 'baseline'` 으로 표시됩니다.
3. `MeasurementList.vue` 에 "기준" `sk-chip`, `KpiStrip` 의 "관리선 밖"은
   대상만 집계, `TrendChart` 범례에 "기준 n건 고정". 기준이 비면 지금 동작.

**테스트** (`afmTrend.test.ts`). 기준 2건을 고정한 뒤 대상을 더해도 limits 가
불변, 기준 1건이면 null, recipe 별 분리.

**브라우저 확인.** mock 으로 기준 지정 → 측정 추가 → 선 유지, 새로고침 유지.

**순서.** AFM 사내 어댑터가 쓰이기 시작한 뒤에 합니다. 그 전에 만들면 코드는
남지만 엔지니어는 mock 위의 기준선을 볼 뿐입니다.

## 동반 항목 (각 S)

### 장비 목록 → H/W 링크 교체

- 지금: `ToolInventoryView.vue:242-245` `goToHardware` 가
  `setSelectedTool(eqpId)` 로 `stores/navigation.ts` 를 바꾼 뒤 `props.fabs` 의
  세그먼트로 `/hardware` 에 갑니다. 그 상태를 쓰는 곳은 이 한 줄, 읽는 곳은
  `HardwareView.vue:49, 97-102` 뿐입니다. H/W 는 `?eqp_id=`(그리고 `start`,
  `end`)를 setup 에서 한 번 읽습니다(:59-87). fab 은 경로 세그먼트, 계열은
  `toolType` prop 에서 옵니다.
- 변경: `utils/hardwareLinks.ts` 에 `hardwareRoute(toolType, fabName, eqpId)`
  (`buildFabSegment` 재사용)와 테스트. 버튼을 `:to` 로 바꾸고(같은 파일 159줄의
  `skewvoirSearchRoute` 호출이 본보기), `HardwareView` 의 store 읽기·지우기와
  `navigation.ts` 의 `selectedToolId`·`setSelectedTool` 을 지웁니다.
- fab 은 행의 `fab_name` 으로 보냅니다(브레인스톰 1.5절). 같은 fab 안의
  중복 id 는 mock 산물이고 사내는 고유하며(`HardwareView.vue:173-179` 주석),
  경로에 fab 이 있으므로 모호 표시 UI 는 두지 않습니다. 브레인스톰의 "모호하다고
  보여야" 문장은 fab 없이 넘길 때의 조건이었고, fab 을 경로에 실으면 해소됩니다.
- 브라우저: 새 탭, 새로고침 후 같은 장비, 뒤로 가기, 다중 fab 선택 상태에서
  다른 fab 행 클릭.

### S16. 디바이스 통계 스텝 → 열어보기

- 지금: 스텝 행은 `components/cdsem/comparison/StepOutlierCard.vue` 의
  `RecipeInfoRow`(`recipe_id`, `fac_id`, `oper_desc`, …). 링크가 없고 머리가
  펼치기 클릭이라 `@click.stop` 이 필요합니다. `recipe_id` 가 `full_name` 과
  같은 값임은 `docs/datatables/hitachi/planstep_r3.txt` 가 확인합니다.
- 변경: `recipe_id` 에 `NuxtLink`, `:to` 는 `recipeDetailRoute('cd-sem',
  step.fac_id, 'open', step.recipe_id, 'redis', step.fac_id)`.
  `recipeView.test.ts` 에 `/` 가 든 `recipe_id` 왕복을 더합니다.
- **결정 필요.** R3 는 `fac_id == fab_name` 이라 그대로 되지만, M-fab 은
  `fac_id` 가 M16 처럼 거친 값이고 상세 화면은 M16A/B/C 를 원합니다. 매퍼가
  없으므로 (가) M-fab 은 `fab_name` 없이 보내 사이드바 primaryFab 폴백에
  맡기거나, (나) M-fab 에서는 링크를 숨깁니다. 디바이스 통계가 지금 R3 만
  다루므로 (나)로 시작해도 잃는 것이 없습니다.

### S10. 스토리지 두 관측 시각

- 지금: `useStorageApi.ts:3-17` 에 `storage_mt`(용량 관측, null 가능),
  `rcp_counts_mt`(recipe 수 관측, ISO, 사용처 없음). `StorageView.vue:192-207` 의
  Recipes 열에는 시각이 없고 Last Reported 열은 `storage_mt` 만 보입니다.
  "안심시키는 종합 표시"는 따로 없고 가장 가까운 것이 MetaBar 의 Healthy 수치
  (`summary`, :515-551)입니다.
- 변경: Recipes 셀 아래 `sk-meta` 로 `rcp_counts_mt` 시각. 두 시각의 날짜가
  다르면 행에 `--sk-warn` 점과 툴팁. Healthy 는 두 시각이 같은 날인 행만 세고,
  아닌 행은 "확인 필요"로 뺍니다. 나이 계산은 `utils/relativeTime.ts` 재사용.

### S11. TTTM 양산 recipe 중복도

- 지금: `useTttmApi.ts:57-61` `ProductionCorroboration { level, note, detail:
  { pair: "EQP01·EQP02", overlap: 0..1 }[] }`, 어느 컴포넌트도 쓰지 않습니다.
  사내는 recipe 집합의 Jaccard 상위 3쌍(`office_example.py:810-849`), mock 은
  `mid` 고정에 bias 기반의 가짜 상관(`mock.py:438-458`, docstring 에 적혀
  있음).
- 변경: `utils/tttmGrouping.ts` 에 `pairOverlap(detail, a, b)`(`·` 로 분리)와
  테스트. `tttm/PairMatrix.vue` 셀 툴팁과 `RecommendationCard.vue` 에 "양산
  recipe 중복도 0.62 (Jaccard, 상위 3쌍만 제공)" 를 적고, "TTTM 판정 미반영"
  을 그대로 보입니다. 측정값 분포가 맞는다는 뜻으로 읽히지 않게 "recipe 집합"
  이라고 씁니다.

## 그다음 큰 과제

S9 H/W 정비 전후 비교는 브레인스톰 2.3절 그대로 다음 과제입니다. 이번 목록이
끝난 뒤 다시 계획합니다. 조건(계열·FAB 범위 명시, 같은 길이의 완결 구간,
`down_dt` → `equp_dt`)은 그 문서에 있습니다.

## 사용자 결정이 필요한 것

1. **S16 의 M-fab.** 위 (가)/(나). 권장은 (나).
2. **S6 의 시점.** AFM 사내 어댑터 뒤로 미루는 데 동의하는지. 어댑터 작업과
   한 묶음으로 가는 것도 됩니다.
3. **2묶음의 순서.** 1묶음 확인 뒤 S1 → S7 → S13 → S8 을 그대로 갈지, 확인
   결과로 바꿀지.
