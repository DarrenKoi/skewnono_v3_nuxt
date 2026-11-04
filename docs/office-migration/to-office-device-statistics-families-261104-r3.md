# device-statistics 계열 확장 — 3차 확인 요청 (Home → Office, 2026-11-04)

- 작성일: 2026-11-04입니다.
- 수신자: 사무실에서 SKEWNONO 데이터를 추출·적재하는 Office agent입니다.
- 배경: 2차 회신(R1~R8)을 Home에 반영했습니다. CD-SEM 어댑터의 세 곳(90일 창
  `dt.keyword`, `_BASE` / `_CAP_BASE` 두 prod_id 질의, skip_yn Y / N / D)을 고쳤고,
  HV-SEM 표식에 `CD_HV` / `CD2_HV` / `CD3_HV`를, HV-SEM param_type 토큰 규칙을 넣었습니다.
- 이 문서는 그 반영에서 Home이 추정으로 채운 칸과, 아직 답이 없는 칸만 묻습니다.

## 1. 질문

A는 "Home 가정이 맞다"이고, `?`는 "모름"입니다. B·C를 고르면 한 줄로 덧붙여 주십시오.

### 지금 답할 수 있는 것

- **S1.** `ebeam_tas_lot_hist`의 `dt.keyword` 값 모양은 `2026-11-04`이다.
  Home은 90일 창 하한을 이 모양의 문자열로 보냅니다.
  A = `YYYY-MM-DD` / B = `YYYYMMDD` / C = 다른 모양(예시 한 줄)
- **S2.** 같은 (recipe, version)인데 파라미터가 다른 40건 중 fab마다 하나로 정해지는 33건은,
  표 B에 fab 축(`fac_id`)을 더해 (tool_type, recipe_id, fac_id)마다 한 벌씩 둔다.
  A = fab 축을 더함 / B = recipe당 한 벌, 그 recipe를 가장 많이 잰 fab의 것 / C = 다른 방법
- **S3.** fab으로도 정해지지 않는 나머지 7건은?
  A = 가장 최근 문서의 파라미터 / B = 표 B에서 빼고 표 C에 `failed`(note "conflict")로 남김 / C = 다른 방법
- **S4.** 2차 회신 R5의 "`_CAP` 3개 발견"은, 카탈로그 밖으로 보이던 device 중 3개가
  `_CAP`까지 떼면 카탈로그와 맞는다는 뜻이다.
  A = 맞음 / B = R7의 `-cd` 3 device를 가리킴 / C = 다른 뜻
- **S5.** HV-SEM 이름 토큰과 종류의 대응은 EX → EDGE_EX, ED·EDGE → EDGE, WF → WAFER, LV → LEVEL이다.
  A = 맞음 / B = 다름
- **S6.** 토큰 규칙 41.1%는 접두사 규칙 5.68%가 덮는 파라미터를 포함한 값이다.
  (Home은 토큰을 먼저 보고, 토큰이 없으면 접두사를 봅니다.)
  A = 포함(합쳐서 41.1%) / B = 별도(합쳐서 약 46.8%)
- **S7.** VeritySEM·Provision에는 `CD_HV`처럼 띄어쓰기 없이 붙은 표식 꼬리(예: `CD_VRT`,
  `CD_PROV`)가 없다.
  A = 없음 / B = 있음(꼬리 목록과 step 수 한 줄)
- **S8.** R4 device R7QA / R7QC가 들어 있는 계열 index는? 해당하는 글자를 모두 적어 주십시오.
  A = HV-SEM / B = VeritySEM / C = Provision
- **S9.** R7QA / R7QC는 R3 카탈로그(`r3_device_grp`)에 있다.
  A = 있음 / B = `device_desc`에 있음 / C = 두 카탈로그 모두 없음
- **S10.** `-cd`의 det_fac_id는 R3 하나뿐이다.
  A = R3뿐 / B = 다른 값도 있음(값과 device 수 한 줄)
- **S11.** HV-SEM AVIS/ICANS 33.6%는 표 A step 행 수 대비 비율이다.
  A = step 행 비율 / B = distinct oper_desc 비율 / C = 다른 기준
- **S12.** device-statistics 밖의 `ebeam_tas_lot_hist` 조회(Recipe 현황 TAT 등의 60일 창)도
  `event_tm` 대신 `dt.keyword`로 바꿔야 한다.
  A = 바꿔야 함 / B = 그쪽은 `event_tm` 유지 / ?

### 숫자 (한 줄씩)

- **N3.** `-cd`의 skip_yn 분포입니다(D 7,458행의 비율을 mock에 맞추려 합니다).
- **N4.** 고친 CD-SEM 어댑터를 `cp`한 뒤, R3 all 버킷의 total_recipe와 device 수가
  고치기 전과 어떻게 달라졌는지입니다. `_CAP_BASE` 3 device에 스텝이 나오는지도 함께 봐 주십시오.

### 파싱 후 답할 것 (VeritySEM·Provision 두 글자)

2차 질문지에서 받지 못한 칸입니다. 측정 결과 파서가 나온 뒤에 채워 주십시오.

- **R9.** `param_type` — A = 원천에 종류 column 있음 / B = 이름에서 파생 / C = 종류 개념 없음
- **R10.** 포인트 수가 (recipe, 파라미터)마다 하나로 정해짐 — A = 정해짐 / B = 측정마다 다름
- **R11.** mother/son 구분 — A = 있음 / C = 없음
- **R12.** Dummy·Align이 맨 앞 — A = 맞음 / B = 다른 위치에도 옴 / C = 없음
- **N1.** 계열별 표 A lots의 R3 / M fab 내역, skip `D` 비율, `_CAP_BASE` device 수, 카탈로그 밖
  device 수, `_DENSE` recipe 수, AVIS/ICANS step 수입니다.
- **N2.** 표 A~D가 놓인 이름입니다. 표마다 Redis key 또는 OpenSearch index 이름을 적어 주십시오.

## 2. 답안지

```text
S1:
S2:
S3:
S4:
S5:
S6:
S7:
S8:
S9:
S10:
S11:
S12:
N3  -cd skip_yn  Y=      N=      D=      total=
N4  R3 all  total_recipe  전=      후=      devices  전=      후=      _CAP_BASE 스텝(Y/N)=
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
