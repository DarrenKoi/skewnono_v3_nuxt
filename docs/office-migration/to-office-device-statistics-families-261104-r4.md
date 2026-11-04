# device-statistics 계열 확장 — 4차 확인 요청 (Home → Office, 2026-11-04)

- 작성일: 2026-11-04입니다.
- 수신자: 사무실에서 SKEWNONO 데이터를 추출·적재하는 Office agent입니다.
- 배경: 3차 회신(S1~S12, N3, N4, 계열 숫자)을 Home에 반영했습니다.
  - `dt.keyword` 하한을 `YYYYMMDD`로 고쳤습니다. device-statistics 90일 창과,
    공용 lot_id ↔ lot_cd bridge의 60일 창 둘 다입니다.
  - 표 B에 `fac_id`를 더해 (tool_type, recipe_id, fac_id)마다 한 벌로 바꿨습니다.
  - CD-SEM mock skip 비율을 실측(Y 47.7% / D 6.5%)으로 맞췄습니다.
- **먼저 할 일:** device-statistics 어댑터를 다시 `cp`해 주십시오. 지금 사무실 사본은
  `YYYY-MM-DD` 하한이라 90일 창이 없는 상태입니다. bridge 쪽은 `git pull`만으로
  반영됩니다. 아래 T4·T5는 그 뒤에 재 주십시오.

## 1. 질문

A는 "Home 가정이 맞다"이고, `?`는 "모름"입니다. B·C를 고르면 한 줄로 덧붙여 주십시오.

### 지금 답할 수 있는 것

- **T1.** VeritySEM planstep index 이름은 `sknn-planstep-r3-verity`이다.
  (2026-10-27 전달값은 `-verify`, 3차 회신은 `-verity`였습니다.)
  A = `-verity` / B = `-verify`
- **T2.** `-cd`의 skip_yn `"Y"`는 여전히 skip(측정하지 않음)이다. 실측 Y가 47.7%라 극성을 다시 묻습니다.
  A = Y가 skip / B = 다름
- **T3.** `hvsem_idp_ver` 문서에서 fab을 읽는 field가 있다(표 B의 `fac_id`). 아래 답안지에 field 이름을 적어 주십시오.
  A = 있음(field 이름) / B = 없음, 다른 방법(한 줄)
- **T4.** S3 "가장 최근 문서"는 `version`이 가장 큰 문서다.
  A = `version` 최대 / B = 다른 field(이름 한 줄)
- **T5.** 표 B~D는 앞으로도 저장하지 않고, Home office 어댑터가 원천에서 매번 계산한다.
  A = Home이 계산 / B = 사무실이 주기 적재(이름은 답안지에)
- **T6.** R4 device R7QA / R7QC의 `ebeam_tas_lot_hist` fab_id는 `R3`이다(표 D의 fab).
  A = `R3` / B = `R4` / C = 그 index에 없음

### 값 (한 줄씩)

- **V1.** S7 — VeritySEM·Provision에 붙은 표식 꼬리 목록과 계열별 step 수입니다
  (예: `veritysem CD_VRT=12 CD2_VRT=3 / provision CD_PROV=5`).
- **V2.** S10 — `-cd` det_fac_id의 R3 밖 값과 그 device 수입니다(예: `R4=2 R5=1`).
- **V3.** `cp` 뒤 device-statistics M fab 창 하한 값과, 그 창으로 읽은 `ebeam_tas_lot_hist` 문서 수입니다.
- **V4.** `cp` 뒤 R3 all total_recipe와 device 수입니다. 3차 회신 N4(57,145 → 57,179,
  513 → 516)는 창이 없던 상태의 값이라 다시 잽니다.
- **V5.** `git pull` 뒤 lot_id ↔ lot_cd bridge의 lot_id 수 전/후입니다(60일 창이 `event_tm`에서
  `dt.keyword`로 바뀌었습니다).

### 파싱 후 답할 것 (VeritySEM·Provision 두 글자)

측정 결과 파서가 나온 뒤에 채워 주십시오.

- **R9.** `param_type` — A = 원천에 종류 column 있음 / B = 이름에서 파생 / C = 종류 개념 없음
- **R10.** 포인트 수가 (recipe, 파라미터)마다 하나로 정해짐 — A = 정해짐 / B = 측정마다 다름
- **R11.** mother/son 구분 — A = 있음 / C = 없음
- **R12.** Dummy·Align이 맨 앞 — A = 맞음 / B = 다른 위치에도 옴 / C = 없음

## 2. 답안지

```text
T1:
T2:
T3:      field=
T4:
T5:      (B면 표 B= 표 C= 표 D=)
T6:
V1  veritysem            / provision
V2  -cd det_fac_id
V3  하한=          문서 수=
V4  R3 all  total_recipe=        devices=        _CAP_BASE 스텝(Y/N)=
V5  bridge lot_id  전=        후=
R9:     (Verity/Provision)
R10:    (Verity/Provision)
R11:    (Verity/Provision)
R12:    (Verity/Provision)
```

파싱 후 VeritySEM·Provision 표 C 숫자는 1차 질문지 5절과 같은 한 줄 모양으로 다시 찍어 주십시오.
