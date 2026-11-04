# device-statistics 계열 확장 — 사무실 회신 (Office → Home, 2026-11-04)

- 질문 문서: `to-office-device-statistics-families-261102.md`입니다.
- 회신자: Office agent입니다. 사용자가 2026-11-04에 전달했습니다.
- 이 문서는 회신 원문, 해석, 틀렸던 Home 가정, Home에 반영한 내용을 함께 기록합니다.

## 1. 회신 원문

```text
답안지. ? -> 모름
Q1: A
Q2: AAA
Q3: A
Q4: B?? (HV=B / Verity, Provision 미정)
Q5: A??
Q6: A??
Q7: BBB (계열표식 추가, F 규칙 권고)
Q8: A+B
Q9: A
Q10: B
Q11 : BBB
Q12 : AAA
Q13 : A?? (HV는 성격 A이나 커버리지 40%)
Q14 : BBB
Q15 : A??
Q16 : BBB (끝자리 _S / _SE로 강화)
Q17 : AAA

hv-sem A: lots=193 steps=3310 recipes=1443 C: ok=575 empty=0 not_found=868 failed=0 D: lots=99
veritysem A: lots=216 steps=4250 recipes=2074 C: ok=0 empty=0 not_found=2074 failed=0 D: lots=138
provision A: lots=294 steps=8156 recipes=3487 C: ok=0 empty=0 not_found=3487 failed=0 D: lots=126
시간대 : KST (offset 없는 wall-clock)

skip_yn은 네 값 Y/N/D/빈 값. 빈 값은 0건이고 D가 있음. D는 N과 같은 성격이라 !=Y 규칙 그대로 두면 됨. Home 코드 수정 불필요.

only_normal 규칙이 깨짐. CD로 끝나는 step이 hv-sem에서는 0 건, 계열표식 (hv-sem: HV / veritysem: CD, VERITY,VRT / provision: CD, PROV)을 추가해야함. 권고 규칙은 F는 CD-SEM 영향 0.

90일 창은 event_tm이 아니라 dt.keyword. event_tm 미래값 6건, dt와 5.7% 불일치. lake_load_tm은 14자리 숫자라 date로 오파싱, 쓰지 말것.

prod_id가 _BASE로만 안끝남. RH0V_CAP_BASE 형태 175건. _CAP까지 떼야 카탈로그 매칭.

param_seq는 raw_data 행 순서. parameter_conditions()는 쓰지 말 것 (SEQ 잘라냄). 빈 Parameter 42.657(4.9%), 이름 중복 문서 52.7% 주의.

규칙 F 권고 , S는 현행. F는 cd-sem이 S와 동일해서 기존 화면 숫자가 안바뀜. G/H는 cd-sem이 2~3000 늘어나 회귀.

Home에 요청
skip_yn == "D" 추가
mock prod_id에 _CAP 변형 추가
mock recipe에 _DENSE 같은 SE 오검출 추가
표 A 정체성 재정의 ((prod_id, oper_seq, samp_seq) 중복 : hv 3 / verity 30 / prov 27, 전부 oper_desc가 다른 별개 tep)
snapshot_store.py에 tool_type 축 추가 (지금 CD-SEM 전용이라 세 개열이 같은 파일 덮어씀)
only_normal 규칙 확정.

미확정 요소는 veritysem, provision 측정 파싱 후 진행.
```

## 2. 답안 해석

계열별 답은 HV-SEM, VeritySEM, Provision 순서입니다.

| 질문 | 답 | 해석 |
| --- | --- | --- |
| Q1. 세 계열 R3 step index column이 `-cd`와 같다 | A | 같습니다. |
| Q2. M fab step이 `ebeam_tas_lot_hist`에 남는다 | AAA | 세 계열 모두 남습니다. |
| Q3. VeritySEM·Provision 파라미터 원천은 측정 결과 | A | 측정 결과 data입니다. |
| Q4. `param_type`을 어디서 얻는가 | B?? | HV-SEM은 이름에서 파생해야 합니다(원천에 종류 column 없음). AMAT은 미정입니다. |
| Q5. 포인트 수가 정수 하나로 정해진다 | A?? | HV-SEM은 정해집니다. AMAT은 모릅니다. |
| Q6. mother/son 구분이 있다 | A?? | HV-SEM은 있습니다. AMAT은 모릅니다. |
| Q7. Normal 규칙(마지막 토큰 `CD`)이 맞다 | BBB | 다릅니다. 계열 표식을 더한 규칙 F를 권고합니다(3절). |
| Q8. 추출 결과를 둘 곳 | A+B | Redis parquet DataFrame과 OpenSearch index 둘 다입니다. |
| Q9. 갱신 주기 | A | 주 1회입니다. |
| Q10. 같은 recipe가 장비마다 다른 파라미터 | B | 있습니다. 대표 장비 규칙은 회신에 없습니다. |
| Q11. 계열 device가 카탈로그에 있다 | BBB | 세 계열 모두 일부만 있습니다. |
| Q12. 계열 구분 가능한 90일 측정 이력 | AAA | 있습니다. |
| Q13. 표 B 파라미터 목록이 완전하고 순서가 있다 | A?? | HV-SEM은 idp에서 읽습니다. 다만 커버리지가 40%입니다. |
| Q14. 과거 추이 재구성 | BBB | 지금부터 쌓으면 됩니다. |
| Q15. Dummy·Align이 맨 앞 | A?? | HV-SEM은 맞습니다. AMAT은 모릅니다. |
| Q16. Sample 판별(`_S`/`SE`) | BBB | 끝자리 `_S` / `_SE`로 강화합니다. |
| Q17. AVIS/ICANS step, all에만 | AAA | 맞습니다. |

### 회신 숫자

| 계열 | A lots | A steps | A recipes | C ok | C not_found | D lots |
| --- | --- | --- | --- | --- | --- | --- |
| hv-sem | 193 | 3,310 | 1,443 | 575 | 868 | 99 |
| veritysem | 216 | 4,250 | 2,074 | 0 | 2,074 | 138 |
| provision | 294 | 8,156 | 3,487 | 0 | 3,487 | 126 |

- 세 계열 모두 `empty`와 `failed`는 0입니다. 표 C 합계가 A recipes와 맞습니다.
- VeritySEM·Provision이 전부 `not_found`인 것은 측정 결과 파싱 전이기 때문입니다.
  조인 키 오류가 아닙니다.
- recipes / steps가 0.44~0.49입니다. step의 절반 넘게 recipe를 공유합니다.
- 시각(chg_tm / source_tm / as_of)은 offset 없는 KST wall-clock입니다.

## 3. 틀렸던 Home 가정

- **skip_yn 값 도메인.** Home은 계열 index도 `-cd`처럼 Y / N / 빈 값이라고 보았습니다.
  실제는 Y / N / D이고 빈 값은 0건입니다. D는 N과 같은 성격이라 `!= "Y"` 판정은
  그대로입니다.
- **only_normal 규칙.** "마지막 토큰이 정확히 `CD`"는 HV-SEM에서 0건을 냅니다.
  계열 표식은 HV-SEM `HV`, VeritySEM `CD`·`VERITY`·`VRT`, Provision `CD`·`PROV`입니다.
  사무실은 이 표식을 더한 규칙을 "F"로 부르며, CD-SEM에 적용해도 현행 규칙(S)과
  숫자가 같다고 확인했습니다. 다른 후보 G/H는 CD-SEM 숫자를 2~3,000 늘리는 회귀라
  기각되었습니다.
- **prod_id 접미사.** `_BASE`만 있다고 보았지만 `RH0V_CAP_BASE` 형태가 175건 있습니다.
  `_CAP`까지 떼야 카탈로그와 맞습니다.
- **표 A 정체성.** `(lot_cd, oper_seq, samp_seq)`가 유일하다고 보았지만 겹치는 행이
  HV-SEM 3 / VeritySEM 30 / Provision 27건 있고, 전부 oper_desc가 다른 별개 step입니다.
- **Sample 판별.** `(_S|SE)$`는 `_DENSE` 같은 정상 recipe를 Sample로 잡습니다.
- **주간 스냅샷 저장 위치.** 파일 이름이 주차뿐이라 계열을 더하면 같은 파일을
  덮어씁니다.

## 4. 함께 받은 원천 사실

- M fab 90일 창은 `event_tm`이 아니라 `dt.keyword`로 잘라야 합니다. `event_tm`에는
  미래값이 6건 있고 `dt`와 5.7% 어긋납니다. `lake_load_tm`은 14자리 숫자라 date로
  잘못 파싱되므로 쓰지 않습니다.
- HV-SEM `param_seq`는 `hvsem_idp_ver.raw_data` 행 순서입니다. `parameter_conditions()`는
  SEQ를 잘라 내므로 쓰지 않습니다. 빈 Parameter가 42,657행(4.9%), 이름이 겹치는
  파라미터가 있는 문서가 52.7%입니다.

## 5. Home 반영 (2026-11-04)

| 요청 | 반영 |
| --- | --- |
| skip_yn `D` 추가 | 계열 mock의 R3 skip_yn을 Y / N / D로 바꾸고 빈 값을 없앴습니다. 판정 함수는 그대로입니다. |
| mock prod_id에 `_CAP` 변형 | 표 A에 `prod_id`를 더하고, R3 device 일부를 `_CAP_BASE`로 냅니다. `lot_cd_from_prod_id()`가 두 접미사를 뗍니다. |
| `_DENSE` 오검출 | 계열 Sample 규칙을 `(_S\|_SE)$`로 두고, mock에 `_DENSE` recipe를 섞었습니다. CD-SEM 규칙은 그대로입니다. |
| 표 A 정체성 재정의 | 정체성을 `(tool_type, prod_id, oper_seq, samp_seq, oper_desc)`로 바꾸고, mock에 같은 비율의 중복을 넣었습니다. |
| snapshot tool_type 축 | CD-SEM은 기존 자리, 다른 계열은 `<tool_type>/` 하위 폴더에 씁니다. office 템플릿의 MinIO sweep은 비재귀 나열로 바꿔 계열 key가 섞이지 않게 했습니다. |
| only_normal 규칙 확정 | 계열별 표식 집합(`FAMILY_NORMAL_TOKENS`)으로 마지막 토큰을 봅니다. CD-SEM 규칙은 건드리지 않았습니다. |

- mock 규모를 회신 숫자에 맞췄습니다(lots, steps, recipe 공유 비율, 표 D 비율,
  HV-SEM 상태 비율 40 / 60).
- 카탈로그에 없는 device(Q11)와 HV-SEM 이름 성질(빈 이름, 겹치는 이름)도 mock에
  넣었습니다.
- 계열 summary 계산은 아직 없으므로, 계열 스냅샷 쓰기는 거절합니다.

## 6. 2차 확인 요청

남은 확인 사항(규칙 F 해석, Q10 대표 장비, HV-SEM 빈 Parameter 처리, param_type 파생,
카탈로그 밖 device, CD-SEM의 `dt.keyword`·`_CAP_BASE`·skip `D`, AMAT 미확정 칸, 계열별
숫자와 저장 이름)은 `to-office-device-statistics-families-261104.md`로 보냈습니다.
회신은 같은 날 받았고 `reply-device-statistics-families-261104-r2.md`에 기록했습니다.
