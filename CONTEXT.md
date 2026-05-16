# SKEWNONO 도메인 용어

이 파일은 implementation이 아니라 **공유 언어**만 담습니다. 코드 결정이나 task 진행 상황은 여기 적지 마세요 — 그건 plan, ADR, 또는 PR description 의 몫입니다.

## 용어

### Lot

CD-SEM 디바이스의 식별 및 **조직적 ownership 단위**입니다. 팹 운영팀에서 팀·담당자 할당이 lot 단위로 이뤄지기 때문에, 디바이스 통계·비교·트렌드 등 모든 분석 surface의 외피 축(primary axis)은 lot이어야 합니다. 코드는 `lot_cd`(R 계열: `R<base36 3-digit>`, M 계열: `<fac-prefix><base36 2~3-digit>`)로 표기합니다.

**lot_cd 는 팀 정체성을 implicit 하게 인코딩** 합니다 — 사용자 (담당자·임원 모두) 는 lot_cd 만 보고 어느 팀의 lot 인지 즉시 인지할 수 있으므로, UI 에 별도의 "owner / team" metadata 를 노출할 필요가 없습니다. 이 도메인 사실은 [[audiences]] 양쪽 모두에게 공유된 literacy 입니다.

### Recipe

측정 작업의 정의 단위. 한 lot은 여러 recipe를 가지며, 각 recipe는 측정 step([[oper-id]])과 짝지어집니다. recipe 단위로 “파라미터가 너무 많다 / 측정이 너무 잦다”가 평가되며, 이것이 [[device-statistics]] 페이지가 발굴하려는 최적화 대상입니다. 단, recipe는 lot보다 한 단계 안쪽 개념이므로 첫 진입 화면의 외피가 될 수 없습니다.

**total_recipe vs avail_recipe**: `total_recipe`는 전산 시스템에 *등록된* recipe 수(명부), `avail_recipe`는 *실제 운영 중*인 recipe 수입니다. 사용자 의사결정은 항상 “지금 작동 중인 것”에 기반하므로 UI 기본 노출은 `avail_recipe`만이고, `total_recipe`는 데이터 모델에는 남겨두되 별도 surface에서만 필요 시 노출합니다 (예: admin의 죽은 recipe 정리).

### Oper ID

Recipe와 쌍을 이루는 측정 step 식별자. 같은 recipe_id라도 oper_id 조합에 따라 다르게 운영될 수 있어, recipe 분석 시 oper_id를 분리해 살펴봅니다.

### Bucket (페이지 단위 기준 보기)

Recipe step을 묶어 보는 4가지 보기 모드: `all`, `only_normal`, `mother_normal`, `only_sample`. [[mother-vs-son]] 관계가 bucket 선택의 의미를 결정합니다.

Bucket은 [[analysis-scope]](=fab)와 달리 **데이터를 잘라내지 않습니다**. 같은 lot·recipe 집합을 그대로 둔 채, **어느 step 묶음을 [[계측-룰]] 검사 입력으로 쓸지** 재해석하는 *기준 보기*입니다. 따라서 신호등·매트릭스·테이블·트렌드 모든 zone 의 숫자가 bucket 값에 종속합니다.

네 가지 속성으로 정의합니다:

- **재해석 (not subsetting)** — bucket 을 바꿔도 보이는 lot·recipe 집합은 그대로. 룰 검사 입력만 달라짐.
- **Page-wide** — 페이지 안의 모든 계산 zone 이 동일 값을 공유. zone 별 local override 없음.
- **Singleton** — 한 번에 정확히 하나만 활성. 두 bucket side-by-side 비교 surface 없음.
- **URL-stateful & audience-shared** — bucket 은 URL query 에 박혀, [[audiences]] 간 link forward 시 같은 기준 보기로 열림. 사용자별 sticky preference 가 아님.

기본값은 `mother_normal` — [[mother-vs-son]] 정의상 TAT 최적화가 주 use case 이기 때문.

### Mother / Son 파라미터

**Mother**는 측정 시간(TAT)에 영향을 주는 파라미터. **Son(자식 파라)**은 Mother 안에서 함께 측정되므로 TAT에 별도 영향을 주지 않습니다. 따라서 `mother_normal` bucket이 “TAT 최적화 대상”을 보는 가장 직접적인 보기입니다.

### TAT

Turn-Around Time. 한 측정의 소요 시간. recipe 최적화의 주요 KPI 중 하나로, mother 파라미터 수가 TAT의 dominant driver 입니다.

### 계측 룰 (Measurement Rule)

한 [[lot]] 내의 recipe들이 가져야 할 **기대 파라미터 분포**. 구체적으로는 para_16 / para_13 / para_9 / para_5 계측 포인트 수의 분포가 정해진 비율 또는 범위에 들어 있는지를 의미합니다. 룰의 형태는 (bucket × fab 종류)에 따라 셋으로 갈립니다:

- `only_sample` bucket — Sample recipe는 “약속된 특정 파라미터만 측정”이라는 조직 합의가 있어 **fab·stage 전부 무관한 고정 룰 한 벌**을 공유합니다. R3와 M-fab 모두 동일 룰.
- R3 의 `only_normal` / `mother_normal` / `all` — **[[device-stage]] 별 룰**(EV/TV/PV/Pool). stage가 후기일수록 더 많은 파라미터 허용.
- M-fab 의 `only_normal` / `mother_normal` / `all` — **fab 단일 룰**. 양산은 공식 “기대 분포” 합의가 없지만, 사용자가 같은 룰 폼에 임계치를 넣어 **이상 감지(anomaly detection)** 용도로 활용합니다. UI 카피상 R3 와 동일 표현을 쓰지 않도록 주의 (“기대 분포” vs “이상 감지 임계치”).

룰은 코드 상수가 아니라 관리자/사용자가 입력·수정하는 도메인 객체이며, 룰을 벗어나는 정도가 [[lot-health-signal]]의 입력입니다.

**편집 권한과 위치**: 룰 편집은 **관리자 전용**, 별도 `/admin/measurement-rules` 페이지에서 수행합니다. 다른 사용자는 read-only — 신호등 색이 cross-team coordination 매체이므로 룰은 single source of truth여야 합니다. seed 룰과 그 read/write API는 `back_dev_home/ebeam/cdsem/device_statistics/rules.py` 에 위치하고, swap pattern에 따라 Phase 2/3에서 함수 시그니처 그대로 DB-backed 구현으로 교체됩니다.

### Device Stage

디바이스 개발 단계 분류 — 현재 알려진 값: **EV / TV / PV / Pool제**. stage에 따라 허용되는 [[계측-룰]]이 달라집니다(중요도 높을수록 파라미터 허용량 ↑). **R&D fab(R3)에만 존재하는 축**이며, 양산 fab(M11/M12/M14/M15/M16)의 lot은 stage 개념이 없습니다. 따라서 룰 매트릭스도 R3에서는 `(stage × bucket)`이고 M-fab에서는 `bucket` 한 축만 갖습니다.

stage 값은 **backend에서 `ctn_desc` 문자열로부터 추출**해 응답에 직접 실어 줍니다 (PV / EV / Pool 등의 단어 추출 로직). 프런트는 이미 정해진 `dev_stage` 컬럼을 소비만 합니다.

**추출 실패 시 fallback**: `ctn_desc` 에 stage 키워드가 없으면 *초기 개발 단계*로 간주해 **EV cap (가장 strict)** 을 적용합니다 — 안전상 가장 엄격한 룰을 걸어 두는 보수적 선택. 단 UI 칩 표시는 `[?]` 로 정직하게 노출해 "fallback 으로 EV cap 적용 중" 임을 tooltip 으로 부연, 데이터 품질 audit 가능성을 살려 둡니다.

### Lot Health Signal (신호등)

각 lot이 [[계측-룰]]을 얼마나 충족하는지 보여 주는 3단 상태(red / yellow / green). device-statistics 페이지의 최상단 entry surface로, 사용자는 신호등에서 문제 lot을 식별 → recipe table 정렬 → 파라미터 inspector 순으로 cascade 합니다.

**계산 방식**:

1. 각 recipe가 자기 lot의 `(fab × stage × bucket)` 룰을 검사 — 룰은 파라미터 카테고리별 정수 cap (`para_16_max`, `para_13_max`, `para_9_max`, `para_5_max`). cap 하나라도 넘으면 violation 1건.
2. lot 단위 roll-up: `violation_ratio = 위반 recipe 수 / 총 recipe 수`.
3. 색 매핑 (provisional, 사용자 합의 시 조정 예정): `< 10%` green, `10~20%` yellow, `≥ 20%` red.

threshold 값은 코드 상수가 아니라 룰 정의 객체의 일부로 저장되어 사용자가 함께 편집합니다.

**Severity (per-cell)**: cap 초과의 심각도는 같은 `(fab × stage × bucket)` 안에서 해당 파라미터 카테고리 actual 값들의 표준편차(σ)를 기준으로 표현합니다. 예) recipe의 `para_16` 값이 cap을 2σ 위로 초과하면 cell이 진한 색조로 표시되어 “단순 over”와 “심하게 over”를 시각적으로 분리합니다. lot-level pass/fail은 단순 binary (cap 초과 여부) 로 두고, severity는 cell-level 시각 표현에만 적용 — 첫 버전 복잡도를 억제합니다.

### Analysis Scope

분석의 단위 scope는 **개별 fab 하나** 입니다 — 사용자는 자기 담당 fab의 lot만 보고 최적화합니다. R3↔M, 또는 M11↔M14처럼 fab 경계를 넘는 비교는 valid use case가 아니므로 카트·신호등·룰 모두 fab 안에서 닫혀야 합니다.

### Audiences (담당자 / 임원)

device-statistics 페이지는 두 audience를 동시에 섬깁니다.

- **Operator (담당자)** — 자기 책임 lot의 recipe를 drill-down 해 비대한 파라미터/측정을 찾아내 직접 개선. 필요 surface: recipe table + parameter inspector + trend.
- **Executive (팀장 · 임원)** — 여러 lot의 정량적 비교를 한 장으로 보고, 최적화가 정체된 팀에 top-down directive를 발동. 필요 surface: lot-level 정량 차트(파라미터·운용 레시피수)와 [[lot-health-signal]].

둘은 같은 URL을 공유합니다 — evidence artifact가 양방향으로 forward 되기 때문. 따라서 어떤 IA든 한 페이지에서 두 audience 모두를 first-class로 다뤄야 하며, 한쪽을 hide-by-tab 처리하면 forwarding 시 깨집니다.
