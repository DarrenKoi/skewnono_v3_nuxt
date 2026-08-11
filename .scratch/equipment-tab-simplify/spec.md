# 장비별 탭 단순화 + Excel 내보내기

Status: shipped
작성일: 2026-08-11
브라우저 확인: 2026-08-11 (M14A, 세 탭 모두)

## 배경

`recipe-status` 페이지의 세 탭(TAT / Align / Meas)은 각각 장비별 하위 뷰를
가지고 있습니다. 이 뷰는 현재 두 겹으로 되어 있습니다.

1. **관측 레이어** — 어떤 장비가 어떤 레시피를 몇 번 돌았고, 얼마나 걸렸으며
   (또는 몇 번 실패했으며), 그 추이가 어떤지.
2. **판정 레이어** — 간접표준화 지수(`tat_index` / `align_index` /
   `meas_index`), Byar 신뢰구간, 플릿 분위수, 그리고 이 셋을 조합해 다는
   신호 배지(`취약` / `양호` / `저사용` / `편중`).

판정 레이어는 "이 장비가 문제인가"에 답하기 위한 것인데, 장비별 탭에서
실제로 필요한 질문은 그보다 앞선 관측입니다 — **어떤 장비가 어떤 레시피를
많이 측정하고, 그 레시피가 얼마나 걸리는가(또는 얼마나 실패하는가)**.
판정 레이어는 이 질문에 답하지 않으면서 화면의 복잡도 대부분을 차지합니다.

간단한 분석 대시보드에서 출발해 점진적으로 고도화한다는 방향에 따라, 판정
레이어를 **화면에서만** 걷어냅니다. 계산은 백엔드에 그대로 남으므로 고도화
단계에서 배선만 다시 꽂으면 됩니다.

## 목표

- 장비별 탭이 관측만 보여주도록 단순화합니다.
- 장비 간 비교의 요약을 **총 측정 수 / 총 레시피 수**로 통일합니다.
- 장비별 탭의 분석 결과를 시트 3개짜리 `.xlsx` 한 파일로 내보냅니다.

## 범위 밖 (Non-goals)

- 백엔드 변경. `_shape.py`의 지수·구간·분위수 계산, `contracts.py`의 상수,
  관련 테스트는 **손대지 않습니다**. payload 필드도 그대로 내려옵니다.
- 전체 요약 탭·랭킹 표 등 장비별 이외의 화면. 거기서 지수를 쓰고 있다면
  계속 씁니다.
- `utils/equipmentSignals.ts` / `utils/failEquipmentSignals.ts` 파일 삭제.
  순수 함수 + 테스트가 갖춰져 있고 고도화 때 되돌아올 코드이므로 남깁니다.
  이번 변경으로 두 모듈은 장비별 탭에서 호출되지 않게 됩니다.

## A. 플릿 표

### A-1. TAT 탭 — `components/ebeam/RecipeTatFleetTable.vue`

| 유지 | 제거 |
| --- | --- |
| `eqp_id`, `fab`, `model`, `실행수`, `총 TAT`, `평균`, `레시피수` | `점유율`, `TAT index`, `신호` |

`점유율`(`occupancy` = 총 TAT ÷ 조회 기간)을 빼는 이유는 총 TAT 열과 같은
사실을 배율만 바꿔 반복하기 때문입니다.

### A-2. Align/Meas 탭 — `components/ebeam/FailIssueFleetTable.vue`

| 유지 | 제거 |
| --- | --- |
| `eqp_id`, `fab`, `model`, `실행수`, `실패수`, `실패율`, `레시피수` | `fail index`, `신호` |

`실패율`은 남깁니다. 간접표준화가 아니라 실패÷실행이라 열 이름 그대로 읽히고,
"얼마나 fail이 발생하는가"라는 질문에 직접 답합니다.

### A-3. 두 표에 공통으로 딸려 나가는 것

- **다중 fab 경고 배너** (`FailIssueFleetTable.vue`) — 문구가 "신호 배지"와
  "fail index 열"을 설명하는데 둘 다 사라지므로 문장 자체가 거짓이 됩니다.
  제거합니다.
- **사라지는 열의 헤더 툴팁** — Fail 쪽 `FAIL_INDEX_HEADER_TOOLTIP`·
  `FAIL_INDEX_MIXED_FAB_TOOLTIP`, TAT 쪽 `OCCUPANCY_HEADER_TOOLTIP`을 열과
  함께 제거합니다.
- **`percentiles` / `peerGroupComparable` props** — 배지 판정 전용 입력이므로
  뷰→표 배선에서 제거합니다. 뷰(`*EquipmentView.vue`)에서 계산하던
  `isPeerGroupComparable(...)` 호출도 함께 사라집니다.
- **정렬의 null-last 특수 규칙** — nullable 열은 지수뿐이었습니다. 사라지면
  `sortedRows`는 일반 비교로 단순해집니다. 단, `MANUAL_SORTING_OPTIONS`
  (`manualSorting`)는 **그대로 둡니다** — 이 표가 자기 행을 스스로 정렬한다는
  사실은 지수와 무관합니다.
- **정렬 가능 열 목록** — 사라진 열을 뺍니다. 기본 정렬은 TAT이
  `total_meastime` 내림차순, Fail이 `fail_count` 내림차순으로 유지합니다.

## B. 선택 요약 칩

두 탭의 칩을 같은 문법으로 맞춥니다.

```text
TAT        :  ● TP-1203   측정 430 · 레시피 12 · 총 2h 14m
Align/Meas :  ● TP-1203   측정 430 · 레시피 12 · 실패 12
```

- `측정` = `exec_count`, `레시피` = `recipe_count`.
- 세 번째 항목만 탭별 관심사입니다(TAT은 `total_meastime`, Fail은 활성 축의
  실패 건수).
- Fail 칩에는 지금 `recipe_count`가 없고 실패율이 대신 들어 있습니다. 실패율은
  플릿 표에 이미 열로 있으므로 칩에서는 레시피 수에 자리를 내줍니다.

칩은 지금과 같이 플릿 표에서 받은 행(props)으로 계산하므로 compare 요청과
무관하게 즉시 맞고, 로딩 바깥에 남습니다.

## C. 비교 패널

변경 없습니다.

- 일별 트렌드 차트 — 유지. 차트 종류 토글도 그대로입니다.
- 레시피 구성 매트릭스 — 유지. 셀 표기도 그대로입니다
  (TAT `430 · 2h 14m`, Fail `12/430 (2.79%)`, 실행 0인 칸은 `—`).
- 페이지네이션(25행) — 유지.

바뀌는 것은 내보내기 버튼뿐입니다(D절).

## D. Excel 내보내기

### D-1. 무엇이 나오는가

장비별 탭 하나당 `.xlsx` 파일 하나, 시트 3개입니다.

| 시트 | 내용 | 출처 |
| --- | --- | --- |
| `장비` | 플릿 표의 전체 행. 화면과 같은 열 | equipments 응답 |
| `레시피` | 선택 장비 × 레시피 매트릭스. 장비마다 원시 열로 분해 | compare 응답 `recipes` |
| `일별추이` | 날짜 × 장비. 트렌드 차트의 원본 수치 | compare 응답 `trends` |

`일별추이`는 현재 어디서도 내보낼 수 없는 데이터입니다 — 차트로만 존재합니다.

값은 화면 표기(`1h 12m`, `62.1%`)가 아니라 **원시 수치**로 냅니다. 스프레드시트로
가는 값은 다시 계산될 것이므로 사람이 읽기 좋은 포맷은 손해입니다. 대신 열
이름에 단위를 박습니다(`total_meastime_sec`, `fail_rate_pct`). 기존 CSV
내보내기가 쓰던 규칙 그대로입니다.

`레시피` 시트는 화면이 한 칸에 합쳐 보여주는 값을 장비마다 열로 풉니다.

- TAT: `<eqp>_meas_counts`, `<eqp>_total_meastime_sec`, `<eqp>_avg_meastime_sec`
- Fail: `<eqp>_exec_count`, `<eqp>_<축>_fail_count`, `<eqp>_<축>_fail_rate_pct`

돌지 않은 장비 칸은 건수 `0`, 비율은 **빈 칸**입니다. 비율을 0으로 채우면
"돌았는데 한 번도 실패하지 않았다"로 읽힙니다.

축(align/meas)은 화면에 보이는 활성 축만 냅니다.

### D-2. 버튼

플릿 표와 레시피 매트릭스의 **CSV 버튼 2개를 제거**하고, 장비별 탭 상단에
`Excel` 버튼 하나를 둡니다. 클립보드 복사 버튼은 남깁니다 — 표 하나를 빨리
붙여넣는 용도라 성격이 다릅니다.

장비가 선택되지 않은 상태에서는 compare 응답이 없으므로 `장비` 시트만
내보냅니다. 버튼은 플릿 행이 하나도 없을 때만 비활성입니다.

파일명은 기존 CSV 규칙을 따릅니다:
`<toolType>-<fab>-recipe-tat-equipments-<YYYYMMDD>.xlsx`
(Fail은 `-fail-issue-equipments-<축>-`).

### D-3. 코드 배치

이 저장소에는 확립된 패턴이 있습니다: **순수 빌더가
`{ sheets: [{ name, rows }] }`를 만들고**, 별도 다운로더가
`await import('exceljs')`로 동적 로드해 씁니다
(`utils/recipeCompare.ts`, `utils/recipeParamExport.ts`).

프론트 테스트가 `node --test`뿐이라 Nuxt 런타임이 없다는 사실이 이 경계를
강제합니다 — exceljs를 import하는 코드는 테스트할 수 없고, 행 배열을 만드는
코드는 테스트할 수 있습니다.

새 파일:

- `utils/equipmentExport.ts` — 순수 빌더. `buildTatEquipmentWorkbook(...)`,
  `buildFailEquipmentWorkbook(...)`. 응답 payload를 받아 `sheets`를 냅니다.
- `utils/equipmentExport.test.ts` — 시트 이름·헤더·0채움·빈 비율 칸·활성 축
  반영을 검증합니다.
- `utils/xlsx.ts` — `downloadWorkbook(filename, sheets)`. 세 번째 사용처가
  생기는 시점이므로 `recipeCompare.ts`·`recipeParamExport.ts`에 복제돼 있는
  `await import('exceljs')` 부트스트랩을 여기로 뽑습니다.

기존 두 호출자는 이미지 삽입·열 너비 같은 자기 로직이 있으므로 **부트스트랩
호출만 갈아끼우고 나머지 동작은 바꾸지 않습니다**. 이 두 파일의 기존 테스트가
그대로 통과해야 합니다.

## 영향받는 파일

| 파일 | 변경 |
| --- | --- |
| `components/ebeam/RecipeTatFleetTable.vue` | 열 3개·props 2개·정렬 규칙 제거 |
| `components/ebeam/FailIssueFleetTable.vue` | 열 2개·props 2개·배너·툴팁·정렬 규칙 제거 |
| `components/ebeam/RecipeTatEquipmentView.vue` | 배지 배선 제거, CSV → Excel |
| `components/ebeam/FailIssueEquipmentView.vue` | 동일 |
| `components/ebeam/RecipeTatEquipmentCompare.vue` | 칩 문법 통일, CSV 버튼 제거 |
| `components/ebeam/FailIssueEquipmentCompare.vue` | 동일 |
| `utils/equipmentExport.ts` (신규) | 순수 워크북 빌더 |
| `utils/equipmentExport.test.ts` (신규) | 빌더 테스트 |
| `utils/xlsx.ts` (신규) | 공용 exceljs 다운로더 |
| `utils/recipeCompare.ts` | 다운로더 부트스트랩만 교체 |
| `utils/recipeParamExport.ts` | 다운로더 부트스트랩만 교체 |

## 검증

- `npm test` — 신규 빌더 테스트 통과, `recipeCompare`·`recipeParamExport`
  기존 테스트 무회귀.
- `npm run typecheck`, `npm run lint` 통과.
- `equipmentSignals.test.ts` / `failEquipmentSignals.test.ts`는 **계속
  통과해야 합니다**. 파일을 남기기로 했으므로 깨진다면 그것은 이 변경이
  의도보다 멀리 갔다는 신호입니다.
- 브라우저 확인(`verify` 스킬): 세 탭 각각에서 표에 지수·배지가 없는지,
  장비 2대 이상 선택 시 칩·차트·매트릭스가 뜨는지, Excel 파일이 시트 3개로
  열리고 `일별추이`의 날짜 수가 조회 기간과 같은지.

### 브라우저 확인 결과 (2026-08-11, cd-sem / M14A)

`npm test` 1373/1373, typecheck·lint 통과. 콘솔 에러 0건.

| 확인 | 결과 |
| --- | --- |
| TAT 표 열 | `eqp_id·fab·model·실행수·총 TAT·평균·레시피수` — 점유율·TAT index·신호 없음 |
| Align 표 열 | `…·align fail·fail율·레시피수` — fail index·신호 없음 |
| Meas 표 열 | `…·meas fail·fail율·레시피수` |
| 다중 fab 배너 | 없음 |
| 내보내기 버튼 | 탭당 `Excel` 하나, CSV 0개 |
| 요약 칩 | `측정 29 · 레시피 18 · 총 8.37h` / `… · 실패 12` |
| 매트릭스 | 미실행 칸 `—` 렌더 확인 |
| 워크북 | 장비 2대 선택 시 시트 3개, 선택 해제 시 시트 1개 |
| 파일명 | `cd-sem-m14a-recipe-tat-equipments-<날짜>.xlsx` / `…-fail-issue-equipments-meas-<날짜>.xlsx` |

기존 내보내기 무회귀: `createWorkbook`·`writeWorkbook`은 위 다운로드가
실제로 통과시킨 경로이며, `recipeCompare`·`recipeParamExport`는 이 두 함수만
갈아끼웠고 시트별 후처리는 그대로입니다.

## 열린 질문

최종 리뷰가 남긴 제품 판단 2건입니다. 결함이 아니라 정책 선택이라 그대로
출하했습니다.

1. 표에서 검색으로 행을 걸러낸 상태로 Excel을 누르면 `장비` 시트만 필터를
   반영하고 `레시피`·`일별추이`는 선택한 장비 전체를 담습니다. "내보내기는
   화면에 보이는 것을 낸다"는 기존 계약을 따른 결과입니다.
2. `장비` 시트는 `exec_count`가 0인 행의 평균·비율을 빈 칸이 아니라 0으로
   냅니다(`레시피` 시트는 빈 칸). 화면 표기와는 일치합니다.
