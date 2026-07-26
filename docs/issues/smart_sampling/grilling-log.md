# 계측 포인트 샘플링 — 설계 결정 로그

`smart_sampling.txt` 의 "측정 포인트 최소화" 아이디어를 web application의
[[계측-포인트-샘플링]] 페이지로 구현하기 위한 grilling 진행 기록입니다.
확정된 결정과 아직 열려 있는 질문을 함께 추적합니다.

관련 문서:

- 원문 아이디어: `docs/issues/smart_sampling/smart_sampling.txt`
- 방법론 결정(핵심): `docs/adr/0005-metrology-sampling-two-mode-engine.md`
- 도메인 용어집: `CONTEXT.md` (계측 포인트 샘플링 / CDU·MTX / 계측 정합성)
- 데이터 substrate: `docs/datatables/msr_file_pickle.txt`(포인트 단위), `docs/datatables/meas_hist.txt`(측정 이력·풀링 축)

## 핵심 통찰

실제 데이터가 **"site 위치는 고정이나 recipe당 wafer는 적음(<10장)"** 이라는 제약을 가지므로,
단일 알고리즘이 아니라 **데이터 양에 따라 엔지니어가 나눠 점검하는 2-모드 엔진**입니다.

- 데이터 희소(기본) → **공간모델 모드**(지오통계로 공간 상관 모델링 + 공정 step·장비로 풀링)
- 데이터 충분 → **이력상관 모드**(`site × wafer` 상관·주성분으로 중복 site 제거)

두 모드의 채택 기준은 동일하게 [[계측-정합성]] — **leave-one-wafer-out 교차검증의
worst-case uniformity gap 이 tolerance 이내**일 때만 축소 추천을 채택합니다.

전체 근거(고려된 대안·되돌리기 어려운 이유)는 ADR 0005 에 있습니다. 아래는 요약입니다.

## 확정된 결정

### D1 — 데이터 양에 따라 2-모드로 나뉜 추천 엔진

공간모델 모드를 기본, 이력상관 모드를 보조(데이터 풍부 recipe 교차 점검)로 둡니다.
이력상관 단일 방법은 wafer < site 일 때 rank-deficient·과적합이라 기본이 될 수 없습니다.

### D2 — v1 은 CDU 에 앵커링, MTX 는 IA 자리만

CDU(매끄러운 공간 장)와 MTX(의도된 gradient)는 통계 구조가 정반대라 추천 엔진이
사실상 분리됩니다. v1 은 CDU 만 구현하고 MTX 는 페이지 IA 에 placeholder 로 둡니다.

### D3 — 풀링 1차 축 = 공정 step(oper-id/layer)·유사 장비

wafer CD 공간 signature 는 제품 설계가 아니라 **공정 장비·스텝**(챔버 성향, 척 온도,
가스 흐름)에서 나옵니다. [[계측-룰]]을 가르는 축(family/phase)과 **다른** 축으로 풀링하며,
family/phase 는 보조 필터로만 둡니다. (룰 축과 풀링 축이 다른 점이 ADR 0005 의 핵심.)

### D4 — acceptance = uniformity 일치, LOWO worst-case 기준

축소 set 의 uniformity 지표가 full set 과 허용오차 이내인지를 **leave-one-wafer-out
교차검증의 worst-case gap** 으로 판정합니다. 평균 CD 일치(산포 누락)나 in-sample
재구성 오차(과적합)는 acceptance 로 부적합합니다.

### D5 — Phase-1 은 계약·UX 까지만, 검증은 office 실데이터

홈·오프라인 Phase-1 은 페이지 + API 계약 + mock 출력까지만 구축합니다. 실제 지오통계
구현은 office 에서 `data.py` 스왑으로 교체하며, "추천이 옳다"는 증명은 office 실데이터로
별도 수행합니다. 합성 mock 으로는 방법론을 검증할 수 없습니다.

### D6 — 엔진 출력 계약이 swap surface

엔진 출력 계약은 두 모드를 모두 표현해야 합니다 — per-site droppability, 추천 축소 set,
LOWO gap 분포 + worst-case, 사용 모드, 풀링 group. 이 계약이 mock 과 office 구현의
swap surface 입니다.

### D7 — acceptance 는 3σ·range 둘 다 통과해야 함 (dual-metric)

uniformity 지표를 단일로 고정하지 않고 **3σ 와 range(max−min) 두 지표가 각자의
허용오차를 동시에 만족**할 때만 축소를 채택합니다(둘 중 하나라도 넘으면 기각).
**3σ 는 산포 형태**, **range 는 극단 포인트(에지·코너)** 를 보호합니다. LOWO gap 은 두
지표 각각으로 계산합니다. 보수적 게이트라 축소 폭은 줄지만, 원문이 정합성을 hard
constraint 로 둔 점과 정합. (range 와 3σ 가 크게 엇갈리는 wafer 는 불량 포인트 신호 — Q3 와 연동.)

> 참고: range-as-gate 는 gap 기준에서 **보수적**입니다. 극단을 버리면 range gap 이 커져
> 기각되므로, 별도 보호 장치 없이도 에지 포인트가 보존됩니다.

### D8 — tolerance 는 v1 에서 엔지니어 knob (admin 게이트 아님)

`3σ_tolerance`·`range_tolerance` 는 **단일 tolerance 객체의 두 필드**로 묶고, v1 에서는
엔지니어가 페이지에서 조정하는 **per-recipe knob**(full-set 대비 % 기본값)입니다.
[[계측-룰]]과 달리 admin 게이트(ADR 0003)에 두지 **않습니다** — 룰은 lot-health 신호를 통해
cross-team 으로 forward 되는 single source of truth 라 admin 전용이지만, 이 페이지는
forward 되지 않는 **개인 분석 surface** 라 그 근거가 전이되지 않습니다. 또 v1 은 write-back
(추천을 recipe 에 반영) 액션이 없어 governance 대상 consequence 자체가 없습니다.

> 후속: "추천 축소를 recipe 에 commit" 액션이 추가되면 그때 admin ceiling(정합성 floor)을
> 재검토 — 그 시점에 cross-org consequence 가 생기기 때문.

### D9 — per-recipe 입력 = `meas_hist` ⋈ `msr_file` (msr join)

한 recipe 를 고르면 `meas_hist` 를 `recipe_name` 으로 필터해 **그 recipe 의 측정 run 들**
(`msr` 1개 = 1 run/wafer)을 얻고, `msr_file` 을 `msr` 로 조인해 **run 별 포인트 단위
`cd_value`** 를 얻습니다. 이것이 엔진의 `site × wafer` 행렬입니다 — 열 = `msr` run,
행 = 고정 wafer site, 셀 = `cd_value`. 풀링 축 필드(`eqp_id`·`class_name`·oper)도
`meas_hist` 에 있어 Q5 의 데이터 가용성은 *per-recipe 데이터셋* 한정 확인됨(cross-recipe
풀링 묶임 여부는 Q5 에 잔여).

> 미해결(이 행렬 위에서 결정): (a) recipe 당 wafer 수가 실제로 희소한지 — `meas_hist` 가
> 60일치라 run 이 많을 수 있음 → **모드 자동선택(Q1)** 의 입력. (b) **site key** 를 무엇으로
> 둘지(`chip_number` grid vs `stage_coordinate` µm vs 복합).

### D10 — uniformity 는 parameter 별, droppability 는 cross-parameter (교집합)

uniformity(3σ·range)는 **(recipe × parameter) 단위**로 계산하되, 추천 축소 set 은 한
포인트에서 측정되는 **모든 parameter 의 게이트를 동시에 만족하는 site 의 교집합**입니다.
물리적으로 한 포인트를 스킵하면 그 포인트의 모든 parameter(예: 한 SEM image 에서 뽑는
`CD_TOP`·`CD_BOTTOM`·`SIDEWALL_ANGLE`)가 함께 빠지기 때문 — 한 parameter 만 보고 고른
축소 set 은 다른 parameter 에 물리적으로 위험합니다. 엔지니어는 parameter 별 wafer map 을
따로 보되, headline 지표는 recipe 의 primary CD 로 기본. 출력 계약(D6)은 **parameter 별 gap
+ 교집합 droppable set** 을 담아야 합니다.

### D11 — 모드는 manual toggle (spatial 기본) + advisory guidance

모드를 자동 선택하지 않고 **엔지니어가 토글**합니다(기본 spatial-model). 대신 페이지가
**데이터 분석의 의미를 안내**합니다 — recipe 의 W(wafer/run 수)·S(site 수)를 표시하고,
history-correlation 모드를 W < k·S 인 데이터에 고르면 "상관행렬 rank-deficient → 과적합
위험" 을 경고하며, 각 모드가 무엇을 하고 언제 유효한지 설명합니다. enforcement 가 아니라
**guidance** 로 ADR 0005 의 과적합 함정을 막고, 엔지니어 agency(D8)는 유지합니다.

> ADR 0005 의 "recipe당 wafer <10장" 은 *예시* 일 뿐, 실제 기준은 **W vs S 상대값**입니다
> (S×S 상관행렬 안정성이 site 수에 묶이므로). UI 경고도 절대값이 아닌 W vs S 로 판정.

### D12 — v1 = redundancy 제거 + 불량 포인트 advisory flag (auto-removal 없음)

v1 은 redundancy 제거를 추천(D7 게이트)하고, 의심 불량 포인트는 **별도 advisory 채널**로
표시합니다 — `align_fail`·`fail_ratio`·`msr_check`(run 단위) + range↔3σ 괴리(site 단위) +
에지/노치 geometry. **auto-removal 없음** — 엔지니어가 검토·판단합니다. redundancy
게이트(`|gap| ≤ tol`)와 불량 제거의 acceptance 가 정반대(불량 제거는 uniformity 를 *향상*
→ signed gap)라 한 게이트에 섞을 수 없어 채널을 분리합니다. 'auto-improve'(signed-gap
acceptance)는 v2. 출력 계약(D6)에 **advisory flag 필드**를 추가합니다.

### D13 — site key = 논리적 point identity `(chip_number, mp_number)`

wafer 간 site 매칭은 recipe 의 **논리적 point identity** = `(chip_number, mp_number)`
복합키(안전 default)로 합니다. `mp_number` 가 wafer-global 로 확인되면 `mp_number` 단독으로
축약. 정확 일치 매칭이라 ε tolerance 불필요하고 'site 위치 고정' 의미와 정합합니다.
`chip_coordinate`/`stage_coordinate` 는 **wafer map 렌더링용 geometry** 로만 쓰고 매칭에는
쓰지 않습니다. office swap 시 필드는 remap 될 수 있으나 contract 의 site 개념은 불변.

> 확인 필요(mock 생성 시): `mp_number` 가 wafer 전체에서 unique 한지 chip 마다 0 부터
> 다시 시작하는지 — 후자면 복합키 필수.

### D14 — 데이터셋 = 최근 window (조정 가능) + drift 경고

"이 recipe 의 wafer" 집합은 **최근 window**(최근 N run 또는 N일)를 기본으로 하고 엔지니어가
조정합니다. window 변경 시 W 를 실시간 표시하고, window 가 긴 기간을 포괄하면 **signature
drift 혼재 위험**을 경고합니다. 기본은 signature coherence 유지, 엔지니어가 history 모드용
wafer 확보를 위해 *의도적으로* 넓히되 trade-off 를 보게 합니다. window 가 W 를 결정하므로
D11 의 W-vs-S 모드 advisory 와 직결됩니다. single-lot 은 보통 너무 희소(recipe 당 lot 별
1~2 wafer)라 기본에서 제외.

### D15 — 풀링 축 = `class_name` × `eqp_model_cd` (oper_id 는 데이터에 없음)

코드 탐색 결과 `meas_hist` 는 풀링 축 필드를 제공하나 ADR 0005 의 "oper-id" 와 다릅니다:

- **유사 장비**: `eqp_model_cd`(모델 동일 = 챔버 성향 유사)·`eqp_id`(동일 물리 장비)·`vendor_nm`. ✓
- **공정 step/layer**: `class_name`(ADI/AEI/OVL/GATE/CNT/…) = layer group. ✓ ("oper-id/layer" 의 layer 절반)
- `oper_id` 컬럼은 `meas_hist` 에 **없음** — CONTEXT §oper-id 는 recipe 와 짝이라 하나 측정이력 mock 미포함.

→ v1 풀링 축 = **`class_name` × `eqp_model_cd`**(필요시 `eqp_id` 로 exact-tool). office 에서 진짜
oper_id/step 풀링이 필요하면 `data.py` swap 시 컬럼 추가. recipe IDP(`wafer_mp_info`: ChipNo_X/Y·
`P_No`·`D_No`)가 site plan 을 정의하므로 D13 site key 와 정합(필드명만 다름 → swap 시 remap).

## 열려 있는 질문 (다음 grilling 대상)

1. **엔진 출력 계약의 구체 스키마** — D6 의 계약을 `docs/api-contracts/` 의 YAML 로 확정
   (per-site droppability·축소 set·LOWO 분포·모드·advisory flag·풀링 group 의 필드 형태).
   *모든 입력 결정(D7–D15)이 확정되어 이제 synthesis 단계 — 다음 산출물 후보.*
2. **MTX 방법론** — placeholder 이후 MTX(설계된 gradient 보존) 추천을 언제·어떻게 다룰지(v2,
   D2 로 이미 defer).
