# storage 의 고아 IP 행을 집은 내보내고 사무실은 버린다

Type: bug
Status: needs-triage
검증: 에이전트 보고(미확인) — 착수 전 원본 대조 필요

## 갈리는 지점

`PpidUnavailableRow` 에서 `sem_list` 로스터에 매칭되는 장비가 없는 IP
("고아 IP") 의 처리:

- **mock** — `ebeam/storage/providers/mock.py`: `eqp_id=""` 인 고아 행을
  **내보냅니다**. 생성기가 일부러 3개를 만듭니다.
- **office** — `ebeam/storage/providers/office_example.py`: 매칭이 없으면
  `continue` 로 **버립니다**. 여기에 더해 mock 에는 읽기 경로 대응물이 없는
  tool-type 필터가 하나 더 걸려 있습니다.

**두 docstring 이 서로 반대 규칙을 선언하고 있습니다.**

## 결과

행 수가 다릅니다. 그리고 mock 이 광고하는 "로스터 공백 신호"(로스터에 없는
장비가 스토리지에 데이터를 남기고 있다는 경고) 가 사무실에는 **아예 존재하지
않습니다**. 집에서 그 기능을 보고 만든 화면 로직이 사무실에서는 죽은 코드입니다.

## 필요한 판단

- 고아 IP 는 **신호인가 잡음인가?**
  - 신호로 본다면 → office 가 `eqp_id=""` 행을 내보내야 하고, 화면에 그 뜻을
    표시할 자리가 필요합니다.
  - 잡음으로 본다면 → mock 이 고아를 만들지 않아야 하고, docstring 과 화면
    로직에서 그 개념을 걷어내야 합니다.
- office 쪽의 추가 tool-type 필터는 의도된 것인가? mock 에 대응물이 없습니다.

## 참고

`sem_list` 의 `"nan"` 누출(커밋 `efaa4378` 에서 수정)이 바로 이 경로로
번졌습니다 — IP `"nan"` 이 fleet 키가 되면 고아 행 하나가 더 생겼습니다.
그 원인은 제거됐지만, 고아 행 자체의 정책은 여전히 미결입니다.
