# FDC fab 단위 장비 순위 뷰 (TemperatureEChuck · LaserPower x1/y1)

Status: resolved
작성: 2026-09-28

## 배경

사무실 실측(`docs/datatables/hitachi/hardware_fdc_sce_characterization.md`,
office 확인 2026-09-28) 결과, 두 신호는 장비 간 차이가 장비 내 noise 보다 훨씬
큽니다.

- TemperatureEChuck: 장비 간 편차가 장비 내 noise 의 15배입니다. 사무실 LLM 은
  "fab 단위 ranking/heatmap 을 만들라" 고 권고했습니다.
- LaserPower: fleet 비교는 x1/y1 에서만 의미가 있습니다.

현재 FDC 화면은 모두 장비 1대 단위입니다.

## 왜 바로 만들지 않았는가

같은 변경(2026-09-28)에서 나머지 권고는 모두 반영했지만, 이 뷰는 설계 결정이
먼저 필요합니다.

- `values` 는 위치 기반 문자열 배열이고 dynamic mapping 이라 `text` + `.keyword`
  입니다. keyword doc value 는 정렬된 집합이라 위치 정보가 사라지므로, OpenSearch
  집계만으로는 "장비별 온도 평균" 을 낼 수 없습니다.
- 원문을 끌어오면 fab 하나에 장비 수십 대 × 30일 최대 16.5k 건이라, 화면 요청
  한 번에 처리할 양이 아닙니다.

그래서 후보는 둘입니다.

1. `backend/_scheduler/` 에 주기 작업을 두어 장비별 일평균을 미리 계산해 Redis 에
   저장하고, 화면은 그것만 읽는다. 선례는 `redis_jobs.py` 입니다.
2. 적재 쪽(`ops_index_mgmt/network_fdc_cdsem.py`)에서 숫자 field 를 따로 적재해
   집계가 가능하게 한다. 사무실 적재 코드를 바꿔야 합니다.

## 정할 것

- 1안과 2안 중 어느 쪽인가.
- 보여 줄 모양: 장비 × 날짜 heatmap 인가, fab 중앙값 대비 편차 순위표인가.
- LaserPower x1/y1 을 같은 뷰에 둘 것인가.

## 결정 (2026-09-28)

2안의 변형으로 정했습니다. 적재 시점에 values 는 그대로 두고 typed side-field 를
함께 씁니다 (`ops_index_mgmt/network_fdc_cdsem.side_fields`, `iter_bulk_actions` 에서
적용). field 와 타입은 `docs/datatables/hitachi/hardware_network_fdc_cdsem.txt` 의
`typed side-field` 절에 있습니다. fleet 화면은 이제 집계 한 번으로 그립니다.

- TemperatureEChuck: `terms eqp_id.keyword` × `date_histogram(1d)` × `avg temp_c`.
- LaserPower: 같은 모양으로 `avg laser_x1` / `avg laser_y1`.
- Contactpin: `terms eqp_id.keyword` × `filter values.keyword=NonConduction` 비율,
  `avg first4_spread`, counter 증가율 (`max counter - min counter`).

남은 것:

- 사무실 FDC 적재 task 가 `iter_bulk_actions` 를 쓰는지 확인하고, 아니면 호출을 추가.
- 과거 문서 backfill 여부 (없으면 fleet 화면은 적재 시작일부터 채워집니다).
- 읽는 쪽: hardware 에 fleet service/adapter (mock + office_example) 와 화면.

## 구현 (2026-09-28)

사무실이 field 이름을 확정해 회신했습니다 (temp_pos/temp_c, laser_x1/laser_y1,
spm_channel/spm_judgment, pin_channel/pin_no/pin_judgment/pin_spread/pin_counter,
dynamic mapping 유지). 그 이름으로 `fdc-fleet` service 를 만들었습니다.

- backend: `providers/fdc/fleet.py` (집계 body + 정규화), `build_fdc_fleet` (office 는
  집계 1회, mock 은 같은 응답을 흉내).
- frontend: FDC 탭의 `장비 | fab 전체` 전환. heatmap, laser 순위, Contactpin 판정 비율,
  margin 분포, counter 증가율.

남은 것: backfill (없으면 배포 후 약 30일에 걸쳐 채워짐).

## 사무실 1차 검증 (2026-09-28)

- 철자는 `pin_judgment` / `spm_judgment` 입니다. 코드를 모두 그 이름으로 바꿨습니다.
- writer 는 사무실 scheduler 저장소에 있고 아직 배포 전입니다 (side-field 문서 0건).
  배포 후 다음 6시간 주기부터 채워집니다.
- 집계 body dry run: 27ms, 빈 field 는 빈 결과로 처리됩니다.
- 중복 제거 (cardinality) 는 확인됐고, SPM 숫자는 집계하지 않습니다.
- V0.3-V4 는 배포 2-3일 뒤 `hardware_fdc_fleet_verification.md` 로 다시 돌립니다.
