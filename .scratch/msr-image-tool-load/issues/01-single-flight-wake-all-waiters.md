# 01 — single_flight: 대기자를 한 명씩 깨우지 말고 한꺼번에 깨운다

Status: ready-for-agent

## 문제

`back_dev_home/msr_image/single_flight.py` 의 `_Attempt` 는 `threading.Lock` 을
handoff 방식으로 씁니다. 선두가 락을 잡고 본문을 돌고, 대기자들은 그 락에
블록됐다가 **한 명씩 순서대로** 깨어납니다. 각 대기자는 깨어난 뒤 게이트 안에서
`cache.get()` 을 한 번씩 합니다.

사무실에서 캐시는 MinIO이므로 `cache.get()` 은 네트워크 왕복입니다. 따라서 대기자
N명은 캐시 읽기 N회를 **직렬로** 수행하고, k번째 대기자의 응답 시간에는 앞선
k-1개의 캐시 읽기가 쌓입니다.

장비 방문 횟수는 정상입니다(여전히 1회). 문제는 **요청 수명**이며, "fetch 1회로
bounded" 라는 설명과 실제가 어긋납니다.

Codex 검토에서 3회 시행 모두 follower 2개가 동시에 진입한 경우가 없음을
관측했습니다(2026-08-10).

## 함께 해결되는 것 — docstring 과장

같은 파일의 `fetch_gate` docstring 은 `"Serialise callers sharing key"` 라고
주장하지만 실제로는 그렇지 않습니다. 선두가 락을 **해제하기 전에** registry 에서
attempt 를 unpublish 하므로, 이전 시도의 대기자가 아직 본문에 있는 동안 새 요청이
새 attempt 를 열 수 있습니다(최종 리뷰에서 동시 진입 2회 재현).

그 unpublish 순서 자체는 바꾸면 안 됩니다 — 반대로 하면 나중에 도착한 요청이 끝난
시도의 `error` 를 물려받아 실패가 negative-cache 되고, 회복된 장비가 가려집니다
(spec §4.2 가 금지).

`Event` 로 바꾸면 "직렬화" 주장을 할 필요 자체가 없어지므로 두 문제가 같이
사라집니다.

## 제안

`_Attempt` 를 락 handoff 대신 **완료 `Event`** 로 표현합니다.

- 선두가 본문을 돌고, 결과(성공 또는 예외)를 `_Attempt` 에 기록한 뒤 `Event.set()`
- 대기자들은 `Event.wait()` 로 **동시에** 깨어나, 각자 캐시를 읽는 대신 선두가
  남긴 결과를 그대로 받습니다
- 실패 공유(현재 동작)는 그대로 유지 — 선두의 예외 객체를 그대로 재전파

이러면 대기자가 캐시를 다시 읽을 필요조차 없어져, 지금 `routes.py` 가 게이트 안에서
하는 재확인의 상당 부분이 primitive 안으로 들어갑니다. 결과적으로 호출부가 더
단순해집니다.

## 검증

- 기존 테스트는 전부 통과해야 합니다: `back_dev_home/msr_image/tests/test_single_flight.py`,
  `test_routes_serve.py` 의 동시성 3건
- **새 테스트**: 느린 `cache.get` 을 주입하고 대기자 3명을 붙였을 때, 전체 소요가
  캐시 읽기 1회 수준이어야 하고 3회가 누적되면 안 됩니다. 지금 코드에 대해 실패해야
  합니다
- 실패 공유가 유지되는지: `test_concurrent_gets_still_make_one_visit_when_the_fetch_fails`
- negative caching 이 생기지 않는지: `test_a_failure_is_not_remembered_for_the_next_arrival`

## 하지 말 것

- 게이트에 타임아웃 추가 (spec §4.2, 확정된 판정)
- unpublish 를 락 해제 뒤로 옮기기 (실패가 negative-cache 됨)
- warm job 경로를 게이트로 감싸기

## 참고

- 설계: `docs/superpowers/specs/2026-08-10-msr-image-tool-load-design.md` §4.2
- 판정 이력: `.superpowers/sdd/2026-08-10-msr-image-tool-load/progress.md`
