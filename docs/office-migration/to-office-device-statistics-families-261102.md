# device-statistics 계열 확장 — 필요한 데이터 (Home → Office, 2026-11-02)

- 작성일: 2026-11-02입니다. 같은 날 Codex 교차 검토로 누락 항목을 보강했습니다.
- 수신자: 사무실에서 SKEWNONO 데이터를 추출·적재하는 Office agent입니다.
- 회신: 2026-11-04에 받았습니다. 원문과 반영 내용은 회신 기록 문서
  (`reply-device-statistics-families-261104.md`)에 있습니다.
- 목적: device-statistics를 CD-SEM 외에 **HV-SEM, VeritySEM, Provision**에도 엽니다.
  이 세 계열은 CD-SEM과 달리 **계측 Rule이 없습니다.** 화면은 Rule 판정 없이
  "디바이스마다 어떤 step을 어떤 recipe로 재고, recipe마다 파라미터가 몇 개이며
  포인트가 몇 개인가"를 보여 주는 느슨한 모니터링 대시보드가 됩니다.
- 이 문서는 그 대시보드가 읽을 **데이터의 모양**을 정합니다. 원천 추출은 사무실에서
  진행하시고, 끝의 답안지만 회신해 주시면 됩니다.

## 1. Home가 이미 알고 있는 것

아래가 틀렸다면 4절의 질문에서 바로잡아 주십시오.

- R3 step 원천은 계열별 index로 갈라져 있습니다: `sknn-planstep-r3-hv`,
  `sknn-planstep-r3-verify`, `sknn-planstep-r3-provision`. column은 `-cd`와 같습니다.
- M fab step 원천은 계열과 무관하게 `ebeam_tas_lot_hist`입니다.
- 파라미터 원천은 HV-SEM이 `hvsem_idp_ver`(CD-SEM의 `cdsem_idp_ver`와 같은 형태)이고,
  VeritySEM·Provision은 idp index가 없어 **측정 결과 data에서 추출할 예정**입니다.
- 디바이스 카탈로그는 CD-SEM과 같은 Redis `r3_device_grp`(R3)와 `device_desc`(M fab)입니다.
  이 두 표는 장비 계열 구분이 없는 제품 목록입니다.
- 장비 계열은 eqp_id를 파싱하지 않고 sem_list 행의 `eqp_model_cd`로 판정합니다.
  eqp_id 접두사(예: MCD)는 네 계열에 걸쳐 있습니다.

## 2. 필요한 데이터 — 표 네 개

화면 전체가 아래 네 표에서 나옵니다.

| 표 | 한 행 | 화면에서 쓰는 곳 |
| --- | --- | --- |
| A. 디바이스 step 표 | 디바이스의 step 하나 | step 목록, recipe 수, 묶음(all/normal/sample) |
| B. recipe 파라미터 표 | recipe의 파라미터 하나 | 파라미터 수, 포인트 수 구간 분포 |
| C. recipe 상태 표 | recipe 하나 | "파라미터 0개"와 "추출 실패"의 구분 |
| D. 디바이스 활동량 표 | 계열·fab·디바이스 하나 | 디바이스 목록에 올릴 대상, "측정 상위 N" 필터 |

조인 키는 다음과 같습니다.

- A ↔ B ↔ C: **`(tool_type, recipe_id)`**입니다. recipe 이름만으로 잇지 않습니다 —
  계열이 다르면 같은 이름이라도 다른 recipe일 수 있습니다.
- A ↔ D ↔ 카탈로그: `(fac_id, lot_cd)`입니다.

### 표 A — 디바이스 step 표

한 행 = **한 계열·한 디바이스의 한 step**입니다.

| 필드 | 형태 | 필수 | 설명 |
| --- | --- | --- | --- |
| `tool_type` | `hv-sem` / `veritysem` / `provision` | 필수 | 장비 계열입니다. |
| `fac_id` | 문자열, 예 `R3`, `M16` | 필수 | fab 대표 코드입니다. |
| `lot_cd` | 문자열, 예 `REXA` | 필수 | 디바이스 코드입니다. R3 index의 `prod_id`에서 `_BASE`를 뗀 값입니다. |
| `oper_id` | 문자열 | 필수 | 공정 ID입니다. |
| `oper_desc` | 문자열, 예 `CBL ETCH CD` | 필수 | 화면에 보이는 step 이름입니다. M fab은 `oper_det_desc`입니다. |
| `oper_seq` | 정수 | R3만 | 공정 순서입니다. M fab은 비워 둡니다(아래). |
| `samp_seq` | 정수 | R3만 | 같은 `oper_seq` 안의 측정 순서입니다. |
| `recipe_id` | 문자열 | 필수 | recipe 이름(full_name)입니다. |
| `eqp_id` | 문자열 | 필수 | 그 step을 재는 장비입니다. |
| `skip_yn` | `Y` / `N` / 빈 값 | R3만 | 원천 값을 **그대로** 둡니다. 빈 값을 `N`으로 바꾸지 마십시오. |
| `chg_tm` | 시각 문자열 | 선택 | 변경 시각입니다. KST인지 UTC인지 함께 알려 주십시오. |

- 행의 정체성은 R3에서 `(tool_type, lot_cd, oper_seq, samp_seq)`입니다. `recipe_id`는
  정체성이 아닙니다 — 한 디바이스 안에서 여러 step이 같은 recipe를 씁니다. **중복
  step을 recipe 기준으로 접지 마십시오.**
- M fab은 CD-SEM과 같은 규칙입니다. 최근 90일 창에서 **그 계열 장비로 잰** 측정만
  보고, unique `oper_det_desc`가 step 목록입니다. step마다 가장 최근 `event_tm`의
  `recipe_id`와 `eqp_id`를 씁니다. 순서는 Home이 공정 접두사로 합성하므로
  `oper_seq`/`samp_seq`는 비워 두셔도 됩니다.

### 표 B — recipe 파라미터 표

한 행 = **한 recipe의 한 파라미터**입니다.

| 필드 | 형태 | 필수 | 설명 |
| --- | --- | --- | --- |
| `tool_type` | 표 A와 같음 | 필수 | 장비 계열입니다. |
| `recipe_id` | 문자열 | 필수 | 표 A와 조인하는 키입니다. |
| `param_seq` | 정수, 1부터 | 필수 | recipe 안의 **측정 순서**입니다(아래). |
| `param_name` | 문자열 | 필수 | 파라미터 이름입니다. 원천 철자를 그대로 둡니다. |
| `param_type` | 문자열, 예 `WAFER`, `LEVEL`, `EDGE` | 있으면 | 파라미터 종류입니다. 원천에 없으면 비워 두십시오(Q4). |
| `point_count` | 정수 | 필수 | 그 파라미터의 계측 포인트 수입니다. |
| `mother` | `true` / `false` / 빈 값 | 있으면 | mother 파라미터 여부입니다. 개념이 없는 계열은 비워 둡니다. |
| `region` | 정수 / 빈 값 | 있으면 | 같은 image를 공유하는 파라미터 묶음 번호입니다. |

- **`param_seq`가 필요한 이유:** recipe 맨 앞에 오는 Dummy·Align은 측정이 아니라
  준비 단계라 통계에서 뺍니다. Home은 이것을 "이름 + 맨 앞"으로 판정합니다. 뒤쪽에
  `ALIGN`으로 끝나는 진짜 측정 파라미터가 있을 수 있어서 이름만으로는 거를 수
  없습니다. 원천 순서를 그대로 옮겨 주십시오. 이 계열에도 Dummy·Align이 맨 앞에
  오는지는 Q15로 확인합니다.
- `point_count`가 확정되지 않는 경우(측정마다 다름 등)는 Q5로 알려 주십시오.
  임의 대표값을 넣지 마십시오.
- **한 recipe의 행은 모두 한 출처에서 와야 합니다.** 한 recipe 버전이나 한 번의
  측정 run에서만 가져오고, 여러 측정에서 본 파라미터를 섞지 마십시오. 섞으면 실제로
  같이 재지 않는 파라미터 조합이 만들어집니다. 어느 출처를 골랐는지는 표 C에 남깁니다.

### 표 C — recipe 상태 표

한 행 = **표 A에 나온 recipe 하나**입니다. 표 A의 distinct `(tool_type, recipe_id)`마다
반드시 한 행을 만듭니다.

| 필드 | 형태 | 필수 | 설명 |
| --- | --- | --- | --- |
| `tool_type` | 표 A와 같음 | 필수 | 장비 계열입니다. |
| `recipe_id` | 문자열 | 필수 | 조인 키입니다. |
| `status` | `ok` / `empty` / `not_found` / `failed` | 필수 | 아래 표를 보십시오. |
| `source_kind` | `idp` / `measurement` | 필수 | 파라미터를 어디서 읽었는지입니다. |
| `source_ref` | 문자열 | `ok`, `empty`면 필수 | idp면 버전, 측정 결과면 그 run을 가리키는 ID입니다. |
| `source_tm` | 시각 문자열 | `ok`, `empty`면 필수 | idp면 버전 수정 시각, 측정 결과면 그 run의 시각입니다. |
| `note` | 문자열 | `failed`면 필수 | 실패 이유 한 줄입니다. |

| `status` | 뜻 | 표 B의 행 |
| --- | --- | --- |
| `ok` | 파라미터를 읽었습니다. | 1개 이상 |
| `empty` | 원천을 찾아 읽었는데 파라미터가 0개입니다. | 없음 |
| `not_found` | 원천에 이 recipe가 없습니다. | 없음 |
| `failed` | 원천은 있는데 읽다가 실패했습니다. | 없음 |

- idp에 버전이 여럿이면 CD-SEM과 같은 규칙으로 고릅니다: 가장 높은 버전, 그다음
  가장 최근 수정 시각입니다. 측정 결과에서 뽑을 때는 가장 최근 run 하나를 고르십시오.

### 표 D — 디바이스 활동량 표

한 행 = **한 계열·한 fab·한 디바이스**입니다.

| 필드 | 형태 | 필수 | 설명 |
| --- | --- | --- | --- |
| `tool_type` | 표 A와 같음 | 필수 | 장비 계열입니다. |
| `fac_id` | 문자열 | 필수 | fab 대표 코드입니다. |
| `lot_cd` | 문자열 | 필수 | 디바이스 코드입니다. |
| `meas_count` | 정수 | 필수 | 최근 90일 동안 그 계열 장비로 잰 측정 건수입니다. |
| `window_days` | 정수, 예 `90` | 필수 | 집계 창입니다. |
| `as_of` | 시각 문자열 | 필수 | 집계 기준 시각입니다. |

- **step 수로 측정 건수를 대신하지 마십시오.** 둘은 다른 양입니다.
- CD-SEM에서는 이 표가 두 가지 일을 합니다. 카탈로그 중 최근 90일에 측정된 디바이스만
  목록에 남기고, 측정 건수 순위로 "측정 상위 N" 필터를 만듭니다. 계열을 구분할 수 있는
  측정 이력이 없으면 Q12로 대안을 알려 주십시오.

### 카탈로그 — 새로 뽑지 않고 확인만 합니다

디바이스 목록 화면은 카탈로그 컬럼을 그대로 보여 주고 거기서 거릅니다.

- R3(`r3_device_grp`): `plan_catg_typ`, `prod_catg_cd`, `tech_cd`, `den_typ`,
  `prod_grp_typ`, `gen_typ`, `lot_cd`, `plan_grade_cd`, `ctn_desc`
- M fab(`device_desc`): `lot_cd`, `tech_nm`, `rnd_connector`, `chg_tm`, `ctn_desc`

세 계열이 재는 디바이스가 이 카탈로그에 다 있는지만 Q11로 알려 주십시오. 없는 디바이스가
있으면 같은 컬럼으로 행을 보충해야 합니다. step이 하나도 없는 디바이스도 카탈로그에는
남습니다 — Home은 그런 디바이스를 "스텝 원본 자료 없음"으로 표시합니다.

### 주간 추이 — 시작 시점부터 쌓입니다

주간 추이는 Home의 주간 스냅샷 스케줄러가 위 표로 만듭니다. 이 스케줄러는 **그 주의
현재 데이터**만 저장하므로, 계열을 연 날 이전의 추이는 생기지 않습니다. 과거 추이가
필요하면 과거 시점의 표 A·B를 재구성할 수 있어야 합니다(Q14).

### 필요 없는 것

Rule 판정용 축은 이 세 계열에 쓰지 않습니다. 아래는 **뽑지 않으셔도 됩니다.**

- recipe family, phase, memory class(Rule 셀렉터용)
- 계측 Rule 표, 경고 임계값

## 3. 화면 묶음 규칙 — Rule은 아니지만 계열마다 확인이 필요합니다

CD-SEM 화면은 step을 네 묶음으로 나눕니다. Rule 판정과 별개인 이름 규칙이라 이 계열에도
그대로 적용될지 확인해야 합니다. 맞지 않는 묶음은 Home이 그 계열 화면에서 끕니다.

| 묶음 | CD-SEM 규칙 | 질문 |
| --- | --- | --- |
| all | 모든 step | — |
| only_normal | skip이 아니고, step 이름의 **마지막 토큰이 정확히 `CD`** | Q7 |
| mother_normal | only_normal 중 mother 파라미터만 | Q6 |
| only_sample | **recipe 이름**이 `_S` 또는 `SE`로 끝남 | Q16 |

- step 이름이 `AVIS`/`ICANS`로 끝나는 이미지 처리 측정은 all에만 들어갑니다(Q17).
- `CD(E)`·`CD(F)` 같은 추가계측은 마지막 토큰이 `CD`가 아니므로 only_normal에서 빠집니다.

## 4. 질문

A는 "Home 가정이 맞다"이고, `?`는 "모름"입니다. 한 글자로 답해 주십시오.
**계열별**이라고 적힌 질문은 HV-SEM, VeritySEM, Provision 순서로 세 글자를 적습니다
(예: `AAB`).

- **Q1.** 세 계열의 R3 step index column이 `-cd`와 같다.
  A = 같음 / B = 다름(다른 필드 이름을 한 줄로) / ?
- **Q2.** (계열별) M fab에서 그 계열의 step이 `ebeam_tas_lot_hist`에 남는다.
  A = 남음 / B = 일부 fab만 / C = 없음 / ?
- **Q3.** VeritySEM·Provision 파라미터 원천은 측정 결과 data다.
  A = 측정 결과 / B = recipe 파일(FTP) / C = 아직 정하지 않음
- **Q4.** (계열별) 파라미터 종류(`param_type`)를 어디서 얻는가.
  A = 원천에 종류 column이 있음 / B = 이름에서 파생해야 함 / C = 종류 개념이 없음
- **Q5.** (계열별) 계측 포인트 수가 (recipe, 파라미터)마다 정수 하나로 정해진다.
  A = 정해짐 / B = 측정마다 다름 / ?
- **Q6.** (계열별) mother/son 구분이 있다.
  A = 있음 / C = 없음 / ?
- **Q7.** (계열별) Normal step 규칙(마지막 토큰이 정확히 `CD`)이 맞다.
  A = 맞음 / B = 다른 규칙(한 줄로) / C = Normal 구분 없음 / ?
- **Q8.** 추출 결과를 둘 곳.
  A = Redis parquet DataFrame(`device_desc`처럼) / B = OpenSearch index / C = MinIO JSON
- **Q9.** 갱신 주기.
  A = 주 1회 / B = 일 1회 / C = 수동
- **Q10.** 같은 `(tool_type, recipe_id)`가 장비마다 다른 파라미터를 가질 수 있다.
  A = 없음(recipe 이름이 곧 정체성) / B = 있음 / ?
  B라면 어느 장비 것을 대표로 쓸지 한 줄로 적어 주십시오.
- **Q11.** (계열별) 그 계열이 재는 디바이스가 카탈로그(`r3_device_grp`/`device_desc`)에 있다.
  A = 전부 있음 / B = 일부만 / C = 없음
- **Q12.** (계열별) 계열을 구분할 수 있는 최근 90일 측정 이력이 있다(R3 포함).
  A = 있음 / B = 일부만 / C = 없음
  B나 C면 대신 쓸 수 있는 원천을 한 줄로 적어 주십시오.
- **Q13.** (계열별) 표 B의 파라미터 목록이 완전하고 순서가 있다.
  A = recipe 정의(idp 등)에서 읽음 / B = 한 번의 완전한 측정 run에서 읽음 /
  C = 여러 측정의 일부만 보임
- **Q14.** (계열별) 계열을 열기 전의 과거 추이가 필요하고, 재구성할 수 있다.
  A = 재구성 가능 / B = 지금부터 쌓으면 됨
- **Q15.** (계열별) Dummy·Align 파라미터가 recipe **맨 앞**에 온다.
  A = 맞음 / B = 다른 위치에도 옴 / C = 없음 / ?
- **Q16.** (계열별) Sample recipe 판별(recipe 이름이 `_S` 또는 `SE`로 끝남)이 맞다.
  A = 맞음 / B = 다른 규칙(한 줄로) / C = Sample 구분 없음 / ?
- **Q17.** (계열별) `AVIS`/`ICANS` 이미지 처리 step이 있고, all에만 넣는 규칙이 맞다.
  A = 맞음 / C = 그런 step 없음 / ?

## 5. 추출 후 회신할 숫자

계열마다 한 줄씩 아래 모양으로 찍어 주십시오(값은 예입니다).

```text
hv-sem     A: lots=233 steps=3569 recipes=410  C: ok=398 empty=0  not_found=10  failed=2   D: lots=233
veritysem  A: lots=92  steps=1200 recipes=180  C: ok=0   empty=0  not_found=180 failed=0   D: lots=0
provision  A: lots=275 steps=7564 recipes=640  C: ok=611 empty=3  not_found=20  failed=6   D: lots=270
```

- `A:`의 `recipes`는 표 A의 distinct `(tool_type, recipe_id)` 수입니다. 표 C의 네 숫자를
  더하면 이 값과 같아야 합니다.
- `not_found`가 크면 조인 키 문자열이 어긋났을 가능성이 큽니다. 먼저 의심해 주십시오.
- `D:`의 `lots`는 표 D의 디바이스 수입니다.

## 6. 답안지

```text
Q1:
Q2:     (HV/Verity/Provision)
Q3:
Q4:     (HV/Verity/Provision)
Q5:     (HV/Verity/Provision)
Q6:     (HV/Verity/Provision)
Q7:     (HV/Verity/Provision)
Q8:
Q9:
Q10:
Q11:    (HV/Verity/Provision)
Q12:    (HV/Verity/Provision)
Q13:    (HV/Verity/Provision)
Q14:    (HV/Verity/Provision)
Q15:    (HV/Verity/Provision)
Q16:    (HV/Verity/Provision)
Q17:    (HV/Verity/Provision)
hv-sem     A: lots=    steps=    recipes=    C: ok=    empty=    not_found=    failed=    D: lots=
veritysem  A: lots=    steps=    recipes=    C: ok=    empty=    not_found=    failed=    D: lots=
provision  A: lots=    steps=    recipes=    C: ok=    empty=    not_found=    failed=    D: lots=
chg_tm / source_tm / as_of 시간대 (KST/UTC):
```
