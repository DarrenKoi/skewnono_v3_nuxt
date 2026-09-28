# FDC fab 단위 장비 순위 뷰 (TemperatureEChuck · LaserPower x1/y1)

Status: needs-triage
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
