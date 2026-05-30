# 계측 룰 편집 프론트엔드 구조

본 문서는 grilling 결정 **D1–D14**(`grilling-log.md`)를 구현 가능한 프론트엔드 구조로 옮긴 설계입니다.
목표는 "인증된 엔지니어 누구나 룰을 **시각적으로 편집**하고 **모니터링**하는 surface"입니다.

## 1. 대체 대상 (greenfield 아님)

| 기존 (old model) | 신규 (D1–D14) |
| --- | --- |
| `useLotHealthMock.ts` 의 `RuleCaps {para_16/13/9/5_max}` | type 기반 `RuleCaps {WAFER/LEVEL/EDGE/EDGE_EX/_other}` + `name_overrides` |
| `DevStage = EV/TV/PV/Pool` 단일 축 | `family` + `phase`/`yield_check` selector (D8) |
| `extractStage(ctn_desc)` | `deriveFamily` + `derivePhase` + `deriveMemoryClass` (D7) |
| `getCaps(facId, stage, bucket)` | `resolveRuleCell(recipe)` → `capFor(param, cell)` (D9) |
| `SummaryRow` 의 `para_N` 집계 | recipe 당 파라미터 행 `{name, point_count}` (D1) |

`useLotHealthMock.ts` 는 신규 엔진으로 교체되며, 기존 `classifyHealth(violation_ratio)` 는 재사용합니다
(단 `violation_ratio` 의 의미가 "cap 카테고리 4개 중 위반 수"에서 **"lot 내 위반 recipe 수 / 전체 recipe 수"**(D14)로 바뀝니다).

## 2. 데이터 모델 (TypeScript)

```ts
type RecipeClass = 'Main' | 'Sample'
type Family      = 'Core' | 'Pool' | 'VG_RTC_Cubic'
type Phase       = 't-EV' | 'EV' | 'TV' | 'PV'
type MemoryClass = 'DRAM' | 'NAND'
type ParamType   = 'WAFER' | 'LEVEL' | 'EDGE' | 'EDGE_EX' | 'OTHER'

interface NameOverride {     // 기타(OTHER) 파라 전용 보조 규칙 (D9)
  patterns: string[]         // 예: ['DSPT','WF','WAFER']
  match: 'contains' | 'affix'
  cap: number | null         // null = 면제(무제한), Sample 의 WAFER/WF 케이스
}

interface RuleCell {
  id: string
  selector: {
    fab: string              // 'R3' | 'M11' | ...
    recipe_class: RecipeClass
    family?: Family          // Main 에서만
    phase_in?: Phase[]       // Core 가 사용 (D8)
    yield_check?: 'before' | 'after'   // Pool 이 사용 (D8)
    memory_class?: MemoryClass         // EDGE/EDGE_EX 분기 셀만 (D11)
  }
  caps: Partial<Record<Exclude<ParamType,'OTHER'>, number>> & { _other: number }
  name_overrides: NameOverride[]
}

interface RuleVersion {      // D12 — append-only 이력 + rollback
  version: number
  cells: RuleCell[]
  author: string             // SSO 신원
  edited_at: string          // ISO8601
  note?: string              // 변경 사유 (운영 practice)
}
```

## 3. 파생 + 판정 로직 (`utils/ruleEngine.ts`)

| 함수 | 입력 → 출력 | 결정 |
| --- | --- | --- |
| `deriveFamily(ctn_desc)` | string → `Family` | D3 (VG·RTC·Cubic > Pool > Core) |
| `derivePhase(ctn_desc)` | string → `Phase \| null` | D3 (없으면 strict fallback) |
| `deriveMemoryClass(prod_catg_cd)` | string → `MemoryClass \| 'unknown'` | D7 (Tech·Advanced → unknown) |
| `deriveType(name)` | string → `ParamType` | D10 longest-prefix `[EDGE_EX,EDGE,WAFER,LEVEL]` |
| `resolveRuleCell(recipe, rules)` | recipe + 어노테이션 → `RuleCell \| Gray` | D8 selector 매칭 |
| `capFor(param, cell)` | `{name,point_count}` + cell → number\|null | D9 알고리즘 |
| `evaluateRecipe(recipe, cell)` | → `{total, violations[]}` | D5 `≤`, D14 집계 |

`resolveRuleCell` 이 셀을 못 찾으면 **Gray-A(룰 미정)**, 어노테이션 미설정이면 **Gray-B(데이터 공백)** → 둘 다 비위반(D14).

## 4. 컴포넌트 트리

기존 `components/ebeam/*View.vue` 관례를 따릅니다.

```text
pages/ebeam/cd-sem/device-statistics/measurement-rules.vue   ← 라우트(§7)
└─ ebeam/MeasurementRulesView.vue        ← 컨테이너 (fab 선택 + 모드 토글)
   ├─ rules/RuleFabSelector.vue          ← R3 / M11 / M14 …
   ├─ rules/RuleMatrix.vue               ← 편집 매트릭스 (D13)
   │  ├─ rules/RuleRow.vue               ← 셀 1행 (compound selector 라벨)
   │  │  ├─ rules/RuleCapCell.vue        ← cap 정수 인라인 편집 + 모니터 색 오버레이
   │  │  └─ rules/NameOverrideRows.vue   ← ▸ 펼침 (D9 이름 예외)
   │  └─ rules/UnassignedBucket.vue      ← Gray-B 미분류 recipe (D14)
   └─ rules/RuleHistoryPanel.vue         ← 버전 목록 + diff + rollback (D12)
```

- `RuleMatrix.vue` 는 **편집/모니터 두 모드**를 한 컴포넌트가 prop(`mode`)으로 토글합니다(D13).
- M-fab 은 family/phase 축이 없어 `RuleMatrix` 가 **단일/소수 행**으로 축소 렌더(§Q3).

## 5. Composable (`useMeasurementRulesApi.ts`)

기존 `use*Api` + `$fetch` + `joinApiPath` 패턴, 읽기는 `useAsyncData` 캐시(CLAUDE.md).

| 함수 | 메서드 · 경로 | 용도 |
| --- | --- | --- |
| `fetchRules(fab)` | GET `/cdsem/device-statistics/rules?fab=` | 현재 버전 룰 셀 |
| `saveRules(fab, cells, note)` | PUT `/cdsem/device-statistics/rules` | 새 버전 append (D12) |
| `fetchHistory(fab)` | GET `/cdsem/device-statistics/rules/history?fab=` | 버전 목록 |
| `rollback(fab, version)` | POST `/cdsem/device-statistics/rules/rollback` | 지정 버전 복원 |

읽기 캐시 키는 `['measurement-rules', fab]` — 저장·rollback 후 `refresh()`.

## 6. 백엔드 (`back_dev_home/ebeam/cdsem/device_statistics/rules.py`)

feature-sliced 관례(routes ↔ data 분리). Phase 1 은 in-memory mock, Phase 2/3 은 동일 시그니처로 DB 교체.

- `rules.py` — seed 룰 셀(§2 형태) + `get_rules(fab)`, `save_rules(fab, cells, author, note)`,
  `get_history(fab)`, `rollback(fab, version)`. 버전 이력은 append-only 리스트(mock).
- `routes.py` — 위 4개 핸들러를 device_statistics 블루프린트에 등록. `author` 는 Phase 1 mock 고정,
  Phase 2/3 에서 SSO 헤더로 교체.

## 7. 라우트 배치 ✅ 확정

`pages/ebeam/cd-sem/device-statistics/measurement-rules.vue` — 소비처(device-statistics)와 colocate,
fab 은 페이지 내 `RuleFabSelector` 로. CONTEXT.md 의 `/admin/measurement-rules` 는 D12(admin 게이트 제거)로 폐기.

## 8-bis. 백엔드 데이터셋 ↔ 프론트엔드 책임

**원칙**: 백엔드는 **raw 데이터**(룰·파라미터·어노테이션)만 보낸다. 위반 판정은 **프론트엔드**(`ruleEngine.ts`)가
client-side 로 수행한다 — cap 한 글자 수정 시 round-trip 없이 모니터링이 즉시 재계산되어야 하기 때문(live what-if).

### 백엔드가 주는 3개 데이터셋

**(A) 룰** — `GET /cdsem/device-statistics/rules?fab=R3` (편집: `PUT /rules`, `GET /rules/history`, `POST /rules/rollback`)

```jsonc
{ "fab":"R3", "version":7, "edited_by":"kim.dy", "edited_at":"2026-05-30T09:14:00",
  "cells":[ /* RuleCell §2 (selector + caps + name_overrides) */ ] }
```

**(B) recipe 파라미터 raw 데이터** — `GET /cdsem/device-statistics/recipe-params?fab=R3` (recipe 당 1행)

```jsonc
{
  "lot_cd":"R3K-12", "recipe_id":"R3K12_CD", "fac_id":"R3",
  "oper_id":"...CD",            // step suffix → recipe_class
  "ctn_desc":"t-EV DRAM ...",   // 원문(투명성·fallback audit 용)
  "prod_catg_cd":"DRAM", "sample":0, "skip_yn":"N",
  // 백엔드가 문자열 분석으로 파생(CONTEXT.md) — 프론트는 소비:
  "recipe_class":"Main", "family":"Core", "phase":"t-EV", "memory_class_auto":"DRAM",
  // 파라미터 단위 raw 행 (D1 — source of truth):
  "parameters":[ {"name":"WAFER","point_count":13}, {"name":"EDGE","point_count":12},
                 {"name":"EDGE_EX","point_count":0}, {"name":"OVL_DSPT","point_count":13} ]
}
```

**(C) lot 어노테이션** — `GET /cdsem/device-statistics/annotations?fab=R3` (편집: `PUT /annotations`, 누구나·이력, D12)

```jsonc
[ {"lot_cd":"R3T-21","memory_class":"DRAM","yield_check":null,"edited_by":"park","edited_at":"..."},
  {"lot_cd":"R3P-07","memory_class":null,"yield_check":"after","edited_by":"kim","edited_at":"..."} ]
```

> 성능: (B) 는 무거우므로 Phase 2/3 에서 **요약**(recipe → 파생 selector + 파라 수)만 먼저 주고, 전체
> `parameters[]` 는 recipe drill-down 시 lazy-load 권장. mock(Phase 1)은 통째로 줘도 무방.

### 데이터 수신 후 프론트엔드가 하는 일 (`ruleEngine.ts`)

| 단계 | 처리 | 결정 |
| --- | --- | --- |
| 1. Merge | (C).memory_class 가 (B).memory_class_auto 를 override, yield_check 주입. 여전히 미설정이면 **Gray-B 미분류** | D4·D7 |
| 2. Resolve cell | recipe.{class,family,phase,yield_check,memory_class} → (A) 셀 매칭. 매칭 없으면 **Gray-A** | D8 |
| 3. Evaluate | 파라미터마다 `deriveType` → `capFor` → `point_count ≤ cap?` | D5·D9·D10 |
| 4. Aggregate | recipe: 총·위반 파라 수, pass/fail · lot: 위반recipe/총 → ratio → health · cell: 오버레이 색 | D14 |
| 5. Render | 매트릭스(A) + 모니터링 cascade(B) + 미분류 버킷 + 회색 셀 | D13·D14 |
| 6. Live what-if | cap 편집 → 3·4 즉시 client 재계산(refetch 없음) | 에디터 핵심 |

## 8. 빌드 순서 (incremental vertical slice)

1. `utils/ruleEngine.ts` + 단위 테스트(derive*/capFor/evaluate) — UI 없이 순수 로직 먼저.
2. `rules.py` seed + GET `/rules` + `useMeasurementRulesApi.fetchRules` → 읽기 전용 매트릭스 렌더.
3. `RuleCapCell` 인라인 편집 + PUT `/rules`(save) — 편집 enable.
4. 모니터 모드 오버레이 + `UnassignedBucket`(D14) — `useLotHealthMock` 대체.
5. `RuleHistoryPanel` + history/rollback(D12).

## 9. M-fab(양산) 룰 형태 ✅ 확정 (Q3)

양산은 개발 개념(phase·yield_check·**Pool**)이 전부 빠지지만 **DRAM/NAND 로는 나뉜다**.

| fab | 룰 키 축 | 행 |
| --- | --- | --- |
| R3 | family × (phase\|yield_check) × memory_class | 다수 (풀 매트릭스) |
| M-fab | `recipe_class × memory_class` | Main DRAM/NAND + Sample DRAM/NAND = 4행 |

`RuleMatrix` 는 M-fab 일 때 family/phase/yield 축을 숨기고 `recipe_class × memory_class` 4행만 렌더한다.
의미도 다르다 — R3 는 "기대 분포", M-fab 은 "이상감지 임계치"(CONTEXT.md). 기존 `CAPS_MFAB`(단일 cap)는
**DRAM/NAND 분리로 교체**된다.
