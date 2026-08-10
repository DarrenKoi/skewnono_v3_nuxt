# 판단이 필요 없는 기계적 수정 묶음

Type: task
Status: done
검증: 9개 항목 전부 원본 확인 완료 (2026-08-10)

어느 쪽이 옳은지 코드나 docstring 이 이미 답하고 있어, 도메인 판단 없이 고칠 수
있는 것들입니다. 01~08 과 달리 사용자 결정을 기다릴 필요가 없습니다.

## 결과 (2026-08-10)

9개 항목을 전부 원본에서 확인한 결과 **7건이 진짜, 2건이 오탐**이었습니다.
7건은 회귀 테스트와 함께 고쳤습니다. 오탐 2건은 아래에 사유를 남깁니다 —
지우지 않는 이유는 다음 감사가 같은 것을 다시 올릴 수 있기 때문입니다.

### 오탐 3번 — pm_planning `_latest_pm_at`

`""` 를 돌려줄 수 있다는 보고였으나 실제로는 `return None` 이 명시돼 있고
시그니처도 `str | None` 입니다. 계약 위반이 아닙니다.

### 오탐 4번 — msr_file `sequence_count`

mock 의 `rows[-1]["sequence"]` 와 office 의 `sorted(...)[-1]` 는 값이 같습니다 —
mock 이 시퀀스를 오름차순으로만 append 하기 때문입니다. 동작 차이 없음.

각 항목은 **되돌리면 실패하는 테스트**와 함께 들어가야 합니다 — 이 계열 전체가
"mock 이 그 입력을 못 만들어서 집 테스트가 통과하던" 문제이므로, 테스트 없는
수정은 같은 방식으로 다시 갈라집니다.

## 1. `meas_hist` `rows[].id`

- mock 이 `f"msr_{i:06d}"` 를 내보내는데 **자기 docstring 이 `id=msr` 규칙을
  명시**합니다. office 는 규칙대로 `id=msr` 입니다.
- → mock 을 docstring 에 맞춥니다.

## 2. `device_statistics` `recipe_params` 의 `prod_catg_cd.upper()`

- mock 이 `None` 에 `.upper()` 를 호출할 수 있는 형태입니다. office 는
  `(prod_catg_cd or "")` 로 이미 방어합니다.
- → mock 에 같은 방어를 넣습니다. `AttributeError` 잠재.

## 3. `pm_planning` `_latest_pm_at` 의 반환 타입

- mock 이 `""` 를 돌려줄 수 있는데 **계약은 `str | None`** 입니다.
- → `None` 을 돌려주도록 고칩니다. (office 어댑터는 아직
  `NotImplementedError` 스텁이라 드리프트는 없지만, 계약 위반은 지금 문제입니다.)

## 4. `msr_file` `sequence_count`

- mock 은 `rows[-1]["sequence"]`, office 는 정렬된 집합의 `max`.
- 행이 시퀀스 순으로 정렬돼 있지 않으면 mock 이 틀립니다. `max` 가 정의에
  충실합니다. → mock 을 `max` 로.

## 5. `msr_file` `total_images` 우선순위

- mock 은 **호출자 인자**가 이기고 부모 행이 fallback,
  office 는 `_int(parent.get("total_images"), default=total_images or 0)` 로
  **부모가 항상** 이깁니다.
- 인자를 받는 함수가 그 인자를 무시하는 것은 형태 자체가 잘못입니다.
  → office 를 mock 쪽(인자 우선)으로 맞춥니다. 다만 호출자가 실제로 인자를
  넘기는지 확인 후.

## 6. `recipe_tat` `get_devices` 정렬 tie-break

- 공유 `_shape.py` 가 이미 `(total_meastime, exec_count)` 쌍을 쓰는데
  mock 만 `total_meastime` 단독입니다. → 공유 헬퍼를 쓰게 합니다.

## 7. `hardware`/mdc 의 mock 정렬

- 자매 계열 전부가 "mock 의 정렬 키로 재정렬" 을 갖고 있고 mdc 만 mock 쪽이
  정렬하지 않습니다. → 다른 계열과 같은 형태로.

## 8. `lateral_recipe` 타임스탬프 표기

- mock 이 `...Z`, office 가 `...+09:00`. 두 docstring 모두 +09:00 규칙과
  9시간 렌더 오류를 명시합니다. → mock 을 +09:00 으로.
- 08번 이슈에도 적어 두었습니다 — 같은 feature 의 다른 판단 건과 함께 만질
  거라면 그쪽에서 처리해도 됩니다.

## 9. `msr_file` health 의 상수 `3.5`

- `_fdc_status` 의 bad 임계값을 손으로 베낀 값입니다. → import 로 바꿉니다.
- 05번과 같은 파일이므로 그쪽 결정과 함께 처리하는 편이 낫습니다.

## 착수 순서 제안

1~4 는 서로 독립이라 병렬 가능합니다. 5 는 호출자 확인이 선행입니다.
8·9 는 각각 08·05 와 묶는 편이 자연스럽습니다.
