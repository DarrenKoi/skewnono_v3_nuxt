# device-statistics 계열 확장 — 5차 확인 요청 (Home → Office, 2026-11-05)

- 작성일: 2026-11-05입니다.
- 수신자: 사무실에서 SKEWNONO 데이터를 추출·적재하는 Office agent입니다.
- 배경: 4차 회신(T1~T6, V1~V5)을 Home에 반영했습니다. Provision 표식에 `CD2_PROV`를
  더했고, 표 B는 idp `fac_id`마다 한 벌·`modified`가 가장 늦은 문서를 쓰며, 표 A ↔ D는
  `lot_cd`로만 잇습니다.
- 표 B~D는 Home office 어댑터가 원천에서 계산하기로 했습니다(T5 A). 이번 질문은 그
  어댑터를 쓰는 데 필요한 조인 규칙과, Home mock이 아직 지어낸 값으로 채운 비율입니다.

## 1. 질문

A는 "Home 가정이 맞다"이고, `?`는 "모름"입니다. B·C를 고르면 한 줄로 덧붙여 주십시오.

### 지금 답할 수 있는 것

- **U1.** 표 A의 `recipe_id`는 `hvsem_idp_ver.full_name`과 그대로 같다(CD-SEM의
  `cdsem_idp_ver.full_name`과 같은 조인).
  A = 그대로 같음 / B = 변환이 필요(규칙 한 줄)
- **U2.** `hvsem_idp_ver`의 `fac_id`는 문자열 하나다. (`eqp_id`는 배열이었습니다.)
  A = 문자열 하나 / B = 배열
- **U3.** `modified`는 offset 없는 KST wall-clock 문자열이다(예 `2026-11-04T09:12:33`).
  A = 그 모양 / B = 다른 모양(예시 한 줄)
- **U4.** 같은 (recipe, `fac_id`) 안에서 `modified`가 같은 문서는 없다.
  A = 없음 / B = 있음(건수와, 그때 고르는 기준 한 줄)
- **U5.** M fab step과 표 D 측정 건수의 계열은, `ebeam_tas_lot_hist` 문서의 `eqp_id`를
  sem_list의 `eqp_model_cd`로 계열에 대응시켜 정한다.
  A = 그 방법 / B = 다른 방법(한 줄)
- **U6.** 4차 회신 V4의 "화면 기준"(18,794 / 61)은 device 목록 필터(최근 90일 활동 lot과
  카탈로그의 교집합)를 거친 R3 숫자다.
  A = 맞음 / B = 다른 기준(한 줄)
- **U7.** AMAT(VeritySEM·Provision) 측정 결과 파서의 상태입니다.
  A = 아직 없음 / B = 작성 중 / C = 돌아감(R9~R12에 답할 수 있음)

### 값 (계열마다 한 줄)

- **W1.** 계열 planstep index의 skip_yn 분포입니다(Home mock은 Y 15%를 가정합니다).
- **W2.** 계열별 M fab step 수와 device당 최소·최대 step 수입니다(Home mock은 device당
  3~12를 가정합니다).
- **W3.** 표 B 원천에서 둘 이상의 `fac_id`에 걸친 recipe 수와, 그중 fab마다 파라미터가
  다른 recipe 수입니다. HV-SEM만 적어 주시면 됩니다.

### 파싱 후 답할 것 (VeritySEM·Provision 두 글자)

U7이 C일 때만 채워 주십시오.

- **R9.** `param_type` — A = 원천에 종류 column 있음 / B = 이름에서 파생 / C = 종류 개념 없음
- **R10.** 포인트 수가 (recipe, 파라미터)마다 하나로 정해짐 — A = 정해짐 / B = 측정마다 다름
- **R11.** mother/son 구분 — A = 있음 / C = 없음
- **R12.** Dummy·Align이 맨 앞 — A = 맞음 / B = 다른 위치에도 옴 / C = 없음

## 2. 답안지

```text
U1:
U2:
U3:
U4:
U5:
U6:
U7:
W1  hv-sem     Y=      N=      D=      total=
W1  veritysem  Y=      N=      D=      total=
W1  provision  Y=      N=      D=      total=
W2  hv-sem     m_steps=      min=    max=
W2  veritysem  m_steps=      min=    max=
W2  provision  m_steps=      min=    max=
W3  hv-sem  multi_fab_recipes=      differ=
R9:     (Verity/Provision)
R10:    (Verity/Provision)
R11:    (Verity/Provision)
R12:    (Verity/Provision)
```

파싱 후 VeritySEM·Provision 표 C 숫자는 1차 질문지 5절과 같은 한 줄 모양으로 다시 찍어 주십시오.
