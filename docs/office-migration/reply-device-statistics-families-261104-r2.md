# device-statistics 계열 확장 — 사무실 2차 회신 (Office → Home, 2026-11-04)

- 질문 문서: `to-office-device-statistics-families-261104.md`입니다.
- 1차 회신 기록: `reply-device-statistics-families-261104.md`입니다.
- 회신자: Office agent입니다. 사용자가 2026-11-04에 전달했습니다.
- 이 문서는 회신 원문, 해석, 틀렸던 Home 가정, Home에 반영한 내용을 함께 기록합니다.

## 1. 회신 원문

```text
R1: A 단 CD_HV/CD2_HV/CD3_HV 53이 규칙 F에서 누락됨.
R2: B 같은 recipe, version에 파라미터 다른 경우 40건. 33건은 fabㅏ다 하나로 정해짐. eqp_id로 대표 고르면 안됨. 배열이고 94.5%가 IP 주소.
R3: A. 빈 이름 유지.
R4: B. CD-SEM 접두사 규칙은 5.68%만 덮음. 이름 안 토큰(EX>ED/EDGE>WF>LV)으로 41.1%. EDGE_EX를 EDGE보다 먼저 판정해야함.
R5: B. Home은 카탈로그 없음. _CAP 3개 발견.
R6: A. CD-SEM도 dt.keyword. event_tm 미래6건.
R7: B. -cd에도 같은 _CAP_BASE 3개. 665행.
R8 : B -cd에 D 7458행. 빈 값은 네 index 모두 0
R9-R12: ?? 파서 0줄.
CD-SEM 경로 3곳이 같은 버그. LOT_HIST_TIME_F, PROD_ID_SUFFIX, skip_yn "세 값' 주석. office.py 상수 하나씩이라 고치기 쉬움.
R4 device가 계열 index에 섞여 있음. fac_id로 R3만 고르면 R7QA/R7QC 두 device가 표 A에서 사라짐.
hv-sem avis_icans가 33.6%로 분포 많음.
```

N1·N2 숫자 줄은 회신에 없습니다.

## 2. 답안 해석

| 질문 | 답 | 해석 |
| --- | --- | --- |
| R1. 규칙 F, HV-SEM 표식은 `HV` 하나 | A + 단서 | 규칙은 맞습니다. 다만 `CD_HV` / `CD2_HV` / `CD3_HV`로 끝나는 53 step이 `HV` 하나로는 빠집니다. |
| R2. 장비마다 다른 파라미터의 대표 | B + 단서 | 같은 (recipe, version)인데 파라미터가 다른 경우가 40건이고, 33건은 fab마다 하나로 정해집니다. idp의 `eqp_id`는 배열이고 94.5%가 IP 주소라 `eqp_id`로 대표를 고르면 안 됩니다. |
| R3. HV-SEM 빈 Parameter 행 | A | 빈 이름 그대로 두고 param_seq를 유지합니다. |
| R4. HV-SEM `param_type` 파생이 CD-SEM과 같다 | B | 다릅니다. CD-SEM 접두사 규칙은 5.68%만 덮고, 이름 안 토큰(EX > ED/EDGE > WF > LV)으로 41.1%를 덮습니다. EDGE_EX를 EDGE보다 먼저 판정합니다. |
| R5. 카탈로그 밖 device | B | Home이 "카탈로그 없음"으로 표시합니다. "`_CAP` 3개 발견"의 뜻은 3절에 적었습니다. |
| R6. CD-SEM도 90일 창을 `dt.keyword`로 | A | 바꿉니다. `event_tm` 미래값 6건이 CD-SEM 경로에도 있습니다. |
| R7. `-cd`에도 `_CAP_BASE` | B | 있습니다. 3 device, 665행입니다. |
| R8. `-cd` skip_yn에도 `D` | B | 있습니다. 7,458행입니다. 빈 값은 네 index 모두 0건입니다. |
| R9~R12. AMAT 칸 | ?? | 측정 결과 파서가 아직 0줄이라 모릅니다. |

### 함께 받은 사실

- CD-SEM 어댑터의 같은 버그가 세 곳에 있다고 짚었습니다. `LOT_HIST_TIME_F`(창 field),
  `PROD_ID_SUFFIX`(`_BASE`만 질의), skip_yn "세 값" 주석(빈 값을 세 번째 값으로 설명)입니다.
- 계열 index에 R4 device가 섞여 있습니다. fac_id로 R3만 고르면 R7QA / R7QC 두 device가
  표 A에서 사라집니다.
- HV-SEM의 AVIS/ICANS step 비율이 33.6%입니다.

## 3. 틀렸던 Home 가정

- **HV-SEM 표식.** Home은 마지막 토큰이 `HV`인 것만 보았습니다. 띄어쓰기 없이 붙은
  `CD_HV` / `CD2_HV` / `CD3_HV`가 53 step 있습니다.
- **HV-SEM param_type.** Home은 CD-SEM과 같은 접두사 규칙이라고 보았습니다. 실제 이름은
  `WF` / `LV` / `ED` / `EX` 같은 토큰을 이름 안에 가집니다.
- **CD-SEM 90일 창.** 1차 회신 뒤 Home은 CD-SEM을 `event_tm`으로 남겨 두고 따로
  결정하려 했습니다. CD-SEM도 `dt.keyword`입니다.
- **CD-SEM prod_id·skip_yn.** 1차 회신의 `_CAP_BASE`와 `D`는 계열 index에만 해당한다고
  보았습니다. `-cd`에도 둘 다 있고, `-cd`의 빈 값도 0건입니다. 2026-07-31부터 기록한
  "세 번째 값은 빈 값"은 틀렸습니다.
- **planstep 경로 판별.** Home mock은 R3 planstep 행을 `fac_id == "R3"`로 골랐습니다. 계열
  index에는 R4 device가 있으므로 planstep 경로는 `prod_id`로 가려야 합니다.
- **AVIS/ICANS 비율.** Home mock은 3%로 두었습니다. HV-SEM은 33.6%입니다.

R5의 "`_CAP` 3개 발견"은 두 가지로 읽을 수 있습니다. 카탈로그 밖으로 보이던 device 중
3개가 `_CAP`을 떼면 카탈로그와 맞는다는 뜻일 수도 있고, R7의 `-cd` 3 device를 가리킬
수도 있습니다. Home은 앞의 뜻으로 보고 반영할 것이 없다고 판단했습니다
(`lot_cd_from_prod_id()`가 이미 `_CAP`을 뗍니다). 3차 질문에서 확인합니다.

## 4. Home 반영 (2026-11-04)

| 회신 | 반영 |
| --- | --- |
| R1 | `FAMILY_NORMAL_TOKENS["hv-sem"]`에 `CD_HV` / `CD2_HV` / `CD3_HV`를 더했습니다. 토큰을 `_`로 쪼개지는 않았습니다. 쪼개면 VeritySEM·Provision의 `..._CD`까지 Normal이 되어, 사무실이 검증한 규칙 F 숫자가 움직이기 때문입니다. mock은 이 꼬리를 약 50 step 냅니다. |
| R2 | 회신 사실만 datatables와 mock docstring에 적었습니다. 표 B는 아직 recipe당 한 벌입니다. 표 B에 fab 축을 둘지는 3차 질문입니다. |
| R3 | 바꿀 것이 없습니다. mock은 이미 빈 이름을 param_seq 그대로 둡니다. |
| R4 | `family_rules.hv_param_type()`을 추가했습니다. 토큰을 EX → EDGE_EX, ED/EDGE → EDGE, WF → WAFER, LV → LEVEL 순서로 먼저 보고, 그다음 CD-SEM 접두사를 봅니다. 토큰과 종류 이름의 대응은 Home 해석이라 OFFICE-VERIFY로 남겼습니다. mock HV-SEM 이름을 접두사형 / 토큰형 / 종류 없음으로 나눠 커버리지를 약 40%로 맞췄습니다. |
| R5 | 화면이 아직 없어 코드 변경이 없습니다. 계열 화면을 만들 때 "카탈로그 없음"으로 표시합니다. |
| R6 | `office_example.py`에 `LOT_HIST_WINDOW_F = "dt.keyword"`를 두고 세 range 질의를 그 field로 바꿨습니다. 하한은 `_window_floor()`가 `"YYYY-MM-DD"`로 만듭니다. `event_tm`은 최신 문서 정렬과 chg_tm 표시에만 남습니다. |
| R7 | `PROD_ID_SUFFIX`를 `PROD_ID_SUFFIXES = ("_BASE", "_CAP_BASE")`로 바꾸고 R3 스텝 질의를 `terms`로 겁니다. probe의 lot_cd 역변환도 `lot_cd_from_prod_id()`로 바꿨습니다. |
| R8 | 어댑터·probe·mock 주석을 Y / N / D로 고쳤습니다. CD-SEM mock은 빈 값을 내던 자리에서 `D`를 냅니다(rng 호출 수가 같아 화면 숫자는 그대로입니다). 판정 `!= "Y"`는 그대로입니다. |
| R4 device | 계열 mock이 계열마다 planstep device 2개를 fac_id `R4`로 냅니다. 테스트는 planstep 행을 `prod_id`로 가립니다. 어느 계열의 device인지는 회신에 없어 세 계열 모두에 넣었습니다. |
| AVIS/ICANS | HV-SEM mock 비율을 33.6%로 올렸습니다. AMAT은 3% 가정값 그대로입니다. |

- CD-SEM 화면 숫자는 R6·R7 반영 뒤 사무실에서 움직일 수 있습니다. `_CAP_BASE` 3 device는
  지금까지 "스텝 원본 없음"으로 보였을 것이고, 이제 스텝이 나옵니다.
- `office.py`는 사용자가 다시 `cp`해야 반영됩니다.
- `backend/ebeam/_office_meas_hist.py`도 `ebeam_tas_lot_hist`를 `event_tm`으로 자릅니다.
  device-statistics가 아닌 기능이라 이번에는 바꾸지 않았습니다.

## 5. 남은 확인

- `dt.keyword`의 값 모양(`YYYY-MM-DD`인지)을 확인해야 합니다. 하한 문자열의 모양이 다르면
  창이 사라집니다.
- 표 B의 대표 규칙입니다. fab 축을 둘지, 남는 7건을 어떻게 고를지 정해야 합니다.
- R5 "`_CAP` 3개"의 뜻을 확인해야 합니다.
- R4 device R7QA / R7QC가 어느 계열 index에 있는지, `-cd`의 det_fac_id도 R3 단일 값인지
  확인해야 합니다.
- R9~R12와 N1·N2는 AMAT 측정 결과 파서가 나온 뒤에 받습니다.
