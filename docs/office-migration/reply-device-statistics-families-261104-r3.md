# device-statistics 계열 확장 — 사무실 3차 회신 (Office → Home, 2026-11-04)

- 질문 문서: `to-office-device-statistics-families-261104-r3.md`입니다.
- 앞선 회신 기록: `reply-device-statistics-families-261104.md`(1차),
  `reply-device-statistics-families-261104-r2.md`(2차)입니다.
- 회신자: Office agent입니다. 사용자가 2026-11-04에 전달했습니다.
- 이 문서는 회신 원문, 해석, 틀렸던 Home 가정, Home에 반영한 내용을 함께 기록합니다.

## 1. 회신 원문

```text
S1. dt.keyword 하한 "2026-11-04"는 dt 값 (20260518)보다 작아서 매칭이 안됩니다.
하한 "2026-08-06" 매칭 to 2641395 (index 전체)
하한 "20260806" 1434084
에러 없이 전 기간이 통과합니다. lte로는 반대로 0건. 90일 창을 걸었다고 믿으면서 2022년까지 읽는 상태라 옛 oper_det_desc가 섞입니다.
하한을 strftime("%Y%m%d")로. 지금은 창이 사라져 전 기간을 읽습니다.

S2: A, S3: A, S4: B, S5: A, S6: B, S7: B, S8: ABC, S9: A, S10: B, S11: A, S12:A
N3 -cd skip_yn Y=55249 N=53198 D=7485 total=115932
N4 R3 all total_recipe 전=57145 후=57179 devices 전=513 후=516 _CAP_BASE 스텝=Y
R9~R12 = ? (Verity/Provision)

hv-sem r3_lots=193 m_lots=64 D=83 2.51% cap_lots=3 off_catalog=33 dense=0 avis_icans=1112
veritysem r3_lots=216 m_lots=74 D=310 7.24% cap_lots=3 off_catalog=19 dense=2 avis_icans=68
provision r3_lots=294 m_lots=71 D=116 1.42% cap_lots=3 off_catalog=47 dense=0 avis_icans=1481
표 A: sknn-planstep-r3-hv / -verity / -provision
표 B: 없음 (HV-SEM= hvsem_idp_ver 조회, Verity/Provision 미착수)
표 C: 없음 (HV-SEM=매번 계산, Verity/Provision=전량 not_found)
표 D: 없음 (ebeam_tas_lot_hist dt.keyword 90일 창으로 계산)

S12 _office_meas_hist.py 60일 창. now-60d date math 못 쓰니 날짜 계산해 %Y%m%d.
```

## 2. 답안 해석

| 질문 | 답 | 해석 |
| --- | --- | --- |
| S1. `dt.keyword` 모양은 `YYYY-MM-DD` | B | `YYYYMMDD`입니다(예 `20260518`). Home 하한 `"2026-08-06"`은 모든 dt보다 작아 에러 없이 index 전체(2,641,395건)를 통과시켰습니다. `"20260806"`은 1,434,084건입니다. |
| S2. 표 B에 fab 축 | A | (tool_type, recipe_id, fac_id)마다 한 벌입니다. |
| S3. fab으로도 안 정해지는 7건 | A | 가장 최근 문서의 파라미터입니다. |
| S4. R5 "`_CAP` 3개"의 뜻 | B | R7의 `-cd` 3 device를 가리켰습니다. Home 해석이 틀렸습니다. |
| S5. 토큰 → 종류 대응 | A | EX → EDGE_EX, ED·EDGE → EDGE, WF → WAFER, LV → LEVEL이 맞습니다. |
| S6. 41.1%가 접두사 5.68%를 포함 | B | 별도입니다. 합쳐서 약 46.8%입니다. |
| S7. VeritySEM·Provision에 붙은 표식 꼬리 없음 | B | 있습니다. 꼬리 목록과 step 수는 회신에 없습니다. |
| S8. R7QA / R7QC가 있는 계열 index | ABC | 세 계열 모두입니다. |
| S9. R7QA / R7QC가 `r3_device_grp`에 있음 | A | 있습니다. |
| S10. `-cd` det_fac_id는 R3뿐 | B | 다른 값도 있습니다. 값과 device 수는 회신에 없습니다. |
| S11. AVIS/ICANS 33.6%의 기준 | A | 표 A step 행 비율입니다. |
| S12. 다른 기능의 `ebeam_tas_lot_hist` 창도 `dt.keyword` | A | 바꿉니다. lot_id ↔ lot_cd bridge의 60일 창도 `%Y%m%d` 하한으로 자릅니다. |
| R9~R12 | ? | AMAT 측정 결과 파서가 아직 없습니다. |

### 회신 숫자

| 계열 | planstep lots | M fab lots | skip D | `_CAP_BASE` | 카탈로그 밖 | `_DENSE` | AVIS/ICANS |
| --- | --- | --- | --- | --- | --- | --- | --- |
| hv-sem | 193 | 64 | 83 (2.51%) | 3 | 33 | 0 | 1,112 |
| veritysem | 216 | 74 | 310 (7.24%) | 3 | 19 | 2 | 68 |
| provision | 294 | 71 | 116 (1.42%) | 3 | 47 | 0 | 1,481 |

- `-cd` skip_yn 분포는 Y 55,249 / N 53,198 / D 7,485 / 합 115,932입니다. skip이 47.7%입니다.
  2차 회신의 D 7,458행과 27행 다릅니다(적재가 이어진 차이로 봅니다).
- N4(고친 CD-SEM 어댑터 `cp` 뒤): R3 all total_recipe 57,145 → 57,179, device 513 → 516,
  `_CAP_BASE` 3 device에 스텝이 나옵니다. 이 숫자는 S1 버그(창이 사라진 상태)로 잰 값입니다.
- 표 A는 `sknn-planstep-r3-hv` / `-verity` / `-provision`입니다. 2026-10-27 전달값은 `-verify`였습니다.
- 표 B·C·D는 저장된 곳이 없습니다. 사무실 추출이 매번 계산합니다. B는 HV-SEM이
  `hvsem_idp_ver` 조회이고 AMAT은 미착수, C는 매번 계산(AMAT은 전량 not_found),
  D는 `ebeam_tas_lot_hist`의 `dt.keyword` 90일 창입니다.

## 3. 틀렸던 Home 가정

- **dt 모양.** Home은 `YYYY-MM-DD`로 가정했습니다. 그 하한은 실패하지 않고 창을 없애,
  device-statistics M fab 경로가 2022년까지의 oper_det_desc를 읽게 됩니다. 2차 회신 반영
  커밋에 들어간 버그이고, 사무실이 이미 `cp`한 상태였습니다.
- **R5 `_CAP` 3개.** Home은 카탈로그 밖 device 3개로 읽었습니다. `-cd` 3 device였습니다.
- **HV-SEM 종류 커버리지.** Home mock은 41.1%를 전체 커버리지로 맞췄습니다. 접두사와
  토큰이 따로라 약 46.8%입니다.
- **R4 device.** Home은 어느 계열인지 몰라 계열마다 다른 lot을 R4로 냈습니다. 세 계열
  모두 같은 두 device입니다. `-cd`도 R3 단일 값이 아닙니다.
- **표 A 숫자의 범위.** Home mock은 표 A lots를 R3 + M fab 합으로 보았습니다. planstep
  index만의 값이고 M fab은 따로 셉니다.
- **표 B~D 저장 위치(1차 Q8 A+B).** Home은 Redis parquet과 OpenSearch에 놓인다고
  읽었습니다. 지금은 어디에도 저장되지 않고 매번 계산됩니다.
- **CD-SEM skip 비율.** CD-SEM mock은 skip 15%였습니다. 실물은 47.7%입니다.

## 4. Home 반영 (2026-11-04)

| 회신 | 반영 |
| --- | --- |
| S1 | device-statistics 템플릿의 `_window_floor()`를 `strftime("%Y%m%d")`로 고쳤습니다. 테스트가 8자리 숫자 하한을 고정합니다. |
| S12 | 공용 모듈 `_office_meas_hist`의 lot_id ↔ lot_cd bridge를 `event_tm` `now-60d`에서 `dt.keyword` `YYYYMMDD` 하한으로 바꿨습니다. 이 모듈은 `office.py` 사본이 아니라 `git pull`로 바로 반영됩니다. |
| S2·S3 | 계약 `FamilyParamRow`에 `fac_id`를 더했습니다. mock은 (recipe_id, fac_id)마다 한 벌을 냅니다. 여러 fab에 걸린 recipe를 만들려고 M fab step 15%가 R3 recipe를 쓰고, 그 절반은 뒤 fab의 마지막 파라미터를 뺍니다(두 비율은 지어낸 값). S3의 "가장 최근 문서"는 어댑터 규칙이라 계약 docstring에 적었습니다. |
| S5·S6 | `hv_param_type()`의 대응을 확정으로 표시했습니다. mock HV-SEM 종류 커버리지를 약 47%로 올렸습니다. |
| S7 | 꼬리 목록이 없어 표식은 그대로 두고 OFFICE-VERIFY로 남겼습니다. |
| S8·S9 | 세 계열 mock이 R3 카탈로그의 같은 두 lot을 R4로 냅니다. |
| S10 | datatables에만 적었습니다. CD-SEM 어댑터는 det_fac_id로 거르지 않습니다. |
| S11, 숫자 | 계열 mock 규모를 회신 숫자에 맞췄습니다(planstep lots, 카탈로그 밖 device, `_CAP_BASE` 3, M fab lots, skip D, `_DENSE`, AVIS/ICANS). 표 D lots도 99 / 138 / 126 근처로 맞췄습니다. |
| N3 | CD-SEM mock skip을 Y 47.7% / D 6.5%로 바꿨습니다. Home CD-SEM 화면의 avail_recipe와 Normal 버킷이 줄어듭니다. 화면 막대 서열 테스트에서 mother_normal > only_sample 비교는 뺐습니다. |

- `office.py`는 사용자가 다시 `cp`해야 S1 수정이 반영됩니다. 그 전까지 사무실 CD-SEM M fab
  경로는 전 기간을 읽습니다.

## 5. 남은 확인

- S1 수정 `cp` 뒤 N4를 다시 재야 합니다(창이 살아난 상태의 total_recipe와 device 수).
- S7 꼬리 목록과 step 수, S10 `-cd` det_fac_id의 다른 값과 device 수입니다.
- 표 A index 이름이 `-verity`인지 `-verify`인지 확인해야 합니다.
- 표 B~D를 저장할지는 Home이 정할 일입니다. 지금 회신으로는 office 어댑터가 원천에서
  매번 계산해야 합니다.
- R9~R12는 AMAT 측정 결과 파서가 나온 뒤에 받습니다.
