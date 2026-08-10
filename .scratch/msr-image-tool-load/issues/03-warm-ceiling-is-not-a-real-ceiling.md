# 03 — WARM_CEILING_MS 가 실제 상한이 아니다

Status: resolved

## 문제

`WARM_CEILING_MS = 15_000` 은 "SEM 패널이 이미지를 붙들고 기다리는 최대 시간" 으로
문서화돼 있고, `useMsrImageWarmer.runWarm` 의 재시도 예산도 여기서 나옵니다.

그런데 경과 시간은 **응답이 돌아온 뒤에만** 검사됩니다:

```ts
const jobId = await api.startDownloadAll(...)   // 여기서 멈추면 아무도 안 봄
...
const poll = await api.pollJob(jobId)
state.status = nextWarmState(poll, Date.now() - startedAt)
```

그리고 `useMsrImageApi` 의 `startDownloadAll` / `pollJob` 은 `$fetch` 에
`timeout` 도 `signal` 도 주지 않습니다. 따라서 POST 나 poll 이 응답 없이 매달리면
**15초를 얼마든지 넘겨서** 패널이 `준비 중` 으로 남습니다.

이 자체는 이 브랜치가 만든 결함이 아닙니다(poll 루프는 이전부터 그랬습니다). 다만
이 브랜치가 `WARM_CEILING_MS` 를 재시도 예산으로도 쓰기 시작하면서, 그 값이 실제
상한이라는 전제가 더 많은 곳에 걸리게 됐습니다.

## 왜 중요한가

`holdForWarm` 이 참인 동안 이미지는 요청되지 않습니다. 그것이 이 기능의 목적이지만,
상한이 실효가 없으면 **장비가 멀쩡한데도 패널이 무기한 비어 있는** 상태가 가능합니다.
사용자에게는 "이미지가 안 뜬다" 로 보이고, 재시도할 방법도 없습니다(자동 재시도는
`<img>` 가 요청을 시작해야 도는데 그 요청 자체가 보류 중).

## 제안

두 가지 중 하나, 또는 둘 다:

1. **요청 자체에 상한을 준다.** `$fetch` 에 `timeout` 을 주거나 `AbortSignal.timeout()`
   을 넘깁니다. 값은 `WARM_CEILING_MS` 와 어긋나지 않게 유도하십시오 — 새 상수를
   또 만들면 두 개가 따로 놀게 됩니다.
2. **대기 자체에 상한을 씌운다.** `runWarm` 전체를 남은 예산으로 race 시켜, 예산이
   끝나면 진행 중인 요청과 무관하게 `gaveup` 으로 떨어뜨립니다.

2번이 상한의 정의("패널이 붙드는 최대 시간")에 더 정확히 대응하지만, 버려진
요청이 그대로 서버에서 도는 것을 막지는 못합니다. 1번은 그것까지 끊습니다.

어느 쪽이든 **`WARM_CEILING_MS` 하나만이 상한이어야 합니다.**

## 검증

`imageWarm.ts` 의 순수 함수로 표현할 수 있는 부분은 `node --test` 로 검사합니다
(`imageWarm.test.ts`). 타이머가 얽히는 부분은 fake timer 없이 검사하기 어려우므로,
판정 로직을 순수 함수로 뽑아내는 쪽을 우선하십시오 — `nextWarmState` 와
`warmRetryDelayMs` 가 이미 그 방식입니다.

최소한: 예산이 소진된 상태에서 판정 함수가 `gaveup` 을 내는지, 그리고 그 판정이
응답 도착 여부와 무관한지.

## 참고

- `front-dev-home/app/utils/imageWarm.ts` — `WARM_CEILING_MS`, `nextWarmState`
- `front-dev-home/app/composables/useMsrImageWarmer.ts` — `runWarm`
- `front-dev-home/app/composables/useMsrImageApi.ts` — `startDownloadAll`, `pollJob`

## Answer

`9a9d1bff` — 1번안을 택했습니다. `remainingBudgetMs(elapsed)` 가 남은 예산을
계산해 `startDownloadAll`/`pollJob` 의 `$fetch` timeout 으로 넘어가므로, 상한은
`WARM_CEILING_MS` 하나로 유지되고 버려진 요청도 함께 끊깁니다.

2번안(전체 race)은 단독으로는 채택하지 않았습니다. POST 를 중도 포기해도 서버가
이미 만든 job 은 `max_jobs` 슬롯을 계속 먹으므로, 포기한 클라이언트가 남의 warm 을
막습니다. 1번안에서도 그 창은 남지만 예산이 끝나는 시점에만 열리고, 그 job 이 받은
파일은 공유 캐시에 그대로 남습니다.

`retry: 0` 을 함께 지정했습니다. ofetch 는 GET 을 기본 1회 재시도하므로, 그러지
않으면 timeout 된 호출이 우리 모르게 다시 나가 예산이 요청 하나만큼 어긋납니다.
