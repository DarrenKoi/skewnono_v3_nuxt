# device-statistics 계열 확장 — 사무실 4차 회신 (Office → Home, 2026-11-04)

- 질문 문서: `to-office-device-statistics-families-261104-r4.md`입니다.
- 앞선 회신 기록: `reply-device-statistics-families-261104.md`(1차), `-r2.md`(2차),
  `-r3.md`(3차)입니다.
- 회신자: Office agent입니다. 사용자가 2026-11-04에 전달했습니다.
- 이 문서는 회신 원문, 해석, 틀렸던 Home 가정, Home에 반영한 내용을 함께 기록합니다.

## 1. 회신 원문

```text
T1: A(-verity), T2: A (Y=skip), T3 : A field=fac_id
T4: B(modified) T5: A ( Home 계산) T6: A (R3)
V1 veritysem ( 없음) / provision CD2_PROV=12
V2 -cd det_fac_id R4=98 device, R4 전용 = 0
V3 하한=20260806 문서 수 =1434819
V4 raw 기준 57179 / 515 / Y (화면 기준 18794 / 61)
V5 bridge lot_id 321460 -> 322840

T4가 틀렸습니다. 3차 S3의 가장 최근 문서는 version이 아니라 modified 였습니다.
T2는 A가 맞습니다.
V4는 두 기준으로 답했습니다. R3 all이 모호했습니다.

3차 서술 정정
-cd의 R4 전용 device는 0개입니다.

새 발견
R7QA/R7QC의 fab이 두 index에서 어긋납니다. 표 A det_fac_id는 R4, 표 D fac_id는 R3, fac_id료 A <->D를 조인하면 같은 device가 두 fab으로 갈립니다.
```

## 2. 답안 해석

| 질문 | 답 | 해석 |
| --- | --- | --- |
| T1. VeritySEM index 이름은 `-verity` | A | `sknn-planstep-r3-verity`입니다. 2026-10-27 기록의 `-verify`는 오기였습니다. |
| T2. `-cd` skip_yn `"Y"`는 skip | A | 맞습니다. 실측 Y 47.7%도 skip입니다. |
| T3. `hvsem_idp_ver`에 fab field | A | `fac_id`입니다. |
| T4. "가장 최근 문서"는 `version` 최대 | B | `modified` 기준입니다. |
| T5. 표 B~D는 Home 어댑터가 계산 | A | 사무실은 적재하지 않습니다. |
| T6. R7QA / R7QC의 `ebeam_tas_lot_hist` fab_id | A | `R3`입니다. 표 A의 det_fac_id `R4`와 어긋납니다(3절). |

### 값

| 항목 | 값 |
| --- | --- |
| V1. 붙은 표식 꼬리 | VeritySEM 없음 / Provision `CD2_PROV` 12 step |
| V2. `-cd` det_fac_id | R4 행을 가진 device 98개, R4 전용 device 0개 |
| V3. `cp` 뒤 90일 창 | 하한 `20260806`, 문서 1,434,819건 |
| V4. `cp` 뒤 R3 all | raw 기준 total_recipe 57,179 / device 515 / `_CAP_BASE` 스텝 있음. 화면 기준 18,794 / 61 |
| V5. bridge lot_id | 321,460 → 322,840 |

- V3으로 창이 살아났습니다. 3차 회신의 하한 `"20260806"` 1,434,084건과 거의 같습니다.
- V4는 "R3 all"이 모호해 두 기준으로 답했습니다. raw는 planstep 원천 전체, 화면은 목록 필터
  (최근 활동 lot과 카탈로그의 교집합)를 거친 값으로 읽었습니다. raw total_recipe 57,179는
  창이 없던 3차 N4 "후" 값과 같습니다. R3 planstep 경로는 90일 창을 쓰지 않으므로
  맞는 결과입니다. device는 516에서 515로 하나 줄었습니다.
- V5는 bridge가 `event_tm`에서 `dt.keyword`로 바뀌며 lot_id가 1,380개(0.4%) 늘었다는
  뜻입니다.

## 3. 틀렸던 Home 가정

- **최근 문서 기준.** Home은 `version` 최대로 보았습니다. `modified`입니다.
- **VeritySEM index 이름.** Home 기록은 `-verify`였습니다. `-verity`입니다.
- **3차 회신 기록의 `-cd` det_fac_id.** "R3 밖의 값이 있다"만 적었습니다. R4 행을 가진
  device는 98개지만 R4 전용 device는 없습니다.
- **표 A ↔ D 조인.** Home 계약은 두 표 모두 `fac_id`를 가져 (fac_id, lot_cd) 조인이 자연스러워
  보였습니다. R7QA / R7QC는 표 A에서 R4, 표 D에서 R3이라 그렇게 조인하면 같은 device가
  두 fab으로 갈립니다.

## 4. Home 반영 (2026-11-04)

| 회신 | 반영 |
| --- | --- |
| T1 | datatables의 index 이름을 `-verity`로 고쳤습니다. 코드에는 이 이름이 아직 없습니다. |
| T3·T4 | 계약 `FamilyParamRow`와 datatables에 "fab = idp `fac_id`, 최근 = `modified`"를 적었습니다. |
| T5 | 바꿀 것이 없습니다. 3차 반영의 "매번 계산"과 같습니다. |
| T6·새 발견 | 계약 `FamilyActivityRow`에 "표 A와는 (tool_type, lot_cd)로 잇고 fac_id를 조인 키에 넣지 않는다"를 적었습니다. mock은 R4 lot을 표 D에 fac_id `R3`으로 냅니다. 테스트가 이 어긋남을 고정합니다. |
| V1 | Provision 표식에 `CD2_PROV`를 더했습니다. mock은 약 14 step을 냅니다. |
| V2 | datatables에만 적었습니다. CD-SEM 어댑터는 det_fac_id로 거르지 않습니다. |
| V3~V5 | datatables에 확인 값으로 적었습니다. |

## 5. 남은 확인

5차 질문지로 보냈고, 회신은 `reply-device-statistics-families-261105.md`에 기록했습니다.

- R9~R12는 AMAT 측정 결과 파서가 나온 뒤에 받습니다.
- 계열 화면과 office 어댑터를 만들 때 표 B~D를 원천에서 계산합니다. 그때 V4 화면 기준
  숫자와 맞춰 봅니다.
