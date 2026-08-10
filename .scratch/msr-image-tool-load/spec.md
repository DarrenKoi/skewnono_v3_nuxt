# msr_image 장비 FTP 부하 감소 — 후속 이슈

이 디렉터리는 `work/msr-image-tool-load` 브랜치가 병합된 뒤 남은 후속 작업을
담습니다. 브랜치 자체의 설계와 구현 계획은 별도 문서에 있습니다:

- 설계: `docs/superpowers/specs/2026-08-10-msr-image-tool-load-design.md`
- 계획: `docs/superpowers/plans/2026-08-10-msr-image-tool-load.md`
- 실행 이력·판정: `.superpowers/sdd/2026-08-10-msr-image-tool-load/progress.md`

## 배경 (새 세션에서 읽을 것)

계측 장비(Hitachi SEM)의 FTP 서버는 동시 세션 수에 상한이 있고, **엔지니어들이
각자 도구로 같은 장비에 접속해 데이터를 수집합니다.** 우리가 여는 세션 하나하나가
그들의 작업을 밀어냅니다. 그래서 이 영역의 최적화 목표는 레이턴시가 아니라
**세션 수** 입니다.

브랜치가 한 일은 두 가지입니다.

1. warm job 이 429(`code=too_many_jobs`)로 거부되면 예전에는 즉시 `gaveup` 이 되어
   화면의 모든 이미지가 **예산 없는 cold GET** 으로 쏟아졌습니다. 이제 jittered
   backoff 로 재시도하며 보류를 유지합니다.
2. `single_flight.py` 를 만들어 같은 이미지에 대한 동시 요청을 장비 방문 1회로
   합칩니다.

확정된 판정 두 가지는 다시 뒤집지 마십시오.

- **커넥션 풀링은 하지 않습니다.** 유휴 세션이 장비 슬롯을 점유해 목표와 정면
  충돌합니다. 실측이 login 을 cold fetch 의 71% 로 지목했지만 그것은 레이턴시
  관점의 판정입니다.
- **게이트에 타임아웃을 넣지 않습니다.** 대기가 곧 목적이고(대안은 포기하고 장비에
  가는 것), 기다리는 fetch 는 `ftp_timeout`/`host_timeout` 으로 이미 묶여 있습니다.

## 이슈

| # | 내용 | 성격 |
| --- | --- | --- |
| [01](issues/01-single-flight-wake-all-waiters.md) | 대기자를 한 명씩 깨워 캐시 읽기가 직렬화됨. 락 handoff → 완료 `Event` | 정확성 + 단순화 |
| [02](issues/02-warm-refusal-must-check-status.md) | 거부 판별이 본문 `code` 만 보고 HTTP status 를 안 봄 | 계약 불일치 |
| [03](issues/03-warm-ceiling-is-not-a-real-ceiling.md) | `$fetch` 에 타임아웃이 없어 `WARM_CEILING_MS` 가 실효 없음 | 정확성 |

셋 다 **장비 방문 횟수에는 영향이 없습니다** — 브랜치의 핵심 목표는 달성돼 있고,
이 이슈들은 요청 수명·판별 정확성·상한 실효성에 관한 것입니다.

01 은 단순화이기도 합니다: `Event` 로 바꾸면 대기자가 캐시를 다시 읽을 필요가
없어져 호출부가 줄고, 지금 과장으로 판정된 docstring 의 "직렬화" 주장도 함께
사라집니다.

## 출처

2026-08-10 Codex 교차 검토(3건)와 최종 whole-branch 리뷰의 판정 보류 1건입니다.
각 지적은 이슈로 옮기기 전에 코드로 확인했습니다.
