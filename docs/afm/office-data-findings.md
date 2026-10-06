# AFM 적재 데이터 명세 — Office 회신

- 아직 답을 받지 못한 질문은 [`to-questionnaire-afm.md`](to-questionnaire-afm.md) 하나에
  모여 있습니다. 2026-10-06에 질문서 다섯 개를 그 문서로 합쳤고, 합치기 전의 질문 원문은
  git 이력(`cc09fa24`)에 있습니다.
- 정리된 스키마는 `docs/datatables/afm/`에 있습니다. 이 문서는 **회신 원문을 보존**하는
  용도이며, 오탈자도 받은 그대로 둡니다.
- 받은 답이 문서와 코드에 반영되었는지는 끝의 "반영 현황"에 있습니다.

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

## 4차 회신 (2026-10-02) — 후속 질문 15문항의 답

2차 질문서(Q1~Q15, P1·P2)에 대한 답입니다. 끝에 MAPC01에
대한 정정이 붙어 있고, ETL이 적재를 시작했다는 소식도 함께 왔습니다.

```text
질문 15문항 답변.
Q1: 미정 (fab은 원본에 없음. PKG는 추정)
2: Info 섹션의 Lot ID (info CSV 안, 예: Lot ID,MON69683)
3: (가) 세션(폴더) 시작 시각 - 같은 세션의 여러 측정이 공유 (나) Info 섹션의 Start Time - 뒤 시각이 NA인 실측에서 첫 시각과 일치 확인
4. RECIPE+LOT+SAMPLE을 구분자 없이 이어붙인 원본 파일명(+선택 접미 _SOP_LEFT_UR 등) #261001#023441#VM_GTFILLOX_5PT_R1#5PNN1768.05$5PNN1768#NA#VM_GTFILLOX_5PT_R15PNN17685PNN178.05.csv

5. 맞음
6. (가)실제: #260709#033958#RL1C_L1_XDEC_5MM_LINE#01#NA#NA#RL1C078.01.csv (마지막 세그먼트는 원본 파일명이라 recipe마다 다름) (나) 맞음 - 현재까지 모든 MAPC01 측정에 _Info.csv 존재
9. 위치 키는 4자리 선행 0 point 번호. Point No=1 <-> 파일명 _0001  <-> info CSV FileName 열 _0001
10. 장비 공통이 아니라 recipe 의존. Site ID 있는 Recipe만 파일명에 site 포함 (_0001_Height.txt vs _0004_X000_Y-002_0002_Height.txt)
11. (가)맞음. (나) 아님 - block마다 컬럼 다름 (실측: 두번째 block은 측정 컬럼 없음, STOPPED) (다) 맞음. 빈 summary block도 존재.
12. 맞음 (0002_X002_Y-001 -> Site X=2, Site Y=-1, 단위 없음)
13. 숫자 recipe:2. 문자열 recipe : L1_XDEC_5MM_LINE. block 매칭은 위치로, Method ID 동일성으로 하면 안됨.
14. (가) Line1_Residue_H (nm) -(nm) 붙음 (나) 전체 이름 SITE19_21_H (nm) 가정과 같음.
15. 0 (1PT 실측: STDEV=0.0, RANGE=0.0)
7. 함께 적재 - 단위는 객체 metadata 필드 XUnit, YUnit, ZUnit, DataSize, SurfaceSize (파일별 유지, 통일 안함). Pixel 길이 환산은 미정 (원본에 근거 없음)
8. 맞음 - 1D도 같은 X/Y/Z parquet, Y=0 고정. 1D/2D 구분은 DataSize metadata (예: 1024 x 1)
P1. 미실측 (실물 아직 없음.)
P2. 미정 (장비 현지 시각, 추정 KST)
추가 예외: Summary 없은 data CSV 실측 있음 (Info -> Data 바로 연결), Info 값 빈 문자열 있음 (Carrier ID, 등)

정정. (1차 회신과 다름)
MAPC01의 info 시각 (124557)과 profile 시각 (132331)은 같은 측정이 아니라 서로 다른 측정입니다. 같은 sample이 하루 여러번 재측정되며 (모니터링 recipe) 측정마다 info CSV가 있고 시각으로 구분됩니다. MAPC01 측정 그루핑 = 앞 4필드 (date#time#recipe#slot) 적재 검증 완료.

ETL 적재 시작 중. 추후에 redis MinIO 정보 물어보길 바래.
```

## Q1~Q15의 결과

| 번호 | 답 | Home의 가정 | 반영 |
| --- | --- | --- | --- |
| Q1 | 미정. fab은 원본에 없고 `PKG`는 추정입니다. | `PKG` | 그대로 두고 OFFICE-VERIFY를 유지합니다. |
| Q2 | Info 섹션의 `Lot ID`입니다. | 얻을 수 없음 | 틀렸습니다. MAPC01도 lot을 갖습니다. |
| Q3 | (가) 세션(폴더) 시작 시각이며 여러 측정이 공유합니다. (나) Info의 `Start Time`입니다. | 의미 모름 | MAP608 측정을 세션으로 묶었습니다. |
| Q4 | RECIPE+LOT+SAMPLE을 이어 붙인 원본 파일명이며 접미가 붙기도 합니다. | 비어 있음 | 틀렸습니다. 파일명 끝을 고쳤습니다. |
| Q5 | 맞음 | 컬럼 51개, 묶음은 별개 컬럼 | 가정 표시를 뗐습니다. |
| Q6 | (가) 같은 이름에서 `_Info`를 뺀 것입니다. (나) 맞음 | `_Info.csv`가 키 | data CSV 이름을 고쳤습니다. |
| Q7 | 함께 적재합니다. 객체 metadata `XUnit`·`YUnit`·`ZUnit`·`DataSize`·`SurfaceSize`입니다. | 정해진 것 없음 | profile 응답에 `meta`를 추가했습니다. |
| Q8 | 맞음. Y=0 고정이고 `DataSize`로 구분합니다. | 같은 형식 | 1D를 선 그래프로 그립니다. |
| Q9 | 4자리 point 번호입니다. | 순번 `0001` | 맞았습니다. |
| Q10 | 장비 공통이 아니라 recipe 의존입니다. | 세 장비 공통 | 틀렸습니다. Site ID recipe만 파일명에 site가 들어갑니다. |
| Q11 | (가) 맞음 (나) 아님, block마다 컬럼이 다릅니다. (다) 맞음 | 셋 다 맞음 | 중단된 block을 추가했습니다. |
| Q12 | 맞음. 단위 없음. | die 번호 | 가정 표시를 뗐습니다. |
| Q13 | 숫자 `2`, 문자열 `L1_XDEC_5MM_LINE`. block은 위치로 맞춥니다. | block 이름과 같음 | 틀렸습니다. Method ID를 block 키로 쓰지 않습니다. |
| Q14 | (가) `(nm)`가 붙습니다. (나) `SITE19_21_H (nm)`입니다. | 같음 | 가정 표시를 뗐습니다. |
| Q15 | `0`입니다(STDEV=0.0, RANGE=0.0). | `0` | 가정 표시를 뗐습니다. |
| P1 | 미실측 | - | FALSE `Valid`의 표기는 여전히 모릅니다. |
| P2 | 미정. 장비 현지 시각이며 KST로 추정합니다. | - | 시간대는 여전히 가정입니다. |

## 5차 전달 (2026-10-06) — Redis·MinIO 적재 명세

ETL 적재 후의 형태입니다. 사용자가 전달했으며(user-confirmed), 사무실 실행으로 검증한
것은 아닙니다. 정리본은 `docs/datatables/afm/afm_redis.txt`입니다.

```text
common rule
값 직렬화 : pandas DataFrame.to_parquet() -> bytes (예외: afm_tool_recipes만 JSON 문자열).

hash field = 장비명 문자열: MAP608, MAPC01, 5EAP1501 (afm_d1_tools만 field가 "all").
갱신 단위 : 장비 (field) 하나 = DataFrame 전체 통짜 재기록. 행 단위 key 없음. TTL 없음.
읽기 : hget -> pd.read_parquet(io.BytesIO(raw)). 웹 응답시 NaN은 null로 변환 필요.

사용 key 4개

1. afm_d1_tools -> 장비 목록
Redis hash, field all 하나뿐
schema: id, name, fab, alias (fab은 미정이라 빈 값)

2. afm_d2_measurements - 측정 이력
hash, field = 장비명 (<TOOL>: MAP608, MAPC01, 5EAP1501)
parquet bytes (측정 전체 목록을 장비별 DataFrame 하나로 통짜 저장. 행 단위 개별 key 아님)
주요 열: unique_key(측정키, 파일명 # 필드), filename, date -> (YYMMDD), formatted_date --> (YYYY-MM-DD) 또는 null.  recipe_name, lot_id, slot_number, time --> HHMM 또는 null, tool_name, fab,
파일리스트 7종: MinIO 객체 Key들 전체 (prefix 2067928/ 포함). 빈 리스트 = 파일 없음
data_dir_list --> list[str]
profile_dir_list, tiff_dir_list, align_dir_list, tip_dir_list, capture_dir_list, raw_dir_list -> 원본 csv/txt 객체 key, point_count -> int 또는 null.
객체 key 패턴 : 2067928/afm/<TOOL>/<측정키>/<파일명> - data는 detail_information.parquet, detail_summary.parquet, detail_points.parquet 3종. profile은 profile_<원본이름>.parquet, 이미지는 <파일명>.webp
측정키 (unique_key) = 앵커(CSV) 그룹의 전체 6필드 키
date#time#recipe#slot#lot_measured (MAPC01은 앞 4필드)
예: 261001#070028#NA_NECKING_SLIM#5NNN0336.01#5NNN0336#NA

주의
쓰기 금지 to minIO
빈 값은 null. time의 'NA'는 null취급
redis 유실 시 MinIO 객체 key만으로 D2 재생성 가능
```

이 전달로 닫힌 질문은 셋입니다 — 첫 질문서 5절의 D1~D5 위치·형식, Q26 (가)(목록의 값은
MinIO key 전체), Q29 (다)(행 단위 key가 없어 목록 전체를 읽어야 함). 3차 질문서(Q16~Q28)와
4차 질문서(Q29)의 나머지는 답을 받지 못했습니다.

## 반영 현황 (2026-10-06 점검)

받은 답마다 **스키마 문서에 기록되었는지**와 **AFM 화면·코드에 구현되었는지**를
확인했습니다. 문서의 `raw`는 `docs/datatables/afm/afm_raw_files.txt`, `redis`는
`docs/datatables/afm/afm_redis.txt`입니다. mock은 `backend/afm/providers/mock.py`,
adapter는 `backend/afm/providers/office_example.py`, 화면 경로는 `frontend/app/` 기준입니다.

| 받은 답 | 문서 | 구현 | 비고 |
| --- | --- | --- | --- |
| 장비는 MAP608·MAPC01·5EAP1501, MAPC01=R3, 5EAP1501=M15 | raw D1 | mock `TOOL_CONFIGS`, 화면 `composables/useAfmToolData.ts` | **부분** — 아래 ①입니다. |
| 파일명의 `#` 필드 순서, MAPC01은 `_Info.csv`와 앞 4필드 (Q4, Q6) | raw D2 | mock 파일명, 화면 `measurementStem` (`utils/afmPoints.ts`) | 완료 |
| MAPC01의 lot은 Info의 `Lot ID` (Q2) | raw D2 | mock, 측정 상세의 LOT | 완료. 적재된 `lot_id` 열이 채워져 있는지는 Q37입니다. |
| MAP608의 첫 시각은 세션 시작, 측정 시작은 Info의 `Start Time` (Q3) | raw D2 | mock의 세션, 시계열 `utils/afmTrend.ts` | 완료 |
| recipe 명에 공백·괄호 가능 | raw D2 | `encodeURIComponent` (`composables/useAfmDetailApi.ts`) | 완료 |
| 파일 유무·point 수(1~36)는 recipe 설정, 부재는 정상 상태 | raw 머리 | mock `RECIPES`, `has_*`, 측정 상세의 빈 상태(404를 "없음"으로) | 완료 |
| 측정 컬럼은 recipe마다 다르고 `(nm)`를 포함 (Q5, Q14) | raw D3 | mock, `collectColumns` (`utils/afmExport.ts`) | 완료 |
| Summary block이 여럿, block은 위치로 맞춤, 중단된 block은 측정 컬럼 없음 (Q11, Q13) | raw D3 | mock, `blocksOfPoint` (`utils/afmPoints.ts`) | 완료. "같은 point가 다시 나오면 다음 block"은 추측입니다(Q21). |
| `State`는 COMPLETED·FAILED·STOPPED | raw D3 | mock, `utils/afmPoints.ts` | 완료 |
| 위치 키는 4자리 point 번호, Site ID recipe는 Site ID + point 번호 (Q9, Q10, Q12) | raw D3·D4 | mock, 화면 `detail/PointRail.vue`·`imagePoint`, adapter `_position` | 완료 |
| point 하나면 STDEV·RANGE는 0 (Q15) | raw D3 | mock (`test_mock_office_facts.py`가 고정) | 완료 |
| Profile은 X/Y/Z parquet, 단위는 파일별 metadata, 1D는 `DataSize`로 구분 (Q7, Q8) | raw D4 | 계약 `AfmProfileMeta`, 화면 `detail/HeatmapChart.vue`·`HistogramChart.vue` | 완료. metadata가 실린 곳은 Q34입니다. |
| 이미지는 webp 변환본, 원본 TIFF는 내려받을 수 있어야 함 | raw D5 | route `tiff`·`tiff.zip`, adapter는 webp를 그대로 전달 | **부분** — 아래 ②입니다. |
| Redis hash 둘, 값은 parquet, field는 장비명 | redis 공통·1·2 | adapter `_hash_rows` | 완료(사무실 미실행) |
| 빈 리스트 = 파일 없음, 빈 값은 null, `time`의 `NA`는 null | redis 2 | 계약의 null 허용, mock의 빈 리스트, adapter `_row`, 화면 `utils/afmSearch.ts` | 완료(사무실 미실행) |
| `unique_key`는 6필드, MAPC01은 4필드 | redis 2 | mock, adapter `_find` | 완료 |
| MinIO key는 `2067928/afm/<TOOL>/<측정키>/<파일명>`, 상세는 parquet 3종 | redis 3 | adapter `MinioObject(prefix="")`, `get_afm_file_detail` | 완료(사무실 미실행). 열 구성은 Q30~Q32입니다. |
| MinIO에 쓰지 않음 | redis 공통 | adapter는 읽기만 합니다. | 완료 |
| 보존 기간은 최근 3개월(방향, 미확정) | redis 3 | 없음 | **미구현** — 아래 ③입니다. |

기록만 되고 화면에는 닿지 않은 곳이 셋입니다.

1. **장비 목록** — 화면은 `useAfmToolData.ts`에 고정된 표를 쓰고 `/api/afm/tools`를 부르지
   않습니다. `afm_d1_tools`의 `alias`와, 나중에 채워질 `fab`은 화면에 나타나지 않습니다.
   `fab`이 비어 있는 동안은 고정 표가 필요하므로, Q40의 답을 받은 뒤 바꿉니다.
2. **원본 TIFF** — 다운로드 route와 버튼은 있으나 사무실에서 원본의 위치를 모릅니다(Q35).
   답을 받기 전까지 사무실 화면에는 버튼이 나오지 않습니다.
3. **보존 기간이 지난 측정** — 조회 이력·그룹·복사한 링크가 삭제된 측정을 가리키면 측정
   상세는 일반적인 "없음"을 보여 줍니다. "보존 기간 경과" 안내는 삭제 계획(Q42 (다))이
   정해지면 만듭니다.
