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

### 파라미터 (Parameter) / 파라미터 타입

한 [[recipe]]가 측정하는 개별 항목. 각 파라미터는 **이름**과 **측정 포인트 수**를 가지며, **타입**(WAFER / LEVEL / EDGE / EDGE_EX / 기타)은 이름에서 파생됩니다. WAFER·LEVEL·EDGE·EDGE_EX 는 "WAFER 파라들"로 통칭되는 가장 중요한 파라미터 타입으로, 항상 측정을 기본으로 합니다. [[계측-룰]]은 (타입 → 기대 측정 포인트 수)로 기술되므로, 룰 검증의 입력 데이터는 **파라미터 단위(이름·타입·포인트수)** 여야 합니다.

**para_16/13/9/5 와의 관계**: 기존 device-statistics 의 `para_N` 컬럼(= N 포인트로 측정되는 파라미터 *개수*)은 이제 파라미터 단위 데이터에서 **파생되는 집계 view** 입니다. `para_N` bin 만으로는 `EDGE_EX=0`·`LEVEL=4` 같은 타입별 룰을 표현할 수 없어, raw 파라미터 데이터가 source of truth 입니다.

### Recipe Class (Main / Sample / 추가계측)

[[recipe]]가 계측 표준화에서 갖는 분류로, [[계측-룰]]의 1차 분기 축입니다. backend 가 사용자가 준비한 데이터(`sample` 0/1 플래그, `skip_yn` Y/N, `recipe_id`, step 명 컬럼)의 문자열 분석으로 파생합니다.

- **Sample** — `recipe_id` 의 `_SE`/`_S` 또는 `sample=1`. WAFER 파라들만 짧게 측정.
- **Main** — process-flow step 명 suffix 가 `CD` 인 핵심 계측. 룰의 주 대상.
- **추가계측** — step suffix `CD(E)`/`CD2`/`CD(F)`… 인 보조 계측. 엔지니어가 수시로 측정/스킵(`skip_yn`). **룰 검증 대상에서 제외**(표시는 되나 violation 없음).

[[bucket]]과의 매핑: `only_sample`=Sample, `only_normal`=Main, **`all`=Main+추가계측**, `mother_normal`=Main(Mother 파라 view). 룰 검증은 `only_sample`→Sample 룰, 그 외 버킷→Main 룰(추가계측 행은 skip).

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

### Product Family (Core / Pool제 / VG·RTC·Cubic)

개발 제품군 분류로, [[계측-룰]]을 가르는 축 중 하나. **backend 가 `ctn_desc` 문자열에서 파생**합니다:

- **Pool제** — `ctn_desc` 에 `"Pool"`/`"Pool제"` 포함.
- **VG·RTC·Cubic** — `"vertical gate"`/`"vertical"`/`"RTC"`/`"Cubic"` 포함.
- **Core** — 그 외 전부 (default).

**우선순위 (다중 매치 시)**: 가장 구체적인 것 우선 → `VG·RTC·Cubic > Pool > Core`.

> ⚠️ 이전 모델은 "Pool제" 를 [[phase]] 의 한 값으로 다뤘으나(§Flagged ambiguities), Pool제는 **phase 와 직교하는 product family** 로 확정. Pool제 제품도 t-EV→PV phase 를 거칩니다.

### Phase (t-EV / EV / TV / PV)

디바이스 개발 단계. [[product-family]]와 **직교**하는 룰 축. PV 는 양산 이관 직전으로 가장 중요. 룰은 종종 **"TV 이후"(TV + PV)** 를 한 묶음으로 다룹니다(예: Core 의 EDGE 16 증가). backend 가 `ctn_desc` 에서 추출(`PV`/`TV`/`EV`/`t-EV` 단어). 프런트는 파생된 컬럼을 소비만 합니다.

**추출 실패 시 fallback**: phase 키워드가 없으면 *초기 개발 단계* 로 간주해 **가장 strict 한 룰(EV 급)** 을 적용 — 보수적 선택. UI 칩은 `[?]` 로 노출해 "fallback 적용 중" 을 tooltip 으로 부연, 데이터 품질 audit 가능성 유지.

**fab 적용 범위**: ground rule 은 *개발 제품* 대상. R3(R&D) 적용은 확정, 양산 M-fab 의 family/phase 적용 여부는 [[analysis-scope]] 와 함께 별도 결정(grilling 진행 중).

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

### 계측 포인트 샘플링 (Measurement Point Sampling)

[[계측-룰]]/ground rule이 정한 "파라미터 타입별 측정 포인트 수"(예: EDGE 16)를 전제로, 그 N개 포인트를 **wafer 위 어디에 찍을지** 및 **정합성을 잃지 않고 몇 개까지 줄일 수 있는지**를 다루는 한 단계 안쪽 개념. ground rule(파라미터 타입 → 개수)과 **직교**한다.

페이지의 역할은 **per-recipe 추천 도구** — 특정 recipe의 과거 포인트 데이터를 입력받아, 줄여도 [[계측-정합성]]이 유지되는 포인트 후보를 추천·시각화한다. 룰 수립이나 일괄 audit가 아니라, 엔지니어가 한 recipe를 다듬을 때 쓰는 분석 surface.

포인트 단위 과거 데이터의 substrate는 [[msr-file]]에 이미 존재한다 — `chip_number`(웨이퍼 그리드 x,y), `chip_coordinate`/`stage_coordinate`(스테이지 µm), `mp_number`, `parameter`, `cd_value`.

**추천 엔진은 데이터 양에 따라 두 모드**를 가지며, 엔지니어가 둘로 나눠 점검할 수 있다 (단일 알고리즘 아님):

- **공간모델 모드 (Spatial-model)** — recipe history가 희소할 때(기본). 단일/소수 wafer의 **공간 상관**을 지오통계(variogram/kriging) 또는 GP 공분산으로 모델링하고, 부족분은 **동일 공정 step([[oper-id]]/layer)·유사 장비**로 풀링해 borrow strength (wafer CD signature는 공정 장비/스텝 물리에서 나오므로 — family/phase는 보조 필터). 다른 site로 잘 예측되는 site부터 greedy하게 제거.
- **이력상관 모드 (History-correlation)** — 같은 recipe에 wafer가 충분히 쌓였을 때. `site × wafer` 행렬의 cross-run 상관/주성분으로 중복 site를 제거. 데이터가 적으면 과적합 위험이라 희소 모드로 후퇴.

두 모드의 acceptance 기준([[계측-정합성]] = uniformity 일치)은 동일하다 — 다른 건 "어느 site를 버릴지" 고르는 selection mechanism뿐.

### CDU / MTX (측정 의도)

한 측정이 **무엇을 보려고** 포인트를 배치하는가. [[계측-포인트-샘플링]]의 방법론을 가르는 1차 축이다 — 두 의도는 통계 구조가 정반대다.

- **CDU** — wafer 전체에서 CD 값의 **uniformity**를 본다. wafer를 일정 간격으로 나눠 측정. wafer는 원형이라 위치별로 CD가 매끄러운 공간 성향을 가짐 → "공간적으로 상관된 장을 최소 포인트로 추정"하는 문제.
- **MTX** — wafer에서 **경향성(trend)**을 본다. 위치에 따라 CD size가 의도적으로 다르도록 공정되어, 가로·세로로 쭉 찍어 실험 경향을 파악 → "설계된 gradient를 잃지 않을 만큼만 측정"하는 문제.

### 계측 정합성 (Measurement Fidelity)

[[계측-포인트-샘플링]] 추천을 사용자가 받아들일지 가르는 **acceptance 기준**. CDU에서는 **줄인 포인트로 계산한 uniformity 지표가 full set과 허용오차 이내**임을 뜻한다. CDU의 결과물 자체가 uniformity이므로, 평균 CD 일치만으로는(산포를 놓쳐) 부족하다. 측정은 **leave-one-wafer-out 교차검증의 worst-case gap**으로 한다 — 최악 wafer에서도 축소·full uniformity 차이가 tolerance 이내일 때만 추천을 채택(평균이 아닌 최악값 기준).

"유지 **또는 향상**" — 포인트를 줄였는데 정합성이 *오르는* 경우는 redundant 제거가 아니라 **불량 포인트**(에지/노치 근처, align fail, 측정 artifact) 제거로 uniformity 추정이 더 견고해질 때다. 따라서 엔진은 "중복 제거 + 불량 포인트 식별" 두 역할을 가진다.

역할 구분(한 단어로 뭉치지 말 것): **acceptance metric**(이 정합성 정의) vs **selection mechanism**(어느 포인트를 버릴지 고르는 엔진 내부 통계) vs **시각 확인**(wafer map signature). 뒤 둘은 acceptance metric에 종속된 하위 개념.

> ⚠️ 미정: uniformity 지표를 **range(max−min)** 로 볼지 **3σ** 로 볼지. range는 단일 outlier에 민감, 3σ는 견고. tolerance 정의와 함께 확정 예정.

## Flagged ambiguities

- **"Pool" — stage 인가 product family 인가 (✅ 해소)**: 이전 모델은 "Pool제" 를 [[phase]](구 Device Stage) 의 한 값으로 다뤘으나, [[product-family]]로 확정 — phase 와 직교. mock `data.py:64` 의 `DEV_PHASES` 가 `Pool` 을 phase 토큰에 섞어 둔 것은 추후 데이터 정비 시 분리 대상.
