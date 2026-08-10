# device_statistics office 어댑터가 카탈로그 조인에서 자기 자신과 모순된다

Type: bug
Status: done
검증: **확인함** (원본 대조)

## 결정 (user-confirmed 2026-08-10) — M계열(양산) 우선

`device_desc` 가 device 의 현재 상태를 반영하므로, 겹치는 `lot_cd` 는 M-fab 이
이깁니다. mock 은 `_lot_index` 와 `_lot_ctn_desc` 양쪽에서 이미 이 순서였고,
office 의 `_lot_index` 도 그랬습니다 — `_lot_meta` 하나만 반대였습니다.

## 고친 것

`_lot_meta()` 를 r3 → hvm 순서로 뒤집어 `_lot_index()` 와 일치시켰습니다.
이제 겹치는 lot 은 `fac_id`·`ctn_desc`·`prod_catg_cd` 를 모두 같은 카탈로그
(M-fab)에서 가져옵니다. M-fab device 는 원천에 `prod_catg_cd` 가 없으므로 ""
이고 `memory_class_auto` 는 "unknown"(수동 분류, D7)으로 떨어집니다 — 겹치는
lot 이 R3 의 값을 잃는 것은 M-fab 으로 판정한다는 결정의 직접적 귀결입니다.

## 테스트

`tests/test_office_template.py` 를 새로 만들어 두 함수가 같은 카탈로그로
해석되는지 고정했습니다. mock 의 두 생성기는 같은 `lot_cd` 를 함께 만들지
않으므로, 겹치는 상황은 테스트가 직접 지어 넣습니다.

## 남은 OFFICE-VERIFY

겹치는 `lot_cd` 가 실물에 **실제로 존재하는지**는 여전히 미확인입니다. 없다면
이 수정은 자기모순 정리로만 의미가 있고 우선순위 결정은 무의미합니다.
확인하려면 두 카탈로그의 `lot_cd` 집합 교집합 크기를 사무실에서 한 번 재면
됩니다.

## 원래 서술 (참고)

## 배경

`device_statistics` 는 `lot_cd` 메타데이터를 두 카탈로그에서 읽습니다 —
R3 연구개발(`r3_device_grp`)과 M 계열 양산(`device_desc`). 두 카탈로그는 어느
쪽도 다른 쪽의 상위 집합이 아니고(mock docstring, user-confirmed 2026-07-31),
**같은 `lot_cd` 가 양쪽에 있을 수 있습니다.**

겹칠 때 어느 쪽이 이기는지가 `SummaryRow.ctn_desc`, `prod_catg_cd`,
그리고 거기서 파생되는 `memory_class_auto` / `family` / `phase` 를 결정합니다.

## 갈리는 지점

**office 어댑터 안에서 두 함수가 서로 반대 순서를 씁니다.**

- `providers/office_example.py` `_lot_index()` — r3 먼저, hvm 나중 → **M 우선**
- `providers/office_example.py` `_hvm_rows()`/`_r3_rows()` 조인 — hvm 먼저,
  r3 나중 → **R3 우선**

mock 쪽(`providers/statistics.py` 의 `_lot_index` 와 조인)은 **양쪽 다 r3 먼저,
`device_desc` 나중** 으로 일관됩니다.

## 결과

양쪽 카탈로그에 있는 `lot_cd` 하나에 대해 office 는

- `fac_id` 를 **HVM 행**에서 (그래서 `_is_r3()` 가 M-fab 으로 라우팅) 가져오고,
- `ctn_desc` / `prod_catg_cd` 는 **R3 행**에서 가져옵니다.

즉 한 행이 두 카탈로그의 조각을 섞어 갖습니다. 집에서는 재현 불가 —
mock 의 두 생성기는 같은 `lot_cd` 를 절대 함께 만들지 않습니다.

## 필요한 판단

1. **자기모순은 어느 쪽이든 버그입니다.** 두 함수를 같은 순서로 맞춰야 합니다.
2. 그 "같은 순서"가 무엇인지가 도메인 판단입니다:
   - **R3 우선** — 연구개발 원본 설명이 더 정확하다고 볼 때
   - **M 우선** — 양산 카탈로그가 현재 상태를 반영한다고 볼 때 (mock 의 현재 선택)
3. 겹치는 `lot_cd` 가 실제로 존재하는지 자체가 `OFFICE-VERIFY` 입니다. 없다면
   순서는 무의미하고 자기모순만 정리하면 됩니다.

## 착수 시

결정된 순서를 한 곳(`_lot_index`)에만 두고 조인이 그것을 재사용하게 하십시오.
두 벌로 남기면 같은 방식으로 다시 갈라집니다.

`CLAUDE.md` 에 따라 확인된 사실은 `docs/datatables/` 와 `mock.py` **양쪽**에
기록해야 합니다. 겹치는 `lot_cd` 가 실재한다면 mock 생성기도 그 상황을 만들어
낼 수 있어야 합니다 — 지금은 그럴 수 없어서 이 버그가 집에서 보이지 않았습니다.
