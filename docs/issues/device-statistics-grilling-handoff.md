# Device Statistics 페이지 IA — Grilling 세션 핸드오프

## 세션 목적

`device-statistics` 페이지의 UI/UX 재설계를 위한 grill-with-docs 세션. 사용자(daeyoung1385@gmail.com)가 “UI/UX 관점에서 해법을 못 찾고 있다”는 문제를 들고 들어왔고, doc의 5개 user job 중 **(A) 비대한 recipe_id 발굴**과 **(D) Recipe 내부 파라미터 드릴다운**이 가장 큰 통점으로 좁혀졌습니다.

## 입력 자료

- `docs/issues/device-statistics.txt` — 사용자가 직접 적은 페이지 목적과 user jobs
- `docs/device-statistics-plan.md` — 현재 페이지 구현 상태와 파일 매핑
- `docs/api-contracts/cdsem-device-statistics.yaml` — API/schema contract
- `front-dev-home/app/pages/ebeam/cd-sem/device-statistics/{index.vue, comparison.vue}` — 현재 구현 (각 936 / 547 줄)

## 합의된 결정 사항

세션 중 잠긴 모든 결정은 [`CONTEXT.md`](../../CONTEXT.md)에 도메인 용어 형태로 박혀 있습니다. 핵심 요약:

- **Lot이 primary axis** — 팀·담당자 할당이 lot 단위이기 때문 (조직적 제약, 되돌릴 수 없음)
- **두 audience (담당자 + 임원) 가 같은 URL을 공유** — evidence forwarding 때문에 hide-by-tab 불가
- **Cascade**: 신호등 → recipe table (process walkthrough) → U1 인라인 행 확장 (slideover 폐기)
- **Rule shape**: per-recipe cap (`para_16_max`, `para_13_max`, `para_9_max`, `para_5_max`) + 매트릭스는 R3는 `(stage × bucket)`, M-fab은 `bucket`, Sample은 1 universal cell
- **Lot health**: `violation_ratio = 위반 recipe / 총 recipe`, 10/20 threshold, severity는 cell-level σ 시각 표현
- **Rule editor**: 별도 `/admin/measurement-rules` 페이지, 관리자(daeyoung) 전용. seed는 `back_dev_home/ebeam/cdsem/device_statistics/rules.py`
- **Device Stage**: R3에만 존재, backend가 `ctn_desc`에서 PV/EV/Pool 추출
- **Page IA**: 1-page (comparison.vue → index.vue로 흡수), cart layer는 last-session state로만 유지 (UI 없음), preset은 명시적 저장 묶음으로 살림
- **Zone ② 시각화**: V2 horizontal stacked bar + 행 색이 신호등
- **Trend zone (TZ-2chart)**: T-A health trajectory line + zone 배경 색 / T-B composition shift stacked area + avail_recipe 보조 line + cap 점선
- **Single focus 기본** (F1), multi-lot focus(F2)는 향후 U4 pinning으로 검토

## 직전 멈춘 지점 — 후보 2 (Bucket 라디오 위치/동작) 의 push-back 대기

다음 4개 push-back 중 사용자 답을 기다리는 중:

1. Bucket을 top sticky bar로 끌어올리는 것 OK?
2. 전환 시 focus 유지 정책 — lot focus 유지, recipe row는 부재 시 conditional collapse
3. 결과 hint chip (“3 red, 5 yellow”) 가치 vs 시각적 노이즈
4. Sample chip 시각 구분 vs popover에만 맡기기

세부 제안 본문은 직전 어시스턴트 메시지에 있음 — 핵심은 “bucket = 페이지-global lens, top sticky bar에 위치, 전환 시 reactive recompute + 가능한 focus 보존”.

## 남은 분기 (사용자가 “1→2→3 순으로 진행” 약속)

| 후보 | 상태 |
| --- | --- |
| 1. Trend chart 의 새 자리 | **합의 완료** (TZ-2chart, recipe-history endpoint 신설 동의) |
| 2. Bucket 라디오 위치와 동작 | **push-back 대기 중** ⬅ 여기서 멈춤 |
| 3. 신호등 카드 자체의 구체 시각 (V2 row tint vs stripe, avail_recipe 위치, stage chip 등 metadata) | 아직 시작 안 함 |

## 알려진 open 항목 (지연된 결정)

- Severity weighting 의 식 (σ 기준이라는 *방향*은 합의, 구체 식은 미정)
- F2 multi-lot focus — 사용자도 고민 중, U4 (recipe pinning) 후보로 향후 검토
- 사용자→관리자 룰 변경 요청 채널 — 첫 버전 없음 (구두/Slack 처리)
- Server-side user tracking 부재 — 현재 cart layer가 그 자리를 임시로 채움

## ADR 후보 (grilling 종료 시 생성 권장)

세 결정은 hard-to-reverse + surprising-without-context + real-trade-off 셋 다 충족하므로 `docs/adr/` 신설 후 ADR로 박아두는 게 좋습니다:

1. **Lot이 primary axis (조직적 ownership boundary 때문)** — α 경로(recipe-primary) 가 제거된 이유 기록
2. **두 audience 동거 정책 (담당자/임원 같은 URL)** — hide-by-tab/IA 분리를 안 한 이유 기록
3. **Rule editor 관리자 전용 (W1)** — single source of truth가 cross-team coordination 매체이기 때문

`docs/adr/`는 아직 없음 — 첫 ADR이 만들면서 생기는 폴더입니다.

## 다음 세션에 추천하는 진행 방식

다음 세션 시작 시 `/grill-with-docs` 다시 호출 + 이 문서를 인자로 첨부:

```
/grill-with-docs @docs/issues/device-statistics-grilling-handoff.md 후보 2(bucket 라디오) push-back 4개부터 이어서
```

- 후보 2 push-back → 후보 3 (신호등 카드 시각) → 마무리 ADR 작성 순으로 흘러가면 grilling이 닫힙니다.
- ADR 작성 단계에선 `grill-with-docs` skill의 “Offer ADRs sparingly” 지침에 따라 위 세 가지를 후보로 제시.
- CONTEXT.md는 이미 충분히 채워졌으니 추가 용어가 등장할 때만 손대면 됨.

## 비고

- 사용자는 단답형으로 빠르게 답하는 스타일 (예: “TZ-2chart 고고”). 긴 추천 패키지를 던지고 친절한 push-back 질문 1~4개로 묶어서 받는 패턴이 잘 통합니다.
- 코드 변경은 아직 한 줄도 안 했음. grilling이 닫히면 별도 plan 문서 (`docs/device-statistics-redesign-plan.md` 가칭) 작성 권장.
