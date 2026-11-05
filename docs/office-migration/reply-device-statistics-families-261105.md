# device-statistics 계열 확장 — 사무실 5차 회신 (Office → Home, 2026-11-05)

- 질문 문서: `to-office-device-statistics-families-261105.md`입니다.
- 앞선 회신 기록: `reply-device-statistics-families-261104.md`(1차), `-r2.md`(2차),
  `-r3.md`(3차), `-r4.md`(4차)입니다.
- 회신자: Office agent입니다. 사용자가 2026-11-05에 전달했습니다.
- 이 문서는 회신 원문, 해석, 틀렸던 Home 가정, Home에 반영한 내용을 함께 기록합니다.

## 1. 회신 원문

```text
U1: A (HV-SEM 한정 - -hv recipe 1449 중 575 exact. Verity/Provision은 hvsem_idp_ver 매칭 0. Verity/Provision은 별도 만들어야 함.
U2: A, U3: A (단 modified는 mapping data라 range 질의가 9시간 밀림)
U4: B - 같은 (recipe,fac_id,modified) 그룹 5614 / 문서 11228. 원인은 fab_name 누락, writer doc_id키로 넓히면 8그룹만 남음
U5: A, U6: A (단 18794는 distinct recipe가 아니라 device별 합; 오늘 distinct 14123 / 합 17974
U7: A -> R9~R12 비움
W1: Y 86.98 / 71.52 / 93.56% (mock 15% 가정과 크게 어긋남)
W2: 851/2168/1150 steps, device당 1~71 / 1~107 / 1~134
W3: multi_fab_recipes 3198 / differ 234

표 B에 fab_name을 넣을 것 (full_name, fac_id)로 묶으면 5606그룹이 ite 만 다른 채 뭉침.
total_recipe 단위를 계약 주석에 고정 : device 행 단위 (합계 17974), 화면 합계 18794 아님.
M fab 장비는 어떤 planstep 계열 index에도 없음. 그래서 표 A <-> 표 D는 device로 안 이어지고 lot_cd 로만 이어짐 -  4차 결졍 재확인

첫 측정이 sort: _doc 페이지네이션으로 20% 틀렸고, composite aggregation으로 다시 쟀습니다.
```

## 2. 답안 해석

| 질문 | 답 | 해석 |
| --- | --- | --- |
| U1. 표 A recipe_id = `hvsem_idp_ver.full_name` | A (HV-SEM 한정) | HV-SEM은 그대로 같습니다. `-hv` recipe 1,449 중 575가 정확히 맞습니다. VeritySEM·Provision recipe는 `hvsem_idp_ver`에 하나도 없어 AMAT 원천을 따로 만들어야 합니다. |
| U2. idp `fac_id`는 문자열 하나 | A | 맞습니다. |
| U3. `modified`는 offset 없는 KST wall-clock | A + 단서 | 맞습니다. 다만 mapping이 date라 range 질의가 9시간 밀립니다. |
| U4. 같은 (recipe, fac_id, modified) 문서 없음 | B | 5,614 그룹 / 11,228 문서가 겹칩니다. 원인은 fab_name 누락이고, 적재 쪽 doc_id 키로 넓히면 8 그룹만 남습니다. |
| U5. 계열 판정은 lot_hist `eqp_id` → sem_list `eqp_model_cd` | A | 맞습니다. |
| U6. V4 "화면 기준"은 목록 필터 뒤 R3 숫자 | A + 단서 | 맞습니다. 다만 18,794는 distinct recipe가 아니라 device별 합입니다. 오늘 값은 distinct 14,123 / 합 17,974입니다. |
| U7. AMAT 측정 결과 파서 | A | 아직 없습니다. R9~R12는 비웠습니다. |

### 값

| 항목 | hv-sem | veritysem | provision |
| --- | --- | --- | --- |
| W1. skip_yn Y 비율 | 86.98% | 71.52% | 93.56% |
| W2. M fab step 수 | 851 | 2,168 | 1,150 |
| W2. device당 M fab step | 1~71 | 1~107 | 1~134 |

- W3(HV-SEM): 둘 이상의 `fac_id`에 걸친 recipe 3,198, 그중 fab마다 파라미터가 다른 recipe
  234(7.3%)입니다. 표 A의 recipe 1,449보다 많으므로 idp 원천 전체의 숫자로 읽었습니다.

### 함께 받은 사항

- 표 B에 `fab_name`을 넣으라는 요청입니다. (full_name, fac_id)로 묶으면 5,606 그룹이 한 값만
  다른 채 뭉칩니다. 원문의 "ite"는 오타로 보이며, U4의 원인(fab_name 누락)과 그룹 수
  (5,614 − 8 = 5,606)로 보아 fab_name을 뜻한다고 읽었습니다.
- `total_recipe`의 단위를 계약 주석에 "device 행 단위(합계 17,974)"로 고정하라는 요청입니다.
- M fab 장비는 어느 planstep 계열 index에도 없습니다. 그래서 표 A ↔ 표 D는 장비로 이어지지
  않고 lot_cd로만 이어집니다. 4차 결정을 다시 확인한 것입니다.
- 첫 측정은 `sort: _doc` 페이지네이션이라 약 20% 틀렸고, composite aggregation으로 다시 잰
  값이 위 숫자입니다.

## 3. 틀렸던 Home 가정

- **표 B 한 벌의 키.** Home은 4차 반영에서 (recipe, fac_id)로 두었습니다. fab_name까지
  넣어야 합니다.
- **계열 skip 비율.** Home mock은 Y 15%였습니다. 실물은 72~94%라 계열 Normal 버킷이 훨씬
  작습니다.
- **M fab step 수.** Home mock은 device당 3~12로 고르게 두었습니다. 실물은 1부터 100을 넘는
  긴 꼬리입니다.
- **fab마다 다른 recipe 비율.** Home mock은 여러 fab에 걸친 recipe의 절반으로 두었습니다.
  7.3%입니다.
- **total_recipe 합계.** Home 기록(4차 해석)은 18,794를 recipe 수처럼 다뤘습니다. device별
  합이고, 공유 recipe가 중복으로 셉니다.

## 4. Home 반영 (2026-11-05)

| 회신 | 반영 |
| --- | --- |
| U1·U7 | mock docstring과 datatables에 적었습니다. AMAT 원천은 파서가 나온 뒤에 다룹니다. |
| U2·U3 | datatables `idp_ver.txt`에 `fac_id` 모양과 `modified` range 9시간 밀림을 적었습니다. |
| U4·fab_name 요청 | 계약 `FamilyParamRow`에 `fab_name`을 더하고 정체성을 (tool_type, recipe_id, fac_id, fab_name, param_seq)로 바꿨습니다. mock은 step 장비의 sem_list fab_name을 붙여, 한 fac_id 안에서 fab_name으로 갈리는 recipe를 냅니다. 테스트가 이를 고정합니다. |
| U6·total_recipe 요청 | 계약 `SummaryRow.total_recipe`에 "device 행 단위, 합 17,974 / distinct 14,123" 주석을 달았습니다. |
| W1 | 계열 mock skip Y를 계열별 실측(86.98 / 71.52 / 93.56%)으로 바꿨습니다. CD-SEM mock과는 따로 둡니다. |
| W2 | M fab step 수를 device당 1부터 긴 꼬리(평균 13.3 / 29.3 / 16.2, 최대 71 / 107 / 134)로 바꿨습니다. mock 합계는 895 / 1,666 / 1,039 step입니다. 분포 꼬리가 길어 VeritySEM이 실물보다 적게 나왔습니다. |
| W3 | fab마다 다른 비율을 7.3%로 맞췄습니다. |
| `_doc` 페이지네이션 | datatables README 표기 규칙과 `idp_ver.txt`에 적었습니다. |

- 이번 반영 중 R4 lot 두 개가 무작위 표본과 겹치면 planstep lot이 하나 줄던 mock 버그를
  고쳤습니다(VeritySEM 216 → 215로 드러남).
- `family_rules.py`의 토큰 → 종류 대응 주석에서 OFFICE-VERIFY를 지웠습니다(4차 S5 확인분).

## 5. 남은 확인

첫 항목은 같은 날 6차 회신으로 답을 받았고 `reply-device-statistics-families-261105-r2.md`에
기록했습니다(planstep `det_fac_id`가 곧 툴 위치 fab_name).

- 표 A → 표 B를 이을 때 fab_name을 어디서 얻는지입니다. 표 A에는 fab_name이 없어 Home mock은
  step 장비의 sem_list fab_name을 씁니다. M fab step은 `ebeam_tas_lot_hist`의 fab_name을 쓸
  수 있지만, R3 planstep step의 fab_name은 정해지지 않았습니다.
- fab_name까지 넣어도 남는 8 그룹의 동률 처리입니다.
- R9~R12는 AMAT 측정 결과 파서가 나온 뒤에 받습니다.
