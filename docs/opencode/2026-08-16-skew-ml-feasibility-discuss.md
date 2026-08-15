# 스큐(TTTM) 페이지 ML 설계 — opencode oc-discuss 기록

- 실행일: 2026-08-16
- 스킬: oc-discuss (2라운드, 상한 3라운드에서 조기 수렴)
- 모델: opencode-go/glm-5.3 (tier=heavy)
- 대상: `back_dev_home/ebeam/skew/` 를 실제 데이터로 되살릴 때의 통계 설계
- 소요: 87s + 48s · Session: `ses_ff84519e1ffep0T9zOuteE5Z5c`

## 논쟁에 부친 입장

1. 데이터는 이제 충분합니다 — MinIO `dict_pkl`(점별 `cd_value`), OpenSearch
   `meas_hist_*`(실행 색인), Redis `mdc_setting` + MinIO 이력, BM/PM 이벤트가 모두
   연결되어 있습니다.
2. "ML" 은 잘못된 프레임입니다. "일관된 스큐인가 랜덤인가"는 분산 분해와 안정성
   질문이지 예측·분류 과제가 아닙니다. 라벨이 없으므로 지도학습 분류기는 애초에
   불가능합니다.
3. 구속 조건은 통계가 아니라 **보존기간과 비용**입니다(`dict_pkl` 61일 삭제,
   `meas_hist` 60일). 따라서 야간 rollup 잡이 먼저입니다.
4. 진짜 과학적 위험은 **교란**입니다. 같은 웨이퍼를 2대 이상에서 측정한 자료가
   없으면 관측 차이 = 장비 스큐 + lot 변동입니다.
5. 정적 fixture 를 **생성형(generative) mock** 으로 교체하는 것이 집에서 할 수 있는
   최고가치 작업입니다. 참값을 알아야 추정기를 검증할 수 있습니다.
6. (사용자 추가 질문) recipe 를 더 많이 참조하면 스큐가 더 정밀해지는가 — 예,
   다만 이유는 평균화가 아니라 **식별가능성**이며, 순진한 pooling 은 해롭습니다.

## 모델이 말한 것 (원문 인용)

라운드 1, 가장 강한 반론부터:

> **1. (3) contradicts (4): the rollup grain destroys the lot random effect.** A
> `(tool, recipe, parameter, cell, day)` median/MAD/n summary has no lot/run key.
> The mixed model — your own identifiability argument — needs lot effects, and
> after the 61-day purge you can never refit from raw. (…) This is the one that
> ships wrong and can't be repaired retroactively.

> **2. (6a) is overstated: a recipe is not one CD.** Pickles carry multiple
> parameters per run at different nominal CDs — within-recipe spread partially
> identifies offset vs gain *on the same lot*, the only clean path. Conversely,
> your cross-recipe `b*CD` design points compare **different wafers**: each recipe
> runs its own lots, so the gain estimate eats full lot variance.

> **3. (6c) partially pooling to an exchangeable `gamma_{tool,recipe}` shrinks to
> the wrong center.** Recipes aren't exchangeable — gamma should be structured
> (function of CD/beam), i.e. the gain term from (6a) belongs *in the mean*, not
> the variance.

> **4. (6d) understated.** Production recipe→tool assignment is near
> block-diagonal; most pairs never co-occur on a shared recipe.

> **5. (6e) magnitude is right (DE = 1+(m−1)ρ; m≈100–300, ρ≈0.8 → 10–25×) — but
> your ICC pseudo-replicates too.** Daily offsets are drift-autocorrelated; within
> a 60-day single-MDC-epoch window a monotonically drifting tool shows high
> σ²_tool, low σ²_tool×time — "consistent," wrong in a month.

> **6. Better estimator exists and is cheaper than your plan.** A local-level
> Kalman (random-walk + obs noise, ~30 lines of numpy, no statsmodels) gives
> σ²_proc/(σ²_proc+σ²_obs) — *literally* the consistent-vs-random ratio — plus
> one-step-ahead intervals, which is the actual product question. Gating it behind
> "only if autocorrelation appears" is backwards.

> **7. (6g) confirmed against the repo, and worse than you said:** the slider
> **maxes at 0.2 nm**, so a real ~0.5 nm tolerance is inexpressible — the frozen
> contract forces churn.

> **8. Your falsifier #2 partially fires now:** pickles carry only mag/vac/pixel —
> no HR/Valley, no Deg, no X/Y axis.

라운드 2, 반박에 대한 재반격:

> recipe_idp.txt verified — point 8 rebuttal stands, dropped.

> **6. Two-stage filter: sound in the direct tier, misspecified in the predicted
> tier.** Stage-1 cluster SE captures within-run sampling noise only. In the
> predicted tier each "offset" is tool offset + **lot difference**, and the
> between-lot variance component is not in that SE. Feed the too-small R to the
> filter and it books lot scatter as process noise (…) Fix: inflate R by the
> between-lot component (…) or co-estimate a **single scalar inflation** on R by
> profile likelihood.

> **4. Concrete failure cases, two.** (a) *Time-resolved disconnection.* (…) A~B
> share recipe 1 in week 1, B~C share recipe 2 in week 4, B takes a PM or MDC
> change between: the pooled graph is connected, the epoch-resolved graph is not,
> and the A–C estimate is biased by B's jump — attributed to the pair, reported
> "consistent." (…) build the graph per epoch. (b) *The grouper consumes point
> estimates only.* `buildAdjacency` (skewGrouping.ts:50) tests `v <= tolerance`;
> confidence and tier never touch adjacency (…) the contract's `confidence` field
> is cosmetic.

> **MDC question: de-apply for estimation, re-apply for display.** The factor is a
> *known setting, not an estimate* — de-applying adds zero variance and moves a
> known step out of the noise (…) a residual jump remaining at a de-applied
> boundary is *signal* — the factor record is wrong.

## 합의된 것

- ML(지도학습 분류기)이 아니라 **분산 분해 + 상태공간 모델**이 맞는 도구입니다.
  라벨이 없으므로 분류기는 선택지가 아닙니다.
- rollup 을 먼저 만들되 **grain 은 실행(run/MSR) 단위**여야 합니다. 일 단위 요약은
  lot 효과를 복구 불가능하게 지웁니다.
- CD·beam 은 **평균 구조(mean)** 에 들어가고, 구조화되지 않은 recipe 랜덤효과는
  그 잔차만 담습니다.
- 국소선형추세(local linear trend) 필터를 써야 합니다. 국소수준(local level)만
  쓰면 꾸준히 드리프트하는 장비가 "일관됨"으로 잘못 보고됩니다.
- 유사반복(pseudo-replication) 배수는 10~25배 규모이며, 유효 표본은 점 개수가
  아니라 실행/lot 개수입니다.
- MDC 는 **추정 단계에서 역적용(de-apply)** 하고 표시 단계에서 다시 적용합니다.
  MDC 는 추정값이 아니라 알려진 설정이므로 분산을 늘리지 않고, epoch 경계를 넘어
  비교 가능하게 만듭니다. 역적용 후에도 남는 점프는 잡음이 아니라 신호입니다.
- 정합성 그래프는 **epoch 단위**로 만들어야 하며, pooled 그래프의 연결성은
  가짜 안심을 줍니다.
- `tolerance_range` (0.01~0.20 nm) 는 fixture 에서 지어낸 값이며 넓혀야 합니다.

## 이견으로 남은 것

- **교차-recipe 브리징의 유효성.** 저는 인접 그래프가 완전할 필요 없이 연결되기만
  하면 A–C 가 B 를 경유해 추정 가능하고, 이것이 계약의 `predicted` tier 가 뜻하는
  바라고 봅니다. 모델은 그 전제가 epoch 단위로는 자주 깨진다고 봅니다. 두 입장 모두
  옳을 수 있으며, **가를 증거는 사무실 데이터 하나뿐입니다** — 실제 recipe→장비
  배정 행렬을 epoch 단위로 뽑아 연결 성분 개수를 세면 끝납니다. 집에서는 판정
  불가입니다.

## 내가 틀린 것

- **rollup grain 을 일(day) 단위로 잡은 것.** 되돌릴 수 없는 종류의 실수였습니다.
  61일 뒤 원본이 사라지면 lot 랜덤효과를 영원히 복구할 수 없고, 그때는 이미 몇 달치
  잘못된 이력이 쌓인 뒤입니다. grain 을 실행 단위로 바꿉니다.
- **"recipe 를 많이 모으면 CD-gain 이 식별된다"는 주장.** recipe 하나가 CD 대역
  하나라는 전제가 틀렸습니다. 한 실행 안에 여러 parameter 가 서로 다른 공칭 CD 로
  들어 있으므로, CD-gain 은 **같은 웨이퍼 안의 대비**로 잡는 것이 깨끗하고, 교차
  recipe 대비는 lot 분산을 통째로 먹습니다. 교차 recipe 의 진짜 값어치는 CD 가
  아니라 **beam/optics 조건의 레버리지**입니다.
- **Kalman 을 "자기상관이 보이면 그때" 로 미룬 것.** 순서가 거꾸로였습니다.
  σ²_proc/(σ²_proc+σ²_obs) 자체가 사용자가 물은 "일관 대 랜덤" 비율이고,
  one-step-ahead 구간이 곧 "다음 run 을 기대할 수 있는가" 입니다. ICC 는 기술통계,
  필터가 답입니다.
- **`confidence` 가 실제로 쓰인다고 가정한 것.** `skewGrouping.ts:50` 의
  `buildAdjacency` 는 점추정만 임계값과 비교하며, `confidence` 와 `tier` 는 그룹
  라벨에만 붙습니다. 2-hop 브리지 추정치가 직접 측정과 똑같은 자격으로 clique 에
  들어갑니다. 불확실성을 인접 판정에 반영하려면 **계약 변경이 필요하고, 저는 그
  비용을 계산에 넣지 않았습니다.**
- **`predicted` tier 의 관측분산.** 2단계 필터에서 stage-1 클러스터 SE 를 그대로
  R 로 넘기면 lot 산포가 process noise 로 기입되어 드리프트가 과대평가됩니다.
  lot 간 nugget 만큼 R 을 부풀리거나 profile likelihood 로 스칼라 하나를
  공동추정해야 합니다.
