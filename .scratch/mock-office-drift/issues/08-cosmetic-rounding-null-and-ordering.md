# 반올림 · None · 정렬 tie-break 표시 차이 묶음

Type: bug
Status: needs-triage
우선순위: 낮음 (크래시 없음, 값이 조금 다르거나 순서가 다름)
검증: 에이전트 보고(미확인) — 착수 전 원본 대조 필요

여러 feature 에 흩어진 소소한 드리프트입니다. 각각은 작지만 전부 "집에서 본
화면과 사무실 화면이 미묘하게 다르다" 로 이어집니다. 한 번에 훑는 편이
효율적이라 묶었습니다.

## 반올림 / None 처리

| 대상 | mock | office |
| --- | --- | --- |
| `hardware`/sce `Coefficients[].values` | 6자리 반올림 float | `list(vals)` 그대로, float 강제 없음 |
| `hardware`/reso_center, bsm | 반올림 + 모든 metric 키 보장 | 반올림 없음, `None` 이거나 키 자체가 없음 |
| `device_statistics` `generated_at` | 초 단위 | 마이크로초 단위 |

`sce` 는 자매 어댑터 `bsm`/`reso_center` 가 쓰는 `_as_float` 를 쓰지 않습니다 —
같은 계열 안에서도 처리가 갈립니다.

## 정렬 / tie-break

| 대상 | mock | office |
| --- | --- | --- |
| `recipe_tat`·`fail_issue` `sample_eqp_ids`/`sample_lot_cds` | 사전순 앞에서 | 빈도 상위 N |
| `recipe_tat` `get_devices` | `total_meastime` 단독 | `(total_meastime, exec_count)` |
| `hardware`/mdc | 정렬 없음 | `(timestamp, beam_condition)` 재정렬 |
| `recipe_search` | 중복 제거 없음 (시드 충돌 시 `total` 부풀림) | `_unique` 로 fab 별 중복 제거 |

`get_devices` 는 공유 `_shape.py` 가 **이미 (total_meastime, exec_count) 쌍**을
쓰고 있어, mock 만 뒤처진 형태입니다 — 이건 거의 자명합니다.

`hardware`/mdc 는 자매 계열 전부가 "mock 의 정렬 키로 재정렬" 한 줄을 갖고
있고 mdc 의 mock 쪽만 빠져 있습니다 — 이것도 거의 자명합니다.

## 타임스탬프 표기

`lateral_recipe` — mock 은 `...Z`, office 는 `...+09:00`. **두 docstring 모두
+09:00 규칙을 명시하고 9시간 렌더 오류를 경고**하고 있으므로 mock 이 틀렸습니다.
자명하지만 09번이 아니라 여기 둔 이유는, 같은 feature 의 `versions[]` 의미
차이(아래)와 함께 봐야 하기 때문입니다.

## lateral_recipe versions[] 의 의미

- mock — `version_counts` 에서 만들어 모든 항목이 `ready_count >= 1`
- office — 인덱스의 모든 버전 문서에서 만들어 `ready_count: 0` 인 최신 버전이
  가능

"버전 이력"이 **보유 장비가 있는 버전만**인지 **존재한 모든 버전**인지의
판단입니다. office 쪽 주석은 후자를 의도로 적고 있습니다 (이력이 계속
탐색 가능해야 한다).

## 필요한 판단

대부분 "office 쪽이 맞고 mock 을 맞추면 된다" 로 보이나, 반올림 자릿수와
`versions[]` 의미는 화면 요구사항을 아는 사람이 정해야 합니다.
