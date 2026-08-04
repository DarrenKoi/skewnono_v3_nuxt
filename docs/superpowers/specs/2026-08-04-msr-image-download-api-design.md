# MSR 이미지 외부 클라이언트 다운로드 설계

- **작성일:** 2026-08-04
- **상태:** 승인된 설계, 구현 계획 작성 전 문서 검토 대기
- **적용 범위:** `back_dev_home/msr_image/routes.py`,
  `back_dev_home/msr_image/tests/`, `scripts/clients/`,
  `docs/back-end/msr-image-download.md`, `docs/back-end/api-tokens.md`

## 1. 배경

사용자가 계측 이미지를 **자신의 PC로 내려받아** 확인하고 싶다는 요구가
있습니다. 사용 언어는 주로 Python이며, 웹 UI를 거치지 않고 스크립트로
처리하기를 원합니다.

한 번의 실행에서 받는 이미지는 **수십 장 수준**(MSR 1~수 건)입니다. 수천 장
규모의 데이터셋 추출은 현재 요구사항이 아닙니다.

## 2. 조사 결과 — 필요한 것은 대부분 이미 존재합니다

설계에 들어가기 전 현행 코드를 확인한 결과, 이 워크플로를 구성하는 네 개의
요소가 **모두 이미 구현되어 있습니다**. 새로 만들어야 하는 데이터 경로는
없습니다.

| 필요한 것 | 현행 구현 | 위치 |
| --- | --- | --- |
| 스크립트 인증 | `Authorization: Bearer skn_...` | `_auth/middleware.py:22-43` |
| 상위 키(lot/recipe/기간) → 좌표 해석 | `GET /api/meas-hist/search` | `meas_hist/routes.py:53` |
| 이미지 목록 | `GET /api/msr-images` | `msr_image/routes.py:49` |
| 이미지 바이트 전송 | `GET /api/msr-image` | `msr_image/routes.py:71` |

### 2.1 상위 키 해석은 `meas-hist/search`가 이미 담당합니다

`GET /api/meas-hist/search`는 `fab`, `model`, `eq`, `recipe`, `lot`, `msr`,
자유 텍스트 `q`, 기간(`from`/`to`), `offset`/`limit`을 받습니다. 응답의
`MeasHistRow`는 이미지 조회에 필요한 세 좌표를 그대로 포함합니다.

```text
lot_cd, lot_id, recipe_name, timestamp   ← 사용자가 아는 값
eqp_ip, class_name, msr                  ← /api/msr-image가 요구하는 값
total_images, fail_images                ← 예상 장수
```

따라서 **별도의 탐색(discovery) 엔드포인트를 신설하지 않습니다.**

### 2.2 rate limit은 장애물이 아닙니다

`back_dev_home/__init__.py:74`의 `application_limits=["20 per 5 seconds"]`는
사용자당 `/api/*` 전체에 걸린 단일 예산입니다. 그러나
`back_dev_home/__init__.py:88-92`가 `msr_image` blueprint 전체를 이미
면제하고 있으며, flask-limiter 4.1.1의 `exempt()` 기본 플래그는
`ExemptionScope.APPLICATION|META|DEFAULT`이므로 application 예산에서도
제외됩니다.

실측으로 확인했습니다.

```text
msr_image  30회 연속 호출:  [200]        429 발생: 0건
meas-hist  30회 연속 호출:  [200, 429]   429 발생: 10건
```

즉 rate limit이 걸리는 호출은 **실행당 1회뿐인 탐색 호출**이며, 이는 20/5초
예산 안에 충분히 들어옵니다. rate limit 관련 코드 변경은 하지 않습니다.

### 2.3 실제로 비어 있는 것

문서와 패키징입니다. 위 네 엔드포인트가 하나의 워크플로로 조합된다는 사실이
저장소 어디에도 기술되어 있지 않으며, 사용자가 복사해 쓸 수 있는 클라이언트도
없습니다.

## 3. 설계 범위

| 산출물 | 경로 | 선정 이유 |
| --- | --- | --- |
| 한국어 사용 안내 | `docs/back-end/msr-image-download.md` | 인증을 다루는 `docs/back-end/api-tokens.md` 옆에 위치시켜 두 문서가 짝을 이루게 합니다 |
| 참조 클라이언트 | `scripts/clients/msr_image_download.py` | `scripts/`는 이미 운영자용 Python(`probe_*.py`, `diagnose_*.py`)을 담고 있습니다. `clients/` 하위 폴더는 "사용자 PC로 복사해 쓰는 파일"임을 표시합니다 |
| 엔드포인트 보완 2건 | `back_dev_home/msr_image/routes.py` | 이 기능에서 동작이 바뀌는 유일한 파일입니다. §10의 부수 작업은 주석·문서만 손대므로 동작 변경이 아닙니다 |

## 4. 백엔드 변경 A — `GET /api/msr-image`에 `Content-Disposition` 추가

`routes.py:91`의 응답 헤더에 한 줄을 추가합니다.

```python
headers = {
    "Cache-Control": "public, max-age=3600",
    "Content-Disposition": f'inline; filename="{safe_name}"',
}
```

### 4.1 `attachment`가 아니라 `inline`인 이유

갤러리는 이 바이트를 `<img :src>`(`SemImage.vue`)와 `fetch()` + blob
(`useMsrImageApi.ts:60`) 두 경로로 읽습니다. `attachment`는 브라우저가 리소스를
다루는 방식을 바꾸는 값이므로, 두 경로에 대해 중립임이 명확한 `inline`을
선택합니다. `curl -OJ`는 disposition 종류와 무관하게 `filename=`을 사용하므로,
대상 사용자(Python·curl)가 얻는 이점은 동일합니다.

`inline`이 중립이라는 것은 명세에 근거한 판단이므로, 구현 후 브라우저에서
갤러리 렌더링을 **실제로 확인합니다**(§9 참조).

### 4.2 파일명은 이스케이프합니다

`name`은 호출자가 제공하는 값입니다. 현재도 256자 제한과
`validate_locator`(`routes.py:82`)를 통과하지만, 헤더 값에 `"` 또는 개행이
들어가는 것은 헤더 인젝션 형태입니다. 검증기의 책임은 **경로 안전성**이지
헤더 안전성이 아니며, 두 책임을 결합하면 한쪽이 완화될 때 다른 쪽이 조용히
깨집니다. 따라서 헤더 생성 시점에서 별도로 이스케이프합니다.

## 5. 백엔드 변경 B — `GET /api/msr-images`에 `ext` 필터 추가

```text
GET /api/msr-images?eqp_ip=…&class_name=…&msr=…&ext=jpg
```

| `ext` 값 | 매칭 대상 | 동작 |
| --- | --- | --- |
| 없음 | 전체 | **기존 기본 동작 유지** — 갤러리는 영향 없음 |
| `jpg` | `.jpg`, `.jpeg` | 미리보기용 이미지만 |
| `tif` | `.tif`, `.tiff` | 원본만 |
| 그 외 | — | `400` 응답. 빈 목록을 조용히 반환하지 않습니다 |

### 5.1 필터는 provider가 아니라 `routes.py`에 둡니다

이것이 이 변경에서 가장 중요한 제약입니다. `data.list_images()`의
**3-인자 시그니처를 그대로 유지**하므로 `providers/office_example.py`와 각
사무실 체크아웃의 gitignore된 `office.py` 복사본은 손대지 않아도 됩니다.

provider 시그니처를 넓히면 모든 사무실 환경이 부팅 전에
`python -m scripts.sync_office_adapters msr_image`를 실행해야 하며, 그렇지
않으면 `STALE office.py: msr_image` 상태가 됩니다. 반환된 리스트에 대한
필터링은 데이터 접근이 아니라 표현 계층의 일이므로, 설계상으로도 `routes.py`가
옳은 위치입니다.

### 5.2 확장자를 그룹으로 묶는 이유

장비의 파일명 규칙이 균일하지 않습니다. 사무실 장비는
`.jpeg`/`.jpg`/`.tif`/`.tiff`를 모두 내보내며(`msr_image/MIGRATION.md`,
office 확인 2026-07-24), mock은 `.jpeg`와 `.tif`만 생성합니다. 사용자가 특정
장비가 어떤 철자를 썼는지 기억해야 하는 API는 좋은 API가 아닙니다.

## 6. 참조 클라이언트

`scripts/clients/msr_image_download.py` — **표준 라이브러리만 사용**합니다
(`urllib.request`, `argparse`, `json`).

저장소에는 `requests>=2.31`이 있으나 이는 **서버** 의존성입니다. 이 파일은
사용자 PC에서 실행되며, 통제된 사내 Windows PC에는 `pip install`이 불가능할 수
있습니다. 표준 라이브러리만 쓰면 코드가 다소 장황해지는 대신 "파일 하나 복사해서
실행"이 성립합니다.

```bash
export SKEWNONO_TOKEN=skn_...
python msr_image_download.py --lot ABC123 --from 2026-08-01 --to 2026-08-04 \
                             --ext jpg --out ./images
```

### 6.1 클라이언트가 구현하는 절차

```text
1. GET  /api/meas-hist/search?lot=…&from=…&to=…    → rows (eqp_ip, class_name, msr)
2. 각 row마다:
     POST /api/msr-images        {eqp_ip, class_name, msr}   → job_id     ← 먼저 warm
     GET  /api/msr-images/<job_id> 를 done|error 까지 polling
     GET  /api/msr-images?…&ext=jpg                          → names
     GET  /api/msr-image?…&name=…                            → bytes → 디스크
```

### 6.2 warm job을 먼저 호출하는 것이 클라이언트를 배포하는 이유입니다

가장 자연스러워 보이는 클라이언트는 POST를 건너뛰고 이미지별 GET을 바로
반복합니다. 사무실에서 이는 장비 FTP로의 **직렬 왕복 N회**입니다. warm job은
같은 파일들을 `SKEWNONO_TOOL_FTP_CONCURRENCY=6`의 병렬 연결로 받아오므로
(`routes.py:189-194`), 이후의 모든 GET은 캐시 적중이 됩니다.

문서로 *설명*할 수는 있지만, 실행 가능한 파일만이 이것을 **기본값**으로
만듭니다. 그러지 않으면 사용자는 이 차이를 "API가 느리다"로 인식하게 됩니다.

### 6.3 저장 규칙

파일은 `<out>/<msr>/<name>`으로 저장하며, 이미 존재하는 파일은 건너뜁니다.
따라서 재실행은 재다운로드가 아니라 이어받기가 됩니다.

## 7. 오류 처리

| 상태 | 의미 | 클라이언트 동작 |
| --- | --- | --- |
| `401 invalid_token` | 토큰이 잘못되었거나 폐기됨 | 즉시 명확한 메시지와 함께 종료. 재시도는 도움이 되지 않습니다 |
| `429` | 1단계 탐색 호출에서만 발생 가능 | backoff 후 재시도 |
| `503` | `SourceUnavailable` — 장비 FTP 접속 불가 | 해당 MSR을 보고하고 다음 MSR로 진행 |
| `404 unknown_job` | job 만료(`SKEWNONO_MSR_IMAGE_JOB_TTL`, 기본 1시간) | warm을 건너뛰고 직접 GET으로 진행 |
| job `status: "error"` | job 전체 실패 | GET은 그대로 진행합니다 |

마지막 행은 의도된 선택입니다. `routes.py:129-135`는 job 전체 실패와 파일별
실패를 구분하는데, 이는 polling이 실패한 job을 성공으로 보고하지 않게 하기
위함입니다. 그러나 job이 `error`로 끝나도 캐시는 부분적으로 채워져 있고 파일별
실패는 개별적으로 드러나므로, 클라이언트는 이를 치명적 오류로 취급하지 않고
GET 단계로 넘어갑니다.

## 8. 문서 — `docs/back-end/msr-image-download.md`

한국어로 작성하며 `~입니다.`/`~합니다.` 체를 사용합니다. 구성:

1. 토큰 발급 방법 — 설정 페이지 안내 및 `api-tokens.md` 링크
2. 4단계 워크플로와 각 엔드포인트의 파라미터
3. `curl` 예시 (단일 이미지, 목록, warm job)
4. Python 예시 — 참조 클라이언트 사용법과 핵심 코드 발췌
5. warm job을 먼저 호출해야 하는 이유 (§6.2)
6. TIFF 안내 — 브라우저는 렌더링하지 못하며 `ext=jpg`가 미리보기용입니다
7. 오류 표 (§7)

## 9. 테스트 계획

**백엔드** — `back_dev_home/msr_image/tests/`에 추가합니다.

- `Content-Disposition`이 존재하고 파일명이 일치하며, `name`에 `"`나 개행을
  넣은 요청에서 값이 이스케이프됨
- `ext=jpg`는 `.jpg`/`.jpeg`만, `ext=tif`는 `.tif`/`.tiff`만 반환
- **`ext` 없는 요청의 결과가 기존과 동일** — 갤러리 회귀 방지 장치
- `ext=png` → 400
- `data.list_images()`의 시그니처가 3-인자로 유지됨을 확인하는 계약 테스트
  (이후 누군가 필터를 provider로 옮기는 것을 막기 위함입니다)

**클라이언트** — 새 테스트 프레임워크는 도입하지 않습니다. 홈 Flask mock을
대상으로 실행해 파일이 디스크에 생성되는지 확인합니다.

**브라우저** — Playwright로 skewvoir 갤러리를 열어 새 헤더가 붙은 상태에서
이미지가 정상 렌더링되는지 확인합니다. §4.1에서 근거가 명세뿐이라고 밝힌
주장을 실제로 검증하는 단계입니다.

## 10. 부수 작업 — `api-tokens.md`의 SSO 서술 정리 (별도 커밋)

`docs/back-end/api-tokens.md`는 존재하지 않는 SSO 로그인 흐름을 기술하고
있습니다. **문서 및 주석만 수정하며 인증 동작은 변경하지 않습니다.**

| 위치 | 현재 서술 | 실제 동작 |
| --- | --- | --- |
| `api-tokens.md:42` | `/login`, `/static/*`은 공개 경로로 인증 생략 | `/login` 라우트는 존재하지 않습니다(`_auth/routes.py:7`). `_attach_identity`에는 공개 경로 허용 목록이 없습니다 |
| `api-tokens.md:46` | 미인증 비 API 요청은 SSO 로그인으로 리다이렉트 | 그대로 통과시켜 SPA mount로 넘깁니다(`_auth/middleware.py:136-142`) |
| `_auth/middleware.py:26` | `fall through to SSO` | 쿠키 신원 확인으로 넘어갑니다 |

`middleware.py:136-142`의 주석은 이 서술이 단순히 낡은 것이 아니라 **이미
철회된 동작**임을 밝히고 있습니다. Phase 3에서 그 자리에 리다이렉트를 넣었다가
브라우저가 앱과 SSO 사이를 무한히 오갔던 사례가 기록되어 있습니다.

지금 고치는 이유는 새 안내 문서가 `api-tokens.md`를 인증 파트의 필독 문서로
링크하기 때문입니다. 이 문서를 처음 읽는 Python 사용자에게 존재하지 않는 로그인
리다이렉트를 설명하게 두지 않습니다.

msr_image 작업과 diff를 섞지 않도록 **별도 커밋**으로 처리합니다.

## 11. 채택하지 않은 대안

| 대안 | 기각 사유 |
| --- | --- |
| `GET /api/msr-images/archive` (zip 스트리밍) | 실행당 수십 장 규모에서는 이득이 없습니다. 새 스트리밍 경로와 메모리·타임아웃 프로파일이 생기고, 기존 엔드포인트가 이미 하는 일을 하는 두 번째 방법이 됩니다. "수천 장" 요구가 실제로 등장하면 재검토합니다 |
| 새 탐색 엔드포인트 신설 | `meas-hist/search`가 동일한 상위 키를 이미 받습니다(§2.1) |
| `ext` 필터를 provider로 | 사무실 `office.py` 복사본 전부가 재동기화 대상이 됩니다(§5.1) |
| `Content-Disposition: attachment` | 갤러리의 `<img>`·`fetch()` 경로에 불필요한 위험을 만듭니다. 대상 사용자에게 이점은 동일합니다(§4.1) |
| 클라이언트에서 `requests` 사용 | 사용자 PC에 `pip install`이 불가능할 수 있습니다(§6) |
| rate limit 완화 | `msr_image`는 이미 면제되어 있습니다. 실측으로 확인했습니다(§2.2) |
| Java 예제 | 사용자 요청으로 제외했습니다. Python과 `curl` 예시로 충분합니다 |

## 12. 관련 파일

| 파일 | 역할 |
| --- | --- |
| `back_dev_home/msr_image/routes.py` | 변경 대상 — 헤더 1건, 필터 1건 |
| `back_dev_home/msr_image/data.py` | **변경 금지** — provider 시그니처 유지 |
| `back_dev_home/msr_image/providers/office_example.py` | **변경 금지** |
| `back_dev_home/__init__.py` | rate limit 면제 근거 (읽기 전용) |
| `back_dev_home/_auth/middleware.py` | Bearer 인증 경로, §10의 주석 수정 대상 |
| `back_dev_home/meas_hist/routes.py` | 탐색 엔드포인트 (읽기 전용) |
| `scripts/clients/msr_image_download.py` | 신규 |
| `docs/back-end/msr-image-download.md` | 신규 |
| `docs/back-end/api-tokens.md` | §10 수정 대상 |
