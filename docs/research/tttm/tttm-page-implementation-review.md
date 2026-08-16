# TTTM 페이지 구현 가능 항목 검토

## 2026-08-16, CD-SEM TTTM 기법 조사(`cdsem-tttm-evolution-2009-2026.md`) 기반

## 1. 배경

CD-SEM Tool-to-Tool Matching(TTTM) 기법의 발전을 정리한 연구 문서
(`cdsem-tttm-evolution-2009-2026.md`, 동일 폴더)를 기준으로, 현재 저장소의
TTTM 페이지에 적용 가능한 항목을 정리합니다. 검토 시점의 코드 상태를
기준으로 하며, 구현 우선순위는 3절에서 다룹니다.

## 2. 기존 자산과 문서 개념의 대응 관계

> **2026-08-16 정정.** 이 절의 초판은 "`tttm` 전용 페이지는 존재하지 않는다"고
> 적었으나 **사실이 아니었습니다.** 작성 시점에 해당 작업이 미병합 워크트리
> (`work/skew-lab-research`)에 있어 main 에서 보이지 않았을 뿐입니다. 그
> 브랜치는 2026-08-16 에 main 으로 병합되었고(93c088e5), 기능 이름은 `skew` 에서
> `tttm` 으로 이미 바뀌어 있었습니다. 아래 경로는 병합 후 기준으로 고쳤습니다.
>
> 같은 이유로 이 문서는 **선행 검토
> [`docs/research/2026-08-16-skew-tttm-feasibility.md`](../2026-08-16-skew-tttm-feasibility.md)를
> 참조하지 못했습니다.** 그 문서는 Kawada 2009 전문 대조를 마쳤고 착수 순서에
> 대해 이 문서와 다른 결론에 도달해 있으므로, 두 문서를 함께 읽어야 합니다.
> 두 결론의 조정 결과는 4절에 있습니다.

TTTM 페이지는 존재하며, 디자인 재작업 중이라 네비게이션의 **실험실** 그룹에서
들어가게 되어 있습니다.

관련 파일은 다음과 같습니다.

- `front-dev-home/app/pages/ebeam/cd-sem/[fab]/tttm.vue`: 라우트 래퍼
- `front-dev-home/app/components/ebeam/TttmView.vue`: 메인 뷰
- `front-dev-home/app/utils/tttmGrouping.ts`: 클라이언트 측 TTTM 엔진
  (Bron–Kerbosch 최대 클리크, 인접 행렬 AND-fold, tolerance 기반 판정)
- `front-dev-home/app/utils/fleetMap.ts`: 장비 그룹 배치도 엔진(고전 MDS)
- `back_dev_home/ebeam/tttm/`: 백엔드 feature (`GET /api/cdsem/tttm/check`)

문서의 핵심 개념과 현재 페이지의 대응 관계는 아래와 같습니다.

| 문서 개념 | 현재 페이지 | 격차 |
| --- | --- | --- |
| Pairwise TTTM (≤ tolerance) | PairMatrix 셀별 행렬 | 이미 구현됨 |
| Fleet consensus (golden tool 없음) | FleetStatus consensus_deviation | 평균 기반 편차만 있음 |
| Tool-to-tool distance matrix | FleetMap 2D 배치도 | 2026-08-16 구현됨 |
| 조건별 matching (Layer/Pattern) | 셀 = beam condition × axis × CD band | Layer/Recipe 차원 없음 |
| Time-series monitoring | TrendChart + epoch 마커 | drift/variance 탐지 없음 |

## 3. 구현 가능 항목

### A. 지금 구현 가능 (목 데이터·계약 확장만으로, 프론트 중심)

1. **3중 matching metric + composite score** — **분류 오류였습니다(2026-08-16
   정정).** `fleet_today`를 mean bias `D_μ`, variance ratio
   `D_σ = |log(σ_i/σ_fleet)|`, Wasserstein `D_W`로 확장하고 가중 합 `S_i`로
   랭킹한다는 방향 자체는 유효합니다. "평균은 같으나 variation 증가"인 tool을
   현재 잡지 못한다는 지적도 그대로 유효합니다. 그러나 **이것은 프론트 작업이
   아닙니다.** `contracts.py` 를 확인한 결과 계약에는 스칼라만 있습니다 —
   `SkewMatrixBlock` 은 `list[list[float | None]]`, `ConsensusDeviation` 은
   부호 있는 실수 하나, `TrendPoint` 는 `{eqp_id, date, skew}` 입니다. σ·n·
   분위수·분포가 **어디에도 없으므로** `D_σ` 와 `D_W` 는 클라이언트에서 계산할
   수 없습니다. 목 데이터·계약 확장이 아니라 **office 어댑터가 분포 통계를 새로
   계산해 실어야 하는 작업**이므로 아래 B 로 옮깁니다.
2. **MDS fleet map** — **2026-08-16 구현 완료**(`utils/fleetMap.ts`,
   `EbeamTttmFleetMap`). 응답에는 있으나 미사용이던 `fleet_today.matrix` 를
   tool×tool 거리행렬로 삼아 2D 배치도를 그립니다. 백엔드 변경이 없다는 판단은
   맞았습니다. 계층적 클러스터링은 아직 없습니다 — 5대 규모에서는 배치도만으로
   군집이 눈에 보여 값어치가 낮고, 사무실 규모(10~12대)에서 다시 판단합니다.

   구현하면서 드러난 것 두 가지를 남깁니다. 둘 다 계약을 읽어서는 나오지 않고
   **화면을 완성하려 해야 마주치는** 종류입니다.

   - 계약은 `values` 어디에나 null 을 허용하고, 실제로 셀
     `bc2-X-50-100-e7` 의 `predicted_skew_matrix` 는 EQP05 행이 전부 null
     입니다. 거리가 하나도 없는 장비는 **옳은 좌표가 존재하지 않으므로**
     원점에 지어내지 않고 배치에서 빼고 `detached` 로 보고합니다. 어느 셀이
     어느 장비에 대해 TTTM 가능한가는 선행 검토 6장 2번(연결 성분) 그
     자체입니다.
   - 허용오차는 **쌍(pairwise) 스펙**이므로 장비 그룹 전체에 대한 평균과
     비교하면 안 됩니다. 초판 구현에서 평균 Score 를 허용오차와 비교했더니
     목 데이터 5대가 **전부** 이상으로 표시되었습니다. 최근접 장비까지의
     거리와 비교해야 맞습니다.
3. **ABBA 불확실성 표시**: self-ABBA ±0.05 nm를 tolerance 슬라이더의
   불확실성 밴드로 표시합니다. 셀별 표본수 표시 및 n < 50 경고를 함께 둡니다.

   **정정(2026-08-16).** 초판은 "슬라이더 최솟값 0.01 nm가 물리적으로 무의미한
   영역"이라는 점을 문제로 들었으나, 실제 문제는 최솟값이 아니라 **상한**입니다.
   Kawada 2009 전문은 matching target 을 **±0.25 nm** 로 명시하는데 노브 상한이
   `0.20` 이라 **현업의 실제 스펙을 표현할 수 없습니다.** 게다가 fixture 의 최대
   셀 스큐가 정확히 `0.200` 이어서, 노브를 끝까지 올리면 모든 쌍이 통과합니다 —
   즉 이 컨트롤은 "불합격인 장비 그룹"을 표현하지 못합니다. 상한을 최소 0.30
   nm 로 올리고 기본값을 0.25(매칭 목표)로 두며, 0.05 는 노브 값이 아니라
   눈금 위의 **바닥선**으로 그려야 합니다. 선행 검토 4장과 같은 결론입니다.
4. **Carryover 주석**: "관측 T2T 차이 ≠ 고유 tool 차이(Δ + (d_B−d_A)/2
   포함 가능)"를 matrix 각주와 `production_corroboration` 노트에
   반영합니다.
5. **미사용 데이터 활용**: epoch 마커의 label 필드(현재는 'PM'/'BM'으로
   하드코딩), 셀별 `mdc_epoch`, recipe 선택 UI(API는 `recipe_id` 파라미터를
   이미 지원)를 활성화합니다.

### B. 중기 구현 (백엔드 계산 추가)

0. **분포 통계를 계약에 싣기** (A-1 에서 이관). `D_σ`·`D_W` 의 전제이며, 이것이
   없으면 3중 metric 은 어느 쪽에서도 계산되지 않습니다. 셀·장비별로 최소한
   σ 와 n 이, Wasserstein 까지 가려면 분위수 또는 히스토그램이 필요합니다.
   `mock.py` 와 `office_example.py` 를 **함께** 고쳐야 합니다.
6. **DBSCAN fleet consensus**: 최대 클러스터를 정상 합의로 정의하고 이탈
   tool을 탐지합니다. 순수 Python 구현이 가능하며 `contracts.py`와
   provider를 확장하는 형태입니다.
7. **Mixed-effect / interaction RCA**: `Tool × (beam·axis·CD band)`
   interaction 분석으로 "특정 조건에서만 틀어지는 tool"을 global offset과
   구분합니다. Layer 차원은 계약 확장이 필요합니다.
8. **S_i(t) 연속 모니터링**: 트렌드 차트에 sudden shift / gradual drift /
   variance 증가 탐지 플래그를 추가합니다. epoch 마커와 연계하면 "PM 후
   degradation" 스토리텔링이 강화됩니다.

### C. 장기·오피스 의존 (데이터 확보 전 불가)

9. **Recipe/AMP parameter 최적화** (Baram 2024): 파라미터와 matching
   residual의 관계를 학습하는 모델입니다. MDC 이력은 있으나 AMP 파라미터
   데이터가 없습니다.
10. **Contour matching** (2021~2023): 이미지 수준 비교입니다. `msr_image`
    인프라는 있으나 별도 작업입니다.
11. **Virtual Metrology** (2026): 예측 tier(`대역 외삽`)가 이미 원형이지만,
    wafer-level VM은 모델과 데이터부터 확보해야 합니다.

## 4. 권장 순서

문서의 4-layer 구성(Ground Truth → Fleet Matching → Optimization →
Monitoring)이 페이지 섹션 재편의 뼈대로 자연스럽게 맞습니다.

**초판 순서는 "A-1 + A-2 를 함께 먼저"였고, 이는 두 가지 이유로 틀렸습니다.**
첫째, A-1 은 프론트 작업이 아니어서 "가성비 최고"가 성립하지 않습니다(3절 A-1).
둘째, 선행 검토는 측정 순서 인식(ABBA/self-ABBA 판별)과 e-beam carryover 를
그보다 앞에 두는데, 이 문서는 그 논점을 보지 못했습니다. SEM 은 측정이 시료를
바꾸므로(레지스트 shrink·카본 오염) 순서 보정 없이 계산한 분포 거리는 tool
차이가 아니라 **측정 순서 편향**을 재고 있을 수 있습니다.

다만 A-2 를 함께 미룰 이유는 없습니다. A-2 는 서버가 이미 단언한 값을 **표시할
뿐** 숨은 양을 복원하지 않으므로(추정기가 아니라 렌더러), 참값을 아는 목이
없어도 검증됩니다 — 실제로 `fleetMap.test.ts` 가 순수 함수로 전부 덮습니다.
반면 `D_σ`·`D_W` 나 상태공간 필터는 추정기이므로 생성형 목이 먼저입니다.
이 구분(**추정기인가 렌더러인가**)이 두 문서의 순서 차이를 조정하는 기준입니다.

조정된 순서는 다음과 같습니다.

1. ~~A-2 (fleet map)~~ **완료** (2026-08-16).
2. A-3 의 tolerance 상한 정정 — 지금 컨트롤이 매칭 목표를 표현하지 못합니다.
3. 선행 검토 7.7 의 1~3번: 측정 순서 인식, 추정기 3종 + 게이트, recipe 적합성
   판정. 나머지 전부의 전제입니다.
4. A-4 ~ A-5, 그리고 선행 검토 7.4 의 스큐보아 렌즈 확장.
5. B-0 (분포 통계를 계약에) → B-6 ~ B-8. B-0 없이는 3중 metric 이 성립하지
   않습니다.
6. C 항목은 오피스 데이터 확보 후 별도 기획.

## 참고

- 선행 검토(순서·통계 설계): [`docs/research/2026-08-16-skew-tttm-feasibility.md`](../2026-08-16-skew-tttm-feasibility.md)
- 이 문서의 A-1·A-2 권고를 두고 벌인 외부 모델 논쟁 기록:
  [`docs/opencode/2026-08-16-tttm-page-start-order-discuss.md`](../../opencode/2026-08-16-tttm-page-start-order-discuss.md)
- 기법 원본 정리: `cdsem-tttm-evolution-2009-2026.md` (동일 폴더)
- 2009 원 논문: `docs/research/Methodologies_for_evaluating_CD-matching_of_CD-SEM.pdf`
  (git 에 넣지 않습니다 — SPIE 유료 논문이고 이 저장소는 공개입니다)
- 백엔드 계약: `back_dev_home/ebeam/tttm/contracts.py`, `MIGRATION.md`
