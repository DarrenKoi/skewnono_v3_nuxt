# AFM 적재 데이터 명세 — Office 회신

- 아직 답을 받지 못한 질문은 [`to-questionnaire-afm.md`](to-questionnaire-afm.md) 하나에
  모여 있습니다. 2026-10-06에 질문서 다섯 개를 그 문서로 합쳤고, 합치기 전의 질문 원문은
  git 이력(`cc09fa24`)에 있습니다.
- 정리된 스키마는 `docs/datatables/afm/`에 있습니다. 이 문서는 **회신 원문을 보존**하는
  용도이며, 오탈자도 받은 그대로 둡니다.
- 받은 답이 문서와 코드에 반영되었는지는 끝의 "반영 현황"에 있습니다.

## 주고받은 기록

회신을 받으면 이 문서에 **원문 그대로**와 **어떻게 읽었는지**를 함께 남깁니다. 답이 글자
하나로 온 회신은 질문 문장을 옆에 붙여, 이 문서만 보아도 무엇을 묻고 무엇을 들었는지 알 수
있게 합니다.

| 회신 | 날짜 | 무엇에 대한 답인지 | 보낸 질문 |
| --- | --- | --- | --- |
| 1차~3차 | 2026-10-02 | raw 파일에서 확인한 사실과 추가 실측 | 첫 질문서(git 이력 `cc09fa24`) |
| 4차 | 2026-10-02 | 후속 질문 Q1~Q15 | 같은 이력 |
| 5차 | 2026-10-06 | Redis·MinIO 적재 명세 전달 | 같은 이력 |
| 6차 | 2026-10-06 | 통합 질문서 Q21~Q42, P2 | [`to-questionnaire-afm.md`](to-questionnaire-afm.md)의 그때 판(git 이력) |
| 7차 | 2026-10-07 | Q32·Q35·Q43~Q46·Q48·Q49·Q51·Q53, 팁 열 추가 구현 | 같은 문서, [팁 열 추가 요청](../office-migration/to-office-afm-tip-columns.md) |
| 8차 | 2026-10-07 | Q55·Q56·Q46·Q54·Q35·Q53, Mileage 판단, 팁 열의 나머지 | [`to-questionnaire-afm-261007.md`](to-questionnaire-afm-261007.md) |
| 9차 | 2026-10-07 | 남은 질문 31개(글자로 답하는 양식) | [`to-questionnaire-afm-261007-2.md`](to-questionnaire-afm-261007-2.md) |
| 10차 | 2026-10-07 | 사무실 확인 목록 31개(변경이 실제 데이터에서 동작하는지) | [사무실 확인 목록](../office-migration/to-office-afm-verify-261007.md) |
| 11차 | 2026-10-07 | 10차에서 B였던 항목의 세부(스크립트 네 줄) | [사무실 확인 후속](../office-migration/to-office-afm-verify-261007-2.md) |
| 12차 | 2026-10-08 | Info의 `Start Time`·`End Time`(측정 소요시간 분석의 선행 확인) | 보낸 질문서 없음. [추가 서비스 추천 보고서](service-recommendations.md) 4절의 미확인 항목에 대한 답입니다. |

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

## 9차 회신 (2026-10-07) — 남은 질문 31개의 답

[`to-questionnaire-afm-261007-2.md`](to-questionnaire-afm-261007-2.md)에 대한 답입니다. 그
양식은 A가 언제나 "Home의 가정이 맞음"이고 `?`가 "미정·미실측"입니다. 실측 기반의 답이라
`office 확인`으로 기록했습니다.

```text
1. KST 추정 유지 - 원본에 시간대 정보 없음.
2. B (추출 파이프라인의 장비별 코드명(tool name). fab 여부는 원본 근거 없음 (미정)
3  A (관측 8종 중 2종 뿐. 미관측 종류의 존재는 미정.
4. A
5. A
6. 원본에 WAFER 방향 정보 없음.
7. A (tip 원본은 _C_PR=.png, C_Result=.bmp 두 확장자)
8 ? 담당자 확인 필요.
9. A
10. A
11. A
12. A
13. A
14. ? (같은 측정량 보증 근거 없음 -> recipe 별 묶음 유지 권장)
15. C align: 1_Result.webp (위치 키 없음) / capture: ..._0001.webp(종류 없이 위치 키로 끝)
16. A (위치당 1장; repeat도 sitexpoint당 1장)
17. B capture는 point마다; align은 측정마다 1~4장
18. B slot_number (recipe_name, lot_id는 현재 0건)
19. A
20. A ('5', '10', '21' - leading zero 없음)
21. A
22. A
23. A (관측 36종 기준)
24. A
25. A
26. 장비별로 팁 다름.
27. C_PR : 미정 (2440x grayscale, point마다) / C_Result: 미정 (448x336 RGB, 측정마다)
28. MAP608: Port 1 Slot 10 (Stage도 관측) / MAPC01: Info에 Sample Location 키 자체가 없음
(slot은 Slot No) / 5EAP1501: Port 1 Slot 5
29. X -11~5 / Y -7~4 / 최대 14 (MAP608 WID_REAL)
30. 133장 (MAP608 WID_REAL 실측; 원본 포함 189 객체)
31. MAP608: 67행 / 7일 / 16, 30. MAPC01: 108행 / 7일 21, 62. 5EAP1501: 28행 / 6일 /11, 12
표본 약 1주일 - 장기치는 미정, 기간 최대 3개월
Q58은 이미 적용.
```

### 번호별로 풀어 쓴 답

| 양식 번호 | 원 번호 | 질문 | 받은 답 | 가정과 |
| --- | --- | --- | --- | --- |
| 1 | P2 | 목록의 날짜·시각은 어느 시간대입니까. | KST 추정 유지 — 원본에 시간대 정보가 없습니다. | 미정 |
| 2 | Q40 | `alias`의 `R3`·`M15`는 그 장비의 fab입니까. | 아닙니다. 추출 파이프라인의 장비별 코드명입니다. fab인지는 원본에 근거가 없습니다. | **다름** |
| 3 | Q57 | 폭이 팁마다 다른 종류는 MCNT 2종뿐입니까. | 관측 8종 가운데 2종뿐입니다. 관측되지 않은 종류가 있는지는 미정입니다. | 같음 |
| 4 | Q58 | 목록에 `last_pick_up_time` 열을 추가할 수 있습니까. | 가능하고, 그 이름으로 이미 적용했습니다. | 같음 |
| 5 | Q36 | profile도 Result 이미지도 없는 recipe는 `point_count`가 null입니까. | null입니다. | 같음 |
| 6 | Q24 | `Site Y`가 커지면 웨이퍼의 위쪽입니까. | 원본에 웨이퍼 방향 정보가 없습니다. | 미정 |
| 7 | Q35 | 원본은 webp와 이름이 같고 확장자만 다릅니까. | 네 종류 모두 맞습니다. tip의 원본은 `_C_PR`이 `.png`, `C_Result`가 `.bmp`입니다. | 같음(확장자 하나 새로 앎) |
| 8 | Q53 | `_C_PR`을 시간순으로 놓으면 마모가 보입니까. | 담당자 확인이 필요합니다. | 미정 |
| 9 | Q52 | 팁을 바꾸는 기준 숫자가 있습니까. | 없습니다. | 같음 |
| 10 | Q47 | 장비가 멈춘 날을 기록한 자료가 있습니까. | 없습니다. | 같음 |
| 11 | Q31 | Summary의 값도 문자열입니까. | 문자열입니다. | 같음 |
| 12 | Q22 | 한 측정 안에서 두 block이 같은 method 명을 가진 적이 있습니까. | 없습니다. | 같음 |
| 13 | S2 | Summary의 통계는 장비가 쓴 값 그대로입니까. | 그대로입니다. | 같음 |
| 14 | S8 | 다른 recipe의 같은 이름 컬럼은 비교할 수 없는 값입니까. | 같은 측정량이라는 근거가 없습니다. recipe별 묶음을 유지하라고 권했습니다. | 미정(방식은 유지) |
| 15 | Q33 | align·capture 이름은 `_<위치 키>_<종류>.webp`로 끝납니까. | 아닙니다. align은 `1_Result.webp`(위치 키 없음), capture는 `…_0001.webp`(종류 없이 위치 키로 끝남)입니다. | **다름** |
| 16 | Q27 | Result 이미지는 point마다 한 장입니까. | 위치마다 한 장입니다. repeat도 Site × point마다 한 장입니다. | 같음 |
| 17 | Q27 | align·capture 이미지는 측정마다 한 장입니까. | 아닙니다. capture는 point마다, align은 측정마다 1~4장입니다. | **다름** |
| 18 | Q36 | Recipe·Lot·Slot 칸은 항상 채워져 있습니까. | `slot_number`는 null인 행이 있습니다. `recipe_name`·`lot_id`는 지금 0건입니다. | **다름** |
| 19 | Q36 | `NA`가 값으로 그대로 들어가는 칸이 있습니까. | 없습니다. | 같음 |
| 20 | Q29 | `slot_number` 값은 어떻게 생겼습니까. | `5`, `10`, `21` — 앞에 0이 없습니다. | (가정 없었음) |
| 21 | Q50 | 이름이 같은 recipe는 같은 recipe이고 이력 기록은 없습니까. | 맞습니다. | 같음 |
| 22 | Q50 | ` (1)` 꼬리가 붙은 recipe는 원본과 별개입니까. | 별개입니다. | 같음 |
| 23 | Q50 | 대소문자·공백만 다른 recipe 이름이 있습니까. | 없습니다(관측 36종 기준). | 같음 |
| 24 | Q42 | 보존 3개월은 측정 시각 기준입니까. | 측정 시각입니다. | 같음 |
| 25 | Q40 | MAP608의 fab은 미정입니까. | 미정입니다. | 같음 |
| 26 | Q57 | 관측된 `Tip ID` 8종을 장비별로. | "장비별로 팁이 다르다"는 답만 받았고 이름은 받지 못했습니다. | 미정 |
| 27 | Q53 | `_C_PR`과 `C_Result`는 무엇을 찍은 것입니까. | 둘 다 미정입니다(크기와 장수는 8차 그대로). | 미정 |
| 28 | Q29 | Info `Sample Location` 값 전체. | MAP608 `Port 1 Slot 10`(`Stage`도 관측), 5EAP1501 `Port 1 Slot 5`. MAPC01은 Info에 그 key가 없고 slot은 `Slot No`에 있습니다. | 읽는 방식은 맞음 |
| 29 | Q24 | `Site X`·`Site Y`의 범위와 한 Site의 point 최대. | X -11~5, Y -7~4, 최대 14(MAP608 `WID_REAL`). | **다름**(가정 -3~2) |
| 30 | Q27 | 측정 한 건의 이미지 최대 수. | webp 133장(MAP608 `WID_REAL`), 원본 포함 189 객체. | **다름**(가정 수십 장) |
| 31 | Q42 | 장비별 행 수 / 일수 / 하루 건수(보통, 최대). | MAP608 67행 / 7일 / 16, 30. MAPC01 108행 / 7일 / 21, 62. 5EAP1501 28행 / 6일 / 11, 12. 약 1주일 표본이고 장기치는 미정입니다. | 표본만 |

옮기면서 이렇게 읽었습니다.

- 1번과 6번은 글자가 없지만 "근거 없음"이므로 `?`(미정)로 읽었습니다.
- 2번의 "코드명(tool name)"은 `alias`가 fab 이름이 아니라 파이프라인이 장비에 붙인
  이름이라는 뜻으로 읽었습니다. 4차 회신의 "코드로 확인 MAPC01=R3, 5EAP1501=M15"는 그
  코드명을 본 것이므로, **두 장비의 fab은 사무실 쪽에서 확인된 적이 없는 것**이 됩니다.
- 18번의 "B slot_number"는 null이 나오는 칸이 `slot_number`라는 뜻으로 읽었습니다.
  28번의 `Stage`(슬롯이 없는 `Sample Location`)가 그 경우로 보입니다(추정).
- 26번은 이름 목록이 없어 답을 받지 못한 것으로 처리했습니다.
- 31번의 "기간 최대 3개월"은 보존 기간이 3개월이므로 목록도 최대 3개월치가 쌓인다는
  뜻으로 읽었습니다.

### 가정이 틀렸던 곳

| 번호 | Home의 가정 | 실제 | 고친 곳 |
| --- | --- | --- | --- |
| Q40 | `alias`는 fab입니다. | 파이프라인의 장비 코드명이고 fab이라는 근거가 없습니다. | 문서. adapter는 `fab`이 비면 여전히 `alias`를 내지만 화면은 그 값을 쓰지 않습니다(고정 표). |
| Q33 | align·capture 이름은 `_<위치 키>_<종류>.webp`로 끝납니다. | align은 `N_Result.webp`, capture는 위치 키로 끝납니다. | 화면 `imagePoint`(`utils/afmPoints.ts`), mock |
| Q27 | align·capture는 측정마다 한 장입니다. | capture는 point마다, align은 1~4장입니다. | mock |
| Q36 | Slot 칸은 항상 채워져 있습니다. | `slot_number`가 null인 행이 있습니다. | 문서. adapter는 빈 문자열로 내고 화면은 빈 칸으로 둡니다. |
| Q29 | `Sample Location`은 `Slot N`입니다(mock). | `Port 1 Slot N`이고 `Stage`도 있습니다. | mock. 화면은 `Slot` 뒤의 숫자만 읽어 그대로 동작합니다. |
| Q29 | `slot_number`는 두 자리입니다(mock). | 앞에 0이 없습니다. | mock |
| Q35 | tip의 원본은 모두 `.png`입니다. | `C_Result`의 원본은 `.bmp`입니다. | mock |
| Q24 | `Site X`·`Site Y`는 -3~2입니다. | X -11~5, Y -7~4입니다. | 문서. 화면의 Site 지도는 값의 범위에 맞춰 그리므로 그대로입니다. |

### 반영 현황 (2026-10-07, 9차)

| 받은 답 | 문서 | 구현 | 비고 |
| --- | --- | --- | --- |
| 목록에 `last_pick_up_time` 열 (Q58) | redis 2 | 계약, adapter, mock, 화면 `tipPoints`(`utils/afmTips.ts`) | 완료(사무실 미실행). 팁 모니터링의 세로선도 시계열 비교와 같은 규칙이 되었습니다. |
| 원본은 webp와 이름이 같고 확장자만 다름, `C_Result` 원본은 `.bmp` (Q35) | redis 2, raw D5 | mock | **부분** — align·tip·capture 원본의 다운로드는 아직 없습니다. |
| align `N_Result.webp` 1~4장, capture는 point마다 위치 키로 끝남 (Q33, Q27) | redis 3.2, raw D5 | 화면 `imagePoint`, mock | 완료 |
| `slot_number`는 앞에 0이 없고 null일 수 있음, `Sample Location`은 `Port 1 Slot N`·`Stage` (Q29, Q36) | redis 2·3.1, raw D3 | mock | 완료. mock은 null과 `Stage`를 내지 않습니다. |
| `alias`는 코드명 (Q40) | redis 1, raw D1 | 없음 | 기록만. fab은 담당자 확인이 필요합니다. |
| Summary는 문자열·장비 값 그대로, 같은 method 명 block 없음 (Q31, S2, Q22) | redis 3.1, raw D3 | 없음(가정과 같음) | 완료 |
| recipe 이름은 그대로 묶음 (Q50), 보존은 측정 시각 기준 (Q42) | redis 공통·2 | 없음(가정과 같음) | 완료 |
| Site 범위 X -11~5 / Y -7~4, 한 Site 최대 14 point (Q24) | raw D3 | 없음 | 기록만 |
| 측정 한 건의 webp 최대 133장 (Q27) | redis 2 | 없음 | 기록만. 요청 제한(5초 50회)에 걸릴 수 있습니다. |
| 팁 교체 기준·장비 정지 기록 없음 (Q52, Q47) | redis 2 | 없음 | 기록만 |

## 사용자 확인 (2026-10-07) — 시간대와 fab

9차 회신에서 사무실이 "원본에 근거 없음"으로 돌려보낸 두 가지를 사용자가 정했습니다.
사무실 실측이 아니므로 `user-confirmed`로 기록했습니다.

```text
KST라고 추정하고 진행. 세 장비의 fab은 MAP608은 PKG, MAPC01은 R3, 5EAP1501은 M15
```

| 번호 | 정한 것 | 문서 | 구현 |
| --- | --- | --- | --- |
| P2 | 목록의 날짜·시각은 KST로 보고 진행합니다. | raw D2 | 바뀐 것 없음(이미 KST로 셉니다) |
| Q40 | MAP608 = PKG, MAPC01 = R3, 5EAP1501 = M15 | raw D1, redis 1 | adapter `get_tools`가 `alias` 대신 이 표로 fab을 채웁니다. mock과 화면의 고정 표는 이미 같은 대응입니다. |

## 사용자 결정 (2026-10-07) — 답을 받아 두고 만들지 않았던 세 가지

9차 회신까지의 반영 현황에서 **부분**으로 남아 있던 것을 사용자가 만들기로 정했습니다.

```text
msr_image 처럼 afm도 이미지 다수에 대한 제한을 없애야함.  원본 다운로드 기능 구현해야함. 1회차 2회차 가능하면 표
```

| 정한 것 | 근거가 된 답 | 구현 |
| --- | --- | --- |
| AFM 화면의 요청을 5초 50회 제한에서 뺍니다. | 측정 한 건의 webp 최대 133장(9차 30번) | `backend/__init__.py`의 `_EXEMPT_BLUEPRINTS`에 `afm` |
| align·tip·capture에도 원본 다운로드를 둡니다. | 원본은 webp와 이름이 같고 확장자만 다름(9차 7번), 각자의 목록에 있음(8차 Q35) | provider `get_tiff_original`이 모든 이미지 목록에서 원본을 찾고, 목록의 모든 이미지가 `original_url`을 가집니다. `tiff.zip?type=`으로 종류별 전체도 받습니다. |
| 반복 측정을 회차로 나누어 표에 보입니다. | 한 바퀴 돈 뒤 다시 돎(7차 Q43), `Sample Count`가 바퀴마다 1 증가(8차 Q54) | 화면 `tagLaps`(`utils/afmPoints.ts`) — 측정 포인트 표의 `회차` 열·필터·Excel |

## 10차 회신 (2026-10-07) — 사무실 확인 결과

[사무실 확인 목록](../office-migration/to-office-afm-verify-261007.md)에 대한 답입니다. 그
양식은 A가 "적힌 기대 결과 그대로", B가 "다름", `?`가 "확인하지 못함"입니다. 사무실에서
adapter를 다시 복사하고 실제 Redis·MinIO로 본 결과이므로 `office 확인`으로 기록했습니다.
회신은 "간추린 답"이라 B의 세부는 7번에만 있습니다.

```text
0 A
1 A
2 A
3 A
4 A
5 B
6 A
7 B
8 A
9 A
10 A
11 B
12 B
13 A
14 A
15 A
16 A
17 B
18 A
19 A
20 A
21 A
22 A
23 A
24 A
25 A
26 A
27 A
28 A
29 -
30 A

7번 실패 목록:
office provider 기준
test_capture_dir_list_populated_for_every_row (capture 없는 측정 존재)
test_get_anlysis_image_svg_valid_for_all_types ( svg 아니라 webp)
test_serve_route_returns_svg (동일)
test_profile_sampling...file_size (total key 없음)

느린 곳 : 상세 본문 5~8초, Result 탭 lazy 로드 느림.
이상 값 : MAP608 NT-DT50-NCHR Tip Width -105.21(음수) - tips 화면에서 발견.
```

### 번호별로 풀어 쓴 답

| 번호 | 확인한 것 | 받은 답 |
| --- | --- | --- |
| 0 | `main` 받기, `office.py` 다시 복사, 재빌드, `STALE` 경고 없음 | 그대로 |
| 1 | 데이터 스크립트가 오류 없이 끝까지 실행됨 | 그대로 |
| 2 | `measured_time`은 값이 있으면 6자리 숫자 | 그대로 |
| 3 | MAP608만 `measured_time`이 `time`과 다른 행이 있음 | 그대로 |
| 4 | `last_pick_up_time`에 날짜·시각 값이 나옴 | 그대로 |
| 5 | `slot_number`가 0으로 시작하는 행이 없음 | **다름** — 0으로 시작하는 값이 있습니다(장비와 값은 받지 못함). |
| 6 | fab이 MAP608 = PKG, MAPC01 = R3, 5EAP1501 = M15 | 그대로 |
| 7 | `pytest backend/afm`이 실패 없이 끝남 | **다름** — 4건 실패(아래). |
| 8 | provider가 `office` | 그대로 |
| 9 | 목록 응답에 `measured_time`·`last_pick_up_time` key가 있음 | 그대로 |
| 10 | 목록에서 한 세션의 측정들이 서로 다른 시각으로 보임 | 그대로 |
| 11 | 목록의 SLOT이 앞에 0 없이 보이고 없는 행은 빈 칸 | **다름** — 세부는 받지 못했습니다(5번과 같은 원인으로 보입니다). |
| 12 | 반복 측정의 표에 `회차` 열이 있고 1회차 다음에 2회차가 나옴 | **다름** — 세부는 받지 못했습니다. |
| 13 | `회차` 필터로 2회차만 남길 수 있음 | 그대로 |
| 14 | 반복이 없는 측정에는 `회차` 열이 없음 | 그대로 |
| 15 | 상세의 SLOT이 세 장비 모두 채워짐 | 그대로 |
| 16 | 네 이미지 탭이 모두 그려짐 | 그대로 |
| 17 | Capture 타일에 포인트 이름이 보이고 누르면 그 포인트가 선택됨 | **다름** — 파일명이 그대로 보입니다. |
| 18 | Tip 탭이 포인트마다 한 장과 `C_Result` 한 장 | 그대로 |
| 19 | 탭마다 "원본 전체" zip에 맞는 확장자가 들어 있음 | 그대로 |
| 20 | 팝업의 "원본 다운로드"로 받은 `.bmp`·`.png`가 열림 | 그대로 |
| 21 | 이미지가 많은 측정을 스크롤해도 429가 없음 | 그대로 |
| 22 | 5EAP1501의 Result 탭에 "원본 전체"가 나옴 | 나옵니다 — **5EAP1501 원본 재적재가 끝났습니다.** |
| 23 | 세 장비의 팁 모니터링이 종류별 목록으로 나옴 | 그대로 |
| 24 | MCNT는 "관리선은 팁마다", 그 밖은 범위 표시 | 그대로 |
| 25 | `OMCL-AC160TS`가 오류 없이 나옴 | 그대로 |
| 26 | 한 팁 안에서 Mileage가 커지기만 함 | 그대로 |
| 27 | 가동 현황의 시간대가 측정 시각대로 퍼짐 | 그대로 |
| 28 | Mileage가 톱니 모양이고 떨어지는 자리에 세로선이 있음 | 그대로 |
| 29 | (28이 다를 때만) | 해당 없음 |
| 30 | console 오류 없음 | 그대로 |

옮기면서 이렇게 읽었습니다.

- 13번이 A이므로 12번의 B는 "`회차` 열이 없다"가 아니라 값이나 순서가 기대와 다르다는
  뜻으로 보입니다(추정). 세부를 다시 물었습니다.
- 5번은 9차 회신의 "`5`, `10`, `21` — 앞에 0이 없음"과 어긋납니다. 장비마다 다른 것으로
  보이지만(추정) 어느 쪽인지 받지 못해 다시 물었습니다. 화면은 받은 값을 그대로 보여 주므로
  틀린 값이 나가지는 않습니다.
- 17번은 9차 회신의 "capture는 `…_0001.webp`"대로라면 포인트를 읽어야 합니다. 실제 이름과
  포인트 이름이 어긋나는 것이므로 둘을 한 쌍 받아야 고칠 수 있습니다.
- `test_get_anlysis…`는 `test_get_analysis…`의 오타로 보았습니다.

### 실패한 테스트 4건

네 건 모두 **코드가 아니라 테스트의 결함**입니다. `data.py`와 routes를 거치는 테스트가 mock의
사실을 단정하고 있어, 사무실에서 dispatcher가 office adapter로 바뀌면 실패합니다.

| 테스트 | 단정하던 것 | 사무실에서 |
| --- | --- | --- |
| `test_capture_dir_list_populated_for_every_row` | 모든 측정에 capture가 있음 | capture가 없는 측정이 있습니다. |
| `test_get_analysis_image_svg_valid_for_all_types` | 이미지가 SVG 문자열임 | 저장된 webp(bytes)입니다. |
| `test_serve_route_returns_svg` | 응답이 `image/svg+xml`임 | `image/webp`입니다. |
| `test_the_route_thins_a_dense_scan_and_reports_the_file_size` | mock의 파일 이름으로 profile을 찾음 | 그 이름의 측정이 없어 404이고 `total`이 없습니다. |

고친 방법: 세 테스트 파일을 mock으로 고정했습니다(`backend/afm/tests/conftest.py`의
`mock_provider`). 사무실 adapter의 동작은 `test_contract.py`와 `test_office_template.py`가
따로 봅니다.

새로 알게 된 사실도 하나 있습니다 — **capture 이미지가 없는 측정이 있습니다.** mock은 모든
측정에 capture를 냅니다(OFFICE-VERIFY였던 것).

### 덧붙여 받은 것

| 받은 것 | 조치 |
| --- | --- |
| 측정 상세 본문이 5~8초 걸림 | 원인을 모릅니다(adapter는 측정 한 건에 MinIO 객체 셋을 차례로 읽습니다). 구간별 시간을 재는 스크립트를 보냈습니다. |
| Result 탭의 이미지가 느리게 뜸 | 이미지 한 장마다 MinIO를 읽기 때문입니다. 저장된 webp에 `Cache-Control: private, max-age=3600`을 붙여 다시 열 때는 받지 않게 했습니다. 처음 여는 속도는 그대로입니다. |
| MAP608 `NT-DT50-NCHR`의 `Tip Width`가 -105.21 | 새 `Tip ID` 이름을 기록했습니다. 음수가 실패 표지인지 실제 값인지 물었습니다. 화면은 지금 값 그대로 보여 주고, 종류의 관리선 밖이므로 "밖"으로 짚습니다. |

### 반영 현황 (2026-10-07, 10차)

| 받은 답 | 문서 | 구현 | 비고 |
| --- | --- | --- | --- |
| 26개 항목이 기대대로 동작 | 이 문서 | 없음 | adapter가 사무실에서 실제로 실행되었습니다. |
| 5EAP1501 Result 원본 재적재 완료 (22번) | redis 2 | 없음 | 기록만 |
| 테스트 4건이 사무실에서 실패 (7번) | 이 문서 | `backend/afm/tests/conftest.py`, 세 테스트 파일 | 완료 |
| capture가 없는 측정이 있음 (7번) | redis 2 | 없음 | 기록만. mock은 모든 측정에 capture를 냅니다. |
| Result 탭이 느림 | 이 문서 | `routes.py`의 `_image` 캐시 header | **부분** — 처음 여는 속도는 그대로입니다. |
| 상세 본문 5~8초 | 이 문서 | 없음 | **미해결** — 측정값을 기다립니다. |
| `slot_number`에 0으로 시작하는 값 (5·11번) | redis 2 | 없음 | **미해결** — 9차와 어긋납니다. |
| 반복 측정의 회차가 기대와 다름 (12번) | 이 문서 | 없음 | **미해결** — 세부를 기다립니다. |
| Capture 타일에 포인트 이름이 안 붙음 (17번) | 이 문서 | 없음 | **미해결** — 실제 이름을 기다립니다. |
| `Tip Width` 음수, 새 Tip ID `NT-DT50-NCHR` | redis 2, raw D3 | 없음 | 기록만. 뜻을 물었습니다. |

후속 질문은 [사무실 확인 후속](../office-migration/to-office-afm-verify-261007-2.md)에
있습니다.

## 11차 회신 (2026-10-07) — 확인 후속의 답

[사무실 확인 후속](../office-migration/to-office-afm-verify-261007-2.md)에 대한 답입니다.
스크립트 네 줄은 받았고, 글자로 고르는 질문 A(회차)·B(음수 폭)·C(가장 느린 요청)는 받지
못했습니다.

```text
1. 이미 고친 것 - 확인
7번 4건. 이제 통과.
Result 탭 캐시 : 확인. Cache-Control : private, max-age=3600.

2. 스크립트 네 줄
MAP608 slot0=['07', '08'] neg={} cap=0002_X005_Y0001_0001.webp pt=['0001_X000_Y000_0001']
MAPC01 slot0=['01', '02', '03'] neg={} cap=0002_X003_Y002_0001.webp pt=['0001_X-003_Y002_0001']
5EAP1501 slot0=[] neg={} cap=7685PNMP768.16_003.webp pt=['0001']
t list 0.0 detail 0.0 again 0.0 img 0.0 prof 0.0 pts 5

t줄이 전부 0.0인 이유: 스크립트 앞부분(3장비 루프)이 adaptor의 lru_cache(60초 TTL)를 이미 데워서 -측정이 아니라 캐시 히트 시간입니다. 참고로 Flask 재시동 직후 콜드로 직접 재면 전부 1초 미만

17번 단서 : cap webp 이름에서 포인트 부분 (0002_X005_Y000_0001)과 available_points(0001_X000_Y000_0001)은 접두사 양식이 같아 문자열 매칭 가능 - pt 첫 포인트는 cap 이름과 어긋나지 않음 ( 이름 규칙 자체는 일치, 어긋난 건 캡처가 포인트별로 일부만 있는 것).
pytest 최종 상태 (office): 3failed, 81passed - 실패 3건은 test_contract profile 3건 (위 1절), 원인은 테스트 전제 vs 실데이터.
```

옮기면서 이렇게 읽었습니다.

- 첫 줄의 `0002_X005_Y0001_0001`은 아래 "17번 단서"에 적힌 `0002_X005_Y000_0001`의 오타로
  보았습니다.
- `slot0`에 값이 있는 MAP608·MAPC01은 **슬롯을 파일명의 `.nn` 꼬리로 채운 행이 있는 장비**로
  읽었습니다(6차 회신: Info에서 못 읽으면 꼬리로 채움). 9차의 "앞에 0 없음"은 Info에서 읽은
  행의 모양이므로 두 답이 모두 맞습니다.
- `neg={}`가 세 장비 모두이므로 **음수 `Tip Width`는 데이터에 없습니다.** 10차의 "-105.21"은
  측정값이 아니라 종류 머리줄에 찍히는 관리선 하한(중앙값 - 3σ)이었을 것으로 봅니다(추정 —
  B의 답은 받지 못했습니다).
- `t` 줄은 Home이 스크립트를 잘못 짠 것입니다. 앞의 루프가 같은 목록을 먼저 읽어 캐시를
  데웠습니다. "콜드로 재면 전부 1초 미만"을 **adapter는 느린 원인이 아니다**로 읽었습니다.
- "17번 단서"는 MAP608·MAPC01에 대한 설명으로 읽었습니다. 5EAP1501의
  `7685PNMP768.16_003.webp`는 3자리 번호로 끝나 point 이름(`0001` 꼴)과 **글자로는 맞지
  않습니다.** 10차 17번에서 파일명이 보인 것이 이 장비였을 것으로 봅니다(추정).
- "test_contract profile 3건"은 profile 점·profile metadata·profile 이미지를 **첫 point**로
  찾는 세 테스트로 읽었습니다.

### 가정이 틀렸던 곳

| 무엇 | Home의 가정 | 실제 | 고친 곳 |
| --- | --- | --- | --- |
| `slot_number` | 한 가지 모양입니다. | Info에서 온 `5`와 파일명에서 온 `07`이 섞여 있습니다. | adapter `_slot`(숫자면 앞의 0을 뗌) |
| capture | 모든 point에 한 장씩 있습니다. | 일부 point에만 있고, 없는 측정도 있습니다. | mock, 테스트 |
| capture 이름 | 위치 키로 끝납니다. | 5EAP1501은 3자리 번호로 끝납니다. | 화면 `imagePoint`(3자리 번호를 같은 번호의 point로), mock |
| profile·Result 이미지 | profile이 있는 측정은 첫 point에 profile이 있습니다. | 모든 point에 있지 않습니다. | `test_contract.py`(파일이 실제로 있는 point를 고름) |
| 관리선 | 하한은 중앙값 - 3σ 그대로입니다. | 폭·횟수는 0 아래로 갈 수 없는데 하한이 음수로 찍혔습니다. | 화면 `tipLimits`(하한을 0에서 자름) |
| 측정 시간 스크립트 | 호출마다 실제로 읽습니다. | 앞의 루프가 캐시를 데워 0.0만 나왔습니다. | 없음 — 답으로 충분했습니다. |

### 반영 현황 (2026-10-07, 11차)

| 받은 답 | 문서 | 구현 | 비고 |
| --- | --- | --- | --- |
| 테스트 4건 통과, 이미지 캐시 header 확인 | 이 문서 | 없음 | 10차의 수정이 사무실에서 확인되었습니다. |
| `slot_number`에 두 모양 | redis 2 | adapter `_slot` | 완료(사무실 미실행) |
| 음수 `Tip Width` 0건 | redis 2, raw D3 | 화면 `tipLimits` 하한 0 | 완료. 10차의 기록을 바로잡았습니다. |
| capture는 일부 point에만 | redis | mock | 완료 |
| 5EAP1501 capture는 `_003` 꼴 | redis | 화면 `imagePoint`, mock | 완료. `_003`이 point 3이라는 것은 **가정**입니다. |
| adapter 호출은 콜드에서도 1초 미만 | redis | 없음 | 상세 5~8초의 원인은 **미해결**(adapter 아님). |
| `test_contract` profile 3건 실패 | 이 문서 | `test_contract.py` | 완료(사무실 미실행) |
| 회차가 어떻게 달랐는지 (A) | — | — | **답을 받지 못함** |

## 12차 전달 (2026-10-08) — Start Time·End Time

측정 소요시간 분석을 논의하던 중 사용자가 전한 내용입니다. 질문서를 보내고 받은 회신이
아니며, 실측 수치가 들어 있으나 누가 언제 돌린 결과인지는 받지 못했으므로
`user-confirmed`로 기록했습니다.

```text
For the Duration anaylsis, Start/End Time format is like 2026.10.01 00:13:58. MAP608의 경우 몇몇 건에서 파일명 시각자리가 NA -> 이 경우 Start Time이 그 측정의 유일한 시각 소스, End Time 없음.
NA 슬롯 세션 (예:#261002#105957# 4건)에서 Start Time이 11:29:56 -> 11:56:00 -> 12:22:06 -> 12:48:12로 측정 마다 순차 증가 - 세션 시각 (파일명 앞 시각)이 아니라 개별 측정 시작 시각이맞음. 자정 넘김 케이스 있음 1건 실측 (22:32:28) -> (00:11:13) 종료.
주의. data CSV에만 존재 - MAPC01은 현재 data CSV가 없어 Start/End Time 쓸 수 없음 (대안: info CSV Date, 밀리초 포함). _Info.csv에도 없음(두 스키마 모두)
End Time은 측정 완료 후에만 기록 - 진행 중에는 파일에는 없어서 완료 판정 마커로 쓰는 현재 설계가 맞음.
KST 추정으로 진행.
정렬 시 D2 time(세션 시작 시각)으로 정렬하면 세션 측정들이 묶임 - 개별 측정 시각 정렬에는 Start Time 기반 measured_time을 써야함.
MAP608 측정키 6번째 필드가 NA면 Info Start Time에서 HHMMSS 추출, 나머지 장비는 파일명 time과 통일.
```

### 어떻게 읽었는지

- `anaylsis`는 `analysis`의 오타로 읽었습니다.
- "NA 슬롯"은 웨이퍼 슬롯이 아니라 **파일명의 측정 시각 자리가 `NA`**라는 뜻으로 읽었습니다.
- "End Time 없음"은 두 가지로 읽혀 사용자에게 되물었고, 같은 날 답을 받았습니다.

  ```text
  1. no End Time at all for some cases for MAP608. In that case, we do not analyze. (note that the End Time is mssing in the front-end)
  ```

  MAP608의 일부 측정에는 `End Time`이 아예 없습니다. 그런 측정은 소요시간을 분석하지
  않고, 화면에 `End Time`이 없다는 것을 표시합니다. `mssing`은 `missing`의 오타로
  읽었습니다. 어느 측정이 해당하는지는 받지 못했습니다.
- MAPC01의 대안(info CSV `Date`)을 쓸지에 대해서도 같은 날 답을 받았습니다.

  ```text
  MAPC01 -> skip analysis too
  ```

  MAPC01은 소요시간을 분석하지 않습니다. `Date`로 대신 계산하는 길은 만들지 않습니다.
- "data CSV에만 존재"는 `Start Time`·`End Time`이 data CSV의 Info 섹션에만 있다는 뜻으로
  읽었습니다.
- "MAPC01은 현재 data CSV가 없어"가 MAPC01에 point 데이터도 없다는 뜻인지는 알 수
  없습니다. 10차 확인에서 그런 보고가 없었으므로 mock의 MAPC01 point 행은 그대로 두었습니다.
- 22:32:28 → 00:11:13은 날짜가 함께 기록되므로 98분 45초로 계산했습니다.
- 마지막 두 줄은 8차 회신(Q55)과 같은 내용이며 바뀌는 것이 없습니다.

### 가정이 틀렸던 곳

| 무엇 | Home의 가정 | 받은 답 | 고친 곳 |
| --- | --- | --- | --- |
| `Start Time`·`End Time`의 표기 | `2026-10-01 00:13:58` (`-`) | `2026.10.01 00:13:58` (`.`) | mock |
| MAPC01의 Info | 8건 중 1건은 15키 | 지금은 `Start Time`·`End Time`을 쓸 수 없습니다. | mock(8건 모두 13키) |
| 추천 보고서 4.2의 "End Time 형식 미확인" | 여러 형식 후보를 지원 | 한 형식이며 날짜가 함께 있습니다. | 추천 보고서 4절 |

### 반영 현황 (2026-10-08, 12차)

| 받은 답 | 문서 | 구현 | 비고 |
| --- | --- | --- | --- |
| 표기 `2026.10.01 00:13:58`, KST | raw D3 Info, redis 2 | mock `_INFO_TIME_FORMAT` | 완료. 화면의 `Date.parse`는 Chrome(V8)에서 이 표기를 같은 시각으로 읽습니다(Node로 확인). 표준이 보장하는 표기는 아니므로 소요시간 파서는 형식을 직접 읽어야 합니다. |
| data CSV의 Info에만 있음, MAPC01은 현재 없음 | raw D3 Info | mock(MAPC01 13키만) | 완료. MAPC01은 분석하지 않기로 했으므로 info CSV `Date`는 쓰지 않습니다. |
| `End Time`은 완료 후에만 기록 | raw D3 Info | 없음 | ETL의 완료 판정과 같습니다. |
| 자정 넘김 1건, 세션 내 순차 증가 | raw D2, raw D3 Info | mock(날짜가 붙어 자연히 재현) | 완료. mock의 소요시간 분포(1~30분)는 지어낸 값입니다. |
| 정렬은 `measured_time` | redis 2 | 없음(화면은 이미 그렇게 정렬) | 8차와 같습니다. |
| MAP608 일부 측정에 `End Time` 없음, 분석하지 않고 화면에 밝힘 | raw D3 Info | mock(시각 자리가 `NA`인 측정에서 key를 뺌) | 완료. 어느 측정인지와 key가 빠지는 방식은 **가정**입니다. 화면 표시는 소요시간 분석을 만들 때 함께 넣습니다. |
