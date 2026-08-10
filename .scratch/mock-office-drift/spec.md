# mock↔office 파생값 드리프트 — 남은 판단 대기 건

Status: 09건 중 8건 완료 · 05 는 사무실 확인 대기
작성: 2026-08-10

## 배경

`msr_file` 의 `ZeroDivisionError`(office 에서만 발생, 커밋 `99fc3344`) 를
고치면서 그 원인이 개별 버그가 아니라 **구조적 계열**임이 드러났습니다.

각 feature 의 `providers/mock.py` 와 `providers/office_example.py` 는 같은 spec
카탈로그 위에서 **같은 파생값을 각자 손으로 구현**합니다. 한쪽에 가드나 규칙이
추가돼도 다른 쪽으로 전파되지 않고, mock 이 그 입력값을 만들어 내지 못하면 집
테스트는 전부 통과합니다. 그래서 이 계열은 "테스트가 초록인 채로" 사무실에서만
터지거나 조용히 다른 답을 냅니다.

31개 mock/office_example 쌍을 전수 대조했습니다 (`chat`·`afm`·`skew` 제외 —
파킹/보류). 약 21건이 나왔고, **어느 쪽이 옳은지 자명한 6건은 이미 고쳐
푸시했습니다** (커밋 `efaa4378`). 이 디렉터리는 **판단이 필요해 남긴 것들**입니다.

## 이미 처리된 것 (참고)

| 대상 | 처리 |
| --- | --- |
| `ebeam/_office_meas_hist` | 날짜 bound 를 `iso_date_or_none` 으로 통과 — `filter_clauses` 8개 호출 지점의 500 제거 |
| `recipe_tat`, `fail_issue` | `extended_bounds` 를 공유 `histogram_bounds` 로 |
| `hardware`/sharpness | `_validate` 가 `SEM_Cond_No` 를 실제로 int 로 강제 |
| `sem_list` | 문자열 6필드를 `_text_or_blank` 로 — 리터럴 `"nan"` 차단 |
| `lateral_recipe` | 버전 문서 없이 측정 이력만 있어도 보유로 판정 |
| `meas_hist`, `device_statistics` (mock) | 공백 검색어 / 빈 fab 판정을 office 와 일치 |

`msr_file` 의 `drift_sigma` 는 `FdcSpec.drift_sigma()` 로 단일화했습니다
(커밋 `2ecc5fbf`) — 복제 자체를 없애는 쪽이 이 계열의 근본 처방입니다.

## 남은 건 — 판단 대기

번호는 `issues/NN-*.md` 와 같습니다.

| NN | 대상 | 무엇이 갈리는가 | 성격 |
| --- | --- | --- | --- |
| 01 | `device_statistics` | ~~자기모순 + 우선순위~~ **완료** — M계열 우선으로 통일 | done |
| 02 | `recipe_tat`, `fail_issue` | ~~`prod_catg_cd` vs `tech_nm`~~ **완료** — M계열 우선(`tech_nm`) | done |
| 03 | `fail_issue` | ~~`avg_fail_ratio` 분모~~ **완료** — 전체 행으로 나눔(mock 이 옳음) | done |
| 04 | `recipe_tat`, `fail_issue` | ~~`total_executions` 규약~~ **완료** — 실행 수와 평균 분모를 분리 | done |
| 05 | `msr_file` | `health` 두 공식 — **보류(OFFICE-VERIFY)**, 눈금 차이를 양쪽 코드에 명시 | deferred |
| 06 | `storage` | ~~고아 IP 행~~ **완료** — 잡음으로 확정, mock 도 버림 | done |
| 07 | `msr_file` | ~~`mp_image_*` 분리~~ **완료** — 한 목록에서 파생 + 불일치 경고 | done |
| 08 | 여러 곳 | ~~표시상 차이 묶음~~ **완료** — 3건 수정, 1건 오탐, 2건 의도적 유지 | done |
| 09 | 여러 곳 | ~~자명한 기계적 수정 묶음~~ **완료** — 7건 수정, 2건 오탐 | done |

## 검증 수준에 관한 정직한 표기

전수 대조는 서브에이전트가 수행했고, 저는 그중 일부만 원본에서 직접
확인했습니다. 각 이슈에 **확인함** / **에이전트 보고(미확인)** 을 표기했습니다.
미확인 항목은 착수 전에 원본 확인이 먼저입니다.

## 왜 개별 수정보다 공유 헬퍼가 먼저인가

04(카운팅 규약)와 01·02(카탈로그 조인 우선순위)는 **각각 여러 feature 에 복제돼**
있습니다. feature 별로 고치면 같은 판단이 3벌 남아 다시 갈라집니다. 결정이 나면
`ebeam/_analytics.py`(mock 쪽)와 `ebeam/_office_meas_hist.py`(office 쪽) 에
한 번씩 넣고 각 어댑터가 호출하게 하는 것이 이 계열의 재발을 막는 유일한 형태입니다
— `msr_file` 의 `FdcSpec.drift_sigma()` 가 그 선례입니다.

## 관련

- `CLAUDE.md` — "Office DB knowledge lands in TWO places, always"
- `docs/back-end/provider-selection.md`
- 커밋 `99fc3344`(발단), `2ecc5fbf`(단일화), `efaa4378`(자명한 6건)
