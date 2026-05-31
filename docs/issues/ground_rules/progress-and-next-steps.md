# 계측 룰 — 진행 요약 & 다음 단계

> _as of 2026-05-31_ · **살아있는 통합본** — 늘 "지금의 결론"만 담도록 매 세션 덮어씁니다.
> 날짜별 도출 과정은 `grilling-log.md`(append-only 저널)를 보세요.

이 문서는 ground_rules grilling 세션의 **요약 + 핸드오프**입니다. 상세는 같은 폴더의
`grilling-log.md`(결정 로그) · `rule-editor-structure.md`(구현 설계) · `adr-0004-open-rule-editing.md`(권한 ADR) 참조.

## 한 줄 요약

`ground_rules.txt`의 계측 Ground Rule 을, **인증된 엔지니어 누구나 시각적으로 편집·모니터링**하는
web 기능으로 옮기기 위한 룰 모델·데이터 계약·프론트 구조를 확정하고, 순수 룰 엔진(step 1)을 구현·검증했습니다.

## 목표 (north star)

> 계측 룰을 **시각적으로 잘 표현**해서, 누구나 쉽게 **(1) 룰을 바꾸고 (2) 준수 상태를 모니터링**하게 한다.

## 확정된 결정 (D1–D15)

D1–D4(이전 세션) · **D5–D15(2026-05-30)** · **D16–D18(2026-05-31, 모니터링·신호등)** (전체 근거는 `grilling-log.md`).

| # | 결정 |
| --- | --- |
| D1 | 룰 입력은 파라미터 단위 raw 데이터(`{name, point_count}`). 옛 `para_N` bin 폐기 |
| D2 | recipe_class(Main/Sample/추가계측) 분기, Main·Sample 만 검증 |
| D3 | 룰 축 = Product Family + Phase (직교) |
| D4 | 수동 어노테이션 = lot 단위 (memory_class, yield_check_state) |
| **D5** | 컴플라이언스 = 단일 상한 `≤`. **과소측정은 위반 아님** (비대화 억제가 목적) |
| **D6** | Sample 룰 완전 명세 + **이름 오버라이드 레이어**(기타 파라 전용) |
| **D7** | memory_class: DRAM→DRAM, NAND·FLASH→NAND, **Tech·Advanced→수동**, VG·RTC·Cubic→잠정 DRAM-side |
| **D8** | Main 키잉이 family마다 다름 — **Core=phase, Pool=yield_check** (균일 그리드 폐기) |
| **D9** | cap 해석: **type 우선**, name-override 는 기타 파라에만 |
| **D10** | `derive_type` = longest-prefix(EDGE_EX>EDGE>WAFER>LEVEL), 접미 허용, Class-독립 + 총파라수 투명성 신호 |
| **D11** | RuleCell = `selector + caps + name_overrides` |
| **D12** | 룰·어노테이션 **전 엔지니어 개방** (SSO 추적 + 이력 + rollback) → ADR 0003 supersede |
| **D13** | UI = 편집 가능 매트릭스 (편집 + 모니터링 겸용) |
| **D14** | 모니터링 = lot→recipe→parameter cascade, 회색 2종(룰미정/미분류) 보수적 비위반 |
| **D15** | M-fab = `recipe_class × memory_class` (family·phase·Pool 없음); 라우트 confirmed |
| **D16** | 신호등 threshold = fab별 `RuleVersion` 의 공유 필드(`yellow_at`/`red_at`); 프론트 편집·버전, **개인 오버라이드 없음** |
| **D17** | 모니터링 = **단일 composable `useMeasurementMonitor`** 가 두 화면 먹임; **적용(local 재계산) ≠ 저장(새 버전)** 분리, what-if 는 명시적 트리거 |
| **D18** | 신호등은 합의 후 **고정** — threshold 는 what-if 제외(양쪽 화면 저장본), what-if/적용은 **cap 에만**. threshold 는 편집 가능하되 거의 안 바꿈 |
| **D19** | Sample **Core TV·PV 만 EDGE 16** (ground_rules.txt L40, memory-blind) — D6 의 "phase 공통" 부분 supersede. seed 에서 phase-blind Sample 앞에 둬 first-match 우선 (step 2 리뷰서 발견) |

열린 질문 Q1–Q8 **전부 해소**.

## 산출물 (이번 세션)

| 파일 | 내용 |
| --- | --- |
| `docs/issues/ground_rules/grilling-log.md` | 결정 로그(D5–D15) + Q1–Q8 해소 기록 |
| `docs/issues/ground_rules/rule-editor-structure.md` | 데이터 모델·컴포넌트·composable·백엔드·**데이터 계약(§8-bis)**·빌드 순서 |
| `docs/issues/ground_rules/adr-0004-open-rule-editing.md` | 편집 권한 ADR (ADR 0003 supersede) |
| `docs/issues/ground_rules/rule-dashboard.prototype.html` | UI 프로토타입 3변형 (A 매트릭스 채택) |
| `front-dev-home/app/utils/ruleEngine.ts` | 순수 룰 엔진 (D1–D15) |
| `front-dev-home/app/utils/ruleEngine.test.ts` | 단위 테스트 13개 (전부 통과) |
| `CONTEXT.md`, `docs/adr/0003` | 신규 모델로 동기화 (admin-only/para_N/stage 서술 갱신) |

## 구현 진행 (`rule-editor-structure.md §8`)

- [x] **1. `ruleEngine.ts` + 단위 테스트** — 완료·검증 + **robustness pass** (Codex 리뷰).
  `npm test` → **26 pass**, `ruleEngine.ts` strict typecheck clean. 리뷰로 잡은 것:
  **(a) D15 fab 축 미적용 버그** — `selectorMatches`/`resolveRuleCell` 가 `selector.fab`↔`fac_id` 를
  검사 안 해 fab 간 룰 오매칭 가능 → 수정 + cross-fab 테스트.
  **(b) D16–D18 threshold 하드코딩** — `classifyHealth(ratio, thresholds=SEED)` · `evaluateLot(…, thresholds)`
  로 주입화(seed 0.1/0.2), `Thresholds` 타입·`SEED_THRESHOLDS` 추가. (엔진이 D15→D18 로 따라잡음.)
  **(c) D7 VG·RTC·Cubic → DRAM-side fallback** 을 `applyAnnotation` 에 추가(수동·auto 우선).
  **(d)** `deriveType`/`matchName` null 가드. **(e)** 누락 테스트 보강(NAND·Core TV/PV·Pool yield_check·
  Sample 매트릭스·`≤`/cap0 경계·TV phase·Gray-B yield).
- [x] **2. `rules.py` seed + GET `/rules` + `useMeasurementRulesApi.fetchRules` → 읽기전용 매트릭스** —
  완료·검증 (`/code-review` + `codex:rescue` 리뷰 reconcile). 산출: `rules.py`(R3 11셀+M-fab 4셀 seed,
  D8/D6/D15/D16) · `routes.py` `GET /rules?fab=`(400/404 처리) · `useMeasurementRulesApi.fetchRules` ·
  `MeasurementRulesView` + `rules/{Matrix,Row,CapCell,FabSelector}` + 페이지 · `ruleMatrix.ts` ·
  계약 YAML(RuleCell/RuleVersion). 리뷰로 잡은 것: **D19**(Sample Core TV·PV EDGE 16, 위 표) +
  `Selector` 필수 base 분리(fab 누락 방지) + `_sample_cell` Literal 타이핑 + `RuleVersion` 을 `ruleEngine.ts`
  로 이동 + Matrix 이름예외 group dedup + 응답 shape 방어 가드. typecheck/eslint clean, 엔진 테스트 27 pass,
  R3/M14 매트릭스 렌더 확인. (남은 LOW: 라우트 provider 예외→500 JSON 변환은 Phase 2/3 때.)
- [ ] 3. `RuleCapCell` 인라인 편집 + PUT `/rules`
- [ ] 4. `useMeasurementMonitor`(§5-bis: 적용/저장 분리, threshold 고정 — D17·D18) + 모니터 오버레이 + `UnassignedBucket` — `useLotHealthMock` 대체
- [ ] 5. `RuleHistoryPanel` + history/rollback

## 다음 단계 (step 2) 상세

채택안: 변형 **A(매트릭스)**, 라우트 `pages/ebeam/cd-sem/device-statistics/measurement-rules.vue`.

1. **백엔드** `back_dev_home/ebeam/cdsem/device_statistics/rules.py` — `RuleCell` seed(D8 전체 cap 표 + M-fab DRAM/NAND)
   + `thresholds` seed(`yellow_at` 0.1 / `red_at` 0.2 — D16) + `get_rules(fab)`. `routes.py` 에 `GET /cdsem/device-statistics/rules?fab=` 등록.
2. **composable** `useMeasurementRulesApi.ts` — `fetchRules(fab)` (`$fetch` + `joinApiPath`, `useAsyncData` 캐시).
3. **프론트** `MeasurementRulesView.vue` + `RuleMatrix`/`RuleRow`/`RuleCapCell`(읽기전용 먼저) + `RuleFabSelector`.
   매트릭스 렌더는 `ruleEngine` 타입 재사용. M-fab 이면 family/phase 축 숨김(D15).

## 미해결 / 향후

- `useLotHealthMock.ts` 는 옛 모델 — step 4 에서 `useMeasurementMonitor`(`ruleEngine` 기반, 구조 설계 §5-bis)로 교체.
  소비처: `device-statistics/comparison.vue` + `LotCards`/`TrendChart`/`StackedBar`/`StageChip`(마이그레이션, greenfield 아님).
- 백엔드 `recipe-params` 데이터셋(파라미터 raw 행, D1)·`annotations` 데이터셋 mock 필요 — 모니터링(step 4) 전제.
- ~~신호등 색 threshold(10/20%) provisional~~ → ✅ **D16·D18 해소**: `RuleVersion.thresholds` 의 편집 가능한
  seed 기본값(10/20%)으로 강등, what-if 제외(합의 후 고정). `classifyHealth(ratio, thresholds)` 로 주입.
