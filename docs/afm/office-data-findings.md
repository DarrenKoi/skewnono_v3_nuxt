# AFM 적재 데이터 명세 — Office 회신

- 질문서는 [`to-questionnaire-afm.md`](to-questionnaire-afm.md)입니다.
- 정리된 스키마는 `docs/datatables/afm/`에 있습니다. 이 문서는 **회신 원문을 보존**하는
  용도이며, 오탈자도 받은 그대로 둡니다.

## 1차 회신 (2026-10-02) — raw 파일에서 확인한 사실

ETL 이전의 raw 파일을 보고 확인한 내용입니다. 이 가운데 "MAPC01은 data CSV가 없음"은
2차 회신이 바로잡았습니다. Redis·MinIO 적재 형태는 포함되어
있지 않으며, ETL이 끝난 뒤 다시 회신받기로 했습니다. 정리본은
`docs/datatables/afm/afm_raw_files.txt`입니다.

```text
What we can give Home (you) now is confirmed from raw data in skewnono-pjt-shared/AFM/
D1: Equipemnt IDs are MAP608, MAPC01, 5EAP1501. Code confirms MAPC01=R3, 5EAP1501=M15, the current mocks' mapping is wrong. Fab field doesn't exist anywhere in the raw data (미정).
측정 식별자 D2: 파일명은 # 구분, 장비마다 필드 순서가 다름:
MAP608: #YYMMDD#hhmmss#RECIPE#SAMPLE_ID#LOT_ID#hhmmss#.csv (시각 2회인데, 마지막 시각은 측정 시작 시각.)
MAPC01: #YYMMDD#hhmmss#RECIPE#SLOT#NA#NA#SAMPLE_ID_Info.csv - 빈자리는 NA
5EAP1501: #YYMMDD#HHMMSS#RECIPE#SAMPLE_ID#LOT_ID#NA#...csv

측정 상세 (D3)
CSV 3개 section (Info key,value / Summary MEAN STDEV MIN MAX RANGE / Data point 별 행):
-측정 컬럼은 recipe마다 다름. 실측: MAP608 Pad_1_H (nm)..., 5EAP 1~51_Minimum (nm). Home에서 사용하는 컬럼도 고려하지만 결과적으로 모두 다름. 모두 nm 포함이라 시계열 필터는 동작.
예외: MAPC01은 data CSV가 없음 - summary/data 표 불가
예외: 5EAP1501은 profile txt가 없음 - heatmap ㅜㄹ가.
Site: 해더에 Site 컬럼은 없으나 각 section 앞에 site 이름 줄이 있고 파서가 Site 필드로 저장. 현재 샘플은 1블록(method명)이지만, 파서가 다중 site 블록을 전제하므로 오래된 /다른 fab 데이터에 Site ID가 나올 수 있음 -> 결정은 아님 데이터가 쌓이면 재검증.

Profile (D4) 2d 격자 txt (헤더: Data Size/Surface Size/X Y Z unit + 탭 구분 X Y Z). MAP608은 512X64 (um/um/nm). MAPC01은 격자 다양 (1024X1 ~ 16384X1등, 1D/2D 혼재). 단위가 파일마다 다름. um/nm/pm/Pixel 반드시 헤더에서 읽을 것.

이미지 D5 webp변환본 있음 tiff 문제 없음.

ETL 끝난 후 데이터 형태 전달 다시 해주겠음.
```

## 2차 회신 (2026-10-02) — raw 파일 추가 실측

같은 날 이어서 받은 회신입니다. 1차의 "MAPC01은 data CSV가 없음"을 바로잡고
("recipe에 따라 존재"), Site ID·State·Method_ID 같은 Data 행의 실제 값을 알려 줍니다.

```text
Site ID , Site X, Site Y 컬럼 존재. 값 예: 0001_X000_Y000, 0002_X002_Y-001(음수 가능). MAPC01 profile 파일명의 Site 부분과 일치.
MAPC01 data CSV도 존재함 (recipe에 따라): 파일 종류 유무 컬럼은 전부 recipe 설정에 의존 - 부재를 정상 상태로 처리할 것.
측정 컬럼 다양성 실측 : Left_H/Right_H/Ref_H (nm), Dishing_H (nm), Ref_Range/Left_TRIM_H (nm), ROUGHNESS_RANGE/Ra/Rq (nm), 1~51_Minimum (nm) 등. 전부 nm 포함.

한 파일에 여러 Summary 블록 가능 실측 (Profile_LEFT_UL + Profile_RIGHT_UL). Summary가 없는 파일, method명 줄만 있는 빈 Summary, 표 없는 빈 Data도 실측.

State 실측 3종: COMPLITED, FAILED, **STOPPED**. Method_ID가 숫자인 Recipe가 있음. Last Pick Up Time/Last Put Back Time 빈 값 가능.

MAP608 오래된 데이터는 뒤 시각 자리가 NA인 경우가 있음. recipe명에 공백 괄호 가능 (Fi-Tapping TEST, RQQA_PFH_MONF (1)) -URL 인코딩 필요.
남은 미정: FALSE Valid 실물, 시간대
```

## 3차 회신 (2026-10-02) — 추가 샘플링

추가로 샘플링해 얻은 내용입니다. State의 철자가 `COMPLETED`로 확정되었으므로 2차 회신의
`COMPLITED`는 오타로 봅니다. Site ID는 "컬럼 존재"에서 "recipe에 따라 있거나 없음"으로
바뀌었습니다.

```text
Site ID recipe 3종 추가 확인 BSOXCMP_CORRELATION_36PT(Bottom_H/Top_H (nm)), RL1A_LPCCMP_CMPWEAK2(Line1_Residue_H), RX1A_M0A_COT_X_PDG(SITE19_21_..) 3개 장비 모두 Site ID 유무가 Recipe따라 갈림
STOPPED 상태 다수 Recipe에서 실측 (VED_BS_TOP01, Fi-Tapping TEST 등) - COMPLETED/FAILED/STOPPED 3종 확정
POINT 수 범위 1~36pt 실측 - point_count는 recipe마다 다름
새 컬럼 형태: RZ1_Minimum (nm) 번호 컬럼 + 접두 변형, Line1_* 접두 계열.
Recipe명 공백 사례 확장 : 5EAP에서도 xy scanner opm, zeroscan 5point pm 존재 - 세 장비 공통
```

## 아직 회신받지 못한 항목

질문서 5절 양식(위치·형식·스키마·연결 키·갱신·규모·샘플)은 dataset 다섯 개 모두
비어 있습니다. 6절은 S1(Site ID가 profile 파일과 이어짐)과 S3(State의 값 목록)만
일부 답을 받았습니다. 세 회신으로 생긴 질문은 아래와 같습니다.

| 번호 | 질문 | 근거 |
| --- | --- | --- |
| Q1 | MAP608의 fab은 무엇입니까. `tool_info.txt`는 `PKG`라고 합니다. | 회신이 MAPC01·5EAP1501만 확인했습니다. |
| Q2 | MAPC01의 lot ID는 어디에서 얻습니까. | 파일명의 lot 자리가 `NA`입니다. |
| Q3 | MAP608 파일명의 첫 번째 시각은 무엇입니까. 뒤 시각이 `NA`인 오래된 측정은 시작 시각을 어디에서 얻습니까. | 마지막 시각만 측정 시작으로 확인되었고, 오래된 데이터는 그 자리가 `NA`입니다. |
| Q4 | 5EAP1501 파일명의 `...` 부분에는 무엇이 옵니까. | 회신에서 생략되었습니다. |
| Q5 | `1~51_Minimum (nm)`은 컬럼 51개입니까. `Ref_Range/Left_TRIM_H (nm)`은 `(nm)`를 단 컬럼 둘입니까. | 표기가 범위·묶음인지 이름인지 분명하지 않습니다. |
| Q6 | MAPC01의 data CSV는 파일명이 무엇입니까. data CSV가 없는 recipe는 측정 한 건을 `_Info.csv`로 식별합니까. | 웹은 data 파일명을 측정의 키로 씁니다. |
| Q7 | ETL이 profile의 단위를 통일합니까, 아니면 파일별 단위를 함께 적재합니까. | 웹의 profile 응답에는 단위 필드가 없습니다. |
| Q8 | 1D profile(N×1)은 2D와 같은 형식으로 적재됩니까. | 화면이 heatmap 대신 선 그래프를 그려야 합니다. |
| Q9 | Site ID가 없는 recipe에서는 측정 위치와 그 profile·이미지 파일을 무엇으로 가리킵니까. | Site ID가 profile 파일을 찾는 연결 키인데, recipe에 따라 없습니다. |
| Q10 | MAP608과 5EAP1501의 profile·이미지 파일명에도 Site ID가 들어갑니까. | MAPC01의 profile 파일명만 확인되었습니다. |
| Q11 | Summary block이 여럿일 때 Data도 block마다 나뉩니까. block마다 측정 컬럼이 같습니까. | Summary가 여러 block일 수 있다는 것만 확인되었습니다. |
| Q12 | `Site X`·`Site Y`의 값은 Site ID의 X·Y 숫자와 같습니까. 단위는 무엇입니까. | 컬럼이 있다는 것만 확인되었습니다. |
| Q13 | `Method_ID`가 숫자가 아닌 recipe에서는 어떤 값입니까. | 숫자인 recipe가 있다는 것만 확인되었습니다. |
| Q14 | `Line1_Residue_H`에도 `(nm)`가 붙습니까. `SITE19_21_..`의 전체 컬럼 이름은 무엇입니까. | 3차 회신에서 단위 없이, 또는 잘린 채로 전달되었습니다. |
| Q15 | point가 하나인 측정의 Summary에서 STDEV·RANGE는 어떤 값입니까. | point 수가 1부터 실측되었습니다. |

남은 미정으로 회신이 직접 적은 것은 FALSE인 `Valid`의 실물 표기와 시각의 시간대입니다.
해소된 질문도 하나 있습니다. State의 `COMPLITED`가 장비 철자인지 물으려 했으나, 3차 회신이
`COMPLETED`로 확정했습니다.
