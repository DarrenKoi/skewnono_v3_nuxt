# Recipe 표준화 — 설계 결정 로그

`ground_rules.txt` 의 계측 Ground Rule 을 web application(특히 [device-statistics] 페이지)에
연동하기 위한 grilling 진행 기록입니다. 확정된 결정과 아직 열려 있는 질문을 함께 추적합니다.

> **📓 저널 규약 (append-only)**: 이 문서는 **날짜별로 쌓이는 결정 저널**입니다. 과거 날짜 섹션과
> 확정된 결정은 **고치지 않습니다** — 틀린 결정은 지우지 말고 새 결정으로 supersede 하세요
> (예: "D8 → D20 이 supersede"). 결정 ID(`D1`, `D2`…)는 **날짜와 무관하게 단조 증가**하는 영구
> 앵커이며 다른 문서가 이 ID 로 인용합니다. "지금의 통합 결론"은 `progress-and-next-steps.md`(살아있는
> 요약, 매번 덮어씀)가 담당하고, 본 저널은 "어떻게 거기 도달했나"의 날짜별 기록을 담당합니다.

> **🎯 이 grilling 의 목표**: 계측 룰을 **시각적으로 잘 표현**해서, 인증된 엔지니어 **누구나 쉽게
> (1) 룰을 바꾸고 (2) 준수 상태를 모니터링**할 수 있게 한다. D1–D11 은 그 시각적 surface 를 가능케 하는
> 룰 엔진 기반이고, **결과물은 visual rule editor + monitoring 화면**(Q7)이다.

관련 문서:

- 원문 룰: `docs/issues/ground_rules/ground_rules.txt`
- **프론트엔드 구조 설계**: `docs/issues/ground_rules/rule-editor-structure.md` (D1–D14 → 구현 구조)
- **편집 권한 ADR**: `docs/issues/ground_rules/adr-0004-open-rule-editing.md` (ADR 0003 supersede)
- 도메인 용어집: `CONTEXT.md` (파라미터 / Recipe Class / Product Family / Phase / 계측 룰)
- 기존 룰 결정: `docs/adr/0003-admin-only-rule-editor.md` (→ adr-0004 로 supersede 예정)

## 핵심 통찰

Ground Rule 문서와 현재 코드는 **서로 다른 어휘**로 룰을 기술합니다.

- 문서: 파라미터 **타입**(WAFER / LEVEL / EDGE / EDGE_EX)별 **기대 측정 포인트 수**
  (예: EDGE = 16, EDGE_EX = 0).
- 코드: **포인트수 bin**(`para_16/13/9/5` = N 포인트로 측정되는 파라미터 *개수*).

두 표현은 호환되지 않습니다. `EDGE_EX = 0`, `LEVEL = 4` 는 현재 bin 모델로 표현할 수 없습니다.
따라서 룰 검증의 입력은 **파라미터 단위 raw 데이터**여야 합니다.

## 2026-05-30 — 룰 모델·데이터 계약 확정 (D1–D15)

> D1–D4 는 이전 세션의 기반 결정을, D5–D15 는 이날 세션에서 확정한 결정을 이 날짜로 정리했습니다.
> (문서 자체가 260530 에 정리됨 — 통합본 `progress-and-next-steps.md` 참조.)

### D1 — 파라미터 단위(raw)를 source of truth 로 둡니다

recipe 마다 파라미터 행 `{name, type(WAFER/LEVEL/EDGE/EDGE_EX/기타), point_count}` 을 보유합니다.
`type` 과 `para_16/13/9/5` bin 은 모두 name·point_count 에서 **파생되는 집계 view** 입니다.
이 선택으로 `DSPT/WF/WAFER` 이름 예외, `EDGE_EX = 0`, `LEVEL = 4` 같은 룰을 모두 표현할 수 있습니다.

### D2 — 룰은 Recipe Class 별로 분기하고, Main·Sample 만 검증합니다

| Class | 판정 근거 | 룰 검증 |
| --- | --- | --- |
| Sample | `recipe_id` 의 `_SE`/`_S`, 또는 `sample=1` 컬럼 | Sample 룰 |
| Main | process-flow step 명 suffix `CD` | Main 룰 (주 대상) |
| 추가계측 | step suffix `CD(E)`/`CD2`/`CD(F)`… | **제외** (표시는 하되 violation 없음) |

- backend 가 사용자가 준비할 데이터(`sample` 0/1, `skip_yn` Y/N, `recipe_id`, step 명)의
  문자열 분석으로 `recipe_class` 를 파생합니다.
- [bucket] 매핑: `only_sample`=Sample, `only_normal`=Main, **`all`=Main+추가계측**,
  `mother_normal`=Main(Mother 파라 view).

### D3 — 룰 키 축을 재구성합니다 (stage → family + phase)

기존 단일 `stage`(EV/TV/PV/Pool) 축을 **두 직교 축**으로 분리합니다.

- **Product Family**: Core / Pool제 / VG·RTC·Cubic — `ctn_desc` 문자열 파생.
  - Pool제 ← `"Pool"`/`"Pool제"`
  - VG·RTC·Cubic ← `"vertical gate"`/`"vertical"`/`"RTC"`/`"Cubic"`
  - Core ← 그 외 default
  - 다중 매치 우선순위: `VG·RTC·Cubic > Pool > Core`
- **Phase**: t-EV / EV / TV / PV — `ctn_desc` 파생. 룰은 종종 `TV 이후`(TV+PV)를 한 묶음으로 다룹니다.

**Pool 모호성 해소**: 이전 모델은 "Pool제" 를 stage 값으로 다뤘으나, phase 와 **직교하는
product family** 로 확정했습니다. Pool제 제품도 t-EV→PV phase 를 거칩니다.

Main 룰 키 = `Class × Family × Phase × memory_class(DRAM/NAND)`.

### D4 — 수동 입력값은 제품(lot_cd) 단위 어노테이션입니다

룰에서 데이터로 확정할 수 없는 값은 **제품(lot_cd) 단위**로 사용자가 입력합니다
(한 제품의 recipe 들이 공유하는 속성).

| 어노테이션 | 산출 방식 | 비고 |
| --- | --- | --- |
| memory_class (DRAM-side / NAND-side) | `prod_catg_cd` 자동 파생 + **수동 오버라이드** | Pool제·`prod_catg_cd` 부재 시 수동 |
| yield_check_state (수율 확인 전 / 후) | **항상 수동** | Pool제 한정, 시간에 따라 전→후 전이 |

### D5 — 컴플라이언스는 단일 상한(≤) 의미입니다 (과소측정은 위반 아님)

모든 룰 값은 파라미터의 **최대 허용 측정 포인트 수(cap)** 입니다. 준수 판정은 `actual ≤ cap`
단일 비교이며, **과소측정은 절대 위반이 아닙니다** — 프로젝트 목적 자체가 "무분별한 계측 파라미터
증가 억제"(비대화 방지)이므로 적게 찍는 것은 항상 허용됩니다.

이 결정으로 원문의 혼재된 표현이 모두 상한으로 수렴합니다:

| 원문 | cap 해석 |
| --- | --- |
| `EDGE_EX 0` | cap 0 (측정하면 위반) |
| `WAFER 13`, `LEVEL 4` | cap 13 / 4 |
| `비-WAFER ≤ 9` | cap 9 (이름 예외 `DSPT/WF/WAFER` → cap 13) |
| `EDGE 8~16` 범위 | 상한 16 만 의미 (하한 8 은 준수와 무관) |
| Core TV·PV `EDGE 16` | cap 16 |

**기존 모델과의 관계**: `CONTEXT.md` §lot-health-signal 의 "cap 하나라도 넘으면 violation"
*비교 의미(≤)는 옳았습니다*. 남은 드리프트는 비교 의미가 아니라 **(1) 키 단위**(`para_16/13/9/5`
bin → 파라미터 **타입**별 cap)와 **(2) 축**(`stage` → `Family × Phase`)에 한정됩니다 — Q4 확정 시 reconcile.

### D6 — Sample 룰 완전 명세 + 이름 기반 오버라이드 레이어

Sample 룰 (Class=Sample, 모든 fab·phase 공통 한 벌 — D2):

| 타입 | cap |
| --- | --- |
| WAFER | 13 |
| LEVEL | 4 |
| EDGE | 10 (DRAM-side·VG·RTC·Cubic) / 8 (NAND·FLASH) |
| EDGE_EX | 0 |
| 그 외 (비-WAFER) | 0 — **단** 이름이 `WAFER`/`WF` prefix·suffix 면 허용 (WAFER 부속 파라) |

핵심 발견: 룰은 `(type → cap)` 만으로 부족하고 **이름 기반 오버라이드 레이어**가 필수다.

| Class | 이름 패턴 | 연산자 | 효과 |
| --- | --- | --- | --- |
| Sample | `WAFER`, `WF` | prefix/suffix | 비-WAFER-0 규칙에서 **면제** |
| Main | `DSPT`, `WF`, `WAFER` | contains | 비-WAFER cap 9 → **13 으로 상향** (L45) |

→ 패턴 집합·매칭 연산자(contains vs prefix/suffix)가 룰 셀마다 다르므로 글로벌 상수가 아니라
**룰 객체의 일부**. Q4 데이터 구조는 이 레이어를 반드시 담아야 한다.

> ⚠️ Sample EDGE 의 `10/8` 분기는 memory_class(DRAM/NAND/FLASH)와 product_family(VG·RTC·Cubic)를
> **섞어** 기술한다. `VG·RTC·Cubic ⊂ DRAM-side` 일 때만 깨끗이 memory_class 단일 축으로 환원됨 → **Q2** 에서 확정.

### D7 — memory_class 매핑 (부분 자동 + 나머지는 수동)

자동 파생 (`prod_catg_cd` → memory_class):

| prod_catg_cd | memory_class |
| --- | --- |
| DRAM | DRAM-side |
| NAND | NAND-side |
| FLASH | NAND-side |
| Tech | **자동 불가 → 수동** |
| Advanced | **자동 불가 → 수동** |

- `Tech`/`Advanced` 는 확정 매핑이 없어 **현장 엔지니어가 수동 결정**한다. → D4 의 수동 오버라이드가
  예외가 아니라 이 두 카테고리에 대해 **상시 경로**임을 확인. (UI 는 미설정 시 unknown 상태 필요 → Q6 연결)
- product_family **VG·RTC·Cubic → 잠정 DRAM-side** ("우선 DRAM 과 동일 룰 적용"). special products 라
  추후 자체 cap 분기 가능. ⚠️ 원문은 VG·RTC·Cubic 전용 Main 룰을 주지 않음(Core/Pool제만 명시) →
  해당 셀은 당분간 DRAM-side/Core 와 동일하게 채움.

**해소**: D6 의 EDGE `10/8` 분기는 **memory_class 단일 축**으로 키잉된다 (VG·RTC·Cubic 이 DRAM-side 로
환원되므로 product_family 는 EDGE cap 에 별도 축을 더하지 않음).

### D8 — Main 룰 키잉: family별 secondary 축 (균일 그리드 폐기) + 전체 cap 표

- **Core → `phase` 로 키잉** (t-EV·EV vs TV·PV)
- **Pool제 → `yield_check_state` 로 키잉, `phase` 무시** (수율 전/후만)
- VG·RTC·Cubic → 잠정 DRAM-side/Core 차용 (D7)

전체 Main cap 표 — 공통: WAFER 13, LEVEL 4, `_other` 9 (이름 `DSPT`/`WF`/`WAFER` → 13):

| Family | 분기 | EDGE | EDGE_EX |
| --- | --- | --- | --- |
| Core | t-EV·EV | DRAM 10 / NAND 8 | 0 |
| Core | TV·PV | 16 | 16 |
| Pool제 | 수율 전 | DRAM 10 / NAND 8 | 0 |
| Pool제 | 수율 후 | DRAM 10 / NAND 8 | DRAM 10 / NAND 8 |

- 관찰: Core 초기 = Pool 수율전 (cap 동일). 키 축이 달라(phase vs yield_check) 셀은 **분리 유지**.
- memory_class 분기(10/8)는 Core 초기·Pool 전체에 존재, Core TV·PV(16 고정)엔 없음 → 셀별 선택적 축.

**구조 결론**: 균일 4D 그리드 ✗ → **`selector + cap-spec` 룰 셀 목록**. selector 가 family 에 따라 다른
축(phase / yield_check) + 선택적 memory_class 를 가진다. (cap-spec 세부 형태는 grilling 진행 중 — Q4 잔여)

### D9 — 단일 파라미터 cap 해석: type 우선, prefix 기반

1. **type 은 이름의 prefix(선행 토큰)로 파생.** `EDGE_WF_CD` → prefix `EDGE` → type=EDGE (내부 `WF` 무시).
2. **type cap 이 name-override 보다 우선.** type 이 WAFER/LEVEL/EDGE/EDGE_EX 면 그 type cap 사용.
   따라서 **name-override 는 기타(비-WAFER) 파라에만 적용**되는 보조 규칙이다.
3. 해석 알고리즘:

   ```text
   type = derive_type_by_prefix(name)
   if type ∈ {WAFER,LEVEL,EDGE,EDGE_EX}: return caps[type]      # type 우선
   else (기타):
       if name 이 name_override 패턴 매치: return override.cap   # 기타 전용 보조
       return caps._other
   ```

   → name-override = "기타 파라 중 패턴 P 매치 시 `_other` 대신 cap C". Main: `DSPT/WF/WAFER`(contains)→13,
   Sample: `WAFER/WF`(prefix·suffix)→면제. 둘 다 기타 파라에만 작동.
4. type 파생 세부(longest-prefix, suffix 허용, Class-독립)는 **D10** 에서 확정.

### D10 — `derive_type` 최종: Class-독립, suffix 허용 + companion 투명성 신호

- **`type = longest-prefix-match(name, [EDGE_EX, EDGE, WAFER, LEVEL])`** — 표준 토큰으로 **시작**하면
  (접미 허용) 해당 WAFER-family type. `EDGE_EX` 를 `EDGE` 보다 먼저 시도(longest match).
- **Class 독립**: `WAFER_2`·`WAFER_CD`·`EDGE_WF_CD` 모두 Main·Sample 동일하게 WAFER-family 로 인정
  (통일성). → D9-④ 의 Class 의존 가설 폐기.
- 표준 prefix 없는 companion(`X_WF`, `_WAFER` suffix) → 기타 → name-override 경로(Main 13 / Sample 면제).
- **트레이드오프 + 완화책**: companion 을 관대히 WAFER-family 로 인정하면 WAFER-이름 companion 으로
  비대해진 recipe 가 violation 없이 green 유지 가능. → 하드 룰 대신 **프론트엔드에 recipe별 "총 파라미터
  수"를 노출**해 또래 대비 비정상 다(多)파라를 사람이 인지하게 한다 (soft 신호, **Q7** 입력).

### D11 — 룰 셀의 cap-spec 형태 (Q4 종결)

각 RuleCell = `selector + caps + name_overrides`:

```jsonc
RuleCell {
  selector: { recipe_class, family, phase_in?, yield_check?, memory_class? },  // family별 다른 축(D8)
  caps:     { WAFER:13, LEVEL:4, EDGE:_, EDGE_EX:_, _other:9 },                 // 누락 type = 해당 없음
  name_overrides: [ { patterns, match:"contains|affix", cap } ]                 // 기타 파라 전용(D9)
}
```

- 판정: recipe 파라미터 행마다 `point_count ≤ cap_for(param, cell)` (cap_for = D9 알고리즘). 하나라도 초과 → 그 recipe violation(D5 ≤).
- **memory_class 분기(10/8)**: selector 에 `memory_class` 를 넣어 **셀을 둘로 분리**(DRAM 셀·NAND 셀) 권장
  — caps 를 평면 정수로 유지(값맵 중첩 회피). 저비용·가역 구현 선택.

### D12 — 룰·어노테이션 편집 전면 개방 (ADR 0003 reversal)

룰(cap 정책)과 어노테이션(`memory_class`/`yield_check_state`) 모두 **인증된 엔지니어 누구나**
프론트엔드에서 자유 편집한다. **admin 전용 게이트 제거.**

- **신뢰 기반(권한 기반 아님)**: SSO 신원으로 변경자 추적, 엔지니어가 책임감 있게 행동한다는 전제.
- **무결성 장치**: 모든 룰 변경에 **버전 이력**(author + timestamp) + **언제든 rollback**.
- **사유**: admin(daeyoung)이 상시 대응 불가 → 병목 제거 위해 개방.

⚠️ 이는 **ADR 0003(룰 편집 admin 전용)을 명시적으로 뒤집고**, ADR 0003 이 *기각했던* "anyone can edit +
audit log" 대안을 채택한다. ADR 0003 의 우려(실시간 SSOT 흔들림)는 **history + rollback + SSO 추적**으로 완화.

- **데이터 모델 영향**: 룰 저장소가 *현재 상태만*이 아니라 **append-only 이력 + rollback** 을 지원해야 한다
  (CONTEXT.md 의 "seed 룰 + read/write API" 보다 확장).
- **새 ADR**: `docs/issues/ground_rules/adr-0004-open-rule-editing.md` (supersedes 0003).
- ⚠️ **루트 문서 충돌(별도 승인 필요)**: 루트 `docs/adr/0003` status → superseded, `CONTEXT.md` §계측-룰
  "관리자 전용" 서술 갱신 — folder 제약상 본 grilling 은 폴더에만 기록하고 루트 수정은 사용자 승인 후.

### D13 — UI 메타포: 편집 가능 매트릭스 (편집 + 모니터링 겸용)

룰 surface 는 **스프레드시트형 편집 매트릭스**다.

- **행** = 룰 셀(`family · secondary축 · memory_class`), **열** = 파라미터 타입(WAFER/LEVEL/EDGE/EDGE_EX/기타),
  **칸** = cap 정수(클릭 편집).
- 비균일성(Core=phase, Pool=yield_check)은 행 라벨의 compound selector 로 흡수("Core · t-EV·EV · DRAM").
- `name_overrides` 는 family 그룹 하위 `▸` 펼침 행.
- **모니터링 모드**: 같은 칸에 actual vs cap 색 오버레이(green `≤` / red `>`). 편집·모니터 한 화면.
- fab 별 매트릭스(R3 / M-fab 별, Q3). Sample 은 고정 1벌 행.

### D14 — 모니터링 계층: lot → recipe → parameter (보수적 unknown)

모니터링은 룰 에디터 매트릭스와 **별개**로, 기존 lot-primary cascade 를 재사용한다(룰 엔진 D1–D13 이 새 입력):

- **lot_cd 단위**: 위반 recipe 갯수 + 전체 대비 **비율**(예: 3/12 = 25%) → [[lot-health-signal]] 입력.
- **recipe 단위(lot 내부)**: 룰 준수 여부(pass/fail), **총 파라미터 수**(D10 투명성), **위반 파라미터 수**.
- **parameter 단위**: 어느 파라가 cap 초과인지(위반 파라 수의 분해).
- **보수적**: 미분류(Gray-B) recipe·미정(Gray-A) 셀은 위반에서 제외하고 별도 표기.

기존 device-statistics 신호등 → recipe table → parameter inspector cascade 와 정렬.

> **우선순위(사용자 지시)**: 먼저 **룰 편집 프론트엔드 구조**를 견고히 구축한다(누구나 시각적으로 편집).

### D15 — M-fab 룰 형태 + 라우트 + 프로토타입

- **M-fab(양산) = `recipe_class × memory_class`** (Main DRAM/NAND + Sample DRAM/NAND = 4행). 개발 개념
  (phase·yield_check·**Pool**)은 전부 없지만 **DRAM/NAND 로는 분리**된다 ("양산은 DRAM/NAND 로 나뉨").
  → 기존 `CAPS_MFAB`(단일 cap) 교체. R3 는 풀 family×phase 매트릭스 그대로.
- **라우트** ✅ `pages/ebeam/cd-sem/device-statistics/measurement-rules.vue` (소비처 colocate, fab 셀렉터).
- **UI 프로토타입**: `docs/issues/ground_rules/rule-dashboard.prototype.html` — 단일 HTML, 3 변형
  (A 매트릭스 / B 마스터·디테일 / C 모니터링우선) `?variant=` + 하단바 + ←/→. 던지는 코드, 승자 확정 후 폴딩.

## 열려 있는 질문 (다음 grilling 대상)

1. ~~**어노테이션 소유권**~~ — ✅ 해소 → **D12** + `adr-0004-open-rule-editing.md`
   (룰·어노테이션 모두 전 엔지니어 개방, SSO 추적 + 이력 + rollback; ADR 0003 supersede).
2. ~~**memory_class 매핑**~~ — ✅ 해소 → **D7** (DRAM→DRAM, NAND·FLASH→NAND, Tech·Advanced→수동,
   VG·RTC·Cubic→잠정 DRAM-side).
3. ~~**M-fab 적용 범위**~~ — ✅ 해소 → **D15** (M-fab = `recipe_class × memory_class`, family·phase·Pool 없음, DRAM/NAND 분리).
4. ~~**룰 데이터 구조**~~ — ✅ 해소 → **D8**(키잉·cap표) + **D9**(cap 해석 순서) + **D10**(derive_type)
   + **D11**(RuleCell 형태).
5. ~~**컴플라이언스 판정 의미**~~ — ✅ 해소 → **D5** (단일 상한 `≤`, 과소측정 비위반).
6. ~~**불완전 룰 표현**~~ — ✅ 해소 → **D14** (회색 2종: Gray-A 룰미정 / Gray-B 어노테이션미설정,
   둘 다 비위반·별도 표기).
7. ~~**UI 표현**~~ — ✅ 해소 → **D13**(편집 매트릭스) + **D14**(모니터링 cascade) + **D15**(라우트) +
   `rule-editor-structure.md`(구조 설계) + `rule-dashboard.prototype.html`(3변형 프로토타입). 구현은 §8 빌드 순서.
8. ~~**Sample 룰 세부 모순**~~ — ✅ 해소 → **D6** (10/8 은 `EDGE`, `EDGE_EX`=0; 이름 오버라이드 레이어 확인).

## 2026-05-31 — 모니터링 구현 + 신호등 threshold (D16–)

> step 4(모니터링)를 구현 가능한 형태로 좁히고, 그간 *provisional* 로 봉인됐던 신호등 threshold 를
> 편집 가능한 정책값으로 확정하는 세션. 기반: D14(cascade) · §8-bis(client-side live what-if) · CONTEXT `lot-health-signal`.

### D16 — 신호등 threshold = fab별 RuleVersion 의 공유 필드 (개인 오버라이드 없음)

신호등 색 경계(`yellow_at`, `red_at`)는 코드 상수도 데이터 파생값도 아닌 **fab별 `RuleVersion` 객체의 필드**다.
cap 과 **동일 생명주기** — 버전 이력·rollback·SSO 추적·전원 공유.

- **편집 위치**: 프론트 룰 에디터에서 cap 과 같은 화면에서 편집·저장(D13 매트릭스에 fab-level threshold 컨트롤 1쌍).
- **live 재색칠은 자연 귀결**: 위반 판정이 client-side(§8-bis)이므로 threshold 를 바꾸면 신호등이 즉시 다시 물든다
  — 별도 "what-if" 기능이 아니라 client 계산의 부수효과. 저장해야 남는다.
- **개인 sticky/오버라이드 없음** (사용자 확정): 신호등은 cross-team **단일 진실원**이어야 한다(ADR 0004 논리,
  `Analysis Scope` = fab 내 닫힘). "팀장은 20%, 담당자는 10%" 식 사적 뷰는 도입하지 않는다.
- **provisional 10/20% 의 처지**: 폐기가 아니라 **seed 기본값**으로 강등 — 이제 데이터가 아니라 편집 가능한 정책 필드의 초기값.
- **데이터 모델 영향**: `RuleVersion` 에 `thresholds: { yellow_at: number, red_at: number }` 추가
  (셀별이 아니라 **fab-level** — lot roll-up 비율에 걸리는 값이므로). `rule-editor-structure.md §2` 갱신 대상.

### D17 — 모니터링 데이터 흐름: 단일 composable + 적용/저장 분리 (§8-bis live 서술 갱신)

- **단일 소스 composable `useMeasurementMonitor(fab)`** 가 3개 데이터셋(`fetchRules` + `recipe-params` +
  `annotations`) fetch 와 `ruleEngine` 계산을 소유하고, **두 모니터 화면을 모두 먹인다** — device-statistics
  캐스케이드(D14)와 룰 매트릭스 모니터 모드(D13). 무거운 `recipe-params` 의 중복 fetch 를 피한다.
- **재계산은 per-keystroke 가 아니라 명시적 "적용" 트리거**(§8-bis 의 "즉시 재계산" 폐기). `draft`(편집 입력값)
  ↔ `applied`(스냅샷) 분리, `apply()` 가 draft→applied 복사, `monitorResult = computed(() => evaluateLot(…, applied))`
  는 **applied 가 바뀔 때만** 재계산. cap 칸 숫자는 타이핑 즉시 보이되 신호등 재색칠은 적용까지 대기.
  - 근거: 멀티자리 입력 중간상태(`1`→`16`) 깜빡임, 다(多)셀 시나리오는 합산 결과를 한 번에 봐야 함, 전 lot×recipe
    재계산 비용.
- **적용 ≠ 저장 (사용자 확정)**: **적용** = 저장 없이 local 재계산(공유 버전을 더럽히지 않는 what-if 탐색),
  **저장** = 마음에 들면 새 `RuleVersion` 영속(D12 버전·rollback·SSO·전원 공유). 두 버튼 분리.
- **코드 귀결**: `ruleEngine.ts:217` `classifyHealth(ratio)` 의 하드코딩 threshold(`0.1`/`0.2`) 제거 →
  `classifyHealth(ratio, thresholds)`, `evaluateLot(…, thresholds)` 로 D16 의 threshold 주입.

### D18 — 신호등은 합의 후 고정: threshold 는 what-if 에서 제외 (D16 미세조정, Q4 해소)

복잡도를 줄이기 위해 **신호등 경계(threshold)는 엔지니어 합의로 정한 뒤 고정**하고 what-if 대상에서 뺀다.
what-if/적용(D17)은 **cap 에만** 작동한다.

- **양쪽 화면 모두 저장된 threshold 로 신호등을 칠한다** — device-statistics 든 에디터 미리보기든 동일.
  적용은 "이 cap 이면 recipe pass/fail 이 어떻게 바뀌나"만 재계산하고, 신호등 경계는 흔들리지 않는다.
  → 단일 질문으로 수렴: *"합의된 신호등 기준 위에서 cap 을 바꾸면 몇 lot 이 빨개지나."*
- **threshold 고정 방식 = (가) 편집 가능하되 거의 안 바꿈** (사용자 확정). D16 의 "fab 별 `RuleVersion` 필드,
  프론트 편집·저장·버전" 은 그대로 유지하되, **what-if draft 에는 포함하지 않는다**(저장 시에만 반영).
  - (나) seed 상수 완전 고정은 기각: Phase 3 양산은 배포가 어려워 재합의 때마다 코드 배포가 필요해짐.
    "거의 안 바꾸되 코드 없이 바꿀 길은 프론트에 열어둔다."
- **Q4 해소**: 화면 간 applied 비대칭은 **cap 에만** 남는다(에디터 draft vs device-statistics 저장본).
  threshold 는 어디서나 저장본이라 비대칭이 사라진다 → composable 단순화(threshold 는 상수처럼 주입, draft 제외).

### D19 — Sample Core TV·PV 는 EDGE 16 (D6 의 "phase 공통 한 벌" 부분 supersede)

step 2(seed) 구현 리뷰에서 `/code-review` 와 `codex:rescue` 가 **충돌**했다: code-review 는
`ground_rules.txt` L40 "Core인 경우 TV 이후 (TV, PV) EDGE 16개로 증가" 가 **Sample 섹션**(L34–41)에
있는데 seed 가 누락했다고 지적, codex 는 "D6 에서 해소됨"으로 판단. 사용자 확정: **L40 을 정본으로 채택**.

- **D6 의 미세 수정**: D6 은 Sample 을 "모든 fab·phase 공통 한 벌"로 단순화하며 L40(Core TV·PV EDGE 상향)을
  의도치 않게 떨궜다. D19 가 **그 부분만** supersede — Sample 의 나머지(WAFER 13/LEVEL 4/EDGE 10·8/EDGE_EX 0/
  `_other` 0, WF/WAFER affix 면제)는 D6 그대로 유지.
- **셀 형태**: `selector {recipe_class:Sample, family:Core, phase_in:[TV,PV]}`, EDGE 16. **memory-blind**
  (Main 의 Core TV·PV(D8)가 memory 분기 없이 EDGE 16 인 것과 동일 — DRAM·NAND Core 모두 16).
  EDGE_EX 0, `_other` 0 은 Sample 기본 유지.
- **순서 = 우선순위 (D11 first-match 의존)**: ruleEngine 은 specificity 정렬 없이 first-match 이므로,
  이 specific 셀을 seed 배열에서 phase-blind Sample 셀(`r3-sample-dram/nand`)보다 **앞에** 둬야 한다.
  뒤에 두면 phase-blind 가 먼저 잡혀 EDGE 10/8 로 떨어져 D19 가 무력화된다. (`rules.py:_r3_cells` 주석 참조,
  `ruleEngine.test.ts` 의 D19 테스트가 순서=우선순위를 고정.)
- **영향**: Core TV·PV Sample recipe 의 EDGE 11–16 이 더 이상 거짓 위반으로 잡히지 않는다.
- ⚠️ Pool·VG 의 Sample TV·PV 는 L40 이 "Core인 경우"로 한정하므로 **대상 아님** — phase-blind 10/8 유지.

## 2026-06-13 — 룰 편집 admin 전용 회귀 + 이력/rollback 폐기 (D20, D12 supersede)

> 구현 직전 재검토 세션. D12(전면 개방 + append-only 이력 + rollback)가 추가한 **무결성 레이어의
> 복잡도**가 단일 편집자 시나리오에는 과하다고 판단하여, 편집 권한을 admin(daeyoung) 전용으로
> 되돌리고 버전 이력·rollback 을 폐기합니다.

### D20 — 룰 편집은 admin 전용, 이력·rollback 폐기 (D12 reversal, ADR 0004 supersede)

룰(cap 정책)과 threshold 는 **admin(daeyoung) 단독 편집**합니다. 버전 이력(append-only)·rollback·
SSO author 추적을 **전부 폐기**합니다. **저장 = 현재 룰 덮어쓰기**(단일 상태, 이력 없음).

- **사유**: 편집자가 1명이면 D12 의 정당화(다수 편집자 → 감사 추적·SSOT 흔들림 방지)가 사라집니다.
  룰 엔진/매트릭스 복잡도(D1–D11)는 편집 권한과 직교하여 그대로 남지만, **버전 이력·rollback·author
  배관은 통째로 제거**할 수 있어 step 3(저장)이 덮어쓰기 한 줄로, step 5(이력 패널)는 **삭제**됩니다.
- **핵심 정정**: D12 의 "anyone can edit, no gate" 는 권한 축에선 오히려 단순했고, 복잡도는 **이력+rollback**
  에서 왔습니다. 따라서 진짜 단순화는 "admin 전용"이 아니라 **이력 폐기**에서 옵니다 (admin gate 자체는
  코드를 약간 *더함*). 사용자 확정 fork = "이력/rollback 을 둘 것인가" → **두지 않음**.
- **트레이드오프(수용함)**: in-app undo 없음. cap 오타 시 복구는 git 또는 수동 재편집뿐.
- **Phase 1(오프라인)**: 사용자가 유일 유저라 gate 도 불필요 — 저장은 in-memory seed 덮어쓰기.
  Phase 2/3 에서 admin 식별(SSO)로 쓰기 경로만 보호.

**ADR 영향**: `adr-0004-open-rule-editing.md` status → **superseded by D20**. ADR 0003(admin 전용)의
*권한 결론*은 사실상 복원되나, 0003 이 전제한 "버전 이력 + read/write API"보다 **더 단순**합니다
(이력 자체를 폐기하므로). 새 ADR `adr-0005-admin-only-no-history.md` 로 D20 을 정본화 예정.

**데이터 모델 영향**:
- `RuleVersion` 의 `version`/`edited_by`/`edited_at` 은 **의미를 잃습니다**(이력 없음). 단일 룰 상태로
  축소하거나, 호환을 위해 필드는 두되 `version` 을 고정값으로 둘 수 있음 — 구현 시 확정.
- threshold(`yellow_at`/`red_at`, D16)는 **유지**합니다. admin 이 같은 화면에서 편집·저장하되, 역시
  이력 없이 덮어쓰기. D18(threshold 는 what-if 제외, 저장본으로 신호등 고정)은 그대로 유효.

**빌드 순서 영향**(rule-editor-structure.md §8):
- step 3(저장) = `PUT /rules` 가 seed 덮어쓰기. `saveRules(fab, cells, thresholds)` — author/note 없음.
- step 5(이력/rollback) **삭제**. `RuleHistoryPanel.vue`, `GET /rules/history`, `POST /rules/rollback`
  미구현.
- step 1·2(ruleEngine + 읽기 매트릭스)·step 4(모니터링)는 **영향 없음** — 편집 권한과 직교.

⚠️ **루트 문서 갱신(사용자 승인 후)**: 루트 `docs/adr/0003` status, `CONTEXT.md` §계측-룰 서술,
`rule-editor-structure.md` §5/§8 은 본 폴더 기록 후 별도 정리. (D12 와 동일한 folder 제약.)

### D21 — 룰 테이블은 정적(static) read-only, 프론트 편집 모드 폐기 (D13·D20·§8 step 3 supersede)

편집자가 1명(admin)이고 룰이 거의 안 바뀌므로, **프론트엔드 편집 모드를 아예 만들지 않습니다.** 룰 테이블은
**정적 read-only 매트릭스**로 배포하고, 드물게 바뀔 때는 **seed(`rules.py`) 를 고쳐 재배포**합니다.

- **위치**: `device-statistics/measurement-rules` **유지**(D15 위치 그대로). admin 전용 페이지로 옮기지
  않습니다 — 어차피 편집 UI 가 없어 일반 read 화면과 동일하므로, 소비처(device-statistics) colocate 가
  자연스럽습니다.
- **D13 supersede(편집 부분만)**: D13 의 "클릭 편집 매트릭스" 중 **편집(inline cap edit)·what-if 적용은
  폐기**. 행=룰셀·열=파라타입·칸=cap 의 **표현(matrix)** 메타포는 유지. 모니터 색 오버레이(D13 monitor
  mode)는 step 4(모니터링)에서 별도 판단 — 편집과 무관.
- **빌드 순서 영향**(§8): **step 3(인라인 편집 + `PUT /rules` 저장) 전면 폐기.** `saveRules`·write 라우트
  불필요. step 1·2(ruleEngine + read 매트릭스)로 **이 테이블은 완성**. step 5(이력/rollback)는 D20 에서 이미 폐기.
- **데이터 경로**: 현행 `GET /rules` → `useAsyncData` → read-only 매트릭스 유지(API 추상화 원칙과 일치,
  Phase 2/3 은 `data.py` swap 으로 실제 소스 교체 가능). 룰 = seed 상수, write 경로 없음.
- **남은 작업**: 룰 테이블 자체는 **없음**(이미 렌더 중). step 4(컴플라이언스 모니터링, D14 cascade)는
  편집과 독립된 별개 결정 — 진행 여부는 추후.

**현 코드 상태 확인(2026-06-13)**: `CapCell.vue`·`Row.vue` 는 순수 표시 컴포넌트(편집 입력 없음).
편집은 미구현 step 3 였으므로 **제거할 잔여 UI 없음** — D21 은 현 상태를 그대로 정본화합니다.

### D22 — descriptive(device-statistics) ↔ prescriptive(R3 룰) 페이지 분리 + M-fab 룰 폐기 (D15·D14·D16 supersede)

M-fab 은 합의된 룰이 없습니다. 따라서 룰 매트릭스를 fab 별로 분기(D15)하는 대신, **기술(descriptive) 뷰와
규범(prescriptive) 뷰를 두 페이지로 분리**합니다. device-statistics 는 전 fab 공통 기술 뷰가 되고, R3 룰 적용은
별도 페이지로 빠집니다.

**도메인 전제(사용자 확인)**: device = `lot_cd`. device 1개 = recipe 100~200개, recipe 1개 = 파라미터 다수,
파라미터마다 측정 point 수가 다름. 따라서 raw 나열은 불가 — **집계/판정으로 환원**해야 함.

**(1) device-statistics = 전 fab 공통 descriptive 뷰**
- device(lot_cd) → recipe → parameter **드릴다운을 모든 fab 이 공유**("같은 방식으로 본다"). 드릴다운은
  **단일 공유 컴포넌트**, 하이라이트 규칙만 파라미터화(outlier vs cap-violation).
- 하이라이트 = **device 내 point-count outlier**. baseline = **(a) 같은 device 내 다른 파라미터 대비**(룰
  불필요·상대 판정), 측정값 = **point count**(Q3). 판정 = **multiplier 기준**(point > k × device median,
  k 기본값 구현 시 확정, 예: 2×).
- **기타(_other) 파라는 드릴다운에서 펼쳐 개별 나열**(D10 — bloat 가시화). 기타는 단일 열이 아니라 다수
  파라미터의 bag.
- over-measuring 의 두 신호(Q1): (i) 파라미터 수 과다(특히 기타) 표시, (ii) point-count outlier 판정.
  device row 는 **device 내 outlier 파라미터 개수**를 노출(사용자 "counts of ... outlier in the device").

**(2) R3 룰 페이지(measurement-rules) = R3 전용 prescriptive 뷰**
- 정적 cap 매트릭스(D21) **+ R3 compliance device-table**: 룰을 **recipe 단위로 적용**, recipe 가 cap 위반 시
  위반 recipe 로 집계 → device row = **위반 recipe count**(D14 ratio supersede). 드릴다운은 **cap 위반 파라미터**
  하이라이트(공유 드릴다운 컴포넌트 재사용).
- **count 채택 이유(사용자)**: 룰은 엔지니어 합의이므로 위반은 recipe 총수와 무관하게 위반. → **D14(ratio
  roll-up) supersede**, **D16 ratio thresholds(yellow 0.1/red 0.2) 무효화**(비율 아님). device row health
  color 유지/폐기는 **미정**(추후 — count ≥ 임계 방식 등).

**(3) R3 는 두 뷰 모두 등장, M-fab 은 device-statistics 만**
- R3 = descriptive(device-statistics) + prescriptive(rule page) **두 렌즈**. M-fab = descriptive 만.
- **M-fab 룰 폐기(D15 supersede)**: `rules.py` `_mfab_cells()`·M-fab seed 제거, rules API 는 **R3 only**.
  `list_rule_fabs()`·`M_FAB_IDS` 의 룰 용도 제거(device-statistics fab 목록과 분리).

**미정(구현 시 확정)**: ① outlier multiplier k 기본값, ② device row 단위(outlier 파라미터 수 vs outlier 포함
recipe 수), ③ R3 compliance device row 의 health-color 유지 여부.

**영향 파일(예상)**: `device-statistics/index.vue`(+ 공유 드릴다운 컴포넌트 신설), `measurement-rules.vue`
(compliance 섹션 추가), `rules.py`(M-fab 제거), 신규 mock `recipe-params`(파라미터 point_count raw, §8-bis B).
