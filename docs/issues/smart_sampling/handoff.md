# 계측 포인트 샘플링 — 세션 핸드오프 (2026-05-30)

이번 세션은 `smart_sampling_methodology.md` 를 ADR 로 승격하고, 추천 엔진 설계 트리를
grilling 으로 확정한 기록입니다. **모든 설계 입력 결정이 끝났고, 다음 토픽은 엔진 출력
계약(API contract) YAML 작성**입니다. 결정의 *상세*는 중복하지 않고 아래 아티팩트를
가리킵니다 — 이 문서는 *왜 그렇게 결정했는지*(토론 흐름)와 *다음에 무엇을 할지*에 집중합니다.

## 이번 세션에서 한 일

1. **파일 재배치** — `smart_sampling_methodology.md` → `docs/adr/0005-metrology-sampling-two-mode-engine.md`
   (ADR 형식 그대로 승격). `ground_rules/` 규약을 따라 `grilling-log.md` 신설.
2. **ADR 번호 충돌 해소** — `docs/issues/ground_rules/adr-0004-open-rule-editing.md`(untracked,
   `accepted`, ADR 0003 supersede)가 이미 `0004` 를 점유 → 샘플링 ADR 을 **0005** 로 재번호.
   ground_rules draft 는 손대지 않음.
3. **설계 트리 grilling** — D7–D15 확정(아래 인덱스), `CONTEXT.md` 용어집 인라인 갱신.

## 토론의 핵심 흐름 (grilling-log 에 없는 *왜*)

- **사용자의 일관된 선호 = automation 이 아니라 guidance·agency.** tolerance(D8), 모드
  선택(D11), 불량 포인트(D12) 모두 "엔진이 자동 결정" 대신 "엔지니어가 판단하되 도구가
  *의미를 안내*"로 수렴. 다음 결정들도 이 방향으로 추천하면 정합도가 높습니다.
- **자기수정 — range 게이트는 over-accept 가 아니라 conservative.** acceptance 가 *절대값*이
  아니라 LOWO *gap* 이라, 극단을 버리면 gap 이 커져 오히려 기각됩니다. 그래서 3σ(산포 형태)
  + range(극단 보호) "둘 다 통과"(D7)가 일관됩니다.
- **"더 많은 데이터는 공짜가 아니다."** window 를 넓히면 W 는 늘지만 장비 상태 drift 로
  signature 가 혼재(D14). "데이터를 많이 = 항상 좋다"가 아님을 UI 가 보여줘야 합니다.
- **물리 제약이 모델을 가른다.** 한 포인트를 스킵하면 그 포인트의 *모든* parameter 가 함께
  빠지므로, uniformity 는 parameter 별로 계산하되 droppable set 은 **교집합**(D10).
- **모드 임계치는 절대값이 아니라 W vs S 상대값.** 상관행렬 안정성이 site 수에 묶여, ADR 의
  "<10장"은 예시일 뿐(D11). 60일치 `meas_hist` 에 run 이 많아도 W < S 면 여전히 spatial.
- **데이터·문서 교차검증으로 드러난 gap.** 풀링 축으로 명시된 `oper_id` 가 `meas_hist` 에
  없음 → 실제 축은 `class_name × eqp_model_cd`(D15).

## 확정된 결정 인덱스 (상세: `grilling-log.md` D1–D15, 근거: ADR 0005)

| ID | 한 줄 요약 |
| --- | --- |
| D1–D6 | ADR 0005 의 핵심 — 2-모드 엔진·CDU 앵커·step/장비 풀링·LOWO acceptance·Phase-1 계약범위·출력계약=swap surface |
| D7 | acceptance = 3σ·range **둘 다** tolerance 통과(dual-metric) |
| D8 | tolerance = **엔지니어 knob**(단일 객체 2필드), admin 게이트 아님 |
| D9 | per-recipe 입력 = `meas_hist` ⋈ `msr_file`(msr) → `site × wafer` 행렬 |
| D10 | uniformity 는 parameter 별, droppability 는 **cross-parameter 교집합** |
| D11 | 모드 = **manual toggle**(spatial 기본) + W·S advisory(과적합 경고) |
| D12 | v1 = redundancy 제거 + 불량 포인트 **advisory flag**(auto-removal 없음) |
| D13 | site key = 논리적 `(chip_number, mp_number)`, geometry 는 map 용 |
| D14 | 데이터셋 = **최근 window**(조정 가능) + drift 경고 |
| D15 | 풀링 축 = `class_name × eqp_model_cd`(`oper_id` 부재) |

## 다음 토픽 (핸드오프)

### ① 1순위 — 엔진 출력 계약 YAML (synthesis, 더 이상 grilling 불필요)

D6–D15 의 입력이 모두 확정되어 *결정*이 아니라 *작성*만 남았습니다.

- **위치/형식**: `docs/api-contracts/cdsem-smart-sampling.yaml` — 기존 `docs/api-contracts/README.md`
  와 `cdsem-device-statistics.yaml`·`cdsem-storage.yaml` 패턴을 그대로 따를 것.
- **계약이 담아야 할 필드**(D6 + 갱신):
  - 입력 식별: recipe + parameter(D10), window 파라미터(D14), 선택 모드(D11)
  - per-site droppability(site key = `(chip_number, mp_number)`, D13) + map geometry
  - 추천 축소 set = **parameter 교집합**(D10)
  - parameter 별 LOWO **gap 분포 + worst-case**, 3σ·range **두 지표 각각**(D7)
  - tolerance 두 필드(`3σ_tolerance`·`range_tolerance`, full-set 대비 %, D8)
  - 사용 모드 + **W·S advisory**(과적합 경고 신호, D11)
  - **불량 포인트 advisory flag**(`align_fail`·`fail_ratio`·`msr_check` + range↔3σ 괴리, D12)
  - 풀링 group(`class_name × eqp_model_cd`, D15)
- **swap surface**: 이 계약이 mock(`data.py`)과 office 구현의 경계(D5). 계약 확정 후 mock 출력 작성.

### ② 2순위 — MTX 방법론 (v2, D2 로 defer)

MTX(설계된 gradient 보존)는 CDU 와 통계 구조가 반대라 별도 엔진. v1 은 IA placeholder 만.
재개 시 `grill-with-docs` 로 grilling.

### mock 생성 시 확인할 작은 항목

- `mp_number` 가 wafer 전체에서 unique 한지, chip 마다 0 부터 재시작인지(D13 — 후자면 복합키 필수).
- office 에서 진짜 step/`oper_id` 풀링이 필요하면 `meas_hist` 에 컬럼 추가(D15).

## 관련 아티팩트

- 결정 로그: `docs/issues/smart_sampling/grilling-log.md`
- 방법론 ADR: `docs/adr/0005-metrology-sampling-two-mode-engine.md`
- 원문 아이디어: `docs/issues/smart_sampling/smart_sampling.txt`
- 용어집(갱신됨): `CONTEXT.md` §계측-포인트-샘플링 / §계측-정합성 / §CDU·MTX
- 데이터: `docs/datatables/meas_hist.txt`(run·풀링 축), `docs/datatables/msr_file_pickle.txt`(포인트),
  `docs/datatables/recipe_idp.txt`(`wafer_mp_info` = site plan)
- 계약 패턴 참고: `docs/api-contracts/README.md`, `cdsem-device-statistics.yaml`

## 미해결 / 주의

- **ADR 번호**: `docs/issues/ground_rules/adr-0004-open-rule-editing.md` 는 untracked draft 이며
  루트 `docs/adr/` 로 이동·ADR 0003 supersede 처리는 ground_rules 작업 소관(이 세션 범위 밖).
  같은 폴더의 `rule-editor-structure.md`(untracked)도 동일 토픽으로 보임 — 손대지 않음.
- **markdownlint 미실행**: `markdownlint-cli2` 가 환경에 미설치라 `npm run lint:md` 게이트를
  돌리지 못함. commit 전 `npm install` 후 lint 권장.

## 추천 스킬 (다음 에이전트가 호출)

- **`agent-skills:api-and-interface-design`** (또는 `agent-skills:spec`) — 출력 계약 YAML 설계·작성.
- **`generate-mock`** — 계약 확정 후 Phase-1 mock 데이터 composable 생성.
- **`grill-with-docs`** — MTX 방법론 grilling 재개 시.
