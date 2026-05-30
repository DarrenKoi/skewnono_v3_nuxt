# 계측 룰 — 진행 요약 & 다음 단계

이 문서는 ground_rules grilling 세션의 **요약 + 핸드오프**입니다. 상세는 같은 폴더의
`grilling-log.md`(결정 로그) · `rule-editor-structure.md`(구현 설계) · `adr-0004-open-rule-editing.md`(권한 ADR) 참조.

## 한 줄 요약

`ground_rules.txt`의 계측 Ground Rule 을, **인증된 엔지니어 누구나 시각적으로 편집·모니터링**하는
web 기능으로 옮기기 위한 룰 모델·데이터 계약·프론트 구조를 확정하고, 순수 룰 엔진(step 1)을 구현·검증했습니다.

## 목표 (north star)

> 계측 룰을 **시각적으로 잘 표현**해서, 누구나 쉽게 **(1) 룰을 바꾸고 (2) 준수 상태를 모니터링**하게 한다.

## 확정된 결정 (D1–D15)

D1–D4 는 이전 세션, **D5–D15 가 이번 세션** 확정입니다 (전체 근거는 `grilling-log.md`).

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

- [x] **1. `ruleEngine.ts` + 단위 테스트** — 완료·검증 (`npm test` → 13 pass, strict typecheck clean)
- [ ] **2. `rules.py` seed + GET `/rules` + `useMeasurementRulesApi.fetchRules` → 읽기전용 매트릭스** ← 다음
- [ ] 3. `RuleCapCell` 인라인 편집 + PUT `/rules`
- [ ] 4. 모니터 오버레이 + `UnassignedBucket` — `useLotHealthMock` 대체
- [ ] 5. `RuleHistoryPanel` + history/rollback

## 다음 단계 (step 2) 상세

채택안: 변형 **A(매트릭스)**, 라우트 `pages/ebeam/cd-sem/device-statistics/measurement-rules.vue`.

1. **백엔드** `back_dev_home/ebeam/cdsem/device_statistics/rules.py` — `RuleCell` seed(D8 전체 cap 표 + M-fab DRAM/NAND)
   + `get_rules(fab)`. `routes.py` 에 `GET /cdsem/device-statistics/rules?fab=` 등록.
2. **composable** `useMeasurementRulesApi.ts` — `fetchRules(fab)` (`$fetch` + `joinApiPath`, `useAsyncData` 캐시).
3. **프론트** `MeasurementRulesView.vue` + `RuleMatrix`/`RuleRow`/`RuleCapCell`(읽기전용 먼저) + `RuleFabSelector`.
   매트릭스 렌더는 `ruleEngine` 타입 재사용. M-fab 이면 family/phase 축 숨김(D15).

## 미해결 / 향후

- `useLotHealthMock.ts` 는 옛 모델 — step 4 에서 `ruleEngine` 으로 교체(마이그레이션, greenfield 아님).
- 백엔드 `recipe-params` 데이터셋(파라미터 raw 행, D1)·`annotations` 데이터셋 mock 필요 — 모니터링(step 4) 전제.
- 신호등 색 threshold(10/20%)는 provisional — 사용자 합의 시 조정.
