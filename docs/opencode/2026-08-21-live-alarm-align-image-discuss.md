# live-alarm align 이미지 표시 설계 — opencode oc-discuss 기록

- Run date: 2026-08-21
- Skill: oc-discuss
- Model: opencode-go/glm-5.3 variant=high (tier=heavy)
- Target: align fail(ALID 9006) 알람에서 recipe align OM/SEM 이미지를 보여주는 기능의 설계
- Elapsed: round1 160s + round2 62s · Session: `ses_fddfa9215ffeIsqNT95ghdxzfp`

## 논쟁에 부친 입장

| 항목 | 입장 |
| --- | --- |
| 소스 | recipe 의 기준 align 이미지 (`IMAP0001.jpeg`=OM, `IMAP0002.jpeg`=SEM) |
| 버전 체크 | 없음 (사용자가 요구했다가 철회) |
| 시점 | Lazy — 사용자가 행을 열 때만 |
| UI | live-alarm 전용 경량 모달 (`AlignPopup` 재사용 아님) |
| 소유 | `recipe_search` — `_locate_idp` 재사용, 엔드포인트 1개 추가 |
| 캐시 | MinIO 7일. prefix 공유 여부는 미결로 두고 공격받게 함 |
| 범위 | Hitachi CD-SEM + HV-SEM, 같은 `IMAP{p:04d}.jpeg` 이름 |

## What the model said

### Round 1

> Inspected: `recipe_search/providers/office_example.py` (`_locate_idp`, `_order_candidates`, `_IdpLocation`), `msr_image/` (single_flight, config, minio_cache), `__init__.py` rate limits, `live_alarm/contracts.py`. Objections, worst first:
>
> **1. The locator does not deliver the claimed source.** The design says "the alarming tool's own FTP folder," but `_locate_idp` returns candidates ordered by `_order_candidates` — *online tools first*, no eqp filter — and its meas_hist fallback points at wherever a measurement ran, possibly stale. The alarm row carries `eqp_id` (contracts.py:97); the design never says it will filter candidates by it. If the alarming tool is marked unavailable, you silently serve a *sibling tool's copy* of the reference. That's not the accepted temporal staleness — it's cross-tool substitution, and per-tool recipe edits are exactly why the alarming tool was specified. An engineer judges "weak target" against a different tool's stronger reference and fixes the wrong thing. Cost: must add eqp filtering plus an explicit "alarming tool unreachable, showing tool X's copy" disclosure, or the premise of point 1 is false.
>
> **2. Worker-pool exhaustion is the real herd, not FTP sessions.** The design reuses `MinioImageCache` but never mentions `single_flight` — which msr_image built precisely because tool FTP caps sessions and concurrent viewers herd (single_flight.py:1-13). Worse: `ftp_host_timeout` is tied in lockstep to the proxy's 75s harakiri (msr_image/config.py:38). A tool that accepts TCP but stalls login holds a uWSGI worker ~75s per click; a hot alarm with a few engineers can starve the shared office workers and take down the *whole app, including the alarm board*. Cost: an availability incident triggered by the incident-response feature.
>
> **3. "One call returns the list" leaves the bytes homeless.** msr_image's GET route is keyed to MSR locators, not IMAP paths. Either the images ride inline in the single response (fine — say so), or you need new byte routes under rate-limited recipe_search: 3+ requests per modal against the 50/5s shared budget the board poll already spends. Note the one-call justification is self-inflicted — msr_image is exempt precisely because image routes fan out.
>
> **4. Open question: share `image_cache/`.** A separate prefix is invisible to the flask_modules Airflow DAG — retention diverges silently in another repo, the exact drift the constraint warns of. Keys don't collide (different path shape); shared prefix costs zero cross-repo change.
>
> Strongest falsifier left standing: #3 — first alarm on a tool is always a cold fetch from a possibly-dead FTP; the 7-day cache only helps the *second* incident.

### Round 2

> **#3 — pressing, with the concrete case.** The rebuttal is right that the byte route exists (`recipe_search_recipe_image`, routes.py:411) but wrong that this settles it: **that route has no server-side cache.** Its docstring says "FTP to memory to response"; `fetch_recipe_image` (office_example.py:1869-1883) calls `_fetch_raw` and returns — nothing is stored. The only cache is the browser's `Cache-Control: immutable` header (routes.py:456). Concrete failure: hot 9006 alarm, three engineers open the modal in an hour, each from their own browser. Engineer 1 pays the FTP fetch; engineers 2 and 3 each pay it *again in full*, straight to the tool that is failing alignments. `single_flight` doesn't help — it dedups only *concurrent* requests, not sequential cold viewers. This is exactly the herd the falsifiers warned about, arriving politely in single file. So design point 6 (MinIO, 7-day) is not reuse — it is a *new* write-through cache inside `fetch_recipe_image`/its route, which is precisely where the shared-prefix decision and the Airflow TTL actually attach. The rebuttal's "no new byte route" is true; "bytes homeless" was fixed by the wrong argument — the cost moved, it didn't vanish.
>
> **#1, #2, #4** — settled as conceded; nothing to add.
>
> No new objection stronger than #1. The position, with your four fixes plus a real server-side cache at the `fetch_recipe_image` seam, is sound.

## Judgement

### 합의된 것

| 항목 | 결론 |
| --- | --- |
| 캐시 prefix | `image_cache/` 를 **공유합니다**. 별도 prefix 는 flask_modules Airflow DAG 에 보이지 않아 다른 저장소에서 조용히 보존 정책이 갈립니다 |
| 캐시 위치 | `fetch_recipe_image` seam 의 **새 write-through 캐시**입니다. 기존 경로는 캐시가 없으므로 "재사용" 이 아닙니다 |
| 소스·시점·UI·소유·실패 경로 | 공격받지 않았습니다. 그대로 유지합니다 |

### 이견으로 남은 것

없습니다. 모델이 2라운드에서 #1·#2·#4 를 정리된 것으로 두고 #3 을 프레이밍
교정으로 좁힌 뒤 수렴했습니다. 3라운드는 돌리지 않았습니다.

### 제가 틀렸던 것

1. **"알람 난 장비의 FTP 에서 가져온다" 는 사실이 아니었습니다.** `_order_candidates` 는
   online 우선·registry 순서 유지로만 정렬하고 **요청된 `eqp_id` 로 거르지 않습니다.**
   `_download_first` 가 먼저 응답하는 장비를 씁니다. `lateral_recipe` 가 존재하는
   이유 자체가 장비마다 recipe 버전이 다르다는 것이므로, 이것은 이론이 아니라 실제
   분기입니다. → 알람의 `eqp_id` 를 넘겨 그 장비를 맨 앞에 두고, **어느 장비가 준
   bytes 인지 항상 표기**합니다.
2. **`single_flight` 를 통째로 놓쳤습니다.** `recipe_search` 는 이 모듈을 쓰지 않습니다
   (grep 확인). 그 docstring 이 위험을 직접 적어 두었습니다 — "a fetch that may already
   be running to `ftp_host_timeout`, under a uWSGI `harakiri` that is only twice that",
   그리고 브라우저의 2.5s/5s 재시도. 정의상 **상태가 나쁜** 장비로 이 무방비 경로를
   겨누려던 것이었습니다.
3. **Q9 절충안("prefix 분리 + 같은 job")이 아무것도 사지 못했습니다.** 여전히
   flask_modules Airflow DAG 변경이 필요하므로, drift 지점만 하나 늘립니다.
4. **MinIO 캐시를 "msr_image 기계 재사용" 이라 불렀습니다.** `fetch_recipe_image` 는
   지금 서버측 캐시가 전혀 없습니다("FTP to memory to response"). 새로 쓰는 코드이고,
   recipe-open 화면의 동작도 함께 바뀝니다.
5. **단일 엔드포인트를 rate limit 으로 정당화했습니다.** 50 req/5s 는 **사용자당**이고
   모달 1회는 3 요청이라 근거가 되지 않습니다. 진짜 이유는 image URL 을 만들기 전에
   locator 해석이 선행돼야 한다는 것입니다.

## Follow-up

구현 전. 위 4개 수정(eqp_id 우선순위 + 출처 표기, `single_flight` 적용,
`image_cache/` 공유, `fetch_recipe_image` 에 write-through 캐시)을 설계에 반영한
뒤 착수합니다.
