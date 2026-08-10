# DeviceRow 의 prod_catg_cd / tech_nm 우선순위가 mock 과 office 에서 반대다

Type: bug
Status: done
검증: **확인함** (원본 대조 완료 2026-08-10)

## 결정 (user-confirmed 2026-08-10) — M계열(양산) 우선

01 번과 같은 결정입니다. 겹치는 `lot_cd` 는 **`tech_nm` 이 이깁니다**.

## 고친 것

`recipe_tat` 과 `fail_issue` 의 office 어댑터에서 조인 순서를 뒤집었습니다:

```python
tech_nm = catalog.get(lot_cd, {}).get("tech_nm") or None
prod_catg_cd = None if tech_nm else (r3.get(lot_cd) or None)
```

이제 mock 의 `_analytics.lot_metadata()`(device_desc 가 r3 엔트리를 통째로
덮어써 `tech_nm` 이 이기는 형태)와 같은 답을 냅니다. office 쪽의
`"" → None` 정규화는 유지했습니다 — 그쪽이 옳습니다.

## 테스트

`recipe_tat/tests/test_office_template.py` 에 겹치는 lot 을 지어 넣어
`tech_nm` 이 살아남는지 고정했습니다. `fail_issue` 의 같은 두 줄은 문자열이
동일해 함께 바뀌었으나 별도 테스트는 없습니다 — 집계 형태가 달라 픽스처를
따로 만들어야 해서, 검토로만 확인했습니다.

## 남은 것

01 번과 같은 OFFICE-VERIFY(겹치는 lot 의 실재 여부)를 공유합니다. 이 결정을
`_office_meas_hist.py` 의 공용 헬퍼로 올리는 일은 하지 않았습니다 — 지금은
두 어댑터에 같은 두 줄이 복제돼 있고, 세 번째 소비자가 생기면 그때가
올릴 시점입니다.

## 원래 서술 (참고)

## 배경

`recipe_tat` 과 `fail_issue` 의 `DeviceRow` 는 `lot_cd` 하나에 대해 화면에
칩(chip) 하나를 붙입니다 — 기술 노드(`tech_nm`) 또는 제품 카테고리
(`prod_catg_cd`). 어느 쪽이 붙느냐는 두 카탈로그가 겹칠 때의 우선순위가
정합니다. 01번과 같은 뿌리이나 이쪽은 **파생 필드가 서로를 지웁니다.**

## 갈리는 지점

- **mock** — `ebeam/_analytics.py` 의 `lot_metadata()` 가 r3 엔트리를
  `device_desc` 엔트리로 **통째로 덮어씁니다**. 결과: `tech_nm` 이 이기고
  `prod_catg_cd` 는 None 이 됩니다.
- **office** — `recipe_tat/providers/office_example.py` 와
  `fail_issue/providers/office_example.py` 의 조인에서 `prod_catg_cd` 가 이기고
  `tech_nm` 이 None 으로 강제됩니다.

추가로 office 는 `"" → None` 정규화를 하고 mock 은 하지 않습니다.

## 결과

같은 lot 이 집에서는 **기술 노드 칩**으로, 사무실에서는 **제품 카테고리 칩**으로
보입니다. 오류도 경고도 없습니다.

## 필요한 판단

- 겹칠 때 화면에 무엇이 보여야 하는가 — `tech_nm` 인가 `prod_catg_cd` 인가?
- 아니면 **둘 다 유지**하고 화면이 고르게 할 것인가? (계약 변경이라 범위가 큼)
- `""` 는 None 으로 정규화하는 것이 맞습니다 — 이건 자명하므로 결정 후 함께.

## 착수 시

01번과 **같은 결정**이 두 곳에 필요합니다. `_analytics.lot_metadata()` 가 이미
mock 쪽 공유 지점이므로, office 쪽 대응물을 `_office_meas_hist.py` 에 만들어
두 feature 가 함께 쓰게 하는 것이 옳습니다. feature 별로 고치면 3벌이 됩니다.
