# Recipe 표준화 — 설계 결정 로그

`ground_rules.txt` 의 계측 Ground Rule 을 web application(특히 [device-statistics] 페이지)에
연동하기 위한 grilling 진행 기록입니다. 확정된 결정과 아직 열려 있는 질문을 함께 추적합니다.

관련 문서:

- 원문 룰: `docs/issues/recipe_standardization/ground_rules.txt`
- 도메인 용어집: `CONTEXT.md` (파라미터 / Recipe Class / Product Family / Phase / 계측 룰)
- 기존 룰 결정: `docs/adr/0003-admin-only-rule-editor.md`

## 핵심 통찰

Ground Rule 문서와 현재 코드는 **서로 다른 어휘**로 룰을 기술합니다.

- 문서: 파라미터 **타입**(WAFER / LEVEL / EDGE / EDGE_EX)별 **기대 측정 포인트 수**
  (예: EDGE = 16, EDGE_EX = 0).
- 코드: **포인트수 bin**(`para_16/13/9/5` = N 포인트로 측정되는 파라미터 *개수*).

두 표현은 호환되지 않습니다. `EDGE_EX = 0`, `LEVEL = 4` 는 현재 bin 모델로 표현할 수 없습니다.
따라서 룰 검증의 입력은 **파라미터 단위 raw 데이터**여야 합니다.

## 확정된 결정

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

## 열려 있는 질문 (다음 grilling 대상)

1. **어노테이션 소유권** — memory_class / yield_check_state 입력 권한이 관리자 전용인지
   (ADR 0003 과 동일 게이트), 담당자가 자기 lot 을 직접 입력하는지. ADR 0003(룰 편집 admin 전용)과
   충돌 가능 → 새 ADR 후보.
2. **memory_class 매핑** — `prod_catg_cd` 의 DRAM/Tech/Advanced vs FLASH/NAND 가 각각
   DRAM-side / NAND-side 중 어디로 가는지 확정.
3. **M-fab 적용 범위** — ground rule 이 R3(R&D) 전용인지, 양산 M-fab 에도 family/phase 룰을
   적용하는지 ([analysis-scope] 와 연동).
4. **룰 데이터 구조** — 타입별 기대 포인트 + Main 의 "비-WAFER ≤9(보통 9 또는 5)" cap +
   이름 예외(`DSPT/WF/WAFER` → 13) 를 담는 객체 형태.
5. **컴플라이언스 판정 의미** — "룰을 지킨다" 가 정확히 일치(=)인지, 이하(≤)인지, 허용 범위인지
   (문서엔 `EDGE 16` 고정값과 `EDGE 8~16` 범위, "9 OR 5" 가 혼재).
6. **불완전 룰 표현** — 아직 정의되지 않은 (family×phase) 셀의 compliance 를 unknown/회색으로
   표현하는 방식. (문서: "아직 완벽하진 않다")
7. **UI 표현** — admin 룰 에디터(`/admin/measurement-rules`) + device-statistics 연동(특정 제품의
   특정 recipe 가 룰 준수 여부) + 수동 입력 surface 의 배치.
8. **Sample 룰 세부 모순** — `ground_rules.txt` 38~40 행의 `EDGE_EX 0` 와
   `DRAM/VG/RTC/Cubic 10, NAND&FLASH 8` 가 EDGE 인지 EDGE_EX 인지 불명확 → 확인 필요.
