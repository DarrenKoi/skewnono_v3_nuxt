# 계측 포인트 샘플링은 데이터 양에 따라 두 모드로 나뉜 추천 엔진입니다

[[계측-포인트-샘플링]] 페이지는 CDU recipe의 측정 포인트를 줄이는 **per-recipe 추천 도구**입니다. 실제 데이터가 "site 위치는 고정이나 recipe당 wafer는 적음(<10장)"이라는 제약을 가지므로, 단일 알고리즘이 아니라 **데이터 양에 따라 엔지니어가 나눠 점검하는 2-모드 엔진**으로 갑니다. 기본은 **공간모델 모드**(소수 wafer의 공간 상관을 지오통계로 모델링하고 동일 공정 step·장비로 풀링), 데이터가 충분히 쌓인 recipe는 **이력상관 모드**(`site × wafer` 상관·주성분으로 중복 site 제거)로 교차 점검합니다. 두 모드의 채택 기준은 동일하게 [[계측-정합성]] — **leave-one-wafer-out 교차검증의 worst-case uniformity gap이 tolerance 이내**일 때만 축소 추천을 채택합니다.

v1은 **CDU에 앵커링**하고 MTX는 페이지 IA에 자리만 둡니다 — CDU(매끄러운 공간 장)와 MTX(의도된 gradient)는 통계 구조가 정반대라 추천 엔진이 사실상 분리되기 때문입니다.

## 고려된 대안

- **이력상관(상관·PCA) 단일 방법** — 문서가 1차로 기대한 "과거 데이터 상관" 접근. `site × wafer` 행렬에서 중복 site를 제거합니다. wafer가 site 수보다 충분히 많아야(보통 수십~수백) 상관행렬이 안정적인데, recipe당 wafer가 <10장이면 rank-deficient라 과적합 — "우연히 닮은" site를 redundant로 오판합니다. 데이터가 풍부한 recipe에 한해 *보조 모드*로만 채택했습니다.
- **family/phase로 풀링** — [[계측-룰]]을 가르는 축(product family + phase)을 그대로 풀링 축으로 사용. 룰·UI와 축이 일치해 일관되나, wafer CD 공간 signature는 **제품 설계가 아니라 공정 장비·스텝**(챔버 성향, 척 온도, 가스 흐름)에서 나옵니다. family로 풀링하면 물리적으로 다른 signature의 wafer를 섞을 위험이 있어, **공정 step([[oper-id]]/layer)·유사 장비를 1차 풀링 축**으로, family/phase는 보조 필터로 둡니다.
- **기하학적 표준 레이아웃만** — 학습 없이 반경×방위 stratified(예: 5링×8각) 표준 축소 레이아웃을 제안. 견고·단순하나 실제 공정 signature를 무시합니다. v0 baseline·fallback으로는 유효하나 "정합성 유지" 근거를 데이터로 제시하지 못해 핵심 방법론에서는 제외했습니다.
- **평균 CD 일치를 acceptance로** — 더 간단하지만 산포를 놓쳐 CDU(=uniformity)의 목적 자체를 놓칩니다. acceptance metric은 **uniformity 지표(range 또는 3σ)**여야 합니다.
- **in-sample 재구성 오차로 검증** — 모델을 만든 그 wafer로 축소·full을 비교. 구현은 최소지만 낙관·과적합이라 새 wafer 성능을 과대평가합니다. 희소 데이터를 알뜰하게 쓰는 **leave-one-wafer-out**을 택했습니다.

## 결과로 따라오는 제약

- **합성 mock으로는 방법론을 검증할 수 없습니다.** Phase-1(홈·오프라인)은 페이지 + API 계약 + mock 출력까지만 구축하고, 실제 지오통계 구현은 office에서 `data.py` 스왑으로 교체합니다. "추천이 옳다"는 증명은 office에서 실데이터로 별도 수행해야 하며, Phase-1이 증명하는 것은 **계약·UX**뿐입니다.
- **엔진 출력 계약**이 두 모드를 모두 표현해야 합니다 — per-site droppability, 추천 축소 set, LOWO gap 분포 + worst-case, 사용 모드, 풀링 group. 이 계약이 mock과 office 구현의 swap surface입니다.
- 풀링 축이 룰 축(family/phase)과 다르므로, 데이터를 **공정 step·장비로 묶을 수 있어야** 합니다([[meas-hist]]의 `eqp_id`·`class_name`·oper 정보로 가능). 묶이지 않으면 공간모델 모드의 borrow strength가 약해집니다.
- "정합성 **향상**"은 redundant 제거가 아니라 **불량 포인트**(에지·노치 근처, align fail, artifact) 제거로 uniformity 추정이 견고해지는 경우라, 엔진은 "중복 제거 + 불량 포인트 식별" 두 역할을 가집니다 — v1 포함 여부는 미정.
- uniformity를 **range vs 3σ** 중 무엇으로 볼지, **tolerance를 누가** 정하는지(admin 룰 객체 vs 엔지니어 knob), **모드 자동선택 임계치**(몇 장부터 이력상관 모드 기본)는 후속 결정으로 남습니다.

## 되돌리기 어려운 이유

방법론은 **엔진 출력 계약과 backend 데이터 접근 형태**를 결정합니다. 계약이 한 번 mock·office 양쪽에 자리 잡고 Nuxt 페이지가 그 형태(2-모드 토글, wafer map, LOWO gap)에 맞춰지면, 단일-모드로 되돌리거나 풀링 축을 family로 바꾸는 일은 계약·UI·backend를 함께 갈아엎는 비용을 부릅니다. 특히 풀링 축이 시스템의 다른 축(family/phase)과 다르다는 점은 맥락 없이는 의아하게 보이므로 — "왜 엔진이 둘인가", "왜 룰과 달리 step·장비로 묶나" — 그 이유를 여기 명시해 둡니다.
