# bm_pm 9시간 anchor 버그 — 확인과 oc-review

- 일자: 2026-08-20
- 스킬: `oc-review` (변형 — 아래 "축 변형" 참조)
- 모델: `glm-5.3` (variant `high`, tier `heavy`), 두 축 병렬 실행 (81초 / 83초)
- 발단: 2026-08-20 `oc-discuss` 에서 드러난 bm_pm 의 기존 버그 확인 요청

## 축 변형

`oc-review` 는 고정점 대비 diff 를 전제하지만 이 건은 변경분이 아니라 **기존
코드**이므로 고정점이 없습니다. 또한 `.scratch/` 에 hardware 스펙이 없어
Spec 축은 스킬 규칙대로 **생략**했습니다(스펙 없이 돌리면 diff 에서 스펙을
지어내 그 diff 를 채점하는 셈이 됩니다). 대신 두 축을 이렇게 두었습니다.

| 축 | 원래 | 이번 |
| --- | --- | --- |
| 1 | Standards (diff) | Standards (기존 코드 대상) |
| 2 | Spec | 독립 검증 — 버그 주장을 반증하도록 지시 |

## 버그의 의미

세 구간을 거치며 시각의 정체성이 한 번 소실되어, 조회 창의 상한이 데이터 자신의
시계보다 9시간 뒤처지는 문제입니다.

| 단계 | 위치 | 값 (사무실 벽시계 KST 2026-08-20 05:38 기준) |
| --- | --- | --- |
| 1 | `HardwareView.vue:66` `toISOString()` | `2026-08-19T20:38:00.000Z` (UTC) |
| 2 | `useHardwareApi.ts:71` | 그대로 `end` 쿼리 파라미터로 전달 |
| 3 | `hardware/routes.py:34` `replace("Z","")` | naive `2026-08-19 20:38` — **tz 정체성 소실** |
| 4 | `routes.py:55` → `data.py` → 어댑터 | 변환 없이 `anchor` 로 도달 |
| 5 | `bm_pm/office_example.py:197` `gte/lte` | 이 naive 를 KST 벽시계로 간주해 질의 |

저장된 값이 offset 없는 KST 벽시계라면, 질의 상한만 9시간 과거입니다. 결과적으로
**최근 약 9시간의 BM/PM 이 창 밖으로 밀려 조회되지 않습니다.**

핵심은 `replace("Z", "")` 가 오프셋을 **변환하지 않고 삭제**한다는 점입니다.
`Z` 는 "이 값은 UTC" 라는 선언인데, 그것만 지우면 UTC 숫자가 KST 숫자인 척하게
됩니다. 저장소 전체에서 `Z` 를 다루는 7곳 중 6곳은 `replace("Z", "+00:00")` 로
오프셋을 보존하고, 오프셋을 버리는 곳은 `hardware/routes.py:34` 하나뿐입니다.

## Standards 축 — 모델의 지적

> The route feeds a **UTC** wall clock into a system whose documented
> wall-clock convention is **KST**. So: not a defensible local choice — the
> repo's own docs flag it as a standing hazard. Caveat for precision: no
> document mandates `replace("Z", "+00:00")` as a blanket rule; the 6-vs-1
> pattern is de facto, not written. The documented violation is the KST/UTC
> wall-clock mismatch, and note the correct fix per the contract is
> convert-to-KST-then-strip, not merely `+00:00` (an aware-UTC anchor compared
> against KST-as-UTC indices slides the same 9 hours).

또한 "start/end 를 받는 유일한 라우트" 라는 표현이 넓다고 교정했습니다 —
`_analytics_routes.py:55` 와 `device_statistics/routes.py:85` 도 `start_date`/
`end_date` 를 받지만 `date.fromisoformat` 으로 **날짜**를 파싱하므로 `Z` 를 실을
수 없습니다. 정확히는 "쿼리 파라미터로 full ISO datetime 을 파싱하는 유일한
라우트" 입니다.

naive/aware 경계를 어디 둘지에 대한 성문 규칙은 이 저장소에 **없습니다**.
모델은 규칙을 지어내지 말라는 지시에 따라 그렇게 보고했습니다.

## 검증 축 — 판정 PARTLY CONFIRMED

STEP 1~4 는 전부 성립하고 중간 정규화도 없음을 모델이 직접 추적해 확인했습니다
(`data.py` 는 순수 디스패치, normalizers 는 행·카드 형태만 손댐). 다만:

> **STEP 5 — MECHANICS HOLD, PREMISE DOESN'T.** […] the file's own docstring
> (lines 23-26) says: *"UNVERIFIED until run at the office: whether these two
> indices store offset-less KST wall clock…"*

> **(a)** If the indices store UTC-with-Z, the naive UTC anchor compares
> like-for-like against UTC storage — **no 9h omission at all**; the symptom
> would instead be displayed timestamps sitting 9h behind KST wall clock.

즉 **버그의 존재는 확정이 아니라 조건부**입니다. 인덱스가 offset 없는 KST 를
저장할 때만 "9시간 누락" 이고, UTC 를 저장한다면 누락은 없고 대신 **표시되는
시각이 9시간 어긋나** 보입니다. 어느 쪽이든 결함이지만 증상과 수정이 다릅니다.

판정을 가르는 증거는 하나입니다 — `fab_inform_notes` 의 `down_dt` 또는
`tool_start_tm` 원본 저장값 하나에 `Z`/offset 접미사가 붙어 있는지. 이 모듈의
`__main__` diagnose 블록이 바로 그것을 출력하도록 이미 만들어져 있습니다.

## 영향 범위 — bm_pm 만의 문제가 아닙니다

> Not bm_pm-special. fdc:147, sharpness:265-266, reso_center:232, bsm:222 all
> compare the same naive route datetimes against presumed-KST storage.

직접 확인했습니다. 원인은 `routes.py:34` 한 줄이고 hardware 탭의 시간창을 쓰는
하위 서비스 전부가 같은 경로를 탑니다. mdc/sce 는 MinIO 의 날짜 단위 폴더를 써서
영향이 가장 적습니다.

탭별 증상이 다릅니다.

| 탭 | 창 | 증상 |
| --- | --- | --- |
| bm_pm 과거 | `anchor - 180d .. anchor` | 최근 약 9시간 누락, 카드도 9시간 지연 |
| bm_pm 미래 | `anchor .. anchor + 90d` | 창이 9시간 일찍 시작 — 이미 지난 계획이 예정으로 표시 |
| fdc/bsm/reso_center/sharpness | 라우트의 30일 창 | 창 오른쪽 끝이 9시간 잘림 |

`bm_pm` 은 라우트의 `start` 를 무시하고 자체 `PAST_DAYS=180` / `FUTURE_DAYS=90`
을 씁니다(직접 확인). 따라서 프론트의 30일 기본창은 bm_pm 에 무관합니다.

## Claude 가 틀렸던 것

- **수정 방향을 잘못 함의했습니다.** 앞 턴에서 다른 파서들이 쓰는
  `replace("Z", "+00:00")` 를 정상 패턴으로 제시했는데, 이 경로에 그대로 적용하면
  **똑같이 9시간 어긋납니다.** aware UTC anchor 를 KST-as-UTC 인덱스와 비교하기
  때문입니다. 올바른 수정은 KST 로 변환한 뒤 tz 를 떼는 것입니다.
- **버그를 확정으로 말했습니다.** 실제로는 미검증 전제에 조건부입니다.
- **bm_pm 국소 문제로 좁혔습니다.** hardware 시간창을 쓰는 전 서비스가 대상입니다.
- 앞선 재현 스크립트에서 과거 창을 90일로 라벨했으나 실제 `PAST_DAYS` 는 180 입니다
  (격차 계산 자체는 창 길이와 무관하므로 9시간 결론은 영향 없음).

## 남는 것

수정은 아직 하지 않았습니다. 전제가 갈리면 수정도 갈리므로, 사무실에서
`python -m back_dev_home.ebeam.hardware.providers.bm_pm.office` 의 diagnose 로
원본 저장값의 접미사를 먼저 확인하는 것이 순서입니다.
