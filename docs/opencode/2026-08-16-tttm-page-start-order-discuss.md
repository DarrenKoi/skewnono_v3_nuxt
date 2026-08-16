# TTTM 페이지 착수 순서 — opencode oc-discuss 기록

- 실행일: 2026-08-16
- 스킬: oc-discuss
- 모델: opencode-go/glm-5.3 (tier=heavy)
- 대상: `docs/research/tttm/tttm-page-implementation-review.md` 의 A-1·A-2 우선
  권고 대 `work/skew-lab-research`(93c088e5) 의 선행 검토
  `docs/research/2026-08-16-skew-tttm-feasibility.md`
- 소요: 15s(무응답) + 51s + 45s · 세션: `ses_ff7b8e5bfffeQ4ogR1V5qfzlSR`

## 논쟁의 구도

새 리뷰 문서는 "A-1 3중 매칭 metric(D_μ/D_σ/D_W) + A-2 MDS 장비 그룹 맵을 목
데이터·프론트만으로 지금 먼저" 를 가성비 1순위로 권고합니다. 워크트리의 선행
검토는 정반대로 "스큐보아 렌즈 → 야간 rollup → 필터 → 페이지" 이며, 그 앞에
측정 순서 인식(ABBA/self-ABBA)과 e-beam carryover 재현을 둡니다.

Claude 의 최초 입장은 **A-1·A-2 를 묶어서 기각** 하는 것이었습니다. 근거는
(1) 정적 fixture 에는 참값이 없어 "틀릴 수 없는 차트"만 나온다, (2) SEM 은
측정이 시료를 바꾸므로 순서 보정 없는 D_W 는 순서 편향을 잰다, (3) 새 문서가
선행 검토와 Kawada 2009 전문 대조를 참조하지 않았다 였습니다.

## 모델이 말한 것

### 1라운드

> **Verdict: you're right about A-1, wrong to bundle A-2 into the rejection — and your reason (1) is the weakest link in your own case.**
>
> **Objection 1 (worst): the "unfalsifiable fixture" argument proves too much.** The prior doc's priorities — skewvoir lens, nightly rollup, state-space filter — all run on the *same* 129-line static fixture with its three hand-written trend points per tool. A state-space filter on three authored points is exactly as unrecoverable as an MDS map. If "no ground truth ⇒ defer" is the sequencing rule, it doesn't justify the prior doc's order; it annihilates the license for *all* Phase 1 work. The argument's real force is "replace the fixture with a generative mock," which is orthogonal to whether A-2 ships first. Cost of keeping it: your position rests on a principle that, applied consistently, also condemns the alternative you're defending.
>
> **Objection 2: A-2 is not an estimator, so "cannot be wrong" is false for it.** MDS renders `fleet_today.matrix` — already summarized, already on the wire. There is no hidden parameter to fail to recover. And it *is* checkable: classical MDS on a 5×5 symmetric matrix is a pure function, so stress bounds, null-cell handling, and permutation invariance fit the repo's Node test convention exactly. Your reason (1) targets A-1's metrics; it never touches A-2. Cost: rejecting A-2 discards the only artifact in this debate that is verifiable today.
>
> **Objection 3: order bias (reason 2) is inherited, not introduced.** Whatever order confound lives in the skew matrices contaminates the lens, rollup, and filter identically. A-2 adds zero confound — and a fleet map where EQP05 sits alone is precisely the screen that makes an order artifact *visible enough to trigger the ABBA question*. Cost: rejecting A-2 delays the Kawada agenda it claims to protect.
>
> **Where you're right — A-1.** I verified the wire: `fleet_today` carries a skew matrix and signed consensus deviations only. No per-tool distributions exist, so D_sigma and D_W are *uncomputable client-side* — "frontend-only" is false, and A-1 requires a contract change, not a chart. Your tolerance catch also stands: `tolerance_range.max = 0.20` while fixture skews already hit 0.20; a ±0.25 nm target is inexpressible.
>
> **Strongest objection considered and rejected:** "any mock-data screen breeds false confidence and ships dead UI at Phase 2." Rejected — per AGENTS.md, mock-shape stability *is* the phase architecture; that risk prices into every page ever built here and cannot rank A-2 below a lens.

### 2라운드

> **Objection 3: dropping half, pressing half.**
>
> Dropped: the observation-time reading. You're right that the map read at home shows what the author drew; EQP05's isolation is decoration, not discovery. Dead.
>
> Pressed: you quietly substituted "ready when real data arrives" for the steelman's actual claim — "without a screen, nobody has a reason to go ask." Motivation, not readiness. And that survives, at construction time. Concrete case: cell 3's predicted matrix carries an all-null EQP05 row. The MDS widget cannot be *finished* without deciding — exclude EQP05 from that cell's map? Render it detached? Mix direct and predicted tiers or keep them separate views? Those decisions are not render trivia; "which cells are TTTM-able for which tools" is prior-doc section 6 territory. The screen earns its keep through what completing it forces you to confront, not through what observing it reveals. Your narrower framing drops exactly the half that justifies building it *now* rather than after the office visit.
>
> Your failure case also proves too much — the move you used on me. The shipped trend view already displays EQP05 sliding -0.04 → -0.13 across three authored points, and FleetStatus already renders consensus_deviation bars calling EQP05 -0.13. If "someone reads mock as real drift" were a live risk, it shipped weeks ago; A-2 adds zero exposure beyond every existing Phase 1 view. The risk prices into the app's whole mock architecture or into none of it.
>
> **No new objection.** Strongest candidate considered: at Phase 2 the *contract itself* bakes in estimators — `fleet_today.matrix` values will be office-adapter outputs, so "renderer" describes the client, not the system. Rejected because it reorders nothing you've proposed; it's a Phase 2 contract-review note, not a sequencing argument.

## 합의된 것

- **판정 기준은 "참값 유무" 가 아니라 "추정기인가 렌더러인가" 입니다.** 숨은 양을
  복원한다고 주장하는 산출물은 알려진 참값을 요구하고, 이미 단언된 양을 표시할
  뿐인 산출물은 요구하지 않습니다.
- **A-1 과 A-2 는 분리해야 합니다.** 새 리뷰 문서가 둘을 한 묶음으로 제시한 것이
  혼선의 원인이었습니다.
- **A-2(MDS 맵)는 지금 진행해도 좋습니다.** 5×5 대칭 행렬 위의 고전 MDS 는 순수
  함수이며, `app/utils/*.test.ts` 의 `node --test` 관례로 stress 상한·null 셀
  처리·순열 불변성을 검증할 수 있습니다.
- **A-1(D_σ·D_W)의 "프론트 중심" 분류는 사실이 아닙니다.** 검증 결과 계약에는
  스칼라만 있습니다 — `SkewMatrixBlock` 은 `list[list[float|None]]`,
  `ConsensusDeviation` 은 부호 있는 실수 하나, `TrendPoint` 는
  `{eqp_id,date,skew}` 입니다. σ·n·분위수·분포가 **어디에도 없습니다.** 따라서
  D_σ·D_W 는 계약 확장이 아니라 office 어댑터가 분포 통계를 새로 계산해 실어야
  하는 작업입니다.
- **`tolerance_range` 상한이 실제로 막혀 있습니다.** fixture 의 최대 셀 스큐가
  정확히 `0.200` 이고 `tolerance_range.max` 도 `0.200` 이므로, 노브를 끝까지
  올리면 모든 쌍이 통과합니다. 매칭 목표 ±0.25 nm 는 표현 자체가 불가능합니다.

  > **뒤집혔습니다 (user-confirmed 2026-08-16).** 이 합의는 Claude 와 모델이
  > 둘 다 Kawada 2009 의 ±0.25 nm 를 현재 스펙으로 취급해서 나온 것입니다.
  > 사용자가 **상한 0.20 이 타당하다**고 판정했고, 2009년 값은 그 시점 노드의
  > 목표치이지 현재 팹의 스펙이 아닙니다. **양쪽 모델이 같은 전제를 공유해
  > 같이 틀린 사례**이므로, 합의가 곧 검증이 아니라는 기록으로 남깁니다.
  > 남는 사실은 목 데이터 쪽 하나뿐입니다 — fixture 의 최대 스큐가 상한과
  > 같아서 데모에서 불합격 상태를 볼 수 없다는 점(`mock.py` 사안).
- **순서 편향은 A-2 가 새로 들여오는 것이 아닙니다.** 렌즈·rollup·필터가 똑같이
  물려받는 교란이므로 A-2 를 기각할 근거가 되지 못합니다.

## 이견으로 남은 것

없습니다. 2라운드에서 모델이 Objection 3 의 절반을 스스로 철회하고 나머지
절반에 대해 Claude 가 승복하여 수렴했습니다. 3라운드는 돌리지 않았습니다.

## Claude 가 틀렸던 것

1. **근거 (1)이 지나치게 증명했습니다.** "참값이 없으면 미룬다" 를 규칙으로
   세우면 선행 검토가 옹호하는 렌즈·rollup·필터도 같은 fixture 위에서 도는
   이상 함께 무너집니다. 즉 그 규칙은 순서를 정당화하는 것이 아니라 Phase 1
   작업 전부의 면허를 없앱니다. 부수적으로, 선행 검토 5.3 의 상태공간 필터도
   같은 기준에서 막힌다는 결론을 받아들였습니다.
2. **A-2 를 A-1 과 함께 기각한 것이 틀렸습니다.** A-2 는 추정기가 아니라
   렌더러이므로 복원에 실패할 숨은 파라미터가 없고, 오늘 당장 검증 가능한
   유일한 산출물입니다.
3. **A-2 의 가치를 "실데이터가 오면 준비되어 있다" 로 좁힌 것이 틀렸습니다.**
   모델의 지적대로 이는 steelman 의 주장("화면이 없으면 물어볼 동기가 없다")을
   조용히 바꿔치기한 것입니다. 진짜 값어치는 **완성하려면 마주칠 수밖에 없는
   질문** 에 있습니다. 검증한 구체 사례: 3번 셀 `bc2-X-50-100-e7` 의
   `predicted_skew_matrix` 는 EQP05 행이 전부 `None` 입니다. 거리가 없는 점은
   임베딩할 수 없으므로 MDS 위젯은 "그 셀에서 EQP05 를 뺄 것인가 · 분리해
   그릴 것인가 · direct 와 predicted tier 를 섞을 것인가" 를 정하지 않고는
   완성되지 않습니다. 이는 렌더링 잡무가 아니라 선행 검토 6장 2번(연결 성분)
   그 자체입니다.
4. **목 데이터 오독 위험 논거도 지나치게 증명했습니다.** 이미 배포된 trend 뷰가
   EQP05 를 -0.04 → -0.13 으로 그리고 있고 `FleetStatus` 도 같은 -0.13 막대를
   렌더합니다. 그 위험은 앱의 목 아키텍처 전체에 매겨지거나 아무 데도 매겨지지
   않으며, A-2 만 따로 끌어내릴 수는 없습니다.

## 후속

- A-2(장비 그룹 배치도)는 `5f0c2f70` 로 구현되었고, `b677e201`(정리 패스)과
  `130786ec`(라벨러 통합)이 뒤따랐습니다.
- 새 리뷰 문서 `docs/research/tttm/tttm-page-implementation-review.md` 는
  `ba741e39` 에서 정정했습니다(A-1 의 "프론트 중심" 분류 등).
- **tolerance 상한은 0.20 유지로 종결되었습니다**(user-confirmed 2026-08-16).
  위 합의 항목의 인용 블록 참고. 세 문서(이 기록·구현 검토·선행 검토) 모두
  이에 맞춰 갱신했으므로 재론 대상이 아닙니다.
- 모델 신뢰성 메모: 1라운드 첫 호출이 도구 사용 후 본문 없이 예고문만 반환했고,
  같은 세션에서 재촉하자 정상 응답했습니다. `models.md` 에 누적할 만한 패턴입니다.
