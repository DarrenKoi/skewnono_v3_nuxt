# device-statistics 계열 확장 — 사무실 6차 회신 (Office → Home, 2026-11-05)

- 질문: 5차 회신 기록 `reply-device-statistics-families-261105.md` 5절의 첫 항목
  "표 A → 표 B를 이을 때 fab_name을 어디서 얻는가"입니다. 별도 질문지 없이 전달했습니다.
- 회신자: Office agent입니다. 사용자가 2026-11-05에 전달했습니다.
- 이 문서는 회신 원문, 해석, 틀렸던 Home 가정, Home에 반영한 내용을 함께 기록합니다.

## 1. 회신 원문

```text
1. Table A의 fab은 det_fac_id이고, 그 값은 sem_list.fab_name (툴의 위치)입니다.
planstep index에는 fab_name 필드가 없습니다.

2. 그래서 표 A의 fab은 det_fac_id 그대로이고, 그 값이 위치(fab_name)입니다. 합성 불필요.

3. sem_list 조인 없이 det_fac_id 그대로 써도 됨.
```

## 2. 해석

- planstep index의 `det_fac_id`는 fac 단위 코드가 아니라, 그 step을 잰 툴의 위치인
  `sem_list.fab_name`입니다. R3 fac 안의 R4 위치 툴로 잰 step은 `R4`로 나옵니다.
- planstep index에는 `fab_name` field가 따로 없습니다. `det_fac_id` 값이 곧 fab_name이므로,
  표 A → 표 B는 `det_fac_id`를 표 B의 `fab_name`과 그대로 잇습니다. 합성도 sem_list 조인도
  필요 없습니다.
- 4차 회신의 "R7QA / R7QC fab 어긋남"도 이것으로 설명됩니다. 표 A의 `R4`는 툴 위치
  fab_name이고, 표 D의 `R3`은 `ebeam_tas_lot_hist`의 fab_id(fac 단위)입니다. 두 값은
  단위가 다르므로, 4차 결정대로 A ↔ D는 lot_cd로만 잇습니다.

## 3. 틀렸던 Home 가정

- **det_fac_id의 뜻.** Home datatables는 "fab 대표 코드"(fac 단위)로 적었습니다. 툴 위치
  fab_name 단위입니다.
- **표 A → 표 B의 fab_name.** Home mock(5차 반영)은 step 장비의 sem_list fab_name을 조인해
  붙였습니다. planstep step은 `det_fac_id`를 그대로 쓰면 됩니다.

## 4. Home 반영 (2026-11-05)

| 항목 | 반영 |
| --- | --- |
| 계약 | `FamilyStepRow.fac_id`에 "planstep 행은 det_fac_id = 툴 위치 fab_name, M fab 행은 lot_hist fab_id(fac 단위)"를 적었습니다. `FamilyActivityRow` 주석의 어긋남 설명을 단위 차이로 고쳤습니다. |
| mock 표 A | planstep step의 `det_fac_id`를 그 step 툴의 위치로 맞췄습니다. R4 lot은 R4에 있는 툴로, 나머지는 R3에 있는 툴로 잽니다. |
| mock 표 B | planstep step은 `det_fac_id`를 fab_name으로 그대로 쓰고, fac_id만 sem_list에서 찾습니다(R4 → R3). M fab step은 원천의 fab_name 대역으로 step 장비의 sem_list fab_name을 씁니다. |
| datatables | `planstep_r3.txt`의 `det_fac_id` 설명을 고쳤습니다. |
| 테스트 | planstep `det_fac_id`가 툴의 sem_list fab_name과 같은지, 표 B의 fab_name과 바로 맞는지 고정했습니다. |

- Home mock의 sem_list에는 R4 위치 Provision 툴이 없습니다. 그래서 Provision의 R4 lot만
  R3 툴로 재되 `det_fac_id`는 `R4`로 둡니다. 테스트에서 이 예외를 따로 표시했습니다.

## 5. 남은 확인

후속 결정(user-confirmed 2026-11-05): 우리는 datatables의 `fab_name` / `det_fac_id`를 쓰고
fac 단위 `fac_id`는 대부분 쓰지 않습니다. 그래서 계열 표 A·B의 fab은 `fab_name` 하나로
바꿨습니다. 표 A의 field 이름을 `fac_id`에서 `fab_name`으로 바꾸고(planstep 행은 `det_fac_id`
값), 표 B에서는 `fac_id`를 뺐습니다. 아래 첫 항목이었던 "표 B의 `fac_id`가 R4 위치 툴에서
`R3`인지"는 물을 필요가 없어졌습니다. 표 D는 `ebeam_tas_lot_hist`의 fac 단위 fab_id로
계산되어 `fac_id`를 그대로 둡니다.

- fab_name까지 넣어도 남는 8 그룹의 동률 처리입니다.
- R9~R12는 AMAT 측정 결과 파서가 나온 뒤에 받습니다.
