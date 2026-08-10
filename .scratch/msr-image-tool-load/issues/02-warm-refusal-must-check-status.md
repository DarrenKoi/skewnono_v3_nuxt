# 02 — warm 거부 판별이 HTTP status 를 보지 않는다

Status: resolved

## 문제

`front-dev-home/app/utils/imageWarm.ts` 의 `warmErrorCode` 는 응답 본문만 봅니다:

```ts
export const warmErrorCode = (err: unknown): string | undefined =>
  (err as { data?: { code?: string } })?.data?.code
```

`warmRetryDelayMs` 는 이 값이 `'too_many_jobs'` 인지만 확인하고 재시도를
결정합니다. **status 는 어디서도 확인하지 않습니다.**

설계 문서는 다르게 적혀 있습니다 — `docs/superpowers/specs/2026-08-10-msr-image-tool-load-design.md` §4.1:

> **429 이면서 본문 `code === "too_many_jobs"`** — ... backoff 후 POST 를 다시 시도

즉 코드가 계약보다 느슨합니다. `500` 이나 `503` 응답이 어떤 경로로든 본문에
`too_many_jobs` 를 실으면 재시도 대상으로 분류됩니다.

## 왜 지금은 안 터지는가, 그리고 왜 그래도 고쳐야 하는가

오늘 `too_many_jobs` 를 내보내는 곳은 `back_dev_home/msr_image/routes.py` 의 job
상한 거부 한 곳뿐이고 그것은 429 입니다. 그래서 현재는 오작동하지 않습니다.

고쳐야 하는 이유는 이 판별이 **정확히 그 느슨함 때문에 위험한** 자리이기 때문입니다.
이 코드가 존재하는 이유 자체가 "429 라고 다 같은 429 가 아니다" 였습니다 — `/api/*`
의 20 req/5s 전역 rate limit 도 429 를 내고, 거기에 재시도로 답하면 이미 제한당한
클라이언트가 요청을 더 보냅니다. 판별자를 한쪽 축(본문)으로만 두면, 미래에 서버가
5xx 에 같은 코드를 실어 보내는 순간 조용히 잘못된 방향으로 재시도합니다.

## 제안

status 와 code 를 함께 보는 하나의 판별 함수로 합칩니다. 예: `isWarmRefusal(err)` 가
status 429 **그리고** `data.code === 'too_many_jobs'` 일 때만 참.

status 추출은 저장소에 이미 선례가 있습니다 — `front-dev-home/app/composables/useMsrFileApi.ts:162`
가 `err.response?.status ?? err.statusCode` 형태로 Nuxt 가 넘기는 두 모양을
모두 다룹니다.

`warmRetryDelayMs` 의 나머지 로직(사다리, jitter, ceiling)은 그대로 둡니다.

## 검증

`front-dev-home/app/utils/imageWarm.test.ts` 에 케이스를 추가합니다. 기존 7건은
그대로 통과해야 합니다.

- status 429 + `code: 'too_many_jobs'` → 재시도 (기존 동작)
- status 429 + code 없음 (rate limit) → `null` (기존 동작)
- **status 500 + `code: 'too_many_jobs'` → `null`** ← 지금 코드에 대해 실패해야 함
- status 없음 + `code: 'too_many_jobs'` → `null`

Nuxt 가 주는 두 에러 모양(`err.statusCode`, `err.response.status`)을 모두 덮으십시오.

## 참고

- 설계: `docs/superpowers/specs/2026-08-10-msr-image-tool-load-design.md` §4.1
- 거부 응답 본문: `back_dev_home/msr_image/routes.py` (job 상한 분기)

## Answer

`5398f41f` — `isWarmRefusal(err)` 가 status 429 와 본문 `too_many_jobs` 를 함께
봅니다. status 추출은 `httpStatus()` 로 분리해 Nuxt 의 두 모양(`err.statusCode`,
`err.response.status`)을 덮었고, 같은 헬퍼를 이슈 04 의 `unknown_job`(404) 판별도
씁니다. 사다리·jitter·상한은 그대로입니다.

### 리뷰 반영

같은 논리를 `isJobGone` 에도 적용했습니다. 처음에는 `404 || unknown_job` 이라
한쪽 축만으로도 참이 됐는데, 그러면 프록시나 잘못 mount 된 라우트가 낸 404 하나가
"job 이 죽었다" 로 읽혀 이슈 04 가 막으려던 폭주를 그대로 엽니다. 지금은 두 축을
함께 봅니다.

`httpStatus` 는 `app/utils/httpError.ts` 로 옮겼습니다. `useMsrFileApi` 의
`statusOf` 가 같은 두 모양 조회를 이미 하고 있었고, 이름만 다른 같은 개념이
둘 있을 이유가 없습니다.
