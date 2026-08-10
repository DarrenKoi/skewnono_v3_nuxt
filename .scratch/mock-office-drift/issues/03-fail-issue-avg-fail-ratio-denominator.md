# fail_issue 의 avg_fail_ratio 분모가 mock 과 office 에서 다르다

Type: bug
Status: needs-triage
검증: 에이전트 보고(미확인) — 착수 전 원본 대조 필요

## 갈리는 지점

`MeasRankingRow.avg_fail_ratio` 를 구하는 방식:

- **mock** — `providers/mock.py`: `fail_ratio_sum / exec_count`. 분모는
  **그룹의 모든 행**입니다.
- **office** — `providers/office_example.py`: OpenSearch `avg` 집계. 분모는
  **그 필드를 가진 문서만** 입니다.

## 결과

필드가 듬성듬성한 그룹일수록 사무실 값이 **체계적으로 높게** 나옵니다.
측정 실패 순위가 화면의 상위 N 필터를 좌우하므로, 같은 데이터에 대해 집과
사무실의 순위 자체가 달라질 수 있습니다.

값이 비어 있는 문서를 "실패율 0" 으로 볼 것인지 "모름" 으로 볼 것인지의
문제이고, 이건 데이터 의미의 문제라 코드로 정할 수 없습니다.

## 필요한 판단

- `fail_ratio` 가 없는 실행은 **0으로 세는가**(mock) **빼는가**(office)?
- 실물 인덱스에서 이 필드가 실제로 비는 비율은? (`OFFICE-VERIFY`) 거의 안
  빈다면 영향이 미미하므로 우선순위가 내려갑니다.

## 착수 시

결정이 "빼는 쪽"이면 mock 이 그 상황(필드 없는 행)을 만들어 낼 수 있어야
합니다. 지금 mock 은 모든 행에 값을 채우므로 어느 규약이든 똑같아 보입니다 —
이것이 이 드리프트가 지금껏 보이지 않은 이유입니다.
