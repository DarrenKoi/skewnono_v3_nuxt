# 04 — 폴링 실패 한 번이 살아 있는 job 을 버리고 패널을 푼다

Status: ready-for-agent

## 문제

`useMsrImageWarmer.runWarm` 의 `try` 는 POST 와 **폴링 루프를 함께** 감쌉니다.
따라서 `api.pollJob` 이 던지면 POST 실패와 똑같이 `warmRetryDelayMs(err, ...)` 로
갑니다.

그런데 `poll_job_route` 는 `too_many_jobs` 를 절대 내보내지 않습니다 —
`unknown_job`(404)뿐입니다(`back_dev_home/msr_image/routes.py`). 즉 **폴링 중
발생하는 모든 실패는 무조건 `null` → `gaveup`** 입니다.

## 왜 이것이 브랜치의 목표를 되돌리는가

`/api/*` 에는 20 req/5s 전역 rate limit 이 있고, `WARM_POLL_MS = 600` 이면 폴링만
초당 1.7 회입니다. 여기에 갤러리의 이미지 GET 이 겹치면 실제로 닿는 한도입니다.
그 429 를 맞는 순간:

- warm job 은 **여전히 살아서** 장비에서 파일을 받고 있습니다
- 그런데 패널은 `gaveup` 이 되어 보류를 풀고
- 화면의 이미지들이 **예산 없는 cold GET** 으로 쏟아집니다

설계 문서 §2.1 이 없앤 증폭 경로와 결과가 같습니다. 다른 문으로 다시 열린 것뿐입니다.
single-flight 는 *같은* 이미지의 중복만 막으므로, 서로 다른 N 장에 대한 무예산
방문은 그대로 남습니다.

429 만의 문제도 아닙니다. 순간적인 네트워크 오류 하나, 프록시의 502 하나가 똑같이
패널을 풉니다.

## 설계 문서와의 관계

`docs/superpowers/specs/2026-08-10-msr-image-tool-load-design.md` §4.1 은 "그 외
오류(죽은 장비, 만료된 job, rate-limit 429) — 지금처럼 `gaveup`" 이라고 적습니다.
그 판정은 **POST 실패를 염두에 둔 것** 입니다. POST 가 실패하면 job 이 없으므로
기다릴 대상 자체가 없고, 그래서 `gaveup` 이 맞습니다.

폴링 실패는 전제가 다릅니다. **job 은 이미 존재하고 이미 장비를 읽고 있습니다.**
여기서 포기하는 것은 "기다려도 나아질 게 없어서" 가 아니라, 곧 도착할 캐시를 눈앞에
두고 장비에 다시 가는 것입니다. 이 이슈는 §4.1 의 그 문장을 폴링 경로에 한해
수정합니다.

## 제안

POST 재시도와 폴링 재시도를 분리합니다. 지금은 `attempt` 하나가 둘을 겸하고 있어
"실패했으니 다시 POST" 밖에 표현하지 못합니다.

- **POST 실패** — 지금 그대로(`warmRetryDelayMs`: 거부만 재시도, 나머지는 `gaveup`)
- **폴링 실패** — 기본은 **폴링 재시도** 입니다. job 이 확정적으로 사라진 경우
  (404 / `code === 'unknown_job'`)만 `gaveup`. 재시도는 **연속 실패 횟수** 로 세고,
  성공하면 0 으로 되돌립니다
- 재시도 예산은 `WARM_CEILING_MS` 하나를 그대로 씁니다. 새 상한을 만들지 마십시오
  (이슈 03 과 같은 이유)
- 사다리는 기존 `WARM_RETRY_DELAYS_MS` 를 재사용합니다. 상수를 늘리지 않으면서
  연속 4 회 실패에서 멈추고, 1+2+4 = 7s 의 관용은 15s 예산 안에 들어갑니다

폴링 실패 중 재-POST 는 하지 마십시오. job 이 살아 있는데 또 만들면 `max_jobs=2`
슬롯을 우리 스스로 먹고, 장비 방문도 늘어납니다.

## 검증

`front-dev-home/app/utils/imageWarm.test.ts` 에 판정 함수 케이스를 추가합니다.

- 429 rate limit 폴링 실패 → 재시도 (지금 코드는 `gaveup`, **실패해야 함**)
- 네트워크 오류 폴링 실패 → 재시도
- 404 / `unknown_job` → `null` (기존 동작 유지)
- 연속 실패가 사다리를 넘어서면 → `null`
- 예산이 소진됐으면 → `null`

`useMsrImageWarmer` 의 루프 자체는 타이머가 얽혀 순수 함수로 뽑히지 않으므로,
판정을 `imageWarm.ts` 로 전부 밀어내고 그것만 검사합니다(기존 방식과 동일).

## 하지 말 것

- 폴링 실패에 재-POST (슬롯 낭비 + 장비 방문 증가)
- 두 번째 상한 상수 추가
- `WARM_POLL_MS` 를 늘려 rate limit 을 피하기 — 증상만 가리고, 폴링이 유일한
  실패 원인도 아닙니다

## 참고

- `front-dev-home/app/composables/useMsrImageWarmer.ts` — `runWarm`
- `back_dev_home/msr_image/routes.py` — `poll_job_route` (404 `unknown_job` 만)
- 설계: `docs/superpowers/specs/2026-08-10-msr-image-tool-load-design.md` §2.1, §4.1
