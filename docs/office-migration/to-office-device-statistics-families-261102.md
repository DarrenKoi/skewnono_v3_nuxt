# device-statistics 계열 확장 — 필요한 데이터 (Home → Office, 2026-11-02)

- 작성일: 2026-11-02입니다.
- 수신자: 사무실에서 SKEWNONO 데이터를 추출·적재하는 Office agent입니다.
- 목적: device-statistics를 CD-SEM 외에 **HV-SEM, VeritySEM, Provision**에도 엽니다.
  이 세 계열은 CD-SEM과 달리 **계측 Rule이 없습니다.** 화면은 Rule 판정 없이
  "디바이스마다 어떤 step을 어떤 recipe로 재고, recipe마다 파라미터가 몇 개이며
  포인트가 몇 개인가"를 보여 주는 느슨한 모니터링 대시보드가 됩니다.
- 이 문서는 그 대시보드가 읽을 **데이터의 모양**을 정합니다. 원천 추출은 사무실에서
  진행하시고, 끝의 답안지만 회신해 주시면 됩니다.

## 1. Home가 이미 알고 있는 것

아래가 틀렸다면 3절의 질문에서 바로잡아 주십시오.

- R3 step 원천은 계열별 index로 갈라져 있습니다: `sknn-planstep-r3-hv`,
  `sknn-planstep-r3-verify`, `sknn-planstep-r3-provision`. column은 `-cd`와 같습니다.
- M fab step 원천은 계열과 무관하게 `ebeam_tas_lot_hist`입니다.
- 파라미터 원천은 HV-SEM이 `hvsem_idp_ver`(CD-SEM의 `cdsem_idp_ver`와 같은 형태)이고,
  VeritySEM·Provision은 idp index가 없어 **측정 결과 data에서 추출할 예정**입니다.
- 장비 계열은 eqp_id를 파싱하지 않고 sem_list 행의 `eqp_model_cd`로 판정합니다.
  eqp_id 접두사(예: MCD)는 네 계열에 걸쳐 있습니다.

## 2. 필요한 데이터 — 표 두 개

화면 전체가 아래 두 표에서 나옵니다. 둘은 **recipe 이름 문자열**로 조인합니다.
주간 추이는 Home의 주간 스냅샷 스케줄러가 이 두 표로 만들므로 따로 뽑지 않으셔도 됩니다.

### 표 A — 디바이스 step 표

한 행 = **한 디바이스의 한 step**입니다.

| 필드 | 형태 | 필수 | 설명 |
| --- | --- | --- | --- |
| `tool_type` | `hv-sem` / `veritysem` / `provision` | 필수 | 장비 계열입니다. |
| `fac_id` | 문자열, 예 `R3`, `M16` | 필수 | fab 대표 코드입니다. |
| `lot_cd` | 문자열, 예 `REXA` | 필수 | 디바이스 코드입니다. R3 index의 `prod_id`에서 `_BASE`를 뗀 값입니다. |
| `oper_id` | 문자열 | 필수 | 공정 ID입니다. |
| `oper_desc` | 문자열, 예 `CBL ETCH CD` | 필수 | 화면에 보이는 step 이름입니다. M fab은 `oper_det_desc`입니다. |
| `oper_seq` | 정수 | R3만 | 공정 순서입니다. M fab에는 없으므로 비워 둡니다. |
| `samp_seq` | 정수 | R3만 | 같은 `oper_seq` 안의 측정 순서입니다. |
| `recipe_id` | 문자열 | 필수 | recipe 이름(full_name)입니다. 표 B의 `recipe_id`와 **같은 문자열**이어야 합니다. |
| `eqp_id` | 문자열 | 필수 | 그 step을 재는 장비입니다. |
| `skip_yn` | `Y` / `N` / 빈 값 | R3만 | 원천 값을 **그대로** 둡니다. 빈 값을 `N`으로 바꾸지 마십시오. |
| `chg_tm` | 시각 문자열 | 선택 | 변경 시각입니다. KST인지 UTC인지 함께 알려 주십시오. |

- 행의 정체성은 R3에서 `(lot_cd, oper_seq, samp_seq)`입니다. `recipe_id`는 정체성이
  아닙니다 — 한 디바이스 안에서 여러 step이 같은 recipe를 씁니다. **중복 step을
  recipe 기준으로 접지 마십시오.**
- M fab은 최근 90일 창의 unique `oper_det_desc`가 step 목록입니다(CD-SEM과 같은 규칙).
- step이 하나도 없는 디바이스는 행을 만들지 않아도 됩니다. Home이 "스텝 원본 자료
  없음"으로 표시합니다.

### 표 B — recipe 파라미터 표

한 행 = **한 recipe의 한 파라미터**입니다.

| 필드 | 형태 | 필수 | 설명 |
| --- | --- | --- | --- |
| `tool_type` | 표 A와 같음 | 필수 | 장비 계열입니다. |
| `recipe_id` | 문자열 | 필수 | 표 A와 조인하는 키입니다. |
| `param_name` | 문자열 | 필수 | 파라미터 이름입니다. 원천 철자를 그대로 둡니다. |
| `param_type` | 문자열, 예 `WAFER`, `LEVEL`, `EDGE` | 있으면 | 파라미터 종류입니다. 원천에 없으면 비워 두십시오(질문 Q4). |
| `point_count` | 정수 | 필수 | 그 파라미터의 계측 포인트 수입니다. |
| `mother` | `true` / `false` / 빈 값 | 있으면 | mother 파라미터 여부입니다. 개념이 없는 계열은 비워 둡니다. |
| `region` | 정수 / 빈 값 | 있으면 | 같은 image를 공유하는 파라미터 묶음 번호입니다. |
| `recipe_version` | 문자열 / 정수 | 선택 | 어느 버전에서 읽었는지입니다. 측정 결과에서 뽑으면 비워 둡니다. |
| `source_tm` | 시각 문자열 | 필수 | 이 행의 근거 시각입니다. idp면 버전 시각, 측정 결과면 마지막 측정 시각입니다. |
| `eqp_id` | 문자열 / 빈 값 | 질문 Q10 | 같은 recipe가 장비마다 파라미터가 다를 때만 채웁니다. |

- recipe당 파라미터가 0개인 경우는 "추출 실패"와 구분해야 합니다. 읽지 못한 recipe는
  행을 만들지 말고 4절의 누락 개수에 세어 주십시오.
- `point_count`가 확정되지 않는 경우(측정마다 다름 등)는 Q5로 알려 주십시오.
  임의 대표값을 넣지 마십시오.

### 필요 없는 것

Rule 판정용 축은 이 세 계열에 쓰지 않습니다. 아래는 **뽑지 않으셔도 됩니다.**

- recipe 분류(Main/Sample의 Rule 셀렉터용), recipe family, phase, memory class
- 계측 Rule 표, 경고 임계값

## 3. 질문

A는 "1절과 2절의 Home 가정이 맞다"이고, `?`는 "모름"입니다. 한 글자로 답해 주십시오.

- **Q1.** 세 계열의 R3 step index column이 `-cd`와 같다.
  A = 같음 / B = 다름(다른 필드 이름을 한 줄로) / ?
- **Q2.** M fab에서 세 계열의 step도 `ebeam_tas_lot_hist`에 남는다.
  A = 세 계열 모두 / B = HV-SEM만(AMAT은 없음) / C = 셋 다 없음 / ?
- **Q3.** VeritySEM·Provision 파라미터 원천은 측정 결과 data다.
  A = 측정 결과 / B = recipe 파일(FTP) / C = 아직 정하지 않음
- **Q4.** 파라미터 종류(`param_type`)를 어디서 얻는가.
  A = 원천에 종류 column이 있음 / B = 이름에서 파생해야 함 / C = 종류 개념이 없음
- **Q5.** 계측 포인트 수가 (recipe, 파라미터)마다 정수 하나로 정해진다.
  A = 정해짐 / B = 측정마다 다름 / ?
- **Q6.** mother/son 구분이 있는 계열.
  A = HV-SEM만 / B = 세 계열 모두 / C = 없음 / ?
- **Q7.** CD-SEM의 Sample recipe 판별(recipe 이름이 `_S` 또는 `SE`로 끝남)이 이 계열에도 맞다.
  A = 맞음 / B = 다른 규칙(한 줄로) / C = Sample 구분 없음 / ?
- **Q8.** 추출 결과를 둘 곳.
  A = Redis parquet DataFrame(`device_desc`처럼) / B = OpenSearch index / C = MinIO JSON
- **Q9.** 갱신 주기.
  A = 주 1회 / B = 일 1회 / C = 수동
- **Q10.** 같은 `recipe_id`가 장비마다 다른 파라미터를 가질 수 있다.
  A = 없음(recipe 이름이 곧 정체성) / B = 있음(`eqp_id`를 채움) / ?

## 4. 추출 후 회신할 숫자

계열마다 한 줄씩 아래 모양으로 찍어 주십시오(값은 예입니다).

```text
hv-sem     A: lots=233 steps=3569 recipes=410   B: recipes=398 params=5120 missing=12
veritysem  A: lots=92  steps=1200 recipes=180   B: recipes=0   params=0    missing=180
provision  A: lots=275 steps=7564 recipes=640   B: recipes=611 params=8800 missing=29
```

- `A:`의 `recipes`는 표 A의 distinct `recipe_id` 수입니다.
- `B:`의 `missing`은 표 A에는 있는데 표 B에 파라미터가 하나도 없는 recipe 수입니다.
  조인 키 문자열이 어긋나면 이 숫자가 커집니다.

## 5. 답안지

```text
Q1:
Q2:
Q3:
Q4:
Q5:
Q6:
Q7:
Q8:
Q9:
Q10:
hv-sem     A: lots=    steps=    recipes=    B: recipes=    params=    missing=
veritysem  A: lots=    steps=    recipes=    B: recipes=    params=    missing=
provision  A: lots=    steps=    recipes=    B: recipes=    params=    missing=
chg_tm / source_tm 시간대 (KST/UTC):
```
