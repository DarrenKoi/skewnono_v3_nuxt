# AFM 적재 데이터 명세 — Office 회신

- 질문서는 [`to-questionnaire-afm.md`](to-questionnaire-afm.md)입니다.
- 정리된 스키마는 `docs/datatables/afm/`에 있습니다. 이 문서는 **회신 원문을 보존**하는
  용도이며, 오탈자도 받은 그대로 둡니다.

## 1차 회신 (2026-10-02) — raw 파일에서 확인한 사실

ETL 이전의 raw 파일을 보고 확인한 내용입니다. Redis·MinIO 적재 형태는 포함되어
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

## 아직 회신받지 못한 항목

질문서 5절 양식(위치·형식·스키마·연결 키·갱신·규모·샘플)은 dataset 다섯 개 모두
비어 있습니다. 6절의 S1~S8도 같습니다. 1차 회신으로 새로 생긴 질문은 아래와 같습니다.

| 번호 | 질문 | 근거 |
| --- | --- | --- |
| Q1 | MAP608의 fab은 무엇입니까. `tool_info.txt`는 `PKG`라고 합니다. | 회신이 MAPC01·5EAP1501만 확인했습니다. |
| Q2 | MAPC01의 lot ID는 어디에서 얻습니까. | 파일명의 lot 자리가 `NA`입니다. |
| Q3 | MAP608 파일명의 첫 번째 시각은 무엇입니까. | 마지막 시각만 측정 시작으로 확인되었습니다. |
| Q4 | 5EAP1501 파일명의 `...` 부분에는 무엇이 옵니까. | 회신에서 생략되었습니다. |
| Q5 | `1~51_Minimum (nm)`은 컬럼 51개입니까. | 표기가 범위인지 이름인지 분명하지 않습니다. |
| Q6 | MAPC01은 data CSV가 없는데 측정 한 건을 무엇으로 식별합니까. `_Info.csv`입니까. | 웹은 data 파일명을 측정의 키로 씁니다. |
| Q7 | ETL이 profile의 단위를 통일합니까, 아니면 파일별 단위를 함께 적재합니까. | 웹의 profile 응답에는 단위 필드가 없습니다. |
| Q8 | 1D profile(N×1)은 2D와 같은 형식으로 적재됩니까. | 화면이 heatmap 대신 선 그래프를 그려야 합니다. |
