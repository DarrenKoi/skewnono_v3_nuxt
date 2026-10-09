# AFM 현재 구현 상태 — 데이터 모델, 화면, 공백 (2026-10-09 기준)

경로는 모두 저장소 루트(`/Users/daeyoung/Codes/skewnono_v3_nuxt`) 기준입니다. 출처 표기는 발견한 그대로 옮겼습니다:
`office 확인 YYYY-MM-DD`(사무실 실측), `user-confirmed`(사용자 전달), `OFFICE-VERIFY`(가정).
이 조사는 코드와 문서만 읽었습니다. 서버·브라우저·사무실 Redis/MinIO 는 실행하거나 접속하지 않았습니다.

먼저 읽을 것 세 가지:

1. 저장소에 이미 같은 주제의 문서 두 개가 있습니다 — `docs/afm/feature-summary.md`(2026-10-08, 화면별 기능 요약)와
   `docs/afm/service-recommendations.md`(2026-10-08, 추가 서비스 7개 추천 + 보류 6개). 이 노트는 그 둘을 코드와 대조해 검증·보완한 것입니다.
2. 오래된 문서 두 곳이 현재 상태와 어긋납니다. `docs/office-migration/STATUS.md:63-75` 와
   `docs/research/2026-10-06-page-value-plans.md:23,521` 은 "AFM 사내 어댑터가 stub(`NotImplementedError`)"이라고 적지만,
   `backend/afm/MIGRATION.md:12` 는 "run at the office 2026-10-07; 26 of 31 checks as expected"이고 `office_example.py` 는 572줄의 완성된 어댑터입니다.
3. AFM 데이터에는 **spec/target, device, step(oper), 제품 코드가 없습니다.** 숫자는 recipe 가 이름 붙인 `(nm)` 컬럼뿐입니다.

## 1. AFM 장비와 데이터 원천은 무엇인가

### Takeaway
장비는 3대(MAP608=PKG, MAPC01=R3, 5EAP1501=M15)이고, 웹은 장비 raw 파일이 아니라 외부 ETL 이 적재한 Redis hash(장비별 측정 목록 parquet) + MinIO 객체(상세·profile·이미지)만 읽습니다. 보존은 3개월, 갱신은 30분 주기이며 웹은 쓰지 않습니다.

### Cited Findings
- 장비 3대와 fab 대응 MAP608=PKG, MAPC01=R3, 5EAP1501=M15 는 `user-confirmed 2026-10-07` 입니다. 사무실 원본·적재물 어디에도 fab 필드가 없고(`afm_d1_tools.fab` 은 빈 문자열, `alias` 는 파이프라인 코드명), 어댑터와 프런트 모두 고정 표로 채웁니다 — [docs/datatables/afm/afm_redis.txt:49-70](docs/datatables/afm/afm_redis.txt), [docs/datatables/afm/afm_raw_files.txt:38-52](docs/datatables/afm/afm_raw_files.txt), [frontend/app/composables/useAfmToolData.ts:13-14](frontend/app/composables/useAfmToolData.ts)
- Redis key 4개: `afm_d1_tools`(field `all`), `afm_d2_measurements`(field=장비명, 값=그 장비의 **측정 전체를 DataFrame 하나로** 담은 parquet), `afm_tool_recipes`(recipe 명 JSON 배열 — "웹은 아직 읽지 않습니다"), `afm_download_history`("웹은 읽지 않습니다") — [docs/datatables/afm/afm_redis.txt:39-46](docs/datatables/afm/afm_redis.txt)
- 공통 규칙: 값은 `DataFrame.to_parquet()` bytes, 행 단위 key 없음, TTL 없음, 장비 field 를 통째로 다시 씀, 갱신 30분 `[확인]`, 보존 3개월 확정 `[확인]`(측정 시각 기준), 삭제는 MinIO 먼저 → Redis 나중이라 "목록에는 있는데 객체가 없는" 측정이 생김, 웹은 MinIO 에 쓰지 않음 — [docs/datatables/afm/afm_redis.txt:20-37,245](docs/datatables/afm/afm_redis.txt)
- MinIO key 패턴 `2067928/afm/<TOOL>/<측정키>/<파일명>`, bucket `user` — [docs/datatables/afm/afm_redis.txt:259-273](docs/datatables/afm/afm_redis.txt)
- 규모 `[확인 9차, 약 1주일 표본]`: MAP608 67행/7일/하루 16건(최대 30), MAPC01 108행/7일/21건(최대 62), 5EAP1501 28행/6일/11건(최대 12). 3개월치 크기는 미정 — [docs/datatables/afm/afm_redis.txt:243-245](docs/datatables/afm/afm_redis.txt)
- 추출에 실패한 측정은 목록에 들어오지 않아 "파일이 원래 없음"과 "추출 실패"를 목록에서 구분할 수 없음 `[확인]` — [docs/datatables/afm/afm_redis.txt:237-238](docs/datatables/afm/afm_redis.txt)
- 백엔드 구성: `routes.py`(336줄, blueprint `afm`), `contracts.py`(TypedDict 6종), `data.py`(dispatcher, 10개 함수), `providers/mock.py`(1390줄), `providers/office_example.py`(572줄), `profile_sampling.py`. `_scheduler/` 에 AFM job 은 없습니다(grep 0건) — [backend/afm/data.py:9-21](backend/afm/data.py), [backend/afm/routes.py](backend/afm/routes.py)
- 사무실 어댑터 상태: 2026-10-07 에 실제 Redis·MinIO 로 실행, 확인 목록 31개 중 26개 기대대로(10차 회신) — [backend/afm/MIGRATION.md:12-27](backend/afm/MIGRATION.md), [docs/datatables/afm/afm_redis.txt:16-17](docs/datatables/afm/afm_redis.txt)
- 어댑터는 장비 하나의 DataFrame 을 60초 동안 프로세스 안에 보관(2026-10-09 커밋 `43180818` 에서 (hash, field) 당 스냅샷 하나 + lock 으로 교체) — [docs/datatables/afm/afm_redis.txt:440-441](docs/datatables/afm/afm_redis.txt), `git log -1 43180818`
- 테스트: backend `backend/afm/tests/` 에 test 함수 88개(7+7+15+4+11+6+38), frontend `utils/afm*.test.ts` 13개 파일. 2026-10-07 리뷰 시점 실행 결과는 pytest 82 passed / node 125 passed — [.scratch/afm-review-261007/REVIEW.md](.scratch/afm-review-261007/REVIEW.md)
- 원래 요구사항(2025-08)은 `afm.skhynix.com` 의 dict 형태였고, 그 페이지는 종료하고 SKEWNONO 로 통합하는 방향 — [docs/afm/개발요구.txt](docs/afm/개발요구.txt), [docs/afm/feature-summary.md:7](docs/afm/feature-summary.md)

### Inferences
- (추론) 3개월 정상 상태에서 장비당 약 1,000~1,900행, MAPC01 최대 속도 지속 시 약 5,600행입니다. 이는 주간 표본을 외삽한 계획치이며 실측이 아닙니다(`.scratch/afm-scale-261009/codex-r2.md` 가 같은 단서를 답니다).
- (추론) 팁·가동·recipe 이력은 모두 "최근 3개월 창"입니다. 팁 수명 전체나 연 단위 추세는 현재 저장 구조로는 볼 수 없습니다.

### Gaps
- 3개월이 쌓였을 때의 실제 행 수와 DataFrame 크기(Q42, 미답) — [docs/afm/to-questionnaire-afm.md](docs/afm/to-questionnaire-afm.md)
- 사무실의 gitignored `office.py` 가 2026-10-09 template 변경(캐시 교체)을 반영했는지는 저장소에서 알 수 없습니다. 커밋 본문은 `sync_office_adapters afm` 이 필요하다고 적습니다.

## 2. 측정 한 건은 무엇으로 이루어지는가 (필드 전체, 단위, 관례, 커버리지)

### Takeaway
측정 한 건 = 목록 행 1개(식별·시각·팁 요약·파일 유무) + Info(13키 또는 15키, 전부 문자열) + Summary(장비가 계산한 MEAN/STDEV/MIN/MAX/RANGE) + point 행(recipe 가 이름 붙인 `(nm)` 컬럼, State, Valid, Sample Count, Approach Count, Mileage) + **raw 높이 표본(X/Y/Z parquet, leveling 안 함)** + 이미지 4종(webp + 원본). 숫자 배열(프로파일)은 실제로 있지만 5EAP1501 에는 없고, 어떤 파일이 있는지는 전부 recipe 설정이 정합니다.

### Cited Findings

#### 2.1 목록 행 — `AfmMeasurementRow` (Redis `afm_d2_measurements` 한 행)
- 필드 전체: `unique_key, filename, date(YYMMDD), formatted_date(YYYY-MM-DD|null), recipe_name, lot_id, slot_number, time(HHMMSS|null), measured_time(HHMMSS|null), measured_info(항상 null/""), tool_name, tool_id(어댑터가 생성), fab, profile_dir_list, data_dir_list, tiff_dir_list, align_dir_list, tip_dir_list, capture_dir_list, raw_dir_list, has_profile, has_data, has_image, has_align, has_tip, point_count(int|null), tip_id, tip_cassette_id, tip_port_no, tip_slot_no, tip_width(float|null), last_pick_up_time, approach_count_mean, mileage_mean, not_completed_count, invalid_count` — [backend/afm/contracts.py:18-71](backend/afm/contracts.py)
- `unique_key` = `date#time#recipe#slot#lot#measured` 6필드(MAPC01 은 앞 4필드). `filename` 은 data CSV 원본 파일명(없으면 `_Info.csv`), 장비 안에서 유일(전수 확인 0건 중복) `[확인]` — [docs/datatables/afm/afm_redis.txt:80-83,247-256](docs/datatables/afm/afm_redis.txt)
- 파일명 필드 순서가 장비마다 다르고 한 파서로 읽을 수 없음: MAP608 `#YYMMDD#hhmmss#RECIPE#SAMPLE_ID#LOT_ID#hhmmss#.csv`, MAPC01 `#…#RECIPE#SLOT#NA#NA#<원본>.csv`, 5EAP1501 `#…#RECIPE#SAMPLE_ID#LOT_ID#NA#<원본>.csv` `[확인]` — [docs/datatables/afm/afm_raw_files.txt:57-63,119-122](docs/datatables/afm/afm_raw_files.txt)
- `lot_id`: MAPC01 은 파일명이 아니라 Info 의 `Lot ID` 로 채워짐 `[확인]`. `recipe_name`·`lot_id` null 은 현재 0건 `[확인 9차]` — [docs/datatables/afm/afm_redis.txt:86-88,240-241](docs/datatables/afm/afm_redis.txt)
- `slot_number`: Info `Sample Location` 의 `Slot N`(실제 웨이퍼 슬롯)에서 옴. 못 읽으면 파일명 `.nn` 꼬리로 채워 두 모양(`5` vs `07`)이 섞임 `[확인 11차]`, 어댑터가 선행 0 제거. null 행 있음 `[확인 9차]`. 5EAP1501 에서 `.05` 와 Slot 5 가 안 맞는 실측이 있어 **파일명에서 슬롯을 읽으면 안 됨** — [docs/datatables/afm/afm_redis.txt:89-98](docs/datatables/afm/afm_redis.txt)
- `time` 은 MAP608 에서 **세션 시작 시각**(같은 세션 측정들이 공유). `measured_time`(2026-10-07 추가 `[확인 7차]`)이 그 측정의 시작: MAP608 최근 파일의 절반쯤(29/46)이 파일명 6번째 필드 `NA` → Info `Start Time` 에서 생성, `Start Time` 없는 13키 Info 측정은 null(6건) `[확인 8차]`. 측정 순서 정렬은 이 열 사용 `[user-confirmed 2026-10-08]`. 시간대는 KST 추정 `[user-confirmed 2026-10-07]` — [docs/datatables/afm/afm_redis.txt:99-118](docs/datatables/afm/afm_redis.txt), [docs/datatables/afm/afm_raw_files.txt:114-115](docs/datatables/afm/afm_raw_files.txt)
- `point_count` = **실제로 스캔한 위치 수**(profile·tiff 파일 수) `[확인 7차]`. recipe 계획 수도 point 행 수도 아님. repeat recipe: 4 Site × 14 point = 56(행 112). 실측 분포 2,3,5,8,14,43,55,56. 첫 point 에서 중단되거나 profile/Result 를 안 남기는 recipe 는 null `[확인 9차]` — [docs/datatables/afm/afm_redis.txt:121-128](docs/datatables/afm/afm_redis.txt)
- `*_dir_list` 7종은 Redis 에서는 MinIO key 전체, 계약에서는 basename. 빈 리스트=파일 없음. **목록 순서는 point 순서가 아님** `[user-confirmed 2026-10-08]`, 어떤 순서인지는 `OFFICE-VERIFY` — [docs/datatables/afm/afm_redis.txt:193-198,427-429](docs/datatables/afm/afm_redis.txt)
- `has_data` 는 `detail_points.parquet` 이 목록에 있을 때만 참(info-only 측정도 `detail_information.parquet` 하나는 가짐) — [docs/datatables/afm/afm_redis.txt:220-223](docs/datatables/afm/afm_redis.txt)

#### 2.2 Info (`detail_information.parquet`, 열 `name`·`value`, 전부 문자열)
- 15키: `Lot ID, Recipe ID, Carrier ID, Sample Location, Sample ID, Data Save Location, Start Time, End Time, Tip ID, Tip Cassette ID, Tip Port No, Tip Slot No, Last Pick Up Time, Last Put Back Time, Tip Width`. 13키: `Port No, Carrier ID, Slot No, Lot ID, Sample ID, Recipe ID, Tip ID, Tip Cassette ID, Tip Port No, Tip Slot No, Last Pick Up Time, Last Put Back Time, Tip Width` `[user-confirmed 2026-10-06]` — [docs/datatables/afm/afm_raw_files.txt:133-142](docs/datatables/afm/afm_raw_files.txt)
- 장비별 분포: 5EAP1501 은 15키 위주, MAPC01 은 13키 위주, MAP608 혼재 `[user-confirmed 2026-10-06]`. 한 장비 안에서 구성을 가르는 요인·비율은 `OFFICE-VERIFY` — [docs/datatables/afm/afm_raw_files.txt:147-151](docs/datatables/afm/afm_raw_files.txt)
- `Start Time`/`End Time` `[전달 12차 = user-confirmed 2026-10-08]`: 표기 `2026.10.01 00:13:58`(KST 로 읽음), **data CSV 의 Info 에만** 존재, 기록 여부는 **장비 설정**에 달림, `End Time` 은 측정 완료 후에만 기록(ETL 의 완료 판정 마커), 자정 넘김 실측 1건(22:32:28→00:11:13 = 98분 45초), MAP608 일부는 `End Time` 이 아예 없음, **MAPC01 은 현재 data CSV 가 없어 둘 다 못 쓰고 소요시간 분석 제외 결정** — [docs/datatables/afm/afm_raw_files.txt:152-172](docs/datatables/afm/afm_raw_files.txt), [docs/afm/office-data-findings.md:771-841](docs/afm/office-data-findings.md)
- `Sample Location` 값은 `Port 1 Slot 10` 꼴(MAP608 에서는 `Stage` 도 관측 → 슬롯 없음). MAPC01 Info 에는 이 key 가 없고 `Slot No` 사용 `[확인 9차]` — [docs/datatables/afm/afm_redis.txt:285-289](docs/datatables/afm/afm_redis.txt)
- `Data Save Location` 은 공백 없는 긴 경로 `[user-confirmed 2026-10-06]`, 폴더 구성은 `OFFICE-VERIFY` — [docs/datatables/afm/afm_raw_files.txt:209-211](docs/datatables/afm/afm_raw_files.txt)
- 빈 값 가능 key: `Carrier ID`, `Last Pick Up Time`, `Last Put Back Time` 등 `[확인]` — [docs/datatables/afm/afm_raw_files.txt:35](docs/datatables/afm/afm_raw_files.txt)

#### 2.3 Summary (`detail_summary.parquet`)
- 열: `Site`(= **method 명**, 위치 아님) · `ITEM`(MEAN/STDEV/MIN/MAX/RANGE) + 측정 컬럼. 통계는 **장비가 쓴 값 그대로**(적재 시 계산 안 함) `[확인 9차]`. Summary 없는 측정은 0행 0열 객체, 중단된 측정은 빈 block, info-only 는 객체 자체가 없음 `[확인 7차]`. point 1개면 STDEV=0.0, RANGE=0.0 `[확인]` — [docs/datatables/afm/afm_redis.txt:292-299](docs/datatables/afm/afm_redis.txt), [docs/datatables/afm/afm_raw_files.txt:278-280](docs/datatables/afm/afm_raw_files.txt)
- 한 파일에 block(method)이 여러 개일 수 있음(실측 `Profile_LEFT_UL` + `Profile_RIGHT_UL`), block 마다 컬럼이 다를 수 있음 `[확인]` — [docs/datatables/afm/afm_raw_files.txt:241-250](docs/datatables/afm/afm_raw_files.txt)

#### 2.4 Point 행 (`detail_points.parquet`, 측정 한 번 = 한 행)
- 식별 컬럼: `Point No`(위치 키, `_0001` 4자리와 대응), `Site ID`(예 `0002_X002_Y-001`, recipe 에 따라 있거나 없음), `Site X`/`Site Y`(**단위 없는 정수 인덱스**, 실측 범위 X -11~5, Y -7~4 `[확인 9차]`), `Site`(행의 block=method 명), `Method ID`(숫자 또는 문자열, block 키로 쓰면 안 됨) — [docs/datatables/afm/afm_raw_files.txt:252-267,283-284](docs/datatables/afm/afm_raw_files.txt), [docs/datatables/afm/afm_redis.txt:301-332](docs/datatables/afm/afm_redis.txt)
- 측정 컬럼(recipe 마다 다름, 전부 `(nm)` 포함 `[확인]`): `Left_H / Right_H / Ref_H`, `Dishing_H`, `Bottom_H / Top_H`(BSOXCMP_CORRELATION_36PT), `Ref_Range / Left_TRIM_H`, `ROUGHNESS_RANGE / Ra / Rq`, `Pad_1_H …`(MAP608), `1_Minimum ~ 51_Minimum`(5EAP1501, 51개), `RZ1_Minimum …`, `Line1_Residue_H`, `SITE19_21_H`. "등"이 붙어 전체 목록은 아님. 측정 컬럼마다 `<측정명>_Valid` 가 있음(존재는 `[가정]`) — [docs/datatables/afm/afm_raw_files.txt:218-239,291](docs/datatables/afm/afm_raw_files.txt)
- `State`: COMPLETED · FAILED · STOPPED 3종 확정. 중단되면 측정 못 한 point 는 **행 자체가 없고**, STOPPED 행은 중단된 그 point 하나 `[확인 7차]` — [docs/datatables/afm/afm_raw_files.txt:260-262,301-303](docs/datatables/afm/afm_raw_files.txt)
- `Valid`: 컬럼은 있으나 **FALSE 인 실물이 없음**(CSV 263개 전수 0건) `[확인 7차]`. FALSE 표기 모름 `OFFICE-VERIFY` — [docs/datatables/afm/afm_raw_files.txt:268-269](docs/datatables/afm/afm_raw_files.txt)
- `Sample Count`: repeat recipe 에서 바퀴마다 증가(실측 4→5), 반복 없으면 한 측정 안에서 동일(1~47). **무엇을 세는 값인지 모름** `[확인 8차]` — [docs/datatables/afm/afm_raw_files.txt:270-273](docs/datatables/afm/afm_raw_files.txt)
- `Mileage`: **팁 단위 누적값**, 팁이 바뀌면 리셋(실측 1430483 → 3520). 단위 미정(um 추정), 재시작·수동 초기화 동작 미실측 `[확인 7차·8차]`. `Approach Count` 도 행마다 있음 — [docs/datatables/afm/afm_redis.txt:148-155](docs/datatables/afm/afm_redis.txt)
- repeat recipe: 한 block 안에서 같은 point 를 되풀이, 반복 번호 열 없음, 모든 Site 를 한 바퀴 돈 뒤 다시 돎(실측 4 Site × 14 point × 2 바퀴 = 112행). profile·이미지는 반복마다 따로 없고 이름 하나 `[확인 7차]` — [docs/datatables/afm/afm_redis.txt:313-320](docs/datatables/afm/afm_redis.txt)
- 적재물은 모든 값이 문자열(`"79.24"`), 측정 못 한 칸은 공백 한 칸, 어댑터가 숫자·bool·null 로 변환 `[확인]`. **행 순서는 point 순서가 아님** `[user-confirmed 2026-10-08]` — [docs/datatables/afm/afm_redis.txt:275-279,306-308,325-327](docs/datatables/afm/afm_redis.txt)
- 서로 다른 recipe 의 같은 이름 컬럼이 같은 측정량이라는 근거 없음 → recipe 별 묶음 유지 권장 `[확인 9차]`. recipe 이름 관측 36종, 이력 기록 없음 — [docs/datatables/afm/afm_raw_files.txt:281-286](docs/datatables/afm/afm_raw_files.txt)

#### 2.5 Profile — raw 높이 표본이 실제로 있음
- `profile_<원본이름>.parquet`, 열 `X` `Y` `Z` 모두 float64. Z=Height, **원본 그대로(leveling 안 함), 결측은 NaN**. 1D 는 Y=0 고정 `[user-confirmed 2026-10-06]` — [docs/datatables/afm/afm_redis.txt:356-383](docs/datatables/afm/afm_redis.txt)
- 단위(XUnit·YUnit·ZUnit·DataSize·SurfaceSize)는 MinIO 객체 user metadata. um / nm / pm / Pixel 이 **파일마다 다르고 통일하지 않음**. Pixel 의 길이 환산은 미정 — [docs/datatables/afm/afm_redis.txt:359-375](docs/datatables/afm/afm_redis.txt), [docs/datatables/afm/afm_raw_files.txt:327-335](docs/datatables/afm/afm_raw_files.txt)
- 장비별 격자 `[확인]`: MAP608 512×64(um/um/nm), MAPC01 1024×1~16384×1 등 1D 와 2D 혼재(2D 크기 `512x64`, `2048x256` — 어느 장비 것인지는 `[가정]`), **5EAP1501 은 profile 없음** — [docs/datatables/afm/afm_raw_files.txt:322-325](docs/datatables/afm/afm_raw_files.txt), [docs/datatables/afm/afm_redis.txt:377-379](docs/datatables/afm/afm_redis.txt)
- profile 과 Result 이미지는 **모든 point 에 있지 않음** `[확인 11차]` — [docs/datatables/afm/afm_redis.txt:418-420](docs/datatables/afm/afm_redis.txt)
- API: `GET /api/afm/files/<filename>/profile/<point>` 는 route 에서 65,536점 이하로 솎아 보냄(2048×256=524,288 → 683×86, 평균 없이 골라내기만). `?full=1` 은 전체 표본. 응답에 `meta`, `count`, `total` — [backend/afm/routes.py:77-112](backend/afm/routes.py), [backend/afm/profile_sampling.py:16-39](backend/afm/profile_sampling.py)
- 미확인 `[가정]`: 격자 간격·원점, 오류·포화 값 표현, NaN 의 빈도와 모양, 단위 철자 전체 목록 — [docs/datatables/afm/afm_raw_files.txt:337-339](docs/datatables/afm/afm_raw_files.txt), [docs/datatables/afm/afm_redis.txt:385-389](docs/datatables/afm/afm_redis.txt)

#### 2.6 이미지 4종 (렌더된 그림, 숫자 배열 아님)
- 유효 타입은 `align`, `tip`, `capture`, `tiff`(화면 표기 Result) — [backend/afm/routes.py:24](backend/afm/routes.py)
- Result(`tiff`): 위치마다 한 장(repeat 도 Site×point 당 한 장), 이름 `_<위치 키>_Height`, webp + 원본 `.tiff` `[확인 7차·9차]`. Result 원본의 크기·bit 수·장비 전용 태그는 `[가정]`(미확인) — [docs/datatables/afm/afm_redis.txt:202,214-215](docs/datatables/afm/afm_redis.txt), [docs/datatables/afm/afm_raw_files.txt:367](docs/datatables/afm/afm_raw_files.txt)
- align: 측정마다 1~4장(`1_Result.webp`, 위치 키 없음), 원본 `.bmp` `[확인 8차·9차]` — [docs/datatables/afm/afm_redis.txt:203-204](docs/datatables/afm/afm_redis.txt)
- tip: 두 계열 — point 마다 `_C_PR`(2440×1832 grayscale 약 2.5MB, 원본 `.png`)와 측정마다 `C_Result` 한 장(448×336 RGB 약 440KB, 원본 `.bmp`). **무엇을 찍은 것인지, 마모가 보이는지는 미정**(담당자 확인 필요, Q53) — [docs/datatables/afm/afm_redis.txt:205-209](docs/datatables/afm/afm_redis.txt), [docs/afm/to-questionnaire-afm.md](docs/afm/to-questionnaire-afm.md)
- capture: point 마다 한 장(`…_0001.webp`), 원본 `.png`. **일부 point 에만 있고 아예 없는 측정도 있음** `[확인 10차·11차]`. 5EAP1501 은 3자리 번호(`_003`)로 끝나며 그것이 point 3 이라는 것은 `[가정]` — [docs/datatables/afm/afm_redis.txt:210-212,407-412](docs/datatables/afm/afm_redis.txt)
- 측정 한 건의 webp 는 실측 최대 133장(MAP608 `WID_REAL`), 원본 포함 189 객체 `[확인 9차]` → `afm` blueprint 는 5초 50회 제한 예외 `[user-confirmed 2026-10-07]` — [docs/datatables/afm/afm_redis.txt:216-218](docs/datatables/afm/afm_redis.txt)
- mock 의 이미지는 webp 가 아니라 자리 표시 SVG, 원본 TIFF 는 256×256 8-bit 가짜 — [backend/afm/MIGRATION.md](backend/afm/MIGRATION.md) ("Mock behavior" 절)

#### 2.7 mock 이 지어낸 것 (집에서 보는 값은 실측 근거가 아님)
- 값 모델 전체가 `OFFICE-VERIFY`: recipe 수준 55~120nm, drift ±0.4nm/일, sample offset σ 0.8nm, point noise 0.6nm, 중심-가장자리 bowl 0.25, 약 9건 중 1건 excursion +7.5nm — [backend/afm/providers/mock.py:1079-1114](backend/afm/providers/mock.py)
- 그 밖에 지어낸 것: recipe-장비-컬럼 대응 대부분, Mileage 증가 속도(분당 240)와 팁 4일 유지, 비 MCNT 폭 70, 소요시간 분포(1~30분), Valid 일부 False, point 수 1~36(실측 최대 56 미재현), 행 수 36/28/30 — [docs/datatables/afm/afm_redis.txt:466-485](docs/datatables/afm/afm_redis.txt), [docs/datatables/afm/afm_raw_files.txt:399-415](docs/datatables/afm/afm_raw_files.txt)

### Inferences
- (추론) "raw 높이맵이 있는가"의 답은 **있다, 단 조건부**입니다: MAP608 은 512×64 2D, MAPC01 은 1D 라인과 2D 혼재, 5EAP1501 은 없음. leveling 이 안 된 원본이고 단위·격자가 파일마다 달라, 프로파일 기반 분석(단차 재계산, 거칠기 재계산, 프로파일 차이)은 단위 정규화와 leveling 정책을 먼저 정해야 합니다.
- (추론) "per-site 수치 결과가 있는가"의 답은 **있다**입니다. 다만 무엇을 재는지(step height / dishing / roughness Ra·Rq / pad height / minimum)는 recipe 컬럼 이름으로만 알 수 있고, 컬럼 사전(이름 → 측정량·단위·spec)이 없습니다. CD·sidewall angle 이라는 이름의 컬럼은 실측 목록에 없습니다.
- (추론) Site X/Y 가 단위 없는 인덱스이고 웨이퍼 방향 정보가 원본에 없으므로(9차 6번), 물리 좌표 기반 웨이퍼 맵(mm, notch 기준)은 현재 데이터만으로는 정확히 그릴 수 없습니다. 인덱스 격자 맵까지만 가능합니다.
- (추론) Result 원본 TIFF 에 높이 데이터가 실려 있을 가능성은 있으나, bit 수·태그가 미확인이라 근거가 없습니다.

### Gaps
- Result 원본 TIFF 가 숫자 높이 데이터(예: 16/32-bit)인지 렌더된 그림인지 — `afm_raw_files.txt:367` 이 미확인으로 남겼습니다.
- `Sample Count` 의 의미, `Mileage` 단위, `Valid=FALSE` 의 실제 표기.
- MAPC01 에 point 데이터가 실제로 있는지: 12차 전달은 "MAPC01 은 현재 data CSV 가 없어"라고 했고 그것이 point 데이터도 없다는 뜻인지 확인 못 함 `OFFICE-VERIFY`(`afm_raw_files.txt:160-164`). 사실이면 MAPC01 의 수치 분석은 profile 뿐입니다.
- 컬럼 전체 목록과 recipe → 컬럼 대응(문서의 목록은 "등").
- spec/target/허용 한계: 저장소 어디에도 없습니다(`docs/afm/service-recommendations.md:326` 도 Cp/Cpk 를 "규격 필요"로 보류).

## 3. 팁 추적은 무엇을 기록하고, 가동·recipe 화면은 무엇을 집계하는가

### Takeaway
팁 교체 이벤트 자체는 기록되지 않습니다. 측정마다 팁 식별 4값·`Tip Width`·`Last Pick Up Time` 과 point 행의 `Mileage`·`Approach Count` 가 남고, ETL 이 그 요약 9~10열을 목록에 적재해 팁 모니터링이 목록만으로 동작합니다. 가동 현황과 Recipe 현황도 목록 열만 읽는 집계 화면입니다.

### Cited Findings
- 팁 하나의 식별 = (`Tip ID`, `Tip Cassette ID`, `Tip Port No`, `Tip Slot No`) 조합. 같은 `Tip ID` 가 여러 슬롯에 꽂혀 있어 ID 만으로 구분하면 안 됨 `[office 확인 2026-10-06]` — [docs/datatables/afm/afm_raw_files.txt:173-177](docs/datatables/afm/afm_raw_files.txt)
- `Tip Width` 는 고정 스펙이 아니라 **측정 시점에 기록된 값**, 단위 표기 없음, 문자열 `NaN` 이 오는 측정 있음(8건 실측). 비 MCNT 종류는 사실상 상수, **MCNT 계열만 33.96~39.11 로 퍼지고 같은 슬롯에서도 오르내림(마모가 아니라 측정 오차로 추정)** `[확인 7차]`. 음수 폭은 세 장비 0건 `[확인 11차]` — [docs/datatables/afm/afm_raw_files.txt:178-202](docs/datatables/afm/afm_raw_files.txt)
- 교체 기록 **없음**. 변경 지점은 4값 중 하나가 달라졌거나, 값은 같은데 Mileage 가 줄고 `Last Pick Up Time` 이 갱신된 자리로 **추정** `[확인 7차·8차]`. 현장에서 팁을 바꾸는 기준 숫자(Mileage·Approach Count 한계)는 **없음** `[확인 9차]` — [docs/datatables/afm/afm_redis.txt:176-192](docs/datatables/afm/afm_redis.txt)
- 관측 `Tip ID` 8종, 이름을 아는 것은 `DT-NCHR_CM`, `OMCL-AC160TS`(5EAP1501, 폭 대부분 NaN), `NT-DT50-NCHR`(MAP608). 장비별로 팁이 다름(9차 26번) — [docs/datatables/afm/afm_raw_files.txt:198-204](docs/datatables/afm/afm_raw_files.txt)
- 목록의 팁 열(2026-10-07 적재, 과거 측정 소급): `tip_id, tip_cassette_id, tip_port_no, tip_slot_no, last_pick_up_time, tip_width, approach_count_mean, mileage_mean, not_completed_count, invalid_count`. 뒤 넷은 block 을 가리지 않고 한 측정의 모든 data 행에서 계산, info-only 측정은 null — [docs/datatables/afm/afm_redis.txt:133-163](docs/datatables/afm/afm_redis.txt), [docs/office-migration/to-office-afm-tip-columns.md](docs/office-migration/to-office-afm-tip-columns.md)
- 팁 판정 로직(프런트 순수 함수): 종류(`Tip ID`)별 **중앙값 ± 3σ(σ=MAD 기반)**, 하한은 0 에서 자름; MCNT 는 팁(슬롯) 단위 폭 관리선(`/MCNT/i` 이름 판별, `[가정]`); 최소 표본 `TIP_MIN_SAMPLES = 5`; 최근 `TIP_RECENT = 5` 건 중 2건 이상 밖=이상, 1건=주의, 0=정상, 표본 부족=보류; Mileage 는 판정 제외. 판정 기준은 `[user-confirmed 2026-10-06]` + 웹이 정한 규칙 — [frontend/app/utils/afmTips.ts:1-7,56-72,107-121](frontend/app/utils/afmTips.ts), [docs/datatables/afm/afm_redis.txt:166-176](docs/datatables/afm/afm_redis.txt)
- 팁 모니터링 화면 요소: 지금 장착된 팁(=최신 측정의 팁) + 판정, 상태별 팁 수, recipe 범위 선택(검색 메뉴), 상태 필터, 종류별 팁 목록 + Tip Width sparkline(선=폭, 띠=관리선, 점=밖), 고른 팁의 `AfmTrendHealthStrip`(4지표), 이 팁으로 잰 recipe 칩, 이 팁의 측정 표(시각, Recipe·Lot, Tip Width, Mileage, Approach, FAILED, 판정, 상세 이동) — [frontend/app/pages/afm/[tool]/tips.vue:46-331,396-415](frontend/app/pages/afm/[tool]/tips.vue)
- 가동 현황 집계(목록 열만): 기간 7일/30일/전체; 요약 = 측정 건수, 가동일/전체일, 가동일 하루당 평균, Recipe 수, Lot 수, `point_count` 합, 미완료 측정 수; 일별 측정 건수(상위 recipe 5개 + 기타 누적 막대); 날짜×시간대 히트맵; 일별 미완료·무효 측정; 선택한 날의 측정 목록 → 상세 이동 — [frontend/app/utils/afmUsage.ts:67-176](frontend/app/utils/afmUsage.ts), [frontend/app/pages/afm/[tool]/usage.vue:46-170,282-339](frontend/app/pages/afm/[tool]/usage.vue)
- Recipe 현황 집계(목록 열만): 타일 = 최근 7일 측정 / 30일 넘게 측정 없음 / 1회만 측정; 표 = Recipe, 측정 수, 마지막·처음 측정일, Lot 수, Point(min–max), 파일 종류(`has_*`, 예 `Profile 3/6`), 최근 14일 sparkline, 미완료; 정렬·이름 검색; 고른 recipe 의 일별 측정 건수, 사용한 팁, 측정 목록 — [frontend/app/utils/afmRecipes.ts:9-22,130-243](frontend/app/utils/afmRecipes.ts), [frontend/app/pages/afm/[tool]/recipes.vue:383-427](frontend/app/pages/afm/[tool]/recipes.vue)
- 세 화면 모두 `useAfmDetailApi().useAfmTipRows(toolName)` 로 `?compact=1` 목록을 읽음 — [frontend/app/composables/useAfmDetailApi.ts:163-176](frontend/app/composables/useAfmDetailApi.ts)
- 활동 로그 slug 는 2026-10-08 에 `afm_tips`/`afm_usage`/`afm_recipes` 로 분리, 나머지 AFM 은 `afm` — [backend/_logging/feature_map.py:171-185](backend/_logging/feature_map.py)

### Inferences
- (추론) "팁 ID 와 팁 사용량이 기록되는가"의 답: ID·좌석·폭·Pick Up 시각·Mileage(누적 주행)·Approach Count 는 측정 단위로 있고, **교체 이벤트·교체 사유·폐기 여부·팁 시리얼은 없습니다.** 팁 수명 예측은 정답 레이블이 없어 현재 데이터로는 검증할 수 없습니다.
- (추론) "장비 상태(운전/대기/정지)"는 어디에도 없습니다. 가동 현황은 "측정이 있었던 시간"의 건수이지 가동률이 아닙니다(`service-recommendations.md:327` 도 OEE 를 보류로 둡니다).
- (추론) 가동 현황의 시간대 히트맵은 `measured_time` 이 null 인 MAP608 측정을 세션 시각에 모으므로(`feature-summary.md:126`), MAP608 의 시간대 분포는 왜곡될 수 있습니다.

### Gaps
- 팁 이미지 `_C_PR`/`C_Result` 의 의미(Q53), MCNT 외에 폭이 팁마다 다른 종류가 있는지(Q57).
- `Last Put Back Time` 은 Info 에 있으나 목록 열로는 적재되지 않았습니다(목록에는 `last_pick_up_time` 만).

## 4. 지금 어떤 화면·패널·차트·통계가 있고, 어디서 계산하는가

### Takeaway
화면은 `/afm`(장비 선택) + 장비별 6개(측정 검색, 측정 상세, 시계열 비교, 팁 모니터링, 가동 현황, Recipe 현황)입니다. **통계는 전부 프런트엔드 순수 함수(`utils/afm*.ts`)에서 계산**하고, 백엔드는 조회·형변환·프로파일 솎기·zip 조립만 합니다. 추세·관리선·포인트 비교·변동 분해·재측정 비교는 "사용자가 손으로 담은 최대 20건"에 대해서만 존재합니다.

### Cited Findings

#### 4.1 라우트와 API
- 페이지: `pages/afm/index.vue`, `[tool]/index.vue`(측정 검색), `[tool]/[filename].vue`(측정 상세), `[tool]/see-together.vue`(시계열 비교), `[tool]/tips.vue`, `[tool]/usage.vue`, `[tool]/recipes.vue`. 탭 4개(측정 결과 / 팁 모니터링 / 가동 현황 / Recipe 현황) — [frontend/app/components/nav/AfmTabs.vue:2-23](frontend/app/components/nav/AfmTabs.vue)
- API 엔드포인트(모두 GET, `?tool=`): `/afm/tools`, `/afm/files`(`?compact=1`), `/afm/files/<filename>`, `…/profile/<point>`(`?full=1`), `…/image/<point>`, `…/image-file/<point>`, `…/images/<type>`, `…/images/<type>/<name>`, `…/tiff/<name>`, `…/tiff.zip?type=`, `…/images.zip?type=`. 구 경로 `/afm-files/*` 별칭 유지 — [backend/afm/routes.py:27-288](backend/afm/routes.py)
- 토큰 API 로 공개됨(`auth: '토큰 가능'`) — [frontend/app/data/apiCatalog.ts:591-625](frontend/app/data/apiCatalog.ts)
- `AFM_ENABLED = true` 한 스위치로 랜딩 카드와 `/afm/*` 접근 제어 — [frontend/app/composables/useAfmAvailability.ts:6](frontend/app/composables/useAfmAvailability.ts)
- 장비 목록은 프런트 고정 표를 쓰고 `/api/afm/tools` 를 부르지 않음 — [docs/datatables/afm/afm_redis.txt:68-69](docs/datatables/afm/afm_redis.txt)

#### 4.2 측정 검색 (`/afm/<tool>`)
- 한 검색창(모든 term 일치), Recipe 다중 선택·Lot·기간(전체/오늘/3일/7일) 필터, 기본은 "전체"라 전 행을 마운트, 행마다 체크박스로 그룹에 담기 — [frontend/app/components/afm/SearchBar.vue:290-336](frontend/app/components/afm/SearchBar.vue), [frontend/app/utils/afmSearch.ts:39-73](frontend/app/utils/afmSearch.ts)
- 브라우저 저장 상태(장비별, `usePersistedState`): 조회 기록 10건, 데이터 그룹 최대 `AFM_GROUP_MAX = 20`, 저장된 그룹 10개, 최근 검색어 5개 — [frontend/app/composables/useAfmCart.ts:38-43](frontend/app/composables/useAfmCart.ts)

#### 4.3 측정 상세 (`/afm/<tool>/<filename>`) — 2026-10-03 Claude Design 2b 재구성 + 이후 보강
- 좌측 rail: 측정 정보(Info key 전체, 값 클릭 복사) + 측정 포인트(State 점·범례, 첫 측정 컬럼 미리보기, **Site X·Y 인덱스 지도** — Site ID 를 기록하는 recipe 에만) — [frontend/app/components/afm/detail/PointRail.vue:12-33,115-116](frontend/app/components/afm/detail/PointRail.vue), [frontend/app/utils/afmPoints.ts:87-89](frontend/app/utils/afmPoints.ts)
- 포인트 요약: 측정 컬럼별 카드, `Δ vs MEAN`, block 통계(MEAN/STDEV/MIN/MAX/RANGE 선택) 위에 선택 포인트를 겹친 사이트별 요약 분포 차트 — [frontend/app/components/afm/detail/PointSummary.vue:42-99](frontend/app/components/afm/detail/PointSummary.vue), [frontend/app/components/afm/detail/SummaryScatterChart.vue:59-124](frontend/app/components/afm/detail/SummaryScatterChart.vue)
- 분석 이미지: Align/Tip/Capture/Result 탭(탭당 lazy 1요청), 썸네일 strip, 팝업(포인트별 격자, ←→ 이동, 1~4 로 종류 전환, 작게/보통/크게/맞춤, 원본 1장 다운로드, 종류별 zip·원본 zip, 이 포인트로 보기) — [frontend/app/components/afm/detail/AnalysisImages.vue:354-414](frontend/app/components/afm/detail/AnalysisImages.vue), [docs/afm/feature-summary.md:60-65](docs/afm/feature-summary.md)
- 측정 포인트 표: 컬럼 선택기(기본 6개, 51개 대응), 텍스트 검색, State/Valid/Block facet 필터, 다중 block 이면 `Block` 열, repeat 이면 `회차`(Lap) 열 — [frontend/app/utils/afmPointsTable.ts:14-33,75-103](frontend/app/utils/afmPointsTable.ts), [frontend/app/utils/afmPoints.ts:33-57](frontend/app/utils/afmPoints.ts)
- 프로파일: 2D 는 "웨이퍼 히트맵"(실제로는 **한 point 의 스캔 영역 높이맵**), 1D 는 라인 프로파일. 이상치 필터 없음/IQR/Z-Score, count·min·max·mean 표시(솎은 표본 기준) — [frontend/app/components/afm/detail/HeatmapChart.vue:4,91-95,146-195](frontend/app/components/afm/detail/HeatmapChart.vue), [frontend/app/utils/afmHeatmap.ts:13-88](frontend/app/utils/afmHeatmap.ts)
- Z값 분포: 히스토그램(자동/사용자 구간, 빈도/밀도/누적) + 정규 적합 곡선 + μ, σ, Q1, Md, Q3, skew, kurt, CV — [frontend/app/components/afm/detail/HistogramChart.vue:89-117](frontend/app/components/afm/detail/HistogramChart.vue), [frontend/app/utils/afmHistogram.ts:50-157](frontend/app/utils/afmHistogram.ts)
- 프로파일 이미지: 원본/PNG/JPG 저장 — [frontend/app/components/afm/detail/ProfileImage.vue:70-114](frontend/app/components/afm/detail/ProfileImage.vue)
- 내보내기: Excel 4시트(측정 정보, 사이트별 요약, 측정 포인트, 선택 포인트 프로파일 — 프로파일은 `full=1` 로 전체 표본 재요청), 링크 복사(/s/ 단축 주소) — [frontend/app/pages/afm/[tool]/[filename].vue:225-323](frontend/app/pages/afm/[tool]/[filename].vue)

#### 4.4 시계열 비교 (`/afm/<tool>/see-together`) — 2026-10-03 Claude Design 3a
- 데이터: 그룹에 담은 측정마다 상세 1요청(실패는 null 로 두고 경고) — [frontend/app/pages/afm/[tool]/see-together.vue:240-242](frontend/app/pages/afm/[tool]/see-together.vue)
- 분석 조건: 블록 × 측정 항목 × 통계(MEAN/STDEV/MIN/MAX/RANGE). recipe 가 섞이면 경고, 추세는 recipe 별 시리즈·관리선 — [frontend/app/pages/afm/[tool]/see-together.vue:56-107](frontend/app/pages/afm/[tool]/see-together.vue)
- KPI: 그룹 평균 μ, lot 간 σ(MEAN 들의 표본 표준편차), wafer 내 σ̄(측정별 STDEV 평균), 관리선 밖, FAILED·STOPPED, 재측정 쌍 — [frontend/app/pages/afm/[tool]/see-together.vue:326-339](frontend/app/pages/afm/[tool]/see-together.vue)
- 01 추세: 추세/박스플롯 모드, MIN–MAX 또는 ±1 STDEV 띠, **UCL/LCL = μ ± 3σ(σ = MAD 기반 강건 표준편차), 그룹 자신에서 계산** — [frontend/app/components/afm/trend/TrendChart.vue:56-95](frontend/app/components/afm/trend/TrendChart.vue), [frontend/app/utils/afmTrend.ts:79-99,179-182](frontend/app/utils/afmTrend.ts)
- 02 포인트별 비교: 포인트 × 측정 선(값 또는 기준 대비 Δ; 기준 = 그룹 평균/첫 측정/선택한 측정), 포인트 안정도(측정 간 STDEV 가 평균+1.5·sd 초과면 불안정) — [frontend/app/utils/afmTrend.ts:226-275](frontend/app/utils/afmTrend.ts), [frontend/app/components/afm/trend/PointsChart.vue:75-79](frontend/app/components/afm/trend/PointsChart.vue)
- 03 그룹 통계: 측정별 요약 표(Excel), 변동 분해(lot² 대 wafer² 의 비율), 재현성(같은 `Sample ID` — 없으면 lot.slot — 를 같은 recipe 로 다시 잰 쌍의 MEAN 차이와 wafer σ̄ 대비 배수) — [frontend/app/utils/afmTrend.ts:277-333](frontend/app/utils/afmTrend.ts)
- 04 장비 건강: Tip Width, Mileage 평균, Approach Count 평균, FAILED+STOPPED 포인트의 2×2 차트 + 공용 줌 슬라이더, 팁 변경 추정 세로선 — [frontend/app/components/afm/trend/HealthStrip.vue:59-138](frontend/app/components/afm/trend/HealthStrip.vue), [frontend/app/utils/afmTrend.ts:359-394](frontend/app/utils/afmTrend.ts)
- 05 측정 소요시간(2026-10-08 `c56130c1` 출시): `YYYY.MM.DD HH:mm:ss` 를 KST 로 직접 파싱, 사유 분류 `no-times | no-end | no-start | bad-format | reversed`, recipe 중앙값 대비 배수(recipe 에 3건 이상일 때), recipe 별 집계 — [frontend/app/utils/afmDuration.ts:6-106](frontend/app/utils/afmDuration.ts), [frontend/app/components/afm/trend/Duration.vue](frontend/app/components/afm/trend/Duration.vue)
- `measurementStats` 는 Summary 가 있으면 그것을, 없으면 data 행에서 계산. 같은 위치가 반복되면 포인트 Map 이 마지막 값을 남김(반복 보존 안 함) — [frontend/app/utils/afmTrend.ts:107-124](frontend/app/utils/afmTrend.ts), [docs/afm/service-recommendations.md:299](docs/afm/service-recommendations.md)

#### 4.5 질문별 존재 여부 (코드 대조)
- 시간 추세: **있음** — 단 손으로 담은 최대 20건에 한함. recipe 전체 이력의 자동 추세는 없음(가동·Recipe 현황은 건수만) — [frontend/app/composables/useAfmCart.ts:38-40](frontend/app/composables/useAfmCart.ts)
- 웨이퍼 맵: **부분** — Site X·Y 인덱스 점 지도는 포인트 선택용이고 값으로 색칠하지 않음. "웨이퍼 히트맵"이라는 제목의 차트는 한 point 의 스캔 높이맵 — [frontend/app/components/afm/detail/PointRail.vue:15-33](frontend/app/components/afm/detail/PointRail.vue), [frontend/app/components/afm/detail/HeatmapChart.vue:4](frontend/app/components/afm/detail/HeatmapChart.vue)
- wafer 내 균일도: **부분** — Summary 의 STDEV/RANGE, wafer 내 σ̄, 포인트 안정도, 포인트×측정 선. 균일도 지표(%, 반경별)나 center-edge 분해는 없음 — [frontend/app/utils/afmTrend.ts:265-293](frontend/app/utils/afmTrend.ts)
- 장비 간 비교: **없음**(규칙상 금지) — [docs/afm/feature-summary.md:13](docs/afm/feature-summary.md)
- 팁 간 비교: **부분** — 같은 종류 내 관리선 대비 판정과 팁별 sparkline. 팁별 측정 결과(수치) 비교는 없음 — [frontend/app/utils/afmTips.ts:140-170](frontend/app/utils/afmTips.ts)
- SPC 한계: **통계적 관리선만**(그룹 μ±3σ, 팁 종류 중앙값±3σ). spec 한계, 고정 기준선, Western Electric 류 규칙, Cp/Cpk 없음 — [frontend/app/utils/afmTrend.ts:91-99](frontend/app/utils/afmTrend.ts)
- 상관/산점도: **없음** — 두 측정 컬럼 간, 수치 대 팁 지표 간 산점도 없음(상세의 `SummaryScatterChart` 는 block 통계 위에 선택 포인트를 찍는 차트) — [frontend/app/components/afm/detail/SummaryScatterChart.vue:82-124](frontend/app/components/afm/detail/SummaryScatterChart.vue)
- 프로파일에서 파생 지표 재계산(step height, Ra/Rq, 기울기 등): **없음** — count/min/max/mean 과 히스토그램 통계뿐 — [frontend/app/utils/afmHeatmap.ts:72](frontend/app/utils/afmHeatmap.ts), [frontend/app/utils/afmHistogram.ts:50](frontend/app/utils/afmHistogram.ts)
- 백엔드 집계 엔드포인트: **없음** — `routes.py` 의 계산은 `thin_profile` 과 zip 조립뿐 — [backend/afm/routes.py](backend/afm/routes.py)

#### 4.6 최근 2주 출시분과 미해결 (git log, 2026-10-02 ~ 10-09)
- 10-02: DESIGN.md 정렬·전폭 레이아웃, 사무실 raw 파일 회신 1~4차 반영. 10-03: 측정 검색/상세(1a·2b)·시계열 비교(3a) 재구성, 원본 TIFF 다운로드·zip, 링크 복사. 10-04: 히트맵 격자 판정·일괄 페인트. 10-06: 사무실 어댑터 작성, 이미지 팝업(원본 크기·키보드 이동·1~4 전환·맞춤), 프로파일 전체 내보내기, 팁 모니터링 첫 판, 그룹 20건 상한. 10-07: 팁 보드 재구성, 가동 현황·Recipe 현황 신설, 7~11차 회신 반영, 회차 열, 요청 제한 예외, Codex 리뷰 6건 수정(`a1242477`). 10-08: 건강 strip 2×2·공용 줌, Start/End Time 기록, 소요시간 카드, point 순서 정렬, 기능 요약·추천 보고서. 10-09: `?compact=1`(`bce8d543`), 어댑터 캐시 교체(`43180818`), scale-up 리뷰 기록(`8523d7ac`) — `git log --since=2026-09-20 -- backend/afm frontend/app/pages/afm frontend/app/components/afm frontend/app/utils/afm* docs/afm docs/datatables/afm`
- compact 응답: `*_dir_list` 7개가 응답의 80~91%(1,900행 기준 7~15MB → 약 1.4MB, mock 합성 측정). opt-in 인 이유는 전체 행이 문서화된 토큰 API 이기 때문 — [backend/afm/routes.py:37-45](backend/afm/routes.py), [.scratch/afm-scale-261009/codex-r2.md](.scratch/afm-scale-261009/codex-r2.md)
- scale-up 토론 결론(Claude↔Codex 2라운드): compact 먼저, 캐시 1세대화 둘째, 검색 DOM 페이지네이션은 FHD 실측 후로 보류, `_find` 인덱스·zip 스트리밍·적재 구조 변경은 현 규모에서 불필요. "provider 분리와 재사용 가능한 화면 구조는 재작성 없이 확장을 지원" — [.scratch/afm-scale-261009/codex-r2.md](.scratch/afm-scale-261009/codex-r2.md), [.scratch/afm-scale-261009/claude-r2.md](.scratch/afm-scale-261009/claude-r2.md)
- 사무실 미해결 `[확인 10차·11차]`: (a) 측정 상세 본문 5~8초 — 어댑터 호출은 모두 1초 미만이라 원인이 요청 수·응답 크기·렌더링 중 무엇인지 모름, (b) 반복 측정 `회차` 가 기대와 다르게 보임(세부 미수신), (c) 5EAP1501 capture `_003` ↔ point 3 미확인, (d) Result 탭 첫 로드가 느림(이미지당 MinIO 1회, 1시간 브라우저 캐시만 추가) — [docs/datatables/afm/afm_redis.txt:403-420](docs/datatables/afm/afm_redis.txt), [docs/afm/office-data-findings.md:680-701](docs/afm/office-data-findings.md)
- 남은 질문 5개(담당 엔지니어 확인 필요): Q24(Site Y 방향), Q57(Tip ID 종류), Q53(팁 이미지 의미), S8(recipe 간 동명 컬럼 동일성), Q42(3개월 행 수) — [docs/afm/to-questionnaire-afm.md](docs/afm/to-questionnaire-afm.md)

### Inferences
- (추론) 과제 설명의 "Redis schema columns pending"은 현재는 해소된 상태로 보입니다. 팁 열 9개 + `measured_time` 은 2026-10-07, `last_pick_up_time` 은 9차에 적재되었습니다. 지금 "없는 열"로 남은 것은 소요시간 요약 열(추천 보고서 4.4 가 가동 현황 전체 확장 시 ETL 추가를 제안)과 `Sample ID` 입니다.
- (추론) 모든 통계가 브라우저에 있고 상세가 측정당 1요청(+사무실 5~8초)이므로, "recipe 전체 이력 자동 추세" 같은 다건 분석은 현재 구조로는 20건 상한에 묶입니다. 목록에 측정당 요약값을 더 적재하거나(팁 열의 선례) 백엔드 집계를 두는 것이 확장 경로입니다.

### Gaps
- 브라우저에서 화면을 실제로 열어 보지 않았습니다. 화면 요소는 템플릿·주석·기능 요약 문서에서 읽은 것입니다.
- 상세 5~8초의 원인.

## 5. e-beam 쪽과의 관계 — AFM vs CD-SEM 상관이 가능한가

### Takeaway
현재 AFM 은 독립 도메인이고 e-beam 과 조인하는 코드·링크가 없으며, 저장소의 기존 결정은 "AFM ↔ SEM 자동 연결 제외"입니다. AFM 쪽 맥락 식별자는 lot, slot, Sample ID, Carrier ID, recipe 뿐이고 device·step·oper 는 없습니다.

### Cited Findings
- ADR 0006: AFM·Thickness 는 "독립 도메인 — 조인할 데이터가 없습니다", "스큐보아는 웨이퍼 → 레시피 → 장비로 넘겨줘야 하지만 AFM 은 그럴 대상이 없습니다" — [docs/adr/0006-page-grouping-by-domain-and-object.md:50,58,61](docs/adr/0006-page-grouping-by-domain-and-object.md)
- 브레인스톰(2026-10-05): "AFM ↔ CD-SEM 자동 연결 — 제외. lot 라벨이 비슷하다고 같은 웨이퍼와 스텝이라는 보장이 없습니다", "AFM ↔ SEM ↔ Thickness 자동 연결 — 같은 웨이퍼, 같은 스텝이라는 식별자 검증이 없습니다", "만들지 않는 것: … AFM 과 SEM 을 잇는 링크" — [docs/research/2026-10-05-page-value-brainstorm.md:201-202,467,516](docs/research/2026-10-05-page-value-brainstorm.md)
- AFM 데이터 명세에 device/step/oper/product 필드 없음(`docs/datatables/afm/*.txt` grep 0건, `spec` 은 "아직 정하지 않아" 한 줄뿐) — [docs/datatables/afm/afm_redis.txt:167](docs/datatables/afm/afm_redis.txt)
- e-beam 쪽은 `lot_id`, `lot_cd`(device 코드), `oper_id`, `oper_det_desc`(스텝 이름) 체계를 가짐 — [docs/datatables/hitachi/ebeam_tas_lot_hist.txt:11-37](docs/datatables/hitachi/ebeam_tas_lot_hist.txt)
- AFM lot 실측 예: `5NNN0336`, `5PNN1768`, `MON69683`(MAPC01 Info) — [docs/datatables/afm/afm_redis.txt:253](docs/datatables/afm/afm_redis.txt), [docs/datatables/afm/afm_raw_files.txt:67,92](docs/datatables/afm/afm_raw_files.txt)
- 장비를 합치지 않는 규칙: "장비마다 fab 이 다르므로 한 화면에서 한 장비만 조회하며, 여러 장비의 측정을 합쳐 보여 주지 않습니다". 장비 간 matching 은 "동일 대상과 조건, Recipe·항목의 동등성, 기준 장비"가 필요해 보류 — [docs/afm/feature-summary.md:13](docs/afm/feature-summary.md), [docs/afm/service-recommendations.md:329](docs/afm/service-recommendations.md)
- AFM 화면은 e-beam 셸(`layouts/default.vue`)에서 전폭으로 돌지만 공유는 크롬뿐 — [DESIGN.md:452](DESIGN.md)

### Inferences
- (추론) AFM `lot_id` 가 e-beam `lot_id` 와 같은 체계인지는 저장소에 근거가 없습니다. 같다 하더라도 AFM 에는 공정 스텝 식별자가 없어 "같은 lot 의 어느 시점 측정인가"를 측정 시각으로만 추정해야 합니다. 상관 분석을 하려면 (1) lot 체계 일치 확인, (2) `ebeam_tas_lot_hist` 같은 lot 이력으로 AFM 측정 시각을 스텝에 사상하는 규칙, (3) 사용자 조건(cross-page 링크에는 유지보수 근거가 필요)이 선행돼야 합니다.
- (추론) MAP608 은 PKG fab 이고 e-beam 장비 fab(M/R3 계열)과 다르므로, 상관 후보는 MAPC01(R3)·5EAP1501(M15)로 좁혀집니다.

### Gaps
- AFM lot_id 와 e-beam lot_id 의 체계 일치 여부, AFM recipe 이름에서 공정 스텝을 유도할 수 있는지 — 문서에 없습니다.

## 6. 무엇이 의도되었고 무엇이 보류되었는가

### Takeaway
저장소에는 이미 순위가 매겨진 AFM 후속 목록이 두 벌 있습니다(10-05 브레인스톰의 S6 고정 기준 비교, 10-08 추천 보고서의 7개). 그중 출시된 것은 소요시간 분석의 "선택 그룹" 단계 하나뿐이고, 나머지는 미구현입니다.

### Cited Findings
- 추천 보고서 순위(2026-10-08): 1 Lot·웨이퍼 이력 자동 연결, 2 측정 소요시간 분석, 3 팁 변경 전후 비교, 4 프로파일 비교·차이 보기, 5 측정 항목 간 관계 분석, 6 이상 측정 조사 묶음, 7 한 측정 안의 반복 회차 분석(회차 매핑 확인 후) — [docs/afm/service-recommendations.md:13-23](docs/afm/service-recommendations.md)
- 추가 데이터가 있어야 하는 것(보류): Spec 합격·Cp/Cpk(규격 필요), 팁 잔여 수명·교체 권고(교체 사유·수명 기준 필요), 실제 가동률·OEE(상태 로그 필요), ETL 누락·성공률 감시(적재 로그 필요), 장비 간 matching, 정식 GRR — [docs/afm/service-recommendations.md:321-332](docs/afm/service-recommendations.md)
- S6 "AFM 고정 기준 대비 비교"(카트 안 이전 측정을 기준으로 고정): 10-05 채택, 10-06 계획에서 "AFM 사내 어댑터 뒤로 보류". 바꿀 이음매는 `trendRows` 의 `centres` 한 곳. **미구현**(`useAfmCart`·`afmTrend` 에 baseline 슬라이스 없음 — `PointBaseline` 은 포인트 Δ 전용) — [docs/research/2026-10-06-page-value-plans.md:505-541](docs/research/2026-10-06-page-value-plans.md), [frontend/app/utils/afmTrend.ts:226](frontend/app/utils/afmTrend.ts)
- 브레인스톰의 다른 AFM 판정: S12 "원본 Summary 와 유효 행만의 통계 나란히 보기" 후보(`Valid=FALSE` 미관측이라 확인 필요), "같은 위치 반복 일치도" 보류(GR&R 이라 부르지 않음), "장비 간 비교" 보류, "팁 교체 전후 비교" 보류(교체 이력 없음), "AFM 관리 한계선" 철회(데이터가 주장을 받쳐 주지 못함) — [docs/research/2026-10-05-page-value-brainstorm.md:453-467,530-532](docs/research/2026-10-05-page-value-brainstorm.md)
- 문서 간 충돌: 10-05 브레인스톰은 팁 교체 전후 비교를 "보류(이력 없음)"로, 10-08 추천 보고서는 3순위로 추천 — 사이에 7·8차 회신으로 "팁 변경 추정"(`tipChanges`) 근거가 생겼고, 추천 보고서는 이벤트 이름을 "팁 변경 추정"으로 제한 — [docs/afm/service-recommendations.md:163-191](docs/afm/service-recommendations.md)
- 사용자 방침(12차): Start/End Time 은 장비 설정에 달려 있으니 지금 값이 있는 장비·측정만 분석하고, 장비 이름이 아니라 값의 유무로 판단 — [docs/afm/office-data-findings.md:810-818](docs/afm/office-data-findings.md)
- 공통 구현 원칙(추천 보고서 10절): 전체 목록으로 후보를 좁히고 고른 측정만 상세 조회, 모든 프로파일·이미지를 미리 읽지 않음, `data.py` 는 수정하지 않음, 목록에 분석 열을 추가하면 계약·office template·mock·데이터 명세를 함께 맞춤 — [docs/afm/service-recommendations.md:311-319](docs/afm/service-recommendations.md)
- 프로젝트 제약: 새 OpenSearch 인덱스·매핑 변경 금지, 모바일·노트북 레이아웃 제외(1920×1080) — [docs/research/2026-10-05-page-value-brainstorm.md:517-519](docs/research/2026-10-05-page-value-brainstorm.md)
- `CONTEXT.md` 에는 AFM 언급이 없습니다(grep 0건). `.scratch/` 의 AFM 관련은 `afm-scale-261009/`, `afm-review-261007/` 두 폴더이며 열린 이슈 티켓은 찾지 못했습니다.

### Inferences
- (추론) 추천 1번(Lot·Slot 후보 자동 연결)은 미구현입니다. 상세 페이지의 컴포넌트 구성(`InfoPanel, PointRail, PointSummary, AnalysisImages, MeasurementPointsTable, HeatmapChart, ProfileImage, HistogramChart`)에 이력 패널이 없습니다(`frontend/app/pages/afm/[tool]/[filename].vue:54-117`).
- (추론) 추천 2번은 절반 출시입니다: 선택 그룹 단계(05 카드)는 있고, 가동 현황 전체로의 확장(ETL 요약 열)과 P90 은 없습니다.

### Gaps
- 사용자가 추천 보고서 7개 중 무엇을 승인했는지는 저장소에 기록이 없습니다(출시된 소요시간 카드 외).

## 7. 공백 정리 — (a) 있는 것 / (b) 데이터는 있으나 쓰지 않는 것 / (c) 추론한 공백

### Takeaway
가장 큰 미활용 자산은 raw 프로파일 표본(높이 배열)과 목록의 3개월 전수 이력입니다. 가장 큰 구조적 제약은 spec·device·step 부재, 팁 교체 레이블 부재, "수치 분석은 손으로 담은 20건"이라는 상한입니다.

### Cited Findings

#### (a) 이미 있는 것 — 다시 만들지 않아도 되는 것
- 측정 검색·조회 기록·그룹 저장, 측정 상세(Info/포인트/요약/이미지 4종/표/프로파일/히스토그램/Excel/링크), 시계열 비교 5구역, 팁 모니터링, 가동 현황, Recipe 현황 — [docs/afm/feature-summary.md](docs/afm/feature-summary.md)
- 재사용 가능한 순수 함수: `prepareEntries, robustSd, controlLimits, measurementStats, trendRows, pointMatrix, pointStability, varianceSplit, repeatPairs, healthSeries, tipChanges`(afmTrend), `tipPoints, tipCategories, widthIsPerTip`(afmTips), `durationOf, durationRows, durationByRecipe`(afmDuration), `profileGrid, isLineProfile, filterProfileByOutlier`(afmHeatmap), `histogramStats, computeHistogram`(afmHistogram), `collectColumns, isMeasurementKey`(afmExport) — [frontend/app/utils/afmTrend.ts](frontend/app/utils/afmTrend.ts), [frontend/app/utils/afmTips.ts](frontend/app/utils/afmTips.ts), [frontend/app/utils/afmDuration.ts](frontend/app/utils/afmDuration.ts)

#### (b) 데이터는 있으나 분석에 쓰지 않는 것 (근거 인용)
- **프로파일 X/Y/Z 전체 표본**: 화면은 한 point 를 그리고 count/min/max/mean·히스토그램만 계산. 두 프로파일 비교, 단차·거칠기 재계산, leveling 없음 — [frontend/app/utils/afmHeatmap.ts:72](frontend/app/utils/afmHeatmap.ts), [docs/afm/service-recommendations.md:193-199](docs/afm/service-recommendations.md)
- **`Site X`/`Site Y`**: 포인트 선택용 점 지도에만 쓰이고 값 색칠 맵·반경 분석에 쓰이지 않음 — [frontend/app/utils/afmPoints.ts:87-107](frontend/app/utils/afmPoints.ts)
- **같은 위치의 여러 측정 컬럼**(Left_H/Right_H, Ra/Rq 등): 컬럼 간 관계 분석 없음 — [docs/afm/service-recommendations.md:225-229](docs/afm/service-recommendations.md)
- **repeat 회차 값**: 표의 `회차` 열로만 노출, 통계에서는 마지막 값만 남음 — [docs/afm/service-recommendations.md:293-299](docs/afm/service-recommendations.md)
- **`Sample ID`·`Carrier ID`**(Info): `Sample ID` 는 시계열 비교의 재측정 쌍 판별에만 쓰이고 검색·자동 이력 연결에는 쓰이지 않음(목록에 없음). `Carrier ID` 는 표시만 — [frontend/app/utils/afmTrend.ts:71](frontend/app/utils/afmTrend.ts), [docs/afm/service-recommendations.md:82](docs/afm/service-recommendations.md)
- **`Last Put Back Time`**(Info): 표시만. 목록 열 없음 — [docs/datatables/afm/afm_redis.txt:142-144,180-181](docs/datatables/afm/afm_redis.txt)
- **`invalid_count`**: 가동 현황의 "무효" 일별 막대·표 열로 쓰이지만 실물 `Valid=FALSE` 는 0건이라 사무실에서는 항상 0 일 가능성 — [docs/datatables/afm/afm_raw_files.txt:268-269](docs/datatables/afm/afm_raw_files.txt)
- **`approach_count_mean`·`mileage_mean`**: 팁 화면·건강 strip 에 선으로만 표시, 측정 결과와의 관계 분석 없음. Mileage 는 판정 제외 — [frontend/app/utils/afmTips.ts:5-7](frontend/app/utils/afmTips.ts)
- **팁 이미지 `_C_PR`/`C_Result`**: 갤러리 표시만, 팁 모니터링은 이미지를 쓰지 않음 — [docs/afm/to-questionnaire-afm.md](docs/afm/to-questionnaire-afm.md) (Q53)
- **Redis `afm_tool_recipes`, `afm_download_history`**: 웹이 읽지 않음 — [docs/datatables/afm/afm_redis.txt:42-46](docs/datatables/afm/afm_redis.txt)
- **`raw_dir_list`(원본 csv/txt)**: 계약에 있으나 프런트가 읽지 않고(`grep dir_list frontend/app` 0건) 다운로드 경로도 없음 — [.scratch/afm-scale-261009/codex-r2.md](.scratch/afm-scale-261009/codex-r2.md)
- **목록의 3개월 전수 이력**: 건수 집계(가동·recipe)와 팁 판정에만 쓰이고, 측정값 추세에는 쓰이지 못함(측정값이 목록에 없음) — [backend/afm/contracts.py:18-71](backend/afm/contracts.py)
- **`Start Time`/`End Time`**: 선택 그룹에서만 소요시간 계산, 가동 현황 전체에는 미연결 — [docs/afm/service-recommendations.md:148](docs/afm/service-recommendations.md)

#### (c) 추론한 공백 — 모두 추론이며 코드·문서의 직접 진술이 아닙니다
- (추론) **recipe 전체 자동 추세 부재**: 엔지니어가 "이 recipe 의 `Dishing_H` 가 지난 3개월 어떻게 움직였나"를 보려면 20건을 손으로 담아야 합니다. 팁 열처럼 측정당 요약값(block×컬럼의 MEAN/STDEV)을 목록에 적재하면 전수 추세·자동 이상 탐지가 목록만으로 가능합니다. 단 컬럼이 recipe 마다 달라(최대 51개) 넓은 열이 아니라 중첩/긴 형태가 필요하고, ETL 담당(Office agent)에게 요청해야 합니다.
- (추론) **고정 기준선 부재**: 관리선이 선택 그룹에서 다시 계산되어 대상과 함께 움직입니다(S6 가 지적, 미구현).
- (추론) **값으로 색칠한 wafer-내 맵·균일도 지표 부재**: Site ID 를 기록하는 recipe 에 한해 인덱스 격자 맵이 가능합니다. 방향(Q24)과 물리 좌표는 미확정입니다.
- (추론) **프로파일 파생 분석 부재**: 높이 표본이 있으므로 단차·거칠기·기울기 재계산이 기술적으로 가능하나, leveling 미적용·단위 혼재·Pixel 축·5EAP1501 부재·모든 point 에 있지 않음이 제약입니다. 장비가 이미 계산한 `(nm)` 컬럼과 재계산값이 어긋날 때의 해석 책임도 생깁니다.
- (추론) **팁 ↔ 측정 결과 연결 부재**: 팁 화면과 수치 추세가 분리되어 있습니다. 팁 변경 "추정" 전후 비교는 가능하나 교체 레이블이 없어 인과 주장은 못 합니다.
- (추론) **spec 기반 판정 불가**: 규격이 없어 합격/불합격, Cp/Cpk, 한계 대비 여유를 낼 수 없습니다. 사용자가 recipe×컬럼별 spec 을 입력·보관하는 구조가 생기면 가능하지만, 그것은 앱 소유 상태(Redis 쓰기)가 필요한 새 범위입니다.
- (추론) **장비 간·AFM↔CD-SEM 상관**: 식별자 검증이 없고 기존 결정이 제외입니다(5절).
- (추론) **적재 건강 가시성 부재**: 추출 실패가 목록에 안 보여 "측정이 없었다"와 "적재가 실패했다"를 구분할 수 없습니다.
- (추론, UI/UX 마찰) (1) 사무실에서 상세 5~8초, 원인 미상; (2) Result 탭 첫 로드가 이미지당 MinIO 1회; (3) 시계열 비교가 측정당 상세 1요청이라 20건 상한이고 진입 전 수동 담기가 필요; (4) 검색 기본이 "전체"라 수천 행을 한 번에 마운트(페이지네이션은 실측 후로 보류); (5) Info key 가 A–Z 순으로 나와 파일 순서가 아님(`afm_raw_files.txt:212-213`); (6) "웨이퍼 히트맵"이라는 카드 제목이 실제로는 한 point 스캔 높이맵이라 오해 소지; (7) 측정 컬럼이 51개인 recipe 는 컬럼 선택이 수동; (8) 그룹·기록·저장 그룹이 브라우저 localStorage 라 다른 PC·동료와 공유되지 않음(링크 복사는 측정 한 건만, `route.query` 를 읽는 AFM 검색·시계열 화면 없음 — `2026-10-05-page-value-brainstorm.md:91`); (9) recipe 간 비교는 경고 후 분리만 가능(S8 미답); (10) MAP608 은 `measured_time` null 측정이 세션 시각에 몰려 시간대 분석이 왜곡.

### Inferences
- (추론) 분석 서비스 후보를 "현재 데이터만으로 가능 / ETL 열 추가 필요 / 외부 데이터 필요"로 나누면: 가능 = Lot·Slot 이력 연결, 고정 기준선, 컬럼 간 산점도, 인덱스 격자 값 맵, 1D 프로파일 겹쳐 보기, 팁 변경 추정 전후 비교, 회차 분석(매핑 확인 후). ETL 필요 = recipe 전수 수치 추세·자동 이상 탐지, 가동 현황 소요시간, Sample ID 검색. 외부 데이터 필요 = spec/Cpk, 팁 수명, OEE, 적재 성공률, 장비 matching, CD-SEM 상관.
- (추론) 집(mock)에서 만든 어떤 분석도 실측 분포를 근거로 삼을 수 없습니다. mock 값 모델은 추세 화면이 "찾을 것이 있도록" 설계된 가짜입니다(`mock.py:1079-1080`).

### Gaps
- 엔지니어가 실제로 어떤 판단을 AFM 화면에서 내리는지(사용 시나리오)에 대한 기록은 저장소에 없습니다. 유일한 사용자 요청 기록은 "팁 불량 모니터링 현황을 보고 싶다"(`docs/office-migration/to-office-afm-tip-columns.md:7`)와 원본 다운로드·회차 표·요청 제한 해제(`docs/afm/office-data-findings.md:549-561`)입니다.
- 활동 로그 기준 AFM 탭별 실제 사용량은 조회하지 않았습니다(slug 분리가 2026-10-08 이라 누적도 하루치입니다).
