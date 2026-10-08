"""SWAP SURFACE — 사무실에서 동일 시그니처/TypedDict 로 재구현 대상.

원본 데이터: Redis 색인 + MinIO 객체 — docs/datatables/afm/afm_redis.txt (적재 형태)
            AFM 장비 raw 파일 — docs/datatables/afm/afm_raw_files.txt (그 원천)
            (회신 원문 docs/afm/office-data-findings.md, 이관 이력 docs/afm-migration-plan.md)
계약:        docs/api-contracts/afm.yaml
픽스처:      backend/afm/__fixtures__/

AFM 은 단일 측정 행(`AfmMeasurementRow`) 보다 풍부한 디테일·프로파일·이미지 응답
구조를 가집니다. 함수별 반환 형태가 다르므로 픽스처에 엔드포인트별 샘플을 모두
캡처해 사무실 LLM이 형태를 한눈에 볼 수 있도록 합니다.

이 mock 이 대신하는 것은 ETL 이후의 적재물입니다 — Redis hash `afm_d1_tools`(장비
목록)·`afm_d2_measurements`(장비별 측정 이력)와, 그 행이 가리키는 MinIO 객체(상세·
profile·이미지)입니다. 값의 내용은 각 장비의 **raw 파일**에서 온 것이라 아래 raw 사실이
그대로 적용됩니다.

적재 형태로 확인되어 그대로 재현하는 것 (afm_redis.txt — 명세 user-confirmed 2026-10-06,
열 구성과 값은 office 확인 2026-10-06 의 6차 회신):
- 목록 행의 열은 unique_key·filename·date(YYMMDD)·formatted_date·recipe_name·lot_id·
  slot_number·time(HHMMSS 6자리)·tool_name·fab·point_count 와 파일 목록 7종(`data`·
  `profile`·`tiff`·`align`·`tip`·`capture`·`raw` + `_dir_list`)입니다.
- **파일이 없으면 빈 리스트**입니다. 예전 mock 의 `["no files"]` 표지는 실제에 없습니다.
- `unique_key` 는 파일명의 앞 6필드(date#time#recipe#slot#lot#measured)이고 MAPC01 은
  앞 4필드입니다.
- `filename` 은 **data CSV 의 원본 파일명 전체**이고, data CSV 가 없는 측정만 info CSV
  (`_Info.csv`)입니다. 한 장비 안에서 `filename`·`unique_key` 모두 유일합니다.
- `measured_info` 열은 있으나 **항상 null** 입니다(계약에서는 빈 문자열). `tool_id` 열은 없습니다.
- `measured_time` 은 그 측정의 시작 시각입니다(office 확인 2026-10-07 에 추가된 열).
  MAP608 의 `time` 은 세션 시각이고, 이름의 6번째 필드(측정 시작)는 최근 파일의 절반쯤
  (29/46)에서 `NA` 입니다. 8차 회신(office 확인 2026-10-07): 값은 `HHMMSS` 6자리이고, 그
  자리가 `NA` 이면 Info 의 `Start Time` 에서 오며(세션 시각과 다릅니다 — 실측 014148 →
  022914), `Start Time` 이 없는 13키 Info 의 측정은 null 입니다. MAPC01·5EAP1501 은 `time`
  과 같습니다. mock 도 그대로 냅니다.
- `point_count` 는 **실제로 스캔한 위치 수**입니다(profile·tiff 파일 수, office 확인
  2026-10-07). 행 수도 recipe 의 수도 아니어서 repeat recipe 는 위치 수만 셉니다.
- MAPC01 의 `lot_id` 는 Info 의 `Lot ID` 로 채워져 있습니다.
- `slot_number` 는 Info `Sample Location` 의 `Slot N` 에서 옵니다(실제 웨이퍼 슬롯).
  앞에 0 이 없는 숫자 문자열입니다(`5`, `10`, `21` — office 확인 2026-10-07, 9차).
  office 에는 null 인 행도 있지만 mock 은 내지 않습니다.
- `last_pick_up_time` 은 Info 의 `Last Pick Up Time` 그대로입니다(9차에 추가된 열).
- 10차·11차(office 확인 2026-10-07, 사무실 실행): capture 는 일부 point 에만 있고 아예
  없는 측정도 있습니다. 5EAP1501 의 capture 이름은 3자리 번호로 끝납니다(`…_003.webp`) —
  mock 도 그렇게 냅니다(그 번호가 point 번호라는 것은 OFFICE-VERIFY). office 의
  `slot_number` 는 Info 에서 온 값(`5`)과 파일명에서 온 값(`07`)이 섞여 있고 adapter 가 앞의
  0 을 떼므로, mock 은 뗀 뒤의 모양만 냅니다.
- 9차 회신(office 확인 2026-10-07)으로 맞춘 이미지 이름: align 은 측정마다 1~4장이고
  `N_Result.webp`(위치 키 없음), capture 는 point 마다 한 장이고 위치 키로 끝나며
  (`…_0001.webp`), 원본은 webp 와 이름이 같고 확장자만 다릅니다(`C_Result` 는 `.bmp`).
  `Sample Location` 은 `Port 1 Slot N` 꼴입니다(MAP608 의 `Stage` 는 내지 않습니다).
- 객체 이름: 상세는 `detail_information.parquet`·`detail_summary.parquet`·
  `detail_points.parquet`, profile 은 `profile_<원본이름>.parquet`, 이미지는
  `<파일명>.webp` 입니다. **data CSV 가 없는 측정은 `data_dir_list` 에 information 하나만**
  들어 있으므로, `has_data` 는 목록이 비었는지가 아니라 points 객체가 있는지입니다.
- **원본 TIFF 는 `tiff_dir_list` 에 webp 와 함께** 들어 있고 확장자는 `.tiff` 입니다.
  5EAP1501 은 초기 적재에서 빠져 있다가 재적재되었습니다(office 확인 2026-10-07, 10차).
- tip 이미지는 두 계열입니다 — point 마다 `_C_PR`, 측정마다 `C_Result` 한 장(office 확인
  2026-10-07).
- MAPC01 의 profile·이미지 이름은 `filename` 으로 **시작하지 않습니다**(5·6번째 필드가
  다릅니다). 어느 point 의 파일인지는 이름의 **끝**(`_<위치 키>_Height`)으로만 알 수 있습니다.
- points 의 각 행은 `Site` 열에 **자기 block 의 method 명**을 갖습니다. block 을 행의
  순서나 "같은 point 가 다시 나옴"으로 추측하면 안 됩니다 — repeat recipe 는 한 block 안에서
  같은 point 가 되풀이됩니다(실측 4 Site × 2 반복 = 8행). 반복 번호 열은 없고, 모든 Site 를
  한 바퀴 돈 뒤 다시 돌며, 바퀴는 `Sample Count`(실측 4 → 5)로 구분됩니다(office 확인
  2026-10-07).
- 측정이 중단되면 **측정하지 못한 point 의 행은 아예 없습니다.** STOPPED 행은 중단된 그
  point 하나입니다(office 확인 2026-10-07). 측정하지 못한 칸은 값이
  없습니다(적재물은 공백 한 칸 `' '`, `_Valid` 는 `''` — 계약에서는 null).
- Summary 가 없으면 열도 없는 0행짜리 객체가 있습니다(계약에서는 빈 목록).
- profile 은 X/Y/Z parquet 이고 단위(XUnit·YUnit·ZUnit·DataSize·SurfaceSize)는 MinIO 객체의
  user metadata 입니다.

적재 형태와 일부러 다른 것:
- Redis 의 파일 목록은 MinIO 객체 key 전체(`2067928/afm/<TOOL>/<측정키>/<파일명>`)이고,
  계약(`AfmMeasurementRow`)의 목록은 그 **basename** 입니다. office adapter 가 잘라 내므로
  mock 도 이름만 냅니다.
- 적재물의 상세는 **모든 값이 문자열**입니다(`"79.24"`, Point No 도 `"1"`). office adapter 가
  단위가 붙은 열·`Point No`·`Site X/Y` 를 숫자로, `Valid` 류를 bool 로 바꾸므로 mock 은 바꾼
  뒤의 형태를 냅니다. `Method ID` 는 바꾸지 않으므로 숫자처럼 보여도 문자열(`"2"`)입니다.
- Redis 의 `formatted_date`·`time`·`point_count` 는 null 일 수 있습니다(`time` 의 `NA` 도
  null). mock 은 null 을 내지 않습니다 — 파일명과 상세를 그 값에서 만들기 때문입니다.
  null 경로는 backend/afm/tests/test_office_template.py 가 adapter 에서 직접 확인합니다.
  그래서 첫 point 에서 중단되어 파일이 없는 측정(`point_count` null)과 도중에 중단되어
  `point_count` 가 recipe 보다 작은 측정(실측 2·3·5·8·14·43·55)도 mock 에는 없습니다.
- align·tip·capture 의 원본은 각자의 목록에 있고 TIFF 가 아닙니다 — align 은 `.bmp`, tip
  과 capture 는 `.png` (office 확인 2026-10-07, 8차). mock 도 webp 옆에 냅니다.
- Redis `afm_d1_tools` 는 `fab` 이 빈 문자열이고 `alias` 가 MAP608=null·MAPC01=R3·
  5EAP1501=M15 입니다(`alias` 는 파이프라인의 장비 코드명이고 fab 이라는 근거는 없습니다 —
  office 확인 2026-10-07). fab 은 MAP608=PKG, MAPC01=R3, 5EAP1501=M15 입니다
  (user-confirmed 2026-10-07). mock 은 그 fab 을 채워 냅니다.
- 이름·값을 지어낸 곳 (OFFICE-VERIFY): repeat recipe 의 이름(`RQQA_REPEAT_4SITE`)과 크기
  (4 Site × 1 point — 실측은 4 × 14), MAPC01 의 profile·이미지 이름에서 5번째 필드에
  들어가는 값(mock 은 lot), align·capture 이름에서 번호·위치 키 앞부분.
- `Sample Count` 는 한 측정 안에서 같은 값이고(1~47) repeat recipe 만 바퀴마다 1 커집니다.
  Site ID 유무와는 무관합니다(office 확인 2026-10-07, 8차).

확인되어 그대로 재현하는 것 (office 확인 2026-10-02, 회신 4회):
- 장비는 MAP608 · MAPC01 · 5EAP1501 이고 MAPC01=R3, 5EAP1501=M15 입니다.
- 파일명은 `#` 구분이며 장비마다 필드 순서가 다르고, 빈자리는 `NA` 입니다.
  - MAP608 의 첫 시각은 **세션(폴더) 시작 시각**이라 같은 세션의 측정들이 공유합니다.
    뒤 시각이 측정 시작이고, 그 자리가 `NA` 인 파일이 많습니다(오래된 파일만이 아니라
    최근 파일의 절반쯤 — office 확인 2026-10-07). 그때도 Info 의 `Start Time` 은 그 측정의
    시작이며 첫 시각과 다를 수 있습니다(8차 정정).
  - MAPC01 은 `_Info.csv` 가 모든 측정에 있고 data CSV 는 같은 이름에서 `_Info` 를 뺀
    것입니다(목록의 `filename` 은 data CSV 가 있으면 그쪽입니다). 측정 한 건은 앞 4필드(date#time#recipe#slot)이며, 같은 sample 이 하루에
    여러 번 다시 측정되어 시각만 다릅니다. lot 은 파일명에 없고(NA) Info 의 `Lot ID` 에 있습니다.
  - 5EAP1501 의 끝은 RECIPE+LOT+SAMPLE 을 구분자 없이 이은 원본 파일명이고 접미
    (`_SOP_LEFT_UR` 등)가 붙기도 합니다. SAMPLE_ID 는 `<lot>.<nn>` 입니다.
- recipe 명에는 세 장비 모두 공백·괄호·소문자가 들어갈 수 있습니다 (`Fi-Tapping TEST`,
  `RQQA_PFH_MONF (1)`, `xy scanner opm`, `zeroscan 5point pm`).
- 어떤 파일(data CSV·profile txt·이미지)이 있는지는 **recipe 설정**이 정합니다. 없는 것이
  정상 상태이므로 `has_*` 와 `*_dir_list` 는 행 번호가 아니라 recipe 에서 나옵니다.
  5EAP1501 은 profile txt 가 없습니다.
- point 수도 recipe 가 정하며 1~36 까지 실측되었습니다(2026-10-07 회신의 최대는 56 =
  4 Site × 14 point; mock 은 36 까지만 냅니다).
- 측정 컬럼은 recipe 마다 다르고 모두 `(nm)` 를 포함합니다 — `Left_H`/`Right_H`/`Ref_H`,
  `Dishing_H`, `Bottom_H`/`Top_H`, `Ref_Range`/`Left_TRIM_H`, `ROUGHNESS_RANGE`/`Ra`/`Rq`,
  `Pad_1_H`…, `1_Minimum`…`51_Minimum`, `RZ1_Minimum`…, `Line1_Residue_H`, `SITE19_21_H`.
- Summary block 의 이름은 method 명이고 한 파일에 여러 개일 수 있습니다
  (`Profile_LEFT_UL` + `Profile_RIGHT_UL`). Data 도 block 마다 나뉘고 block 은 point 마다
  한 행을 냅니다. block 마다 컬럼이 다를 수 있습니다 — 실측된 것은 중단된 뒤쪽 block 이
  측정 컬럼 없이 STOPPED 행만 남기는 경우이고, 그 block 은 Summary 가 비어 있습니다.
- `Method ID`(공백 — office 확인 2026-10-07)는 한 파일의 모든 block 에서 같은 값이라(`2`, 또는 `L1_XDEC_5MM_LINE`)
  block 을 가리는 키가 아닙니다. block 은 행의 `Site` 열로 가립니다(위 적재 형태).
- Summary 가 없는 파일(Info 뒤에 바로 Data), 표가 없는 Data 도 있습니다.
- 위치 키는 4자리 point 번호입니다 (`Point No`=1 ↔ 파일명 `_0001`). Site ID 를 기록하는
  recipe 만 `Site ID`·`Site X`·`Site Y` 컬럼을 갖고, 그때 파일명은
  `_0004_X000_Y-002_0002_Height.txt` 처럼 Site ID 뒤에 point 번호가 붙습니다.
  `Site X`·`Site Y` 는 Site ID 안의 숫자와 같고 단위가 없습니다.
- `State` 는 COMPLETED · FAILED · STOPPED 셋입니다. point 가 하나면 STDEV·RANGE 는 0.0 입니다.
- Info 의 key 는 측정에 따라 두 가지 구성입니다 (user-confirmed 2026-10-06).
  15키: Lot ID, Recipe ID, Carrier ID, Sample Location, Sample ID, Data Save Location,
  Start Time, End Time, Tip ID, Tip Cassette ID, Tip Port No, Tip Slot No,
  Last Pick Up Time, Last Put Back Time, Tip Width.
  13키: Port No, Carrier ID, Slot No, Lot ID, Sample ID, Recipe ID, Tip ID,
  Tip Cassette ID, Tip Port No, Tip Slot No, Last Pick Up Time, Last Put Back Time,
  Tip Width. 13키에는 `Sample Location`·`Start Time`·`End Time` 이 없습니다. 화면은 key 를 정해 두지
  않고 있는 key 만 보여 줍니다(JSON 응답이 key 를 정렬하므로 화면 순서는 A–Z 입니다).
- `Start Time`·`End Time` 은 `2026.10.01 00:13:58` 꼴입니다(user-confirmed 2026-10-08, KST 로
  읽습니다). 둘은 **data CSV 의 Info 에만** 있고 `_Info.csv` 에는 두 구성 모두 없습니다.
  `End Time` 은 측정이 끝난 뒤에만 기록됩니다. 날짜가 함께 있어 자정을 넘긴 측정도 그대로
  읽습니다(실측 22:32:28 → 00:11:13). MAPC01 은 지금 data CSV 가 없어 둘 다 쓸 수 없으므로
  mock 의 MAPC01 Info 는 전부 13키입니다. MAP608 에는 `Start Time` 만 있고 `End Time` 이
  없는 측정이 있습니다(user-confirmed 2026-10-08) — 그런 측정은 소요시간을 분석하지 않습니다.
  두 값이 남는지는 장비의 설정에 달려 있어(user-confirmed 2026-10-08) 나중에 생길 수 있으므로,
  화면은 장비 이름이 아니라 값이 있는지로 판단해야 합니다.
- Info 의 값은 비어 있을 수 있습니다 (`Carrier ID`, `Last Pick Up Time`,
  `Last Put Back Time`). 적재본은 빈 문자열이고 계약에서는 null 입니다.
- Profile 격자는 MAP608 512×64, MAPC01 은 1D(N×1, 1024~16384)와 2D 혼재이고 2D 는
  2048×256 입니다(user-confirmed 2026-10-06 — 524,288 점). 1D 는 Y 가 0 으로 고정되고
  DataSize(`1024 x 1`)로 구분합니다. 단위는 통일하지 않고 파일마다 um/nm/pm/Pixel 로
  다릅니다.
- Profile 의 Z 는 원본 그대로입니다(leveling 없음). 값이 없는 표본은 NaN 이고 응답에서는
  null 입니다(user-confirmed 2026-10-06). mock 도 null 을 섞습니다 — 얼마나 자주, 어떤
  모양으로 빠지는지는 모릅니다(OFFICE-VERIFY: mock 은 2000 점에 하나꼴로 흩어 놓습니다).
- 2048×256 은 화면이 그릴 수 없는 크기라 route 가 `profile_sampling.thin_profile` 로
  솎아서 보냅니다. provider 는 파일 전체를 돌려줍니다.

지어냈거나 일부러 다른 것 (OFFICE-VERIFY):
- recipe 명 가운데 실측된 것은 `BSOXCMP_CORRELATION_36PT`·`RL1A_LPCCMP_CMPWEAK2`·
  `RX1A_M0A_COT_X_PDG`·`VED_BS_TOP01`·`RL1C_L1_XDEC_5MM_LINE`·`VM_GTFILLOX_5PT_R1`·
  `Fi-Tapping TEST`·`RQQA_PFH_MONF (1)`·`xy scanner opm`·`zeroscan 5point pm` 이고 나머지는
  지어냈습니다. 어느 recipe 가 어느 장비·method·파일 종류·point 수를 갖는지는 일부만
  확인된 대응입니다.
- lot ID 는 실측 예(`MON69683`, `5PNN1768`)의 생김새만 따랐습니다. MAP608 의 SAMPLE_ID 와
  MAPC01 의 원본 파일명도 `<lot>.<nn>` 이라고 보았습니다.
- MAPC01·5EAP1501 의 profile·이미지 파일명에서 위치 키 앞부분. 격자 크기 `512x64`,
  `2048x256` 이 각각 MAP608, MAPC01 의 것이라는 대응(회신은 크기만 나열했습니다).
- Site ID recipe 에서 한 Site 에 point 가 몇 개인지 — 파일명 예(`0004…_0002`)로 여럿일 수
  있다는 것만 알고, mock 은 한 recipe 에만 Site 당 2개를 둡니다.
- 숫자가 아닌 `Method ID` 는 recipe 명에서 첫 토막을 뺀 것으로 만들었습니다(실측 한 건이
  그 모양입니다).
- `Valid` 는 FALSE 가 아직 실측되지 않았습니다(CSV 263개 전수 0건, office 확인
  2026-10-07). mock 은 일부를 False 로 냅니다.
- data 행과 이미지 목록의 **순서**. office 는 point 순서가 아닙니다(0003 부터 나옵니다 —
  user-confirmed 2026-10-08). 어떤 순서인지는 모르므로(OFFICE-VERIFY) mock 은 측정마다
  고정된 seed 로 뒤섞어 냅니다: data 는 한 바퀴 안의 point 순서만 뒤섞고(block 과 바퀴의
  순서는 그대로 — 그쪽은 확인된 사실입니다), `available_points` 는 그 순서를 따르며,
  이미지 목록은 종류마다 따로 뒤섞습니다. 화면이 point 번호로 정렬합니다.
- data 행의 나머지 키(`X (um)`, `<측정명>_Valid`, `Pick Up Count` …).
- 5EAP1501 은 15키 위주, MAPC01 은 13키 위주, MAP608 은 혼재라는 것까지가
  user-confirmed(2026-10-06)입니다. 비율(mock 은 13키를 8건 중 1·8·4건)과 한 파일의
  구성을 정하는 것(recipe·시기·파일 종류)은 지어냈습니다.
- 측정에 걸린 시간(`End Time` − `Start Time`)은 지어냈습니다 — mock 은 1~30분이고, 실측은
  한 세션의 측정 간격 약 26분과 98분 45초 한 건뿐입니다. `Last Pick Up Time`·
  `Last Put Back Time` 의 표기가 `Start Time` 과 같은 꼴인지도 모릅니다(mock 은 `-` 로 씁니다).
  MAPC01 에 data CSV 가 없다는 말이 point 데이터도 없다는 뜻인지는 확인하지 못했고, mock 은
  MAPC01 에 point 행을 그대로 냅니다.
- `End Time` 이 없는 MAP608 측정이 어느 것인지는 모릅니다. mock 은 이름의 측정 시각 자리가
  `NA` 인 15키 측정에서 key 자체를 뺍니다 — 어느 측정인지도, key 가 빠지는지 값이 비는지도
  지어냈습니다.
- Info 값의 생김새 가운데 `Port No`·`Slot No`·`Data Save Location`·`Tip *` 는
  생김새를 지어냈습니다(`Slot No` 는 숫자만, `Tip Width` 는 단위 없는 소수로 두었습니다).
  `Tip *` 는 office 확인(2026-10-06)을 따릅니다: 한 팁이 여러 측정에 같은 `Tip ID` 로
  오고, 같은 `Tip ID` 가 카세트의 여러 슬롯에 있어 팁은 (Tip ID, Tip Cassette ID,
  Tip Port No, Tip Slot No) 로 식별하며, `Tip Width` 는 측정 시점의 기록값이라 MCNT 계열은
  같은 자리에서도 측정마다 달라지고, 기록이 없으면 문자열 `NaN` 입니다(mock 은 20건 중 1건).
  office 확인(2026-10-07): MCNT 가 아닌 종류는 폭이 사실상 상수이고, MCNT 계열만
  33.96~39.11 로 퍼지며 같은 슬롯에서도 오르내립니다(마모가 아닌 측정 오차로 추정). mock 은
  MCNT 를 36.5 중심에 팁마다 ±1.5, 측정마다 ±1.05 로, 나머지 종류는 한 값으로 냅니다.
  data 행의 `Mileage` 는 **팁 단위 누적값**이라 한 팁을 쓰는 동안 커지기만 하고 팁이 바뀌면
  리셋됩니다(실측 `DT-NCHR_CM` slot 9 → slot 1, 1430483 → 3520). 교체를 적은 기록은 없어
  이것이 팁이 바뀐 것을 아는 근거입니다. `DT-NCHR_CM` 은 실제 Tip ID 입니다.
  8차 회신(office 확인 2026-10-07): 같은 팁에서 Mileage 가 줄어든 일은 0건이지만 재시작·
  수동 초기화는 미실측입니다. `Last Pick Up Time`·`Last Put Back Time` 은 팁 단위 값이라
  한 팁의 모든 측정이 같은 값을 갖고, 갱신은 재픽업입니다. 관측된 Tip ID 는 8종(MCNT 포함
  2종)이고 5EAP1501 의 `OMCL-AC160TS` 는 폭이 대부분 NaN 입니다 — mock 은 5EAP1501 에서
  `DT-NCHR_CM` 자리에 그 종류를 내고 20건 중 16건을 `NaN` 으로 둡니다.
  지어낸 것(OFFICE-VERIFY): MCNT 계열의 이름(`MCNT-150`·`MCNT-500`)과 종류 수, 한 팁이 4일
  유지된다는 것, `DT-NCHR_CM` 의 폭(70)과 `OMCL-AC160TS` 의 폭(7), Mileage 의 증가 속도
  (분당 240), `NaN` 의 비율, Put Back 이 Pick Up 7분 전이라는 것.
  `Data Save Location` 은 공백 없는 긴 경로라는 것만 user-confirmed(2026-10-06)이고,
  폴더 구성(드라이브·장비·날짜·recipe·lot 순서)은 지어냈습니다.
- 목록의 팁 열 9종(`tip_id`·`tip_cassette_id`·`tip_port_no`·`tip_slot_no`·`tip_width`·
  `approach_count_mean`·`mileage_mean`·`not_completed_count`·`invalid_count`)은 2026-10-07 에
  office 의 `afm_d2_measurements` 에 이 이름으로 적재되었습니다(office 확인). 상세와 같은 첫
  data CSV 에서 계산하므로 목록과 상세가 어긋나지 않고, mock 도 각 측정의 상세에서 같은
  정의로 채웁니다. `tip_width` 는 office 에서 float64(기록이 없으면 NaN)이고 계약에서는
  null 이며, 뒤의 넷은 data 행이 없는 측정에서 null 입니다.
- 측정값의 수준·추세·퍼짐은 전부 지어낸 것입니다. recipe·컬럼마다 고정된 수준(55~120 nm)에
  측정 시각에 비례하는 완만한 드리프트(하루 ±0.4 nm 이내), sample(lot+slot) 공통 오프셋
  (σ 0.8 nm, 재측정끼리 같음), 중심에서 바깥으로 커지는 site 패턴(반지름²당 0.25 nm),
  포인트 노이즈(σ 0.6 nm)를 더하고, 9건에 1건꼴로 +7.5 nm 이탈이 FAILED·Valid=FALSE·
  Approach Count 증가와 함께 옵니다. 시계열 비교가 집에서도 추세·관리선 밖·포인트 패턴·
  재현성을 잡을 수 있게 둔 구조이지 실측 값 범위가 아닙니다. 드리프트는 BASE_TIME 기준
  절대 시각의 함수라 파일이 오래돼도 값이 바뀌지 않습니다.
- Summary 는 그 block 의 행에서 계산합니다. STDEV 는 표본 표준편차(ddof=1)이고 Valid 는
  거르지 않습니다.
- "method 명 줄만 있는 빈 Summary" 는 행 목록으로는 "Summary 없음"과 구분되지 않아 같은 모양으로 냅니다.
- 시각의 시간대는 KST 로 보고 진행합니다(user-confirmed 2026-10-07; 원본에는 시간대
  정보가 없습니다).
- 목록은 **오늘 날짜에서 끝납니다**(KST 기준). 하루가 지나면 하루치가 새로 생기고
  가장 오래된 하루치가 빠지며, 이미 있던 파일의 이름·lot·내용은 바뀌지 않습니다. 오늘
  측정의 시각은 고정이라 조회 시각보다 뒤일 수 있습니다.
- profile metadata 의 `SurfaceSize` 값 형식, Pixel 축의 길이 환산(근거 없음).
- 이미지는 자리 표시 SVG 입니다. 실제는 webp 변환본이며 office adapter 는 그 bytes 를
  그대로 돌려줍니다(route 가 str 은 SVG, bytes 는 webp 로 내보냅니다).
- 원본 TIFF 는 MinIO 에 있고 내려받을 수 있어야 합니다(user-confirmed 2026-10-03). mock 은
  Result 이미지마다 256x256 8bit 회색조 TIFF 를 지어냅니다. 원본의 파일명(변환본 이름에서
  확장자만 `.tiff` 로 바꾼 것으로 가정), 크기·bit 수·장비 전용 태그, MinIO 경로, 보존
  기간은 모두 OFFICE-VERIFY 입니다.
"""

import hashlib
import html
import io
import math
import random
import statistics
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import quote

from backend.afm.contracts import AfmMeasurementRow, AfmOriginalFile, AfmProfileMeta


__all__ = [
    "AfmMeasurementRow",
    "normalize_tool",
    "get_tools",
    "list_afm_files",
    "get_afm_file_detail",
    "get_profile_points",
    "get_profile_meta",
    "get_profile_image_svg",
    "list_analysis_images",
    "get_analysis_image_svg",
    "get_tiff_original",
]


ToolConfig = dict[str, Any]

# The day the row numbering is anchored on. Row 0 is this day's first
# measurement; every later day counts down from it, so a day's files are the
# same whichever day the list is read on.
BASE_TIME = datetime(2026, 4, 24, 9, 30, 0, tzinfo=timezone.utc)


# Korea has no DST, so a fixed offset is exact (the same choice, for the same
# reason, as ebeam/recipe_tat's mock).
KST = timezone(timedelta(hours=9), "KST")


def _today() -> date:
    """The list's newest day, in KST: the viewer's "오늘" is a Korean date, and
    a UTC host would otherwise serve yesterday's list until 09:00.
    A function so a test can pin it.
    """
    return datetime.now(KST).date()


# (Site X, Site Y) of each measured position, centre outwards; 36 is the most seen.
SITE_LAYOUT = tuple(sorted(
    ((site_x, site_y) for site_x in range(-3, 3) for site_y in range(-3, 3)),
    key=lambda position: (position[0] ** 2 + position[1] ** 2, position)
))
SUMMARY_ITEMS = ("MEAN", "STDEV", "MIN", "MAX", "RANGE")
# One measurement's detail is three parquet objects in MinIO.
DETAIL_OBJECTS = (
    "detail_information.parquet",
    "detail_summary.parquet",
    "detail_points.parquet",
)
# A point fails now and then; STOPPED rows come only from a block that stopped
# (OFFICE-VERIFY: the real failure rate is unknown).
STATE_CODES = ("COMPLETED",) * 24 + ("FAILED",)

# A profile file states its own X/Y/Z units; nothing unifies them. The factors turn
# the mock's um (lateral) and nm (height) into the unit a file declares.
_UM_UM_NM = ("um", "um", "nm")
_LATERAL_PER_UM = {"um": 1.0, "nm": 1e3, "pm": 1e6}
_HEIGHT_PER_NM = {"um": 1e-3, "nm": 1.0, "pm": 1e3}
# Lateral length of a scan line.
_SCAN_UM = 50

IMAGE_TYPE_FIELDS: dict[str, str] = {
    "align": "align_dir_list",
    "tip": "tip_dir_list",
    "capture": "capture_dir_list",
    "tiff": "tiff_dir_list",
}

_IMAGE_TYPE_ACCENT: dict[str, str] = {
    "align": "#2563eb",
    "tip": "#d97706",
    "capture": "#7c3aed",
    "tiff": "#0f766e",
}

def _numbered(template: str, count: int) -> tuple[str, ...]:
    return tuple(template.format(number) for number in range(1, count + 1))


_HEIGHTS = ("Left_H (nm)", "Right_H (nm)", "Ref_H (nm)")
_ROUGHNESS = ("ROUGHNESS_RANGE (nm)", "Ra (nm)", "Rq (nm)")

# What a recipe is configured to write, which is the only thing that decides
# what exists: `columns` of its data CSV (None = no data CSV), `methods` naming
# its Summary/Data blocks, how many `points`, whether rows carry a `site_id`
# (and then how many points `per_site`), `profile` txt or not, and which
# `images`. `method_id` is the Method_ID every block of the recipe reports;
# left out, it is the recipe name without its first token. `repeat` measures
# every point that many times inside one block.
RECIPES: dict[str, dict[str, Any]] = {
    "BSOXCMP_CORRELATION_36PT": {
        "columns": ("Bottom_H (nm)", "Top_H (nm)"), "methods": ("Correlation",),
        "points": 36, "site_id": True, "profile": True, "images": ("tiff", "align", "tip")
    },
    "VED_BS_TOP01": {
        "columns": _HEIGHTS, "methods": ("Profile_LEFT_UL", "Profile_RIGHT_UL"),
        "points": 10, "site_id": True, "per_site": 2, "profile": True, "images": ("tiff",)
    },
    "CMP_POST": {
        "columns": _HEIGHTS, "methods": ("Profile_LEFT_UL", "Profile_RIGHT_UL"),
        "points": 9, "site_id": True, "profile": True, "images": ("tiff", "tip")
    },
    "Fi-Tapping TEST": {
        "columns": _ROUGHNESS, "methods": ("Roughness",),
        "points": 1, "site_id": False, "profile": True, "images": ("align",)
    },
    "ROUGHNESS_SCAN": {
        "columns": _ROUGHNESS, "methods": ("Roughness",),
        "points": 5, "site_id": False, "profile": True, "images": ("tiff",)
    },
    "FSOXCMP_DISHING_9PT": {
        "columns": ("Dishing_H (nm)",), "methods": ("Dishing",),
        "points": 9, "site_id": True, "profile": False, "images": ("tiff", "tip")
    },
    "ETCH_TRIM": {
        "columns": ("Ref_Range (nm)", "Left_TRIM_H (nm)"), "methods": ("Trim Height",),
        "points": 13, "site_id": False, "profile": False, "images": ("tiff", "align")
    },
    "PAD_HEIGHT_3PAD": {
        "columns": _numbered("Pad_{}_H (nm)", 3), "methods": ("Step Height",),
        "points": 5, "site_id": False, "profile": True, "images": ()
    },
    "RL1A_LPCCMP_CMPWEAK2": {
        "columns": ("Line1_Residue_H (nm)",), "methods": ("Line Residue",),
        "points": 17, "site_id": True, "profile": True, "images": ("tiff",)
    },
    "RX1A_M0A_COT_X_PDG": {
        "columns": ("SITE19_21_H (nm)",), "methods": ("Step Height",),
        "points": 21, "site_id": True, "profile": False, "images": ("tiff", "align")
    },
    "RQQA_PFH_MONF (1)": {
        "columns": None, "methods": (),
        "points": 5, "site_id": True, "profile": True, "images": ("tiff",)
    },
    "RL1C_L1_XDEC_5MM_LINE": {
        "columns": ("Line1_Residue_H (nm)",), "methods": ("Line Residue",),
        "points": 3, "site_id": False, "profile": True, "images": ()
    },
    # Fabricated name; the property is real: one block holds every point twice.
    "RQQA_REPEAT_4SITE": {
        "columns": ("Bottom_H (nm)",), "methods": ("Correlation",),
        "points": 4, "site_id": True, "repeat": 2, "profile": False, "images": ("tiff",)
    },
    "VM_GTFILLOX_5PT_R1": {
        "columns": ("Bottom_H (nm)", "Top_H (nm)"), "methods": ("Correlation",),
        "points": 5, "site_id": True, "profile": False, "images": ("tiff", "align")
    },
    "xy scanner opm": {
        "columns": _numbered("RZ{}_Minimum (nm)", 12), "methods": ("Trench Depth",),
        "points": 1, "site_id": False, "profile": False, "images": (), "method_id": "2"
    },
    "zeroscan 5point pm": {
        "columns": _numbered("{}_Minimum (nm)", 9), "methods": ("Trench Depth",),
        "points": 5, "site_id": False, "profile": False, "images": ("tiff", "tip")
    },
    "TRENCH_MIN_51LINE": {
        "columns": _numbered("{}_Minimum (nm)", 51), "methods": ("Trench Depth",),
        "points": 13, "site_id": True, "profile": False, "images": ("tiff",),
        "method_id": "2"
    }
}

# Per tool: `filename` is the raw file name's field order, `profile_grids` the
# (nx, ny) shapes its profile txt comes in (empty = the tool writes no profile
# txt) and `profile_units` the X/Y/Z unit sets those files declare.
TOOL_CONFIGS: dict[str, ToolConfig] = {
    "MAP608": {
        "tool_id": "map608",
        "fab": "PKG",
        "row_count": 36,
        "lot_prefixes": ("T7HQR", "T3HQR", "TT032", "CRAP1"),
        "recipes": (
            "BSOXCMP_CORRELATION_36PT",
            "VED_BS_TOP01",
            "Fi-Tapping TEST",
            "PAD_HEIGHT_3PAD",
            "FSOXCMP_DISHING_9PT",
            "ETCH_TRIM"
        ),
        # The leading time is the session (folder) start, shared by the session's
        # measurements; the trailing one is the measurement start, NA on old files.
        "filename": "#{date}#{time}#{recipe}#{sample}#{lot}#{start}#.csv",
        "session_size": 3,
        "profile_grids": ((512, 64),),
        "profile_units": (_UM_UM_NM,)
    },
    "MAPC01": {
        "tool_id": "mapc01",
        "fab": "R3",
        "row_count": 28,
        "lot_prefixes": ("MON69", "MON70", "RL1C0"),
        "recipes": (
            "RQQA_PFH_MONF (1)",
            "RL1A_LPCCMP_CMPWEAK2",
            "RL1C_L1_XDEC_5MM_LINE",
            "ROUGHNESS_SCAN",
            "RX1A_M0A_COT_X_PDG",
            "CMP_POST"
        ),
        # The lot is not in the name (NA); it is read from the Info section. The last
        # segment is the tool's original file name, and the data CSV drops `_Info`.
        "filename": "#{date}#{time}#{recipe}#{slot}#NA#NA#{sample}_Info.csv",
        # The same sample is measured again later the same day; only the time differs.
        "repeats": 3,
        "profile_grids": ((1024, 1), (2048, 256), (4096, 1), (16384, 1)),
        "profile_units": (
            _UM_UM_NM,
            ("nm", "nm", "nm"),
            ("um", "um", "pm"),
            ("Pixel", "Pixel", "nm")
        )
    },
    "5EAP1501": {
        "tool_id": "5eap1501",
        "fab": "M15",
        "row_count": 30,
        "lot_prefixes": ("5PNN17", "5PNN18", "5PMM20"),
        "recipes": (
            "xy scanner opm",
            "RQQA_REPEAT_4SITE",
            "TRENCH_MIN_51LINE",
            "zeroscan 5point pm",
            "VM_GTFILLOX_5PT_R1"
        ),
        # The tail is the tool's original file name: RECIPE + LOT + SAMPLE run
        # together with no separator, sometimes with a suffix such as _SOP_LEFT_UR.
        "filename": "#{date}#{time}#{recipe}#{sample}#{lot}#NA#{recipe}{lot}{sample}{suffix}.csv",
        "profile_grids": (),
        "profile_units": ()
    }
}


def normalize_tool(tool_name: str | None) -> str:
    if not tool_name:
        return "MAP608"

    normalized = tool_name.strip().upper()
    if not normalized:
        return "MAP608"

    return normalized


def get_tools() -> list[dict[str, str]]:
    return [
        {
            "id": config["tool_id"],
            "name": tool_name,
            "label": tool_name,
            "fab": config["fab"]
        }
        for tool_name, config in TOOL_CONFIGS.items()
    ]


def list_afm_files(tool_name: str | None = None) -> list[AfmMeasurementRow]:
    tool = normalize_tool(tool_name)
    return list(_listed(tool, _today()))


@lru_cache(maxsize=8)
def _listed(tool_name: str, today: date) -> tuple[AfmMeasurementRow, ...]:
    return tuple(
        {**row, **_tip_columns(row)} for row in _generate_measurements(tool_name, today)
    )


def _tip_columns(row: AfmMeasurementRow) -> dict[str, Any]:
    # The list's tip columns are the measurement's own Info and data rows,
    # summarised — read off the detail so the two can never disagree. The
    # uncached call: a whole tool's details would flush the detail cache.
    detail = get_afm_file_detail.__wrapped__(row["filename"], row["tool_name"])
    info, rows = detail["information"], detail["data"]
    width = float(info["Tip Width"])

    def mean(column: str) -> float | None:
        return round(statistics.fmean(r[column] for r in rows), 2) if rows else None

    return {
        "tip_id": info["Tip ID"],
        "tip_cassette_id": info["Tip Cassette ID"],
        "tip_port_no": info["Tip Port No"],
        "tip_slot_no": info["Tip Slot No"],
        "tip_width": None if math.isnan(width) else width,
        "last_pick_up_time": info["Last Pick Up Time"],
        "approach_count_mean": mean("Approach Count"),
        "mileage_mean": mean("Mileage"),
        "not_completed_count": (
            sum(r["State"] != "COMPLETED" for r in rows) if rows else None
        ),
        "invalid_count": (
            sum(r["State"] == "COMPLETED" and r["Valid"] is False for r in rows)
            if rows else None
        ),
    }


@lru_cache(maxsize=256)
def get_afm_file_detail(
    filename: str,
    tool_name: str | None = None
) -> dict[str, Any] | None:
    row = _find_measurement(filename, tool_name)
    if row is None:
        return None

    rng = random.Random(_seed_for("detail", row["tool_name"], row["filename"]))
    recipe = RECIPES[row["recipe_name"]]
    positions = _positions(recipe)
    # Stored order is not point order at the office (user-confirmed 2026-10-08;
    # which order it is: OFFICE-VERIFY). Its own Random, and applied after the
    # rows are drawn, so the detail stream below is left as it was.
    stored = [key for key, *_ in positions]
    random.Random(_seed_for("stored-order", row["tool_name"], row["filename"])).shuffle(stored)
    # A recipe with no data CSV has no blocks, so both tables stay empty.
    columns = recipe["columns"] or ()
    method_id = recipe.get("method_id", row["recipe_name"].split("_", 1)[-1])
    # A measurement stopped part-way leaves its later blocks with rows but no values.
    stopped_early = (
        len(recipe["methods"]) > 1
        and _seed_for("stopped", row["tool_name"], row["filename"]) % 3 == 0
    )
    excursion = _is_excursion(row)
    summary: list[dict[str, Any]] = []
    detail: list[dict[str, Any]] = []
    mileage = _tip_mileage(row)
    sample_count = _seed_for("sample-count", row["tool_name"], row["filename"]) % 47 + 1

    for method_index, method in enumerate(recipe["methods"]):
        stopped = stopped_early and method_index > 0
        bases = [_baseline(row, column, method_index) for column in columns]
        block_rows: list[dict[str, Any]] = []
        # A stopped block keeps the row it stopped on; the points it never reached
        # have no row at all. A repeat recipe goes round its points again.
        measured = positions[:1] if stopped else positions * recipe.get("repeat", 1)

        for row_no, (key, site_id, (site_x, site_y), point_no) in enumerate(measured):
            # `Site` is the row's own block: the method name of its section.
            record: dict[str, Any] = {"Site": method, "measurement_point": key}
            if site_id:
                record.update({"Site ID": site_id, "Site X": site_x, "Site Y": site_y})
            record.update({
                "Point No": point_no,
                "X (um)": round(site_x * 8000 + rng.uniform(-100, 100), 1),
                "Y (um)": round(site_y * 8000 + rng.uniform(-100, 100), 1),
                "Method ID": method_id,
                "State": (
                    "STOPPED" if stopped
                    else "FAILED" if excursion and rng.random() < 0.3
                    else rng.choice(STATE_CODES)
                ),
                "Valid": rng.random() > (0.3 if excursion else 0.08)
            })
            bowl = _BOWL_NM * (site_x ** 2 + site_y ** 2)
            for column, base in zip(columns, bases, strict=True):
                # A cell that was never measured is empty, not missing: one frame
                # holds every block, so the column is there for every row.
                record[column] = (
                    None if stopped else round(base + bowl + rng.gauss(0, _POINT_NOISE_NM), 2)
                )
                record[f"{column.removesuffix(' (nm)')}_Valid"] = (
                    None if stopped else rng.random() > 0.06
                )
            rng.randint(1, 5)  # a draw the stream once spent on Sample Count
            approach_count = rng.randint(1, 3) + (rng.randint(1, 2) if excursion else 0)
            # Mileage counts up for as long as one tip is in use and starts
            # over with the next tip (office 확인 2026-10-07).
            mileage = round(mileage + rng.uniform(2, 98) / 100, 2)
            record.update({
                "Pick Up Count": rng.randint(1, 10),
                # One value for the whole measurement (seen 1–47), except that a
                # repeat recipe's goes up by one each lap — the only thing that
                # tells the laps apart (office 확인 2026-10-07).
                "Sample Count": sample_count + row_no // len(positions),
                "Approach Count": approach_count,
                "Mileage": mileage
            })
            block_rows.append(record)

        # Still one lap after another (office 확인 2026-10-07); only the order
        # of the points inside a lap is the stored one.
        block_rows.sort(key=lambda r: (r["Sample Count"], stored.index(r["measurement_point"])))
        detail.extend(block_rows)
        if not stopped:
            summary.extend(_summary_records(method, block_rows, columns))

    # Both were seen in real files: one with no Summary, one whose Data has no table.
    oddity = _seed_for("oddity", row["tool_name"], row["filename"]) % 12
    if oddity == 0:
        summary = []
    elif oddity == 1:
        detail = []

    clean_filename = _strip_known_extension(row["filename"])

    return {
        "filename": row["filename"],
        "tool": row["tool_name"],
        "pickle_filename": f"{clean_filename}.pkl",
        "information": _information(row, rng),
        "summary": summary,
        "data": detail,
        "available_points": stored
    }


def get_profile_points(
    filename: str,
    point: str,
    tool_name: str | None = None,
    site_info: dict[str, str | int | None] | None = None
) -> list[dict[str, float | None]] | None:
    row = _find_measurement(filename, tool_name)
    if row is None or not row["has_profile"]:
        return None

    seed_parts = [
        "profile",
        row["tool_name"],
        row["filename"],
        point,
        str(site_info or {})
    ]
    rng = random.Random(_seed_for(*seed_parts))
    nx, ny, (x_unit, y_unit, z_unit) = _profile_layout(row)
    step = _SCAN_UM / (nx - 1)
    z_base = rng.uniform(80, 120)
    peak1_x = rng.uniform(25, 50)
    peak1_y = rng.uniform(0, 5)
    peak2_x = rng.uniform(0, 25)
    peak2_y = rng.uniform(0, 5)
    points: list[dict[str, float | None]] = []
    # Samples the scan has no value for: NaN in the file, null here. Drawn from their
    # own stream so they do not shift the heights. OFFICE-VERIFY: rate and pattern.
    missing = set(
        random.Random(_seed_for(*seed_parts, "missing")).sample(range(nx * ny), nx * ny // 2000)
    )

    # A 1D profile (ny == 1) sits on y = 0.
    for row_index in range(ny):
        y = row_index * step
        for col_index in range(nx):
            x = col_index * step
            wave = 10 * math.sin(x / 10) * math.cos(y / 10)
            peak1 = 5 * math.exp(-((x - peak1_x) ** 2 + (y - peak1_y) ** 2) / 100)
            peak2 = 3 * math.exp(-((x - peak2_x) ** 2 + (y - peak2_y) ** 2) / 150)
            noise = rng.gauss(0, 1)
            z = z_base + wave + peak1 + peak2 + noise

            points.append({
                "x": _lateral(x, col_index, x_unit),
                "y": _lateral(y, row_index, y_unit),
                "z": (
                    None if row_index * nx + col_index in missing
                    else round(z * _HEIGHT_PER_NM[z_unit], 5)
                )
            })

    return points


def get_profile_meta(
    filename: str,
    point: str,
    tool_name: str | None = None
) -> AfmProfileMeta | None:
    # `point` is unused here — a mock file scans every point the same way — but the
    # office reads one object per point, each with its own metadata.
    row = _find_measurement(filename, tool_name)
    if row is None or not row["has_profile"]:
        return None

    nx, ny, (x_unit, y_unit, z_unit) = _profile_layout(row)
    step = _SCAN_UM / (nx - 1)
    width = _lateral(_SCAN_UM, nx - 1, x_unit)
    height = _lateral(step * (ny - 1), ny - 1, y_unit)

    return {
        "x_unit": x_unit,
        "y_unit": y_unit,
        "z_unit": z_unit,
        "data_size": f"{nx} x {ny}",
        "surface_size": f"{width:g} x {height:g}"
    }


def get_profile_image_svg(
    filename: str,
    point: str,
    tool_name: str | None = None
) -> str | None:
    row = _find_measurement(filename, tool_name)
    if row is None:
        return None

    rng = random.Random(_seed_for("image", row["tool_name"], row["filename"], point))
    stops = [
        ("0%", "#18213a"),
        ("35%", "#136f63"),
        ("70%", "#d7a334"),
        ("100%", "#f4f0e6")
    ]
    circles = []
    for _ in range(28):
        circles.append(
            "<circle "
            f"cx=\"{rng.randint(35, 605)}\" "
            f"cy=\"{rng.randint(55, 365)}\" "
            f"r=\"{rng.randint(14, 58)}\" "
            f"fill=\"rgba(255,255,255,{rng.uniform(0.05, 0.18):.2f})\" />"
        )

    label = html.escape(f"{row['tool_name']} {row['lot_id']} {point}")
    recipe = html.escape(row["recipe_name"])
    stop_markup = "\n".join(
        f"<stop offset=\"{offset}\" stop-color=\"{color}\" />"
        for offset, color in stops
    )
    circle_markup = "\n".join(circles)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420">
  <defs>
    <linearGradient id="surface" x1="0" x2="1" y1="0" y2="1">
      {stop_markup}
    </linearGradient>
  </defs>
  <rect width="640" height="420" fill="#0f172a" />
  <rect x="24" y="24" width="592" height="328" rx="10" fill="url(#surface)" />
  {circle_markup}
  <path d="M48 300 C 155 190, 255 365, 374 214 S 520 135, 592 232" fill="none" stroke="#f8fafc" stroke-width="3" stroke-opacity="0.8" />
  <text x="36" y="385" fill="#f8fafc" font-family="Arial, sans-serif" font-size="19" font-weight="700">{label}</text>
  <text x="36" y="407" fill="#cbd5e1" font-family="Arial, sans-serif" font-size="13">{recipe}</text>
</svg>"""


def list_analysis_images(
    filename: str,
    image_type: str,
    tool_name: str | None = None,
) -> list[dict[str, str]]:
    field = IMAGE_TYPE_FIELDS.get(image_type)
    if field is None:
        return []

    row = _find_measurement(filename, tool_name)
    if row is None:
        return []

    tool = normalize_tool(tool_name)
    encoded_filename = quote(row["filename"], safe="")
    encoded_tool = quote(tool, safe="")

    images: list[dict[str, str]] = []
    names = row.get(field, [])
    for name in names:
        if _is_original(name):
            continue
        encoded_name = quote(name, safe="")
        image = {
            "name": name,
            "url": (
                f"/api/afm/files/{encoded_filename}/images/{image_type}/{encoded_name}"
                f"?tool={encoded_tool}"
            ),
        }
        # Offered only where the original is listed beside its conversion.
        if _original_of(name, names):
            image["original_url"] = (
                f"/api/afm/files/{encoded_filename}/tiff/{encoded_name}?tool={encoded_tool}"
            )
        images.append(image)
    # Not in point order at the office either (user-confirmed 2026-10-08).
    random.Random(_seed_for("stored-order", tool, row["filename"], image_type)).shuffle(images)
    return images


def get_tiff_original(
    filename: str,
    name: str,
    tool_name: str | None = None,
) -> AfmOriginalFile | None:
    # Despite the name, the original of ANY displayed image: names are unique
    # inside one measurement, so the list it sits in does not need saying.
    row = _find_measurement(filename, tool_name)
    stored = None if row is None or _is_original(name) else next(
        (found for field in IMAGE_TYPE_FIELDS.values() if (found := _original_of(name, row[field]))),
        None,
    )
    if stored is None:
        return None
    image_format = _ORIGINAL_FORMATS[stored.rsplit(".", 1)[-1]]

    # Lazy: Pillow is only needed for this one download.
    from PIL import Image

    rng = random.Random(_seed_for("tiff-original", row["tool_name"], row["filename"], name))
    fx, fy, phase = rng.uniform(0.02, 0.09), rng.uniform(0.02, 0.09), rng.uniform(0, math.tau)
    size = 256
    pixels = bytes(
        int(127.5 + 127.5 * math.sin(x * fx + phase) * math.cos(y * fy))
        for y in range(size)
        for x in range(size)
    )
    buffer = io.BytesIO()
    Image.frombytes("L", (size, size), pixels).save(buffer, format=image_format)
    return {
        "filename": stored,
        "content_type": f"image/{image_format.lower()}",
        "data": buffer.getvalue(),
    }


def get_analysis_image_svg(
    filename: str,
    image_type: str,
    name: str,
    tool_name: str | None = None,
) -> str | None:
    field = IMAGE_TYPE_FIELDS.get(image_type)
    if field is None:
        return None

    row = _find_measurement(filename, tool_name)
    if row is None:
        return None

    if name not in row.get(field, []) or _is_original(name):
        return None

    rng = random.Random(
        _seed_for("analysis-image", row["tool_name"], row["filename"], f"{image_type}:{name}")
    )
    accent = _IMAGE_TYPE_ACCENT.get(image_type, "#0f766e")
    shapes = "\n".join(
        "<circle "
        f"cx=\"{rng.randint(30, 610)}\" cy=\"{rng.randint(45, 285)}\" "
        f"r=\"{rng.randint(10, 46)}\" "
        f"fill=\"rgba(255,255,255,{rng.uniform(0.04, 0.16):.2f})\" />"
        for _ in range(18)
    )
    title = html.escape(f"{image_type.upper()} · {row['tool_name']} {row['lot_id']}")
    subtitle = html.escape(name)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
  <rect width="640" height="360" fill="#0f172a" />
  <rect x="20" y="20" width="600" height="280" rx="10" fill="{accent}" fill-opacity="0.85" />
  {shapes}
  <text x="32" y="330" fill="#f8fafc" font-family="Arial, sans-serif" font-size="18" font-weight="700">{title}</text>
  <text x="32" y="351" fill="#cbd5e1" font-family="Arial, sans-serif" font-size="12">{subtitle}</text>
</svg>"""


# ponytail: only today's window is searched, so a file older than the list
# (12 days on MAP608) answers 404 to a saved group that still names it. Derive
# the day from the file name if home use ever keeps groups that long.
@lru_cache(maxsize=8)
def _generate_measurements(tool_name: str, today: date) -> tuple[AfmMeasurementRow, ...]:
    config = TOOL_CONFIGS.get(tool_name)
    if config is None:
        return tuple()

    rows: list[AfmMeasurementRow] = []
    session_size = config.get("session_size", 1)
    repeats = config.get("repeats", 1)

    # The list ends today: each day after BASE_TIME moves the window one group
    # on, into negative indices. Everything below is a function of the index
    # alone, so a file keeps its name, lot and contents as it ages.
    group_size = session_size * repeats
    newest = (BASE_TIME.date() - today).days * group_size

    for index in range(newest, newest + config["row_count"]):
        # A day holds one group: a session of different samples (MAP608) or the
        # repeated runs of one sample (MAPC01). Elsewhere a group is a single row.
        day, member = divmod(index, group_size)
        sample_no = index // repeats
        timestamp = (
            BASE_TIME - timedelta(days=day, hours=day % 6)
            + timedelta(minutes=157 * (index % repeats))
        )
        date_code = timestamp.strftime("%y%m%d")
        time_code = timestamp.strftime("%H%M%S")
        # NA where the start time goes is not an old-file thing: 29 of 46 recent
        # files carry it (office 확인 2026-10-07), scattered among the others.
        true_start = (timestamp + timedelta(minutes=4 + 11 * member)).strftime("%H%M%S")
        start_code = "NA" if (index * 7) % 46 < 29 else true_start
        recipe_name = config["recipes"][sample_no % len(config["recipes"])]
        recipe = RECIPES[recipe_name]
        lot_prefixes = config["lot_prefixes"]
        lot_id = f"{lot_prefixes[sample_no % len(lot_prefixes)]}{_base36(sample_no + 42, 2)}"
        slot_number = f"{(sample_no % 25) + 1:02d}"
        has_data = recipe["columns"] is not None
        anchor = config["filename"].format(
            date=date_code,
            time=time_code,
            recipe=recipe_name,
            slot=slot_number,
            sample=f"{lot_id}.{slot_number}",
            lot=lot_id,
            start=start_code,
            suffix="_SOP_LEFT_UR" if index % 4 == 3 else ""
        )
        # The list names a measurement by its data CSV; only one that has none is
        # named by its info CSV. (On MAP608 / 5EAP1501 the two are one file.)
        data_filename = anchor.replace("_Info.csv", ".csv")
        filename = data_filename if has_data else anchor
        # date#time#recipe#slot#lot#measured; a MAPC01 measurement is the first four.
        unique_key = "#".join(filename.split("#")[1:5 if tool_name == "MAPC01" else 7])
        clean_filename = _strip_known_extension(data_filename)
        # A MAPC01 profile or image does not start with the list name: its fifth
        # and sixth fields differ (OFFICE-VERIFY what they hold; here, the lot).
        file_stem = (
            clean_filename.replace("#NA#NA#", f"#{lot_id}#NA#") if tool_name == "MAPC01"
            else clean_filename
        )
        keys = [key for key, *_ in _positions(recipe)]
        profile_txts = _point_files(file_stem, keys, "txt")
        webps = _point_files(file_stem, keys, "webp")
        has_profile = recipe["profile"] and bool(config["profile_grids"])
        has_image = "tiff" in recipe["images"]
        has_align = "align" in recipe["images"]
        has_tip = "tip" in recipe["images"]

        rows.append({
            "unique_key": unique_key,
            "filename": filename,
            "date": date_code,
            "formatted_date": timestamp.strftime("%Y-%m-%d"),
            "recipe_name": recipe_name,
            "lot_id": lot_id,
            # No leading zero in the column ('5', '10', '21'); the file name
            # keeps its two digits.
            "slot_number": str(int(slot_number)),
            "time": time_code,
            # When this measurement started (office 확인 2026-10-07, 8차): equal
            # to `time` on MAPC01 / 5EAP1501. On MAP608 it is the name's trailing
            # time, and where that is NA the loader takes Info's Start Time —
            # which the 13-key Info does not have, so there it is null.
            "measured_time": (
                time_code if "{start}" not in config["filename"]
                else None if start_code == "NA" and _info_is_short(tool_name, filename)
                else true_start
            ),
            # The column exists at the office and is always null.
            "measured_info": "",
            "tool_name": tool_name,
            "tool_id": config["tool_id"],
            "fab": config["fab"],
            "profile_dir_list": _file_list(
                has_profile,
                [f"profile_{name[:-4]}.parquet" for name in profile_txts]
            ),
            # Info is loaded for every measurement, so this list is never a
            # "has data" flag: without a data CSV it holds information alone.
            "data_dir_list": list(DETAIL_OBJECTS if has_data else DETAIL_OBJECTS[:1]),
            # The untouched csv/txt the objects above were loaded from.
            "raw_dir_list": (
                list(dict.fromkeys([anchor, *([data_filename] if has_data else [])]))
                + (profile_txts if has_profile else [])
            ),
            # Each Result webp, then the original TIFFs it was converted from —
            # the same list holds both (5EAP1501's were reloaded 2026-10-07).
            "tiff_dir_list": _file_list(
                has_image,
                webps + [_original_name(n) for n in webps]
            ),
            # Each kind's originals sit in its own list, in the tool's own
            # format: align .bmp, tip and capture .png (office 확인 2026-10-07, 8차).
            "align_dir_list": _file_list(
                has_align,
                # One to four per measurement, numbered, with no position key.
                _with_original(
                    [f"{file_stem}_{n}_Result.webp" for n in range(1, index % 4 + 2)], "bmp"
                )
            ),
            # Two series: a `_C_PR` per point, and one `C_Result` for the
            # measurement (office 확인 2026-10-07). The position key sits right
            # before `_C_PR` on every recipe, with or without a Site ID.
            "tip_dir_list": _file_list(
                has_tip,
                _with_original([f"{file_stem}_{key}_C_PR.webp" for key in keys], "png")
                + _with_original([f"{file_stem}_C_Result.webp"], "bmp")
            ),
            # The name ends with the position key itself. Not every point has
            # one, and some measurements have none at all (office 확인
            # 2026-10-07): here every other measurement lacks its first point's,
            # and one in seven has none. 5EAP1501 writes a plain point number
            # with three digits (`_003`), not the four its points carry.
            "capture_dir_list": _with_original(
                [
                    f"{file_stem}_{key[1:] if tool_name == '5EAP1501' and key.isdigit() else key}.webp"
                    for key in ([] if index % 7 == 6 else keys[index % 2:])
                ],
                "png",
            ),
            "has_profile": has_profile,
            "has_data": has_data,
            "has_image": has_image,
            "has_align": has_align,
            "has_tip": has_tip,
            "point_count": len(keys)
        })

    return tuple(rows)


def _find_measurement(
    filename: str,
    tool_name: str | None = None
) -> AfmMeasurementRow | None:
    clean_filename = _strip_known_extension(filename)
    tool = normalize_tool(tool_name)

    # Not list_afm_files: its tip columns are read off the detail this serves.
    for row in _generate_measurements(tool, _today()):
        if _strip_known_extension(row["filename"]) == clean_filename:
            return row

    return None


# The value model is fabricated (OFFICE-VERIFY): the real levels, drift and spread
# are unknown. It is shaped so the trend views have something to find at home.
_POINT_NOISE_NM = 0.6
_BOWL_NM = 0.25           # centre-out site pattern, per unit of site radius²
_SAMPLE_SIGMA_NM = 0.8    # one offset per sample, shared by its re-measurements
_DRIFT_PER_DAY_NM = 0.4   # bound of the slow drift a recipe's column follows
_EXCURSION_NM = 7.5
_EXCURSION_EVERY = 9      # about one measurement in nine


def _is_excursion(row: AfmMeasurementRow) -> bool:
    return _seed_for("excursion", row["tool_name"], row["filename"]) % _EXCURSION_EVERY == 0


def _baseline(row: AfmMeasurementRow, column: str, method_index: int) -> float:
    """A column's level on this measurement, before the per-point terms.

    Recipe level (shared by every lot of the recipe) + a slow drift keyed on the
    measurement's own timestamp, so a file reads the same as it ages + an offset
    per sample, so re-measurements of one sample agree + an excursion on about
    one file in nine.
    """
    recipe_rng = random.Random(_seed_for("level", row["recipe_name"], column))
    level = recipe_rng.uniform(55, 120)
    method_offset = method_index * recipe_rng.uniform(-6, 6)
    drift_per_day = recipe_rng.uniform(-_DRIFT_PER_DAY_NM, _DRIFT_PER_DAY_NM)
    measured_at = datetime.strptime(row["date"] + row["time"], "%y%m%d%H%M%S")
    days = (measured_at.replace(tzinfo=timezone.utc) - BASE_TIME).total_seconds() / 86400
    sample_rng = random.Random(
        _seed_for("sample", row["tool_name"], row["lot_id"], f"{int(row['slot_number']):02d}")
    )
    return (
        level + method_offset + drift_per_day * days
        + sample_rng.gauss(0, _SAMPLE_SIGMA_NM)
        + (_EXCURSION_NM if _is_excursion(row) else 0.0)
    )


def _summary_records(
    site: str,
    site_rows: list[dict[str, Any]],
    columns: tuple[str, ...]
) -> list[dict[str, Any]]:
    column_values: dict[str, dict[str, float]] = {}

    for column in columns:
        values = [record[column] for record in site_rows]
        column_values[column] = {
            "MEAN": statistics.fmean(values),
            "STDEV": statistics.stdev(values) if len(values) > 1 else 0.0,
            "MIN": min(values),
            "MAX": max(values),
            "RANGE": max(values) - min(values)
        }

    return [
        {
            "Site": site,
            "ITEM": item,
            **{key: round(values[item], 2) for key, values in column_values.items()}
        }
        for item in SUMMARY_ITEMS
    ]


def _signed(value: int) -> str:
    return f"{'-' if value < 0 else ''}{abs(value):03d}"


def _positions(recipe: dict[str, Any]) -> list[tuple[str, str | None, tuple[int, int], int]]:
    """(key, Site ID, (Site X, Site Y), Point No) of every measured point.

    The key is what a point's profile and image files are named after: the
    4-digit point number alone (`0001`), or on a recipe that records Site ID
    the Site ID followed by the point number within that site
    (`0004_X000_Y-002_0002`).
    """
    per_site = recipe.get("per_site", 1) if recipe["site_id"] else 1
    positions = []
    for index in range(recipe["points"]):
        site_no, point_no = divmod(index, per_site)
        site_x, site_y = SITE_LAYOUT[site_no]
        if recipe["site_id"]:
            site_id = f"{site_no + 1:04d}_X{_signed(site_x)}_Y{_signed(site_y)}"
            key = f"{site_id}_{point_no + 1:04d}"
        else:
            site_id, key = None, f"{index + 1:04d}"
        positions.append((key, site_id, (site_x, site_y), point_no + 1 if site_id else index + 1))
    return positions


def _profile_layout(row: AfmMeasurementRow) -> tuple[int, int, tuple[str, str, str]]:
    # The scan is recipe configuration like everything else, so a recipe keeps one
    # grid shape and one unit set: the tool's lists are dealt out in recipe order.
    config = TOOL_CONFIGS[row["tool_name"]]
    grids, units = config["profile_grids"], config["profile_units"]
    position = config["recipes"].index(row["recipe_name"])
    return (*grids[position % len(grids)], units[position % len(units)])


def _lateral(value_um: float, index: int, unit: str) -> float:
    # A Pixel axis counts samples; nothing in the source says how long a pixel is.
    if unit == "Pixel":
        return float(index)
    # Four decimals in um: a 16384-point line steps 0.003 um, which two would merge.
    return round(value_um * _LATERAL_PER_UM[unit], 4)


# The two Info layouts, keys in file order (user-confirmed 2026-10-06).
_INFO_KEYS_15 = (
    "Lot ID", "Recipe ID", "Carrier ID", "Sample Location", "Sample ID",
    "Data Save Location", "Start Time", "End Time", "Tip ID", "Tip Cassette ID",
    "Tip Port No", "Tip Slot No", "Last Pick Up Time", "Last Put Back Time", "Tip Width",
)
_INFO_KEYS_13 = (
    "Port No", "Carrier ID", "Slot No", "Lot ID", "Sample ID", "Recipe ID",
    "Tip ID", "Tip Cassette ID", "Tip Port No", "Tip Slot No",
    "Last Pick Up Time", "Last Put Back Time", "Tip Width",
)
# How many measurements in 8 carry the 13-key layout: 5EAP1501 is mostly 15-key,
# MAPC01 mostly 13-key, MAP608 mixed (user-confirmed 2026-10-06). The ratios
# themselves, and what decides a single file's layout, are OFFICE-VERIFY.
_INFO_13_IN_8 = {"5EAP1501": 1, "MAPC01": 8, "MAP608": 4}
# Info's Start Time / End Time as the tool writes them: `2026.10.01 00:13:58`
# (user-confirmed 2026-10-08), read as KST.
_INFO_TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


# How long one tip stays mounted. Made up (OFFICE-VERIFY).
_TIP_LIFE_DAYS = 4

# Tip ID names a tip TYPE, so the same ID sits in several cassette slots and a
# tip is told apart by (Tip ID, Tip Cassette ID, Tip Port No, Tip Slot No).
# An MCNT tip's Tip Width is re-recorded by every measurement; a fixed tip's is
# not (office 확인 2026-10-06). `DT-NCHR_CM` is a real ID (office 확인
# 2026-10-07); the MCNT names and how many types a tool carries are made up
# (OFFICE-VERIFY) — few, so one ID recurs in another slot. The last field is
# the type's width: the MCNT one centres the observed 33.96–39.11, the fixed
# one's 70 is made up.
_TIP_TYPES = (("MCNT-150", True, 36.5), ("MCNT-500", True, 36.5), ("DT-NCHR_CM", False, 70.0))


def _tip_period(row: AfmMeasurementRow) -> tuple[int, float]:
    """Which tip was mounted when `row` started, and for how many minutes."""
    started = datetime.strptime(_display_start_time(row), _INFO_TIME_FORMAT)
    period = started.toordinal() // _TIP_LIFE_DAYS
    since = started - datetime.fromordinal(period * _TIP_LIFE_DAYS)
    return period, since.total_seconds() / 60


def _tip_mileage(row: AfmMeasurementRow) -> float:
    # What the tip's counter read before this measurement. It grows with the
    # time the tip has been on (seen: 1430483 on a used tip, 3520 on the next),
    # so a new tip starts far below the last. The rate is made up.
    period, minutes = _tip_period(row)
    return _seed_for("tip-mileage", row["tool_name"], str(period)) % 4000 + round(minutes * 240, 1)


def _information(row: AfmMeasurementRow, rng: random.Random) -> dict[str, str | None]:
    start_time = _display_start_time(row)
    slot = int(row["slot_number"])
    # Its own stream, so the tip values do not re-roll the measurement values.
    tip = random.Random(_seed_for("tip", row["tool_name"], row["filename"]))
    started = datetime.strptime(start_time, _INFO_TIME_FORMAT)
    end_time = started + timedelta(seconds=tip.randint(60, 1800))
    # One tip stays on a tool for _TIP_LIFE_DAYS, so the Tip * values are drawn
    # per (tool, period) and consecutive measurements share a tip.
    period, _ = _tip_period(row)
    mounted = random.Random(_seed_for("tip-mounted", row["tool_name"], str(period)))
    tip_id, remeasured, nominal_width = mounted.choice(_TIP_TYPES)
    picked_up = datetime.fromordinal(period * _TIP_LIFE_DAYS) + timedelta(minutes=93)
    # 5EAP1501's OMCL-AC160TS records almost no width (office 확인 2026-10-07, 8차).
    unrecorded = tip_id == "DT-NCHR_CM" and row["tool_name"] == "5EAP1501"
    if unrecorded:
        tip_id, nominal_width = "OMCL-AC160TS", 7.0
    tip_cassette = f"TC{mounted.randint(10, 99)}"
    tip_port = str(mounted.randint(1, 2))
    tip_slot = str(mounted.randint(1, 16))
    # A fixed type's width is one value for every tip of it. An MCNT tip sits at
    # its own level and each measurement reads it a little differently, which
    # is taken to be measurement error, not wear (office 확인 2026-10-07: MCNT
    # spans 33.96–39.11 and moves both ways within one slot).
    seat_offset = mounted.uniform(-1.5, 1.5)
    width = nominal_width + (seat_offset + tip.uniform(-1.05, 1.05) if remeasured else 0)
    # A width the measurement did not record is the literal text 'NaN'.
    no_width = _seed_for("tip-nan", row["tool_name"], row["filename"]) % 20 < (16 if unrecorded else 1)
    tip_width = "NaN" if no_width else f"{width:.1f}"
    values = {
        "Lot ID": row["lot_id"],
        "Recipe ID": row["recipe_name"],
        # An empty Info value is null in the contract.
        "Carrier ID": None if rng.random() < 0.2 else f"CAR{rng.randint(100, 999)}",
        "Sample ID": f"{row['lot_id']}.{slot:02d}",
        # The wafer's real slot; the list's slot_number is read from here.
        "Sample Location": f"Port 1 Slot {slot}",
        "Start Time": start_time,
        # Both belong to the tip, not the measurement: every measurement a tip
        # makes carries the same pair, and a new pick-up time is a re-pick
        # (office 확인 2026-10-07, 8차).
        "Last Pick Up Time": None if rng.random() < 0.3 else picked_up.strftime("%Y-%m-%d %H:%M:%S"),
        "Last Put Back Time": (
            None if rng.random() < 0.3
            else (picked_up - timedelta(minutes=7)).strftime("%Y-%m-%d %H:%M:%S")
        ),
        # Written only once the measurement has finished, with its own date, so
        # a run past midnight needs no guessing (seen: 22:32:28 → 00:11:13).
        "End Time": end_time.strftime(_INFO_TIME_FORMAT),
        # Everything below is a made-up value shape (OFFICE-VERIFY).
        # A long path with no spaces (user-confirmed 2026-10-06: it does not fit
        # a 300px column on one line). The folder layout itself is made up.
        "Data Save Location": (
            f"D:\\AFM_DATA\\{row['tool_name']}\\Automation\\Result"
            f"\\{start_time[:4]}\\{start_time[5:7]}\\{start_time[8:10]}"
            f"\\{row['recipe_name']}\\{row['lot_id']}"
            f"\\{row['lot_id']}.{slot:02d}_{start_time[11:].replace(':', '')}"
        ),
        "Port No": str(tip.randint(1, 4)),
        "Slot No": str(slot),
        "Tip ID": tip_id,
        "Tip Cassette ID": tip_cassette,
        "Tip Port No": tip_port,
        "Tip Slot No": tip_slot,
        "Tip Width": tip_width,
    }
    short = _info_is_short(row["tool_name"], row["filename"])
    info = {key: values[key] for key in (_INFO_KEYS_13 if short else _INFO_KEYS_15)}
    # Some MAP608 measurements have no End Time at all (user-confirmed
    # 2026-10-08) and get no duration. Tying it to the NA start field, and
    # leaving the key out instead of null, are guesses (OFFICE-VERIFY).
    if row["tool_name"] == "MAP608" and row["filename"].split("#")[6] == "NA":
        info.pop("End Time", None)
    return info


def _info_is_short(tool_name: str, filename: str) -> bool:
    return _seed_for("info-keys", tool_name, filename) % 8 < _INFO_13_IN_8[tool_name]


def _display_start_time(row: AfmMeasurementRow) -> str:
    # The measurement's own start; the leading time only where the list has none.
    raw_time = (row["measured_time"] or row["time"]).ljust(6, "0")
    return (
        f"{row['formatted_date'].replace('-', '.')} "
        f"{raw_time[:2]}:{raw_time[2:4]}:{raw_time[4:6]}"
    )


def _strip_known_extension(filename: str) -> str:
    if filename.endswith(".csv") or filename.endswith(".pkl"):
        return filename[:-4]
    return filename


def _file_list(has_files: bool, files: list[str]) -> list[str]:
    # An empty list is how the office says "no files" — there is no sentinel.
    return files if has_files else []


def _original_name(webp_name: str) -> str:
    # OFFICE-VERIFY: the original is assumed to carry the webp's name with a
    # TIFF extension.
    return f"{webp_name.rsplit('.', 1)[0]}.tiff"


# Extension of a stored original → the Pillow format the mock fabricates it in.
_ORIGINAL_FORMATS = {"tiff": "TIFF", "bmp": "BMP", "png": "PNG"}


def _original_of(webp_name: str, names: list[str]) -> str | None:
    # The webp's own name with another extension (office 확인 2026-10-07).
    stem = webp_name.rsplit(".", 1)[0]
    return next(
        (name for name in names if _is_original(name) and name.rsplit(".", 1)[0] == stem), None
    )


def _is_original(name: str) -> bool:
    # Whatever is not the webp conversion: .tiff for Result, .bmp / .png elsewhere.
    return not name.lower().endswith(".webp")


def _with_original(webps: list[str], extension: str) -> list[str]:
    # An original is its webp's name with its own extension (office 확인 2026-10-07, 9차).
    return webps + [f"{name.rsplit('.', 1)[0]}.{extension}" for name in webps]


def _point_files(clean_filename: str, keys: list[str], extension: str) -> list[str]:
    return [f"{clean_filename}_{key}_Height.{extension}" for key in keys]


def _seed_for(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _base36(value: int, width: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    # Only the last `width` digits are kept, so wrap first: the result is the
    # same for any non-negative value, and a negative one (a day after
    # BASE_TIME) no longer divides forever.
    value %= len(alphabet) ** width
    if value == 0:
        encoded = "0"
    else:
        chars = []
        next_value = value
        while next_value:
            next_value, remainder = divmod(next_value, len(alphabet))
            chars.append(alphabet[remainder])
        encoded = "".join(reversed(chars))

    return encoded.rjust(width, "0")[-width:]
