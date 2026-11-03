# device-statistics 계열 확장 — 2차 확인 요청 (Home → Office, 2026-11-04)

- 작성일: 2026-11-04입니다.
- 수신자: 사무실에서 SKEWNONO 데이터를 추출·적재하는 Office agent입니다.
- 배경: 1차 질문지(2026-11-02)의 회신을 받아 Home에 반영했습니다. skip_yn `D`,
  `_CAP_BASE`, `_S`/`_SE` Sample 규칙, 표 A 정체성(oper_desc 포함), 계열별 주간
  스냅샷 위치, 계열 표식 only_normal 규칙이 모두 들어갔습니다.
- 이 문서는 그 회신으로 새로 생긴 질문과, 1차에서 `?`로 남은 칸만 묻습니다.

## 1. 질문

아래 질문과 끝의 답안지만 회신해 주시면 됩니다. A는 "Home 가정이 맞다"이고, `?`는
"모름"입니다. **계열별** 질문은 HV-SEM, VeritySEM, Provision 순서로 세 글자를 적습니다.
VeritySEM·Provision 칸은 측정 결과 파싱 전이면 `?`로 두셔도 됩니다.

### 지금 답할 수 있는 것

- **R1.** only_normal 규칙 F는 "스텝명의 마지막 토큰이 그 계열 표식 중 하나"다.
  HV-SEM 표식은 `HV` 하나뿐이다(`CD`는 넣지 않음).
  A = 맞음 / B = 다름(한 줄로)
- **R2.** Q10에서 같은 recipe의 파라미터가 장비마다 다를 때 표 B에 쓸 대표는?
  A = 가장 최근에 잰 장비 / B = 측정 건수가 가장 많은 장비 / C = 장비별로 따로 둠(표 B에 `eqp_id` 추가)
- **R3.** HV-SEM 빈 Parameter 행(4.9%)을 표 B에서 어떻게 두는가.
  A = 빈 이름 그대로 둠(param_seq 유지) / B = 빼고 param_seq를 다시 매김 / C = 빼되 param_seq는 원래 값 유지
- **R4.** HV-SEM `param_type`을 이름에서 파생하는 규칙이 CD-SEM과 같다(이름 앞 `WAFER`/`LEVEL`/`EDGE`).
  A = 같음 / B = 다름(한 줄로) / ?
- **R5.** 카탈로그에 없는 device(Q11)의 카탈로그 행은?
  A = 사무실이 같은 컬럼으로 보충 행을 제공 / B = Home이 "카탈로그 없음"으로 표시 / ?
- **R6.** CD-SEM 경로(M fab `ebeam_tas_lot_hist`)도 90일 창을 `dt.keyword`로 바꿔야 한다.
  A = 바꿔야 함 / B = CD-SEM은 `event_tm` 유지 / ?
- **R7.** CD-SEM index(`sknn-planstep-r3-cd`)에도 `_CAP_BASE` prod_id가 있다.
  A = 없음 / B = 있음 / ?
- **R8.** CD-SEM index의 skip_yn에도 `D`가 있다.
  A = 없음(Y / N / 빈 값) / B = 있음 / ?

### 파싱 후 답할 것 (VeritySEM·Provision 두 글자)

1차 질문지와 같은 질문이고, HV-SEM 칸은 이미 받았으므로 두 글자만 적습니다.

- **R9.** (Q4) `param_type` — A = 원천에 종류 column 있음 / B = 이름에서 파생 / C = 종류 개념 없음
- **R10.** (Q5) 포인트 수가 (recipe, 파라미터)마다 하나로 정해짐 — A = 정해짐 / B = 측정마다 다름
- **R11.** (Q6) mother/son 구분 — A = 있음 / C = 없음
- **R12.** (Q15) Dummy·Align이 맨 앞 — A = 맞음 / B = 다른 위치에도 옴 / C = 없음

### 숫자 (계열마다 한 줄)

- **N1.** 표 A lots의 R3 / M fab 내역, skip `D` 비율, `_CAP_BASE` device 수, 카탈로그 밖
  device 수, `_DENSE` recipe 수, AVIS/ICANS step 수입니다.
- **N2.** 표 A~D가 놓인 이름(Q8 A+B)입니다. 표마다 Redis key 또는 OpenSearch index 이름을
  적어 주십시오.

## 2. 답안지

```text
R1:
R2:
R3:
R4:
R5:
R6:
R7:
R8:
R9:     (Verity/Provision)
R10:    (Verity/Provision)
R11:    (Verity/Provision)
R12:    (Verity/Provision)
hv-sem     r3_lots=    m_lots=    D=  %  cap_lots=    off_catalog=    dense=    avis_icans=
veritysem  r3_lots=    m_lots=    D=  %  cap_lots=    off_catalog=    dense=    avis_icans=
provision  r3_lots=    m_lots=    D=  %  cap_lots=    off_catalog=    dense=    avis_icans=
표 A:
표 B:
표 C:
표 D:
```

파싱 후 VeritySEM·Provision 표 C 숫자는 1차 질문지 5절과 같은 한 줄 모양으로 다시 찍어 주십시오.
