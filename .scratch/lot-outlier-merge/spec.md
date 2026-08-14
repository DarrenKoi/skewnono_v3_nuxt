# Lot 상세 팝업에 outlier 정보 합치기

Status: shipped
작성일: 2026-08-15
브라우저 확인: 2026-08-15 (전체/초과만, 다중 스텝 recipe, CSV 파일명, 다크 모드,
measurement-rules 회귀 포함 — 콘솔 오류·경고 0건)
대상 화면: `/ebeam/cd-sem/device-statistics/comparison` (디바이스 비교) 의 Lot 요약

## 배경

Lot 요약 표에서 한 디바이스를 이해하려면 지금 **두 번 클릭하고 두 오버레이를
오갑니다**.

| 클릭 | 열리는 것 | 보여 주는 것 |
| --- | --- | --- |
| 행·카드 | `CdsemComparisonLotDetailModal` (모달) | 스텝(oper_desc) 카드 — recipe_id, oper_id, samp_seq, para 분포, 추이 |
| outlier 배지 | `EbeamDevstatDrillSlideover` (슬라이드오버) | recipe 목록 — 파라미터별 point_count 와 초과 표시 |

두 목록의 주어는 **같은 lot 의, 같은 버킷 범위의, 같은 recipe 들**입니다.
`comparison.vue` 는 그 사실을 이미 코드로 못박아 두었습니다 — `bucketRecipes`
를 한 번만 좁혀 health·프로파일·drill 이 모두 같은 배열을 받게 합니다
(`comparison.vue:398-427`). 화면만 둘로 갈라져 있습니다.

그래서 "이 디바이스의 어느 스텝·recipe 가 규칙을 어겼는가" 라는 **하나의
질문**에 답하려면 모달을 열어 스텝 이름을 외우고, 닫고, 배지를 눌러 recipe
이름을 대조하는 왕복이 필요합니다. 사용자가 번거롭다고 지적한 지점이 이것입니다.

## 목표

- Lot 상세 모달 **한 곳**에서 스텝·recipe·초과 파라미터를 모두 읽습니다.
- 모달 안에서 **전체 / 초과만** 을 토글합니다. 기본은 전체입니다.
- 표의 outlier 배지는 같은 모달을 **초과만** 상태로 엽니다.
- 초과 판정의 기준선(중앙값·문턱)을 초과 개수와 **같은 화면**에 둡니다.

## 결정 사항

### D1 — 기본은 전체, 토글로 좁힙니다 (user-confirmed 2026-08-15)

모달은 전체 스텝을 공정순으로 보여 주는 것이 기본입니다. 이 목록을 여는 질문이
"이 device 가 공정을 따라가며 무엇을 재는가" 이고, 정렬 기본값이 공정순인 이유도
같습니다 (`recipeStepSort.ts` 주석). 초과만 보기는 그 위에 얹는 필터입니다.

**진입점이 초기 상태를 정합니다.** 행을 눌러 들어오면 `전체`, outlier 배지를
눌러 들어오면 `초과만` — 어느 질문을 하고 들어왔는지 클릭이 이미 말했으므로
화면이 그것을 되풀이해 묻지 않습니다.

### D2 — 카드 축은 스텝, outlier 축은 recipe. 조인 키는 `recipe_id` 입니다

이 스펙에서 가장 조심할 지점입니다.

| | grain | 정체성 |
| --- | --- | --- |
| 모달 카드 (`RecipeInfoRow`) | **스텝** | `recipeStepKey` = `lot_cd/oper_seq/samp_seq` |
| outlier (`RecipeInput` → `DrillRecipe`) | **recipe** | `recipe_id` |

`RecipeInput` 에는 `oper_seq` 가 없습니다. 한 recipe 가 여러 스텝에서 돌아가므로
조인은 **1:N** 입니다 — 같은 `초과 3` 배지가 카드 두 장에 붙는 일이 정상입니다.

그래서 두 가지를 지킵니다.

1. **카드 키는 계속 `recipeStepKey`** 입니다. `recipe_id` 로 키를 바꾸면 Vue 가
   카드를 접어 스텝이 조용히 사라집니다 — 이미 한 번 겪은 버그입니다
   (`recipeStepSort.ts` 의 `recipeStepKey` 주석, "Duplicate keys found").
2. **헤더의 초과 총계는 카드 배지의 합이 아니라 `DeviceOutlierResult.outlier_count`**
   입니다. 카드를 세면 여러 스텝에 걸친 recipe 가 중복 계산됩니다.
3. 한 recipe 가 스텝 두 곳 이상에서 돌면 카드에 `스텝 N곳` 꼬리표를 답니다.
   말해 두지 않으면 같은 숫자가 두 번 보이는 것이 버그로 읽힙니다.

### D3 — `DrillSlideover` 는 지웁니다가 아니라 **호출처 하나를 뗍니다**

`components/ebeam/devstat/DrillSlideover.vue` 에는 호출처가 둘입니다.

| 호출처 | 어댑터 | 성격 |
| --- | --- | --- |
| `comparison.vue:212` | `toOutlierDrill` | 서술 — 디바이스 내 과다 측정 |
| `components/ebeam/rules/ComplianceTable.vue:82` | `toViolationDrill` | 규범 — cap 위반 |

이번 작업은 앞의 하나만 뗍니다. 컴포넌트도 `utils/deviceDrill.ts` 도 그대로
둡니다. `toOutlierDrill` 은 **계속 씁니다** — 모달이 그 산출물(`DrillDevice`)을
받아 그립니다. 이 어댑터에는 `분석 제외` 꼬리표 규칙과
`dropLeadingHelperParams` 정합성이 들어 있고 `utils/deviceDrill.test.ts` 가
지키고 있어서, 모달 안에서 다시 판정하면 그 테스트가 지키던 것이 풀립니다.

### D4 — CSV/클립보드 내보내기는 화면을 따라갑니다

정렬 칩이 파일의 행 순서를 바꾸는 것과 같은 규약입니다
(`LotDetailModal.vue:349-351`). `초과만` 상태에서 내려받으면 초과 recipe 의
행만 나갑니다. 버튼 옆의 `N행` 표시가 이미 있으므로 무엇을 받는지는 화면에
드러납니다. 파일 이름에는 `_flagged` 를 붙여 전체 파일과 섞이지 않게 합니다.

### D5 — `분석 제외` 배지는 반드시 남습니다

CDU 계열·FULL/HALF/MTX job 은 설계상 많이 재므로 초과 판정에서 빠집니다. 아무
표시 없이 큰 숫자만 놓이면 규칙이 고장난 것으로 읽힙니다 — `deviceDrill.ts`
와 `DrillSlideover.vue` 양쪽에 그 이유가 주석으로 남아 있습니다. 모달로 옮길 때
배지와 `title` 문구를 그대로 가져갑니다. 파라미터 층의 `분석 제외`(선두
DUMMY/Align) 도 같습니다.

## 범위 밖 (Non-goals)

- 백엔드 변경. 요청도 payload 도 늘지 않습니다 — 모달은 이미 받아 둔
  `recipeParams` 를 씁니다.
- outlier 판정 로직. `outlierDetect.ts` 의 중앙값·문턱·제외 규칙은 손대지
  않습니다.
- `measurement-rules` 의 `ComplianceTable` 과 그쪽 슬라이드오버.
- `LotTable.vue` 의 배지 마크업. `open-outliers` 이벤트는 이름도 페이로드도
  그대로 두고, 페이지의 **수신부만** 바꿉니다.
- 추이 차트(`TrendChart`) 와 para 분포 막대. 지금 자리 그대로입니다.

## 후속 작업 (이번 브랜치 범위 밖)

**이관됨 (2026-08-15).** 1·3순위는 `.scratch/sk-bad-sweep/` 스펙과 티켓으로
옮겼습니다 — 이 스펙이 `shipped` 라 여기 남겨 두면 스윕 대상에서 빠집니다.
2순위(`exempt` 가지)는 코드 작업이 아니라 룰 데이터 결정 대기라 이관하지
않았습니다. 아래는 판단 근거로 남깁니다.

1. **(1순위) live-live 마크업 중복.** `StepOutlierCard.vue` 와 `DrillSlideover.vue`
   가 초과 배지 클래스와 파라미터 행 마크업 약 25줄을 각자 들고 있습니다.
   `DrillSlideover` 쪽은 `ComplianceTable.vue`(cap 위반 화면)에서 **살아서
   렌더링**되므로 진짜 중복입니다. 한쪽에 넣은 수정이 다른 쪽에 닿지 않는 것은
   이 저장소가 이미 여러 번 겪은 실패 양식입니다. 추출하려면 양쪽이 같은 모듈을
   import 해야 하고, 그러면 이번 브랜치의 브라우저 확인 목록이 다루지 않는
   measurement-rules 화면이 딸려 들어옵니다 — 그래서 미룹니다.
2. **(2순위) 도달 불가능해진 `exempt` 가지.** `deviceDrill.ts` 에서 `exempt` 를
   세팅하는 것은 `toOutlierDrill` 뿐이고 `toViolationDrill` 은 세팅하지 않습니다.
   이번 브랜치가 `toOutlierDrill → DrillSlideover` 경로를 끊었으므로
   `DrillSlideover` 의 `v-if="recipe.exempt"` 배지는 남은 호출처에 대해
   렌더링될 수 없습니다. 죽은 것은 그 템플릿 가지 하나뿐입니다 — `toOutlierDrill`
   어댑터 자체는 모달의 `selectedLotDrill` 이 계속 씁니다. 지우기 전에 판정(cap)이
   CDU/FULL/HALF/MTX job 을 면제해야 하는지를 먼저 결정해야 하는데, 그것은
   룰 데이터의 결정이지 리팩터링이 아닙니다.

3. **(3순위) `LotTable.vue` 의 raw rose outlier 배지.** 모달 쪽 초과 표시는 이번에
   `--sk-bad` 계열로 옮겼지만, 그 모달을 여는 **표의 배지**는 아직
   `bg-rose-100 … dark:bg-rose-950/50` 입니다 (`LotTable.vue` 200행·346행).
   이번 브랜치가 만든 드리프트가 아니라 원래 있던 것이고, 함께 걷어내지 않은
   이유는 **hover 상태에 답이 없기 때문**입니다 — `hover:bg-rose-200` /
   `dark:hover:bg-rose-950/80` 에 대응하는 `--sk-bad` 토큰이 `main.css` 에 없고,
   `DESIGN.md` 규칙 7 은 문서가 먼저 바뀌고 같은 변경에서 `main.css` 가 따라온다고
   못박습니다. 기능 브랜치 끝에서 hover 토큰을 즉흥으로 만드는 것은 디자인
   시스템이 빨강에 대한 네 번째 의견을 얻는 방식입니다. 토큰을 먼저 정한 뒤
   `--sk-bad` 스윕과 함께 처리합니다.

토론 기록은 `docs/opencode/2026-08-15-lot-outlier-merge-duplication-discuss.md`
입니다.

## 완료 조건

1. 표의 행을 누르면 모달이 `전체` 로 열리고, 초과가 있는 스텝 카드에 `초과 N`
   배지가 보입니다.
2. 표의 outlier 배지를 누르면 **같은 모달**이 `초과만` 으로 열립니다.
   슬라이드오버는 이 페이지에서 더 이상 열리지 않습니다.
3. 카드를 펼치면 파라미터 이름 · point_count · 꼬리표(`> N` / `분석 제외`)가
   나옵니다.
4. 모달 헤더에 `중앙값 / 문턱 / 초과 N개` 가 있고, 초과 총계가 표의 배지 숫자와
   같습니다.
5. 한 recipe 가 두 스텝에 걸친 lot 에서 카드가 사라지지 않고, 각 카드에
   `스텝 2곳` 이 붙습니다.
6. `npm test` · `npm run typecheck` · `npm run lint` 통과.
7. `measurement-rules` 의 cap 위반 슬라이드오버는 그대로 동작합니다.

## 검증

자동 E2E 가 없는 저장소이므로 브라우저 확인은 손으로 합니다 (`verify` 스킬).
확인 항목은 `issues/05-browser-verify.md` 에 있습니다.
