# total_executions 카운팅 규약이 한 파일 안에서도 혼용된다

Type: bug
Status: done
검증: **확인함** — 원인 사실은 user-confirmed 2026-08-10

## 결론 (2026-08-10)

처음 서술("doc_count 냐 value_count 냐 하나를 고르라")이 **잘못된 프레이밍**
이었습니다. 코드를 읽어 보니 한 변수가 서로 다른 두 숫자를 원하는 자리에
동시에 쓰이고 있었고, 각 provider 가 반쪽씩만 맞았습니다.

| | mock | office | 옳은 쪽 |
| --- | --- | --- | --- |
| 실행 건수 | 전체 행 | `value_count(meastime)` | **mock** |
| 평균 분모 | 전체 행 | `value_count(meastime)` | **office** |

- **실행 건수** — MSR 파일이 없어도 측정은 실행됐습니다. 전부 세야 합니다.
- **평균 측정 시간** — meastime 이 없는 문서를 분모에 넣으면 결측 비율만큼
  평균이 내려갑니다. 있는 것만 세야 합니다.

## 근거가 된 사실 (user-confirmed 2026-08-10)

`meastime` 은 **`msr_check == "Yes"` 인 문서에만 존재**합니다. `"No"` 이면
필드 자체가 없고, office 어댑터의 `_int(src.get("meastime"))` 를 거쳐 행에서는
0 이 됩니다. `docs/datatables/meas_hist.txt` 와 `meas_hist/providers/mock.py`
양쪽에 기록했습니다.

`_office_meas_hist.py` 의 `# every doc has one` 주석이 **틀린 단언**이었고,
그 주석이 두 숫자를 교환 가능해 보이게 만든 원인이었습니다.

## 고친 것

- `_office_meas_hist.DOC_COUNT_AGG` 신설 — `value_count(timestamp)`.
  `aggregate()` 가 `aggregations` 만 돌려줘 `hits.total` 을 못 쓰는데,
  `filter_clauses` 가 항상 `range(timestamp)` 를 포함하고 range 질의는 필드가
  있는 문서만 매칭하므로 범위 안 문서 수와 정확히 같습니다.
- `recipe_tat` office 요약 — `docs`(실행 건수)와 `measured`(평균 분모)로 분리.
- `fail_issue` office 요약 — `execs` 를 문서 수로. 여기가 더 나빴습니다:
  이 값이 **모든 비율의 분모**인데 분자는 filter 의 `doc_count` 라, meastime
  없는 문서의 실패가 분자에만 들어가 비율이 부풀려졌습니다. MSR 파일 부재
  자체가 실패 신호라 하필 문제가 몰린 곳에서 가장 크게 틀렸습니다.
- `recipe_tat` mock — 평균 분모를 meastime 있는 행으로.
- `meas_hist` mock — `msr_check == "No"` 행의 meastime 을 0 으로. 233행 중
  16행(6.9%)이 결측을 재현합니다.

## 남은 것 (별건)

- **`recipe_tat` mock fixture 는 결측을 만들지 못합니다.** 자체 행 생성기를
  쓰고 `msr_check` 열이 없습니다. fixture 에 결측을 넣으려면 장비 speed
  스칼라와 tat_index 임계값 튜닝을 함께 봐야 해서 미뤘고, mock docstring 에
  "알려진 값 영역 공백" 으로 기록했습니다. 그 구분은 행을 지어 넣는 테스트가
  지킵니다.
- **장비별 `avg_meastime`** (`_shape.py`) 는 여전히 전체 행으로 나눕니다.
  요약 카드와 같은 규칙으로 맞추려면 버킷마다 measured 수가 필요합니다 —
  격자 계약을 건드리므로 별도 건입니다.
