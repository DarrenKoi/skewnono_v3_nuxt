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

## 6차 회신 (2026-10-06) — 적재물을 보고 답한 내용

통합 질문서(Q21~Q42, P2)에 대한 답입니다. 실제 적재물을 보고 확인한 것이므로 5차의 명세와
달리 `office 확인`으로 기록했습니다. 답이 없는 번호(Q22, Q24, Q27, S2, S4, S8)와 일부만
답한 번호는 질문서에 남겼습니다.

```text
Q32 Point No, Site ID 철자 그대로 (공백, 밑줄 아님). lbock을 담은 열이 있다. Site 열이 method명을 갖고 있어 Q21 추측이 필요 없음. 단 모든 값이 문자열로 적재됨("79.24", Point No도 "1")
Q33 맞음: 위치 키 = Site ID 있으면 <Site ID>_<Point No 4자리>(0001_X-001_Y-001_0014), 없으면 0001. 마지막 4자리는 Site안의 point 번호가 맞음. 단 MAPC01은 "filename에서 _Info 뺀 것으로 시작" 매치가 깨짐(5, 6번째 필드 불일치) - 끝 세그먼트로 찾아야 함.
Q39 filename = data CSV 원본 파일명 전체 (없으면 info CSV). 둘 다 유일 실측(전수 0건 중복). $/5PNN178 오타 확인.
Q34 (가) MinIO 객체 user metadata(x-amz-meta-datasize 등 소문자 저장), parquet 파일 metadata 아님. (나) 맞음.
Q35 원본 TIFF는 tiff_dir_list에 포함. 단 5EAP1501은 현재 0개.
Q21 다름 - repeat recipe는 block=point에 8행 (4 Sitex2반복). "같은 point 재등장 = 다음 block" 규칙 쓰지 말걸. 측정 중단 시 못한 point 행은 아예 없음 (STOPPED 행으로 채우지 않음).
P2 미정 - 원본에 시간대 정보 없음 (KST 추정 유지)

그외 주요
Q30 열 이름이 name, value(key 아님). 빈 값 = 빈 문자열 ''. MAPC01 info CSV의 Data 섹션 FileName 열이 위치 키 매핑이지만 현재 적재에서 제외됨.
Q32 Site/ITEM 맞음. Summary 없으면 0행짜리 객체 존재(열도 없음), MAPC01(info-only)은 객체 자체 없음.
Q28 측정 못한 칸 = 공백 한칸 ' ', _Valid = ''. NaN/- 없음.
Q36 time 6자리, 첫 시각=세션 시작(같은 세션 측정들이 time 공유 - 개별 시각은 측정키 6번째 필드).
Q37 measured_info 열은 있으나 항상 null, tool_id 없음, tool_name은 대문자 그대로. MAPC01 lot_id는 Info로 채워짐.
Q29 다름 - 우선 Info Sample Location의 Slot N(실제 웨이퍼 슬롯), 실패시만 .nn 꼬리(5EAP은 .05<-> Slot 5 불일치 실측 -> fallback은 추정)
Q38 (가) information 하나 - "데이터 있음' 표시가 켜지므로 주의. (나) 없음. (다) 실패 측정은 목록에 안들어옴(구분 불가).
Q40 id 대문자 그대로, fab 빈 문자열, alias MAP608=null/R3/M15.
Q42 30분 주기 (종료 후 통산 30분 내 반영), 3개월 보존 확정, MinIO 먼저 -> Redis 행 나중 삭제.
Q41 afm_tool_recipes = recipe명 JSON배열 (Recipe 필터용으로 읽어도 됨), afm_download_history = 다운로드 이력 parquet (웹 불필요).
```

옮기면서 이렇게 읽었습니다.

- "그외 주요"의 두 번째 `Q32 Site/ITEM 맞음…`은 Summary에 대한 답이므로 Q31로 보았습니다.
- `lbock`은 `block`, `통산`은 `통상`의 오타로 보았습니다.
- Q21의 "block=point에 8행"은 "한 block 안에 같은 point가 되풀이되어 8행"으로 읽었습니다.
- Q29의 "`.05` ↔ Slot 5 불일치"는 `.nn` 꼬리가 실제 슬롯과 다를 수 있다는 뜻으로 읽었습니다.
- Q38 (나)는 "없음"이지만 Q42의 삭제 순서(MinIO 먼저)에 따르면 삭제 도중에는 목록에만 있는
  측정이 생깁니다. 웹은 그 경우를 "없음"으로 다룹니다.

### 가정이 틀렸던 곳

| 번호 | Home의 가정 | 실제 | 고친 곳 |
| --- | --- | --- | --- |
| Q21 | 같은 point가 다시 나오면 다음 block입니다. | repeat recipe는 한 block 안에서 point가 되풀이됩니다. block은 `Site` 열입니다. | 화면 `utils/afmPoints.ts`·`utils/afmTrend.ts`, mock의 data 행 |
| Q21 | 중단된 block도 모든 point의 행을 STOPPED로 남깁니다. | 측정하지 못한 point의 행은 없습니다. | mock |
| Q32 | 값은 숫자로 적재됩니다. | 모든 값이 문자열입니다. | adapter `_cell` |
| Q33 | 이미지 이름은 `filename`(에서 `_Info`·`.csv`를 뺀 것)으로 시작합니다. | MAPC01은 5·6번째 필드가 달라 시작이 맞지 않습니다. | 화면 `imagePoint`, mock의 MAPC01 파일명 |
| Q34 | parquet 파일의 metadata를 먼저 봅니다. | MinIO 객체의 user metadata입니다. | adapter `get_profile_meta` |
| Q35 | 원본 TIFF는 `raw_dir_list`에 있을 것입니다. | `tiff_dir_list`에 webp와 함께 있습니다. | adapter `_original_key`, mock |
| Q29 | Slot은 파일명의 네 번째 필드에서 읽습니다. | Info `Sample Location`의 `Slot N`입니다. `.nn` 꼬리는 슬롯이 아닐 수 있습니다. | 화면 측정 상세, mock의 Info |
| Q30 | 열 이름은 `key`, `value`입니다. | `name`, `value`입니다. | adapter `_information` |
| Q37 | `measured_info`가 비어 있을 때만 빈 값입니다. | 항상 null입니다. | mock, 화면의 빈 badge 감춤 |
| Q38 (가) | `data_dir_list`가 비어 있지 않으면 측정 데이터가 있습니다. | info만 있는 측정도 information 하나를 갖습니다. | adapter `has_data`, mock |
| Q39 | MAPC01의 `filename`은 `_Info.csv`입니다. | data CSV가 있으면 data CSV입니다. | mock |
| Q40 | `alias`는 표시용 이름입니다. | `R3`·`M15`가 들어 있습니다(fab으로 해석). | adapter `get_tools` |

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
| Summary block이 여럿이고 data 행의 `Site`가 그 행의 block, repeat recipe는 block 안에서 point가 되풀이됨 (Q11, Q13, Q21, Q32) | raw D3, redis 3.1 | mock, `blockOf` (`utils/afmPoints.ts`), `utils/afmTrend.ts` | 완료 |
| 중단된 block은 측정하지 못한 point의 행이 없고 칸이 비어 있음 (Q21, Q28) | redis 3.1 | mock, adapter `_cell`(null로) | 완료. 남는 행의 수는 Q44입니다. |
| 상세의 모든 값이 문자열 (Q32) | redis 3.1 | adapter `_cell` | 완료(사무실 미실행). FALSE의 표기는 Q32입니다. |
| `State`는 COMPLETED·FAILED·STOPPED | raw D3 | mock, `utils/afmPoints.ts` | 완료 |
| 위치 키는 4자리 point 번호, Site ID recipe는 Site ID + point 번호 (Q9, Q10, Q12, Q33) | raw D3·D4, redis 3.2 | mock, 화면 `detail/PointRail.vue`, adapter `_position` | 완료 |
| MAPC01의 profile·이미지 이름은 `filename`으로 시작하지 않음 (Q33) | redis 3.2 | mock, 화면 `imagePoint`(이름의 끝에서 읽음) | 완료 |
| point 하나면 STDEV·RANGE는 0 (Q15) | raw D3 | mock (`test_mock_office_facts.py`가 고정) | 완료 |
| Profile은 X/Y/Z parquet, 단위는 MinIO 객체의 user metadata, 1D는 `DataSize`로 구분 (Q7, Q8, Q34) | raw D4, redis 3.3 | 계약 `AfmProfileMeta`, adapter `get_profile_meta`, 화면 `detail/HeatmapChart.vue`·`HistogramChart.vue` | 완료(사무실 미실행) |
| 이미지는 webp 변환본, 원본 TIFF는 `tiff_dir_list`에 함께 있음 (Q35) | raw D5, redis 2 | route `tiff`·`tiff.zip`, adapter `_original_key`, mock | 완료(사무실 미실행). webp와의 짝은 가정입니다(Q35). |
| Redis hash 둘, 값은 parquet, field는 장비명 | redis 공통·1·2 | adapter `_hash_rows` | 완료(사무실 미실행) |
| 빈 리스트 = 파일 없음, 빈 값은 null, `time`의 `NA`는 null | redis 2 | 계약의 null 허용, mock의 빈 리스트, adapter `_row`, 화면 `utils/afmSearch.ts` | 완료(사무실 미실행) |
| `unique_key`는 6필드, MAPC01은 4필드 | redis 2 | mock, adapter `_find` | 완료 |
| MinIO key는 `2067928/afm/<TOOL>/<측정키>/<파일명>`, 상세는 parquet 3종(information은 `name`·`value`) | redis 3 | adapter `MinioObject(prefix="")`, `get_afm_file_detail` | 완료(사무실 미실행) |
| `filename`은 data CSV(없으면 info CSV), `measured_info`는 항상 null, MAPC01의 `lot_id`는 Info에서 (Q37, Q39) | redis 2 | mock, 화면의 빈 badge 감춤 | 완료 |
| info만 있는 측정도 `data_dir_list`에 information 하나 (Q38) | redis 2 | adapter `has_data`, mock | 완료 |
| Slot은 Info `Sample Location`의 `Slot N` (Q29) | redis 2 | 목록은 `slot_number` 열, 측정 상세(`pages/afm/[tool]/[filename].vue`)는 Info | 완료. 값의 모양은 Q29입니다. |
| `afm_d1_tools`의 `alias`가 R3·M15, `fab`은 빈 문자열 (Q40) | redis 1 | adapter `get_tools`(alias를 fab으로) | **부분** — 아래 ①입니다. |
| `afm_tool_recipes`는 recipe 명 JSON 배열, `afm_download_history`는 웹 불필요 (Q41) | redis 공통 | 없음 | 읽지 않습니다. Recipe 필터는 목록에서 모읍니다. |
| 갱신은 30분 주기 (Q42) | redis 공통 | adapter의 60초 캐시 | 완료 |
| MinIO에 쓰지 않음 | redis 공통 | adapter는 읽기만 합니다. | 완료 |
| 보존은 3개월로 확정, MinIO를 먼저 지우고 Redis 행을 나중에 지움 (Q42) | redis 공통 | adapter는 없는 객체를 "없음"으로 돌려줍니다. | **부분** — 아래 ②입니다. |

기록만 되고 화면에는 닿지 않은 곳이 둘입니다(6차 회신 반영 후).

1. **장비 목록** — 화면은 `useAfmToolData.ts`에 고정된 표를 쓰고 `/api/afm/tools`를 부르지
   않습니다. MAP608의 fab이 여전히 비어 있어 고정 표가 필요하므로, `alias`가 fab이
   맞는지(Q40)를 확인한 뒤 바꿉니다.
2. **보존 기간이 지난 측정** — 조회 이력·그룹·복사한 링크가 삭제된 측정을 가리키면 측정
   상세는 일반적인 "없음"을 보여 줍니다. 3개월 보존이 확정되었으므로 "보존 기간 경과"
   안내를 만들 수 있습니다. 3개월을 세는 기준 시각(Q42 (나))만 남았습니다.

## 7차 회신 (2026-10-07) — 팁·측정 시각·repeat recipe

질문서의 Q32·Q35·Q43~Q46·Q48·Q49·Q51·Q53에 대한 답과, 팁 열 추가 요청의 구현 결과입니다.
실제 적재물을 보고 답한 것이므로 `office 확인`으로 기록했습니다.

```text
Q43 repeat recipe : 반복 번호 열 없음 (Sample Count 4->5로 구분 가능). Site 한 바퀴 돈 뒤 다시 돎 - 맞음.
point_count=56(site 4xpoint 14; 행 112도 recipe 14도 아님). profile, 이미지는 반복마다 따로 없음 (같은 이름 1개)
Q44 STOPPED : STOPPED 행 하나 - 맞음. 단 summary는 없는게 아니라 빈 block (0행 parquet). tiff, profile, capture 0 건, point_count=null
Q45/Q48 : 6 번째 필드 NA는 오래된 파일만이 아니라 최근 파일 절반가량 (29/46) .measured_time 열 추가 가능 - 구현 완료.
Q49: point_count = 실제 스캔한 위치 수 (profile/tiff 파일 수). 중단 측정은 작아짐 (실측 분포 2,3,5,8,14,43,55,56)
Q46 팁교체: 교체 기록은 없지만 결정적 실축: Mileage는 팁 단위 누적계이고 다른 슬롯으로 바뀌면 리셋(DT-NCHR_CM slot9 -> slot1, 1430483->3520). 세로선은 "Tip ID, Cassette, Port, Slot 변화 or Mileage 리셋" 지점에.
Q51 : 비 MCNT 종류는 폭이 사실상 상수 (종류 단위 관리선 OK). MCNT 계열만 33.96~39.11로 퍼짐 + 같은 슬롯에서도 오르내림 -> 마무가 아닌 측정 오차로 추정. MCNT는 슬롯 단위 필요.
Q32: FALSE 여전히 미슬측(263 CSV 전수 0 건), Method ID (공백)
Q35: .tiff; 5EAP도 mirror에 원본 206개 있음(초기 적재 누락 -> 재적재 예정); align/tip/capture 원본 이미 적재됨
Q53: tip 이미지 2계열. point마다 _C_PR(site recipe는 위치 키 포함) + 측정당 1장 C_Result(6차 답 정정)

Implementation (done, tested)
- afm_d2_measurements에 팁 열 9개(tip_width=float64, NaN->NaN) + measured_time 추가. 계산은 상세(detail_points)와 같은 첫 data csv에서 - 목록 상세 불일치 없음.
```

옮기면서 이렇게 읽었습니다.

- `결정적 실축`은 `결정적 실측`, `마무`는 `마모`, `미슬측`은 `미실측`의 오타로 보았습니다.
- Q43의 `point_count=56`은 4 Site × 14 point인 repeat recipe 한 건의 값으로 읽었습니다.
  6차 회신의 "4 Site × 2 반복 = 8행"과는 다른 측정입니다.
- Q44의 "tiff, profile, capture 0건, point_count=null"은 첫 point에서 중단된 측정 한 건의
  모습으로 읽었습니다. Q49의 분포(2, 3, 5, …)는 도중에 중단된 측정입니다.
- Q46의 "다른 슬롯으로 바뀌면 리셋"은 "같은 `Tip ID`라도 다른 슬롯의 팁은 다른 팁"이라는
  뜻으로 읽어 Q46 (다)의 답(`교체`)으로 보았습니다. (나)(`Last Pick Up Time`의 뜻)는 답이
  없어 질문서에 남겼습니다.
- Q35의 `.tiff`는 (가)의 답으로, 뒤의 둘은 (다)·(라)의 답으로 읽었습니다. (나)(webp와의
  짝)는 답이 없어 남겼습니다.
- Q53의 "6차 답 정정"이 6차의 어느 답을 고친 것인지는 알 수 없습니다. 6차 회신에는 tip
  이미지에 대한 답이 없습니다.
- `measured_time`의 값 모양과 6번째 필드가 `NA`일 때의 값은 회신에 없습니다. 요청한
  대로(`HHMMSS`, 없으면 Info `Start Time`)라고 가정하고 Q55로 물었습니다.

### 가정이 틀렸던 곳

| 번호 | Home의 가정 | 실제 | 고친 곳 |
| --- | --- | --- | --- |
| Q49 | `point_count`는 points의 행 수입니다. | 실제로 스캔한 위치 수입니다(profile·tiff 파일 수). | 계약·화면의 주석, 문서. 화면의 합과 범위 표시는 그대로 맞습니다. |
| Q45 | 6번째 필드의 `NA`는 오래된 파일입니다. | 최근 파일의 절반쯤(29/46)입니다. | mock의 `NA` 비율, 화면이 `measured_time`을 먼저 읽음 |
| Q51 | 같은 종류의 팁은 폭이 비슷합니다. | MCNT 계열만 33.96~39.11로 퍼지고 슬롯마다 다릅니다. | 화면 `utils/afmTips.ts`(MCNT는 팁 단위 관리선), mock의 폭 |
| Q46 | 팁이 바뀐 것은 Tip 값 네 개로만 알 수 있습니다. | Mileage가 팁 단위 누적값이라 리셋도 근거입니다. | 화면 `tipChanges`(`utils/afmTrend.ts`), mock의 Mileage |
| (팁 모니터링) | Mileage를 종류의 관리선과 비교합니다. | 누적값이라 수준을 비교할 수 없습니다. | 화면 `utils/afmTips.ts`(Mileage는 판정에서 뺌) |
| Q32 | 열 이름은 `Method_ID`일 수 있습니다. | `Method ID`입니다. | mock |
| Q44 | 중단된 block은 Summary 객체가 없습니다. | 0행짜리 빈 block이 있습니다. | 문서. 계약에서는 둘 다 빈 목록입니다. |
| Q53 | tip 이미지는 측정마다 한 장입니다. | point마다 `_C_PR`, 측정마다 `C_Result` 한 장입니다. | mock, 화면 `imagePoint`(`utils/afmPoints.ts`) |
| Q35 (라) | align·tip·capture에는 원본 TIFF가 없습니다. | 있고 이미 적재되어 있습니다. | adapter(`has_align`·`has_tip`에서 원본을 뺌). 다운로드는 아직 없습니다. |

### 반영 현황 (2026-10-07)

| 받은 답 | 문서 | 구현 | 비고 |
| --- | --- | --- | --- |
| 팁 열 9개 적재, `tip_width`는 float64 (NaN) | redis 2 | adapter `_row`, 화면 `/afm/<장비>/tips` | 완료(사무실 미실행). 소급 범위는 모릅니다. |
| `measured_time` 열 (Q45, Q48) | redis 2 | 계약, adapter, mock, 화면 `measuredAt`(`utils/afmSearch.ts`)·`utils/afmUsage.ts` | 완료. 값의 모양은 Q55입니다. |
| `point_count`는 스캔한 위치 수 (Q43, Q49) | redis 2 | 주석만 | 완료. mock은 중단으로 작아진 값을 내지 않습니다. |
| repeat는 한 바퀴씩, `Sample Count`로 구분 (Q43) | raw D3, redis 3.1 | mock | **부분** — 화면은 아직 회차를 나누어 보여 주지 않습니다(Q54). |
| STOPPED 행은 하나, Summary는 빈 block (Q44) | raw D3, redis 3.1 | mock | 완료 |
| Mileage는 팁 단위 누적, 팁이 바뀌면 리셋 (Q46) | raw D3, redis 2 | 화면 `tipChanges`, mock | 완료. 단위와 예외는 Q56입니다. |
| MCNT만 폭이 퍼짐, 슬롯 단위 관리선 (Q51) | raw D3, redis 2 | 화면 `utils/afmTips.ts`, mock | 완료. MCNT는 `Tip ID`의 이름으로 가립니다. |
| `Valid` FALSE는 여전히 미실측, 열 이름 `Method ID` (Q32) | raw D3, redis 3.1 | mock | 완료 |
| 원본은 `.tiff`, 5EAP1501 재적재 예정, align·tip·capture 원본 적재됨 (Q35) | raw D5, redis 2 | adapter | **부분** — align·tip·capture 원본의 다운로드는 없습니다(Q35 (마)). |
| tip 이미지 두 계열 (Q53) | raw D5, redis 2·3.2 | mock, 화면 `imagePoint` | 완료. 이름의 나머지는 Q33·Q53입니다. |

## 8차 회신 (2026-10-07) — 7차 후속 질문의 답

[`to-questionnaire-afm-261007.md`](to-questionnaire-afm-261007.md)(Q55·Q56·Q46·Q54·Q35·Q53)에
대한 답입니다. 전부 실측 기반이라고 하셨으므로 `office 확인`으로 기록했습니다.

```text
답변. (전부 실측 기반)
Q55 (나) = Start ime - 6번째 필드 NA인 MAP608은 Info Start Time에서 HHMMSS 생성 (실측: time='014148' -> measured_time = '022914'). (다) 13키 짧은폼 = null (6건). (가) 6자리 선행 0 전수 확인, (라) MAPC01, 5EAP는 time과 전수 일치.
Q56 (나) = 없음. 같은 팁에서 감소 0 건, 리셋은 슬롯 변화와 동반. 단 재시작, 수동 초기화는 미실측이라 "감소 + Tip 값 변화 / Pick Up 갱신" 묶음을 권고. (가) 단위 미정(um 추정). (다) 리셋 후 첫 값 3520 (0아님).

핵심 새 실측
Q46: Pick Up/Put Back은 팁 단위 값입니다. 같은 팁의 연속 4개 측정 (02:50~06:31)에서 네 건 모두 Pick Up 01:33:39 동일. 값이 갱신되면 재픽업 -> Home이 쓰려는 같은 슬롯 새팁 + Mileage 리셋 확인 용도에 유효.
Q54: Sample Count는 반복 없는 Recipe에서 측정 내 안 바뀜 (4종 전수: 39/1/2/18), 첫 바퀴 값은 측정마다 다름 (1~47). 주의 실측: WID_11KEY는 Site ID가 있어도 반복이 없으면 안 바뀜 - Site ID 유뮤 != 반복 여부.
Q35 (마) 원본은 각자의 목록 (align .bmp -> align_dir_list, tip .png-> tip_dir_list, capture .png -> capture_dir_list) 실측 key 쌍 제공.
Q53: _C_PR=2440x1832 grayscale (~2.5MB) vs C_Result=448x336 RGB(440KB) - 전혀 다른 종류 (다) site 없는 recipe도 앞 4자리=point (0001_C_PR.webp)

Mileage 판정 제외 판단에 동의 (꽌측 전수에서 모든 reipce가 팁 단위 누적, "리셋 없는 종류" 관측 0건)
MCNT 판별 : 관측 8종 중 MCNT 포함은 2종뿐, 그외는 미정 + 5EAP OMCL-AC160TS는 Tip Width 대부분 NaN이므로 관리선 계산 방어 필요.
팁열 미수령 5개 항목은 이미 답이 됬던거라 요약 재전달 (소급 완료, 보존 3개월, 종류 수와 단위 없음. State 3종)
```

옮기면서 이렇게 읽었습니다.

- `Start ime`은 `Start Time`, `꽌측`은 `관측`, `reipce`는 `recipe`, `유뮤`는 `유무`의 오타로
  보았습니다.
- Q55 (나)의 실측(`time='014148'` → `measured_time='022914'`)은 **6번째 필드가 `NA`여도
  `Start Time`이 세션 시각과 다르다**는 뜻으로 읽었습니다. 4차 회신의 "뒤 시각이 NA인
  실측에서 Start Time이 첫 시각과 일치"와 어긋나므로 뒤의 답을 따랐습니다.
- Q56의 권고는 "Mileage 감소만으로는 팁이 바뀌었다고 보지 말고, 팁 값이 달라졌거나 Pick
  Up이 갱신된 것과 함께일 때만 보라"로 읽었습니다.
- Q54의 "39/1/2/18"은 반복 없는 recipe 네 종의 `Sample Count` 값으로 읽었습니다.
- Q35의 "실측 key 쌍 제공"은 key 쌍이 전달된 내용에 없어, webp와 원본의 짝(이름이 같고
  확장자만 다른지)은 여전히 가정으로 두고 질문서에 남겼습니다.
- Q53의 "전혀 다른 종류"는 두 계열이 크기·색이 다른 별개의 이미지라는 뜻으로 읽었습니다.
  무엇을 찍은 것인지와 마모가 보이는지는 답이 없어 남겼습니다.
- "종류 수와 단위 없음"은 "`Tip ID`는 관측 8종, `Tip Width`에는 단위가 붙지 않음"으로
  읽었습니다. 8종의 이름은 `DT-NCHR_CM`·`OMCL-AC160TS` 둘만 알아 Q57로 물었습니다.

### 가정이 틀렸던 곳

| 번호 | Home의 가정 | 실제 | 고친 곳 |
| --- | --- | --- | --- |
| Q55 | 6번째 필드가 `NA`이면 측정 시각은 세션 시각과 같습니다. | Info `Start Time`이 따로 있고 세션 시각과 다릅니다. 13키 Info는 null입니다. | mock의 `measured_time`·`Start Time` |
| Q56 | Mileage가 작아지면 팁이 바뀐 것입니다. | 관측상 맞지만 재시작·수동 초기화는 미실측이라 Pick Up 갱신과 묶어야 합니다. | 화면 `tipChanges`(`utils/afmTrend.ts`) |
| Q46 | `Last Pick Up Time`은 측정마다의 값일 수 있습니다. | 팁 단위 값이고 갱신은 재픽업입니다. | mock의 Info, 화면 `tipChanges` |
| Q54 | 반복이 없는 recipe의 `Sample Count`는 행마다 다를 수 있습니다(mock). | 한 측정 안에서 같은 값입니다(1~47). | mock |
| Q35 (마) | align·tip·capture의 원본도 TIFF입니다. | align은 `.bmp`, tip·capture는 `.png`입니다. | adapter `_is_original`(webp가 아닌 것), mock |

### 반영 현황 (2026-10-07, 8차)

| 받은 답 | 문서 | 구현 | 비고 |
| --- | --- | --- | --- |
| `measured_time`은 `HHMMSS`, `NA`이면 `Start Time`, 13키는 null (Q55) | redis 2, raw D2 | adapter, mock | 완료 |
| Mileage는 같은 팁에서 감소 0건, 감소는 Pick Up 갱신과 묶음 (Q56) | redis 2, raw D3 | 화면 `tipChanges` | 완료. 팁 모니터링은 목록에 Pick Up이 없어 팁 값 변화만 봅니다. |
| Pick Up·Put Back은 팁 단위 값 (Q46) | raw D3 | mock, 화면 `healthSeries` | 완료 |
| `Sample Count`는 측정 안에서 같고 반복 바퀴마다 1 증가 (Q54) | raw D3, redis 3.1 | mock | **부분** — 화면의 "1회차 / 2회차" 구분은 아직 없습니다. |
| 원본은 각자의 목록에 `.bmp`·`.png` (Q35) | raw D5, redis 2 | adapter, mock | **부분** — align·tip·capture 원본의 다운로드는 없습니다(짝은 Q35). |
| `_C_PR` 2440×1832, `C_Result` 448×336, 이름은 `…_0001_C_PR.webp` (Q53) | raw D5, redis 3.2 | 화면 `imagePoint`, mock | 완료 |
| Mileage 판정 제외에 동의 | redis 2 | 화면 `utils/afmTips.ts` | 완료 |
| OMCL-AC160TS는 폭이 대부분 NaN | redis 2, raw D3 | 화면 `utils/afmTips.ts`(5건 미만이면 관리선 없음), mock | 완료 |
| 팁 열: 소급 완료, 보존 3개월, `Tip ID` 8종, 폭에 단위 없음, `State` 3종 | redis 2 | 없음 | 기록만 |
