# Lot 을 모든 분석 surface 의 primary axis 로 둡니다

Device statistics 페이지의 외피 축은 [[lot]] 입니다 — 최적화 *대상* 은 recipe 임에도 불구하고. 팹 운영 조직이 팀·담당자 할당을 lot 단위로 하기 때문에, 분석의 단위가 조직적 ownership boundary 와 정렬돼야 evidence 가 forward 가능하고 "누가 책임지는 lot 인가" 가 한 눈에 잡힙니다.

## 고려된 대안

- **Recipe-primary** — recipe 단위로 정렬·비교하고, lot 은 grouping 정도로 두는 방식. 최적화 use case 와 직결되어 자연스러워 보이나, 한 recipe 의 개선 책임을 *누구에게* 묻을지가 모호해지고, 임원 audience 의 "어느 팀이 정체됐는가" 질문에 답하지 못함.
- **Hybrid (recipe-primary, lot-secondary)** — 검색·정렬은 recipe 단위, drill-up 으로 lot summary. 두 축을 모두 first-class 로 가지려다 둘 다 흐려지고, sticky bar / URL state / cascade 방향이 모두 양립해야 해 IA 복잡도가 큼.

## 결과로 따라오는 제약

- Zone ② (신호등) 의 행 단위는 **항상 lot**. recipe-level summary 는 행 펼침 (U1) 에서만 노출.
- 정렬 축의 default 는 `violation_ratio` (lot 단위 roll-up). 사용자 정렬 옵션도 lot 단위 메트릭만 1급.
- T-A trend zone 의 추이 대상도 focused **lot** 의 health trajectory — recipe trajectory 는 drill-down 단계에서만.
- 추후 multi-focus 가 필요해지면 (F2 / U4 pinning) 그것도 lot 단위로 설계 — recipe pinning 은 의미는 있어도 외피 축을 깨지 않는 한에서.

## 되돌리기 어려운 이유

페이지의 모든 zone (sticky lens / 신호등 카드 / 매트릭스 / 트렌드 / cascade 방향 / URL state) 이 lot 을 입력으로 가정해 짜여 있어, 외피 축을 바꾸려면 사실상 전 zone 재설계입니다. 따라서 이 결정은 "처음에 골랐고, 계속 유효한지 매번 검증" 이 아니라 "한 번 박고 가는" 종류의 결정입니다.
