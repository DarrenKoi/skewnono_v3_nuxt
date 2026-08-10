# 장비별 탭 단순화 + Excel 내보내기 구현 계획

> **에이전트 작업자에게:** 이 계획은 `superpowers:subagent-driven-development`
> 또는 `superpowers:executing-plans`로 티켓 단위로 실행합니다. 각 티켓은
> `.scratch/equipment-tab-simplify/issues/NN-*.md` 에 있고, 단계는 체크박스
> (`- [ ]`)로 되어 있습니다.

**목표:** `recipe-status`의 장비별 탭에서 판정 레이어(지수·신뢰구간·분위수·
신호 배지)를 화면에서 걷어내고, 관측만 남긴 뒤, 탭의 결과를 시트 3개짜리
`.xlsx` 한 파일로 내보냅니다.

**스펙:** [`spec.md`](spec.md)

**아키텍처:** 백엔드는 손대지 않습니다 — payload는 지금 그대로 내려오고
프론트가 판정 필드를 읽지 않게 될 뿐입니다. 내보내기는 이 저장소의 기존
패턴을 따릅니다: **순수 빌더**가 `{ name, rows }[]`를 만들고(`node --test`로
검증), **다운로더**가 `await import('exceljs')`로 그 배열을 파일로 씁니다.
세 번째 내보내기가 생기는 시점이므로 다운로더는 `utils/xlsx.ts`로 한 번만
둡니다.

**기술 스택:** Nuxt 4 + NuxtUI, TypeScript, `exceljs@^4.4.0`(이미 의존성),
테스트는 `node --test`.

## 전역 제약

- **백엔드 무변경.** `back_dev_home/**`는 이 작업에서 한 줄도 바뀌지 않습니다.
- **`utils/equipmentSignals.ts` / `utils/failEquipmentSignals.ts` 삭제 금지.**
  두 파일과 그 테스트는 그대로 통과해야 합니다. 장비별 탭에서 호출되지 않게
  될 뿐입니다.
- **`node --test`에는 Nuxt 런타임이 없습니다.** `utils/`에서 값 import는
  상대 `.ts` 경로로, 타입 import만 `~/` 별칭으로 씁니다
  (`utils/recipeCompare.ts` 머리말의 근거를 따릅니다).
- **auto-import 이름 중복 금지.** `utils/`의 export는 전역 이름이 됩니다. 새
  export를 추가하기 전에 `grep`으로 같은 이름이 없는지 확인하고, 재수출로
  같은 함수에 이름을 둘 만들지 않습니다.
- **내보내는 값은 원시 수치.** 화면 표기(`1h 12m`, `62.1%`)가 아니라 숫자로
  내고, 단위는 열 이름에 박습니다(`_sec`, `_pct`).
- 커밋은 **직접 편집한 파일만 명시적 경로로** 스테이징합니다
  (`git add <정확한 경로>`). `git add -A`/`git add .` 금지.
- 작업 트리는 `git worktree`로 분리합니다 — 이 작업은 파일 여러 개를
  건드립니다.

## 파일 구조

| 파일 | 책임 |
| --- | --- |
| `app/utils/xlsx.ts` (신규) | exceljs 부트스트랩 + 파일 쓰기. 행을 만드는 로직은 두지 않습니다 — 테스트할 수 없는 코드만 모으는 자리입니다. |
| `app/utils/equipmentExport.ts` (신규) | 장비별 탭의 워크북 빌더. 순수 함수 2개(TAT/Fail). |
| `app/utils/equipmentExport.test.ts` (신규) | 위 빌더의 테스트. |
| `app/utils/recipeCompare.ts` | `WorkbookSheet`를 `xlsx.ts`로 넘기고 부트스트랩만 교체. 나머지 동작 불변. |
| `app/utils/recipeParamExport.ts` | 부트스트랩만 교체. 나머지 동작 불변. |
| `app/components/ebeam/RecipeTatFleetTable.vue` | 열 3개·props 2개·정렬 특례 제거, CSV → Excel 버튼. |
| `app/components/ebeam/FailIssueFleetTable.vue` | 열 2개·props 2개·배너·툴팁·정렬 특례 제거, CSV → Excel 버튼. |
| `app/components/ebeam/RecipeTatEquipmentView.vue` | 배지 배선 제거, 워크북 조립·다운로드. |
| `app/components/ebeam/FailIssueEquipmentView.vue` | 동일. |
| `app/components/ebeam/RecipeTatEquipmentCompare.vue` | 칩 문법 통일, compare payload 위로 emit, 매트릭스 CSV 버튼 제거. |
| `app/components/ebeam/FailIssueEquipmentCompare.vue` | 동일. |

**compare payload가 위로 올라가는 이유:** 통합 워크북은 플릿 행(View가 가짐)과
compare 응답(Compare가 fetch함)을 한 파일에 담아야 합니다. 캐시 키를 View가
다시 조립해 `useNuxtData`로 훔쳐보는 방법도 있지만, 그러면 키 문자열이 두 곳에
살게 되고 한쪽이 바뀌면 조용히 빈 시트가 나옵니다. `@loaded` emit은 배선이
눈에 보이고 타입이 붙습니다.

## 티켓

| # | 티켓 | 산출물 |
| --- | --- | --- |
| 01 | [`01-xlsx-downloader.md`](issues/01-xlsx-downloader.md) | `utils/xlsx.ts` + 기존 두 내보내기 재배선 |
| 02 | [`02-tat-workbook-builder.md`](issues/02-tat-workbook-builder.md) | `buildTatEquipmentWorkbook` + 테스트 |
| 03 | [`03-fail-workbook-builder.md`](issues/03-fail-workbook-builder.md) | `buildFailEquipmentWorkbook` + 테스트 |
| 04 | [`04-tat-equipment-tab.md`](issues/04-tat-equipment-tab.md) | TAT 장비별 탭 전체(단순화 + 칩 + Excel) |
| 05 | [`05-fail-equipment-tab.md`](issues/05-fail-equipment-tab.md) | Align/Meas 장비별 탭 전체 |
| 06 | [`06-browser-verify.md`](issues/06-browser-verify.md) | 브라우저 검증 + 스펙 상태 갱신 |

01 → 02·03 → 04·05 → 06 순서입니다. 02와 03은 서로 독립이고, 04는 02에,
05는 03에 의존합니다.
