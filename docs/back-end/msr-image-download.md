# MSR 이미지 다운로드 API

이 문서는 계측(MSR) 이미지를 SKEWNONO 웹 UI가 아니라 스크립트로 내려받으려는
사용자를 위한 안내입니다. 대상은 Python 또는 curl을 사용하는 사용자이며,
결과물은 사용자 PC에 저장되는 이미지 파일(jpg/tif)입니다.

## 1. 개요

`/api/msr-images`(목록/warm)와 `/api/msr-image`(개별 이미지)는 원래 skewvoir
갤러리 UI가 사용하던 엔드포인트이지만, `Authorization: Bearer` 토큰만 있으면
브라우저 없이도 그대로 호출할 수 있습니다. 이 문서가 다루는 시나리오는
"특정 lot/레시피/장비의 계측 이미지를 로컬 PC로 일괄 내려받기"이며,
결과는 API 응답이 아니라 디스크에 쓰인 파일입니다.

표준 라이브러리만 사용하는 참조 클라이언트가
`scripts/clients/msr_image_download.py`에 있습니다. 직접 curl을 조합해도
되고, 이 스크립트를 그대로 복사해 실행해도 됩니다.

## 2. 토큰 발급

API 호출에는 API 토큰이 필요합니다. 토큰은 **웹 UI의 설정(settings) 페이지 →
API tokens** 에서 발급하며, 응답에 담긴 평문(`plaintext`)은 **그 순간에만
표시**됩니다. 이후에는 서버가 SHA-256 해시만 보관하므로 다시 볼 수 없고,
분실 시 폐기 후 재발급해야 합니다.

발급에는 브라우저 세션이 필요합니다. `POST /api/account/api-tokens`는
`LASTUSER` 신원 쿠키로 식별된 사람의 브라우저 세션에서만 호출할 수 있고,
이미 발급된 토큰으로 인증한 호출은 403으로 거부됩니다
(`back_dev_home/api_tokens/routes.py:16-27`의 `_reject_token_auth`). 즉
**스크립트가 자기 토큰을 스스로 발급할 수는 없습니다** — 최초 1회는 반드시
누군가 브라우저로 로그인해 발급해야 합니다.

토큰 체계 전반(형식, 로깅, 권한 범위, 사무실 스왑 계약)은
[`api-tokens.md`](./api-tokens.md)를 참고합니다.

## 3. 4단계 흐름

```text
1. GET  /api/meas-hist/search   lot/recipe/eq/기간  → rows (eqp_ip, class_name, msr)
2. GET  /api/msr-images         ext=jpg             → 파일명 목록
3. POST /api/msr-images         names=[...]         → warm job (job_id)
4. GET  /api/msr-image          name=…               → 이미지 바이트
```

1번으로 어떤 MSR(계측 실행)이 대상인지 찾고, 그 `eqp_ip` / `class_name` /
`msr`를 2~4번에 그대로 재사용합니다. 이 순서가 왜 중요한지는 §6에서
설명합니다.

## 4. 파라미터 표

### 4.1 `GET /api/meas-hist/search`

| 파라미터 | 설명 | 비고 |
| --- | --- | --- |
| `lot` | 검색할 lot | **`lot_id`(예: `KPB266344`)와 일치하며, `lot_cd`(예: `KPB`)를 넣으면 오류 없이 0건이 반환됩니다** |
| `recipe` | 레시피 이름 |  |
| `eq` | 장비 id(예: `ECDX285`) |  |
| `msr` | MSR 식별자 |  |
| `from` / `to` | 조회 기간(`YYYY-MM-DD`) |  |
| `limit` | 처리할 MSR 최대 개수(기본 50) |  |

> **`lot`은 `lot_id`이지 `lot_cd`가 아닙니다.** 이 둘을 헷갈리는 것이 이
> 흐름에서 사용자의 오후를 가장 쉽게 날려버리는 실수입니다. `lot_cd`는
> 3~4글자 코드(예: `KPB`)이고 `lot_id`는 그 코드 뒤에 로트 번호가 붙은 전체
> 값(예: `KPB266344`)입니다. `search_meas_hist`의 lot 필터는
> `row["lot_id"]`와만 대소문자 무시 정확히 일치하는지 비교하므로, `lot_cd`를
> 넣으면 **오류도, 경고도 없이 0건**이 돌아옵니다. 결과가 비어 있으면 가장
> 먼저 의심할 것은 이것입니다.

### 4.2 `GET /api/msr-images` — 이미지 이름 목록

| 파라미터 | 필수 | 설명 |
| --- | --- | --- |
| `eqp_ip` | 예 | 장비 IP(허용된 서브넷 내에서만 유효) |
| `class_name` | 예 | 레시피 클래스 |
| `msr` | 예 | MSR 식별자 |
| `ext` | 아니오 | `jpg`(`.jpg`/`.jpeg`) 또는 `tif`(`.tif`/`.tiff`)로 필터링. 그 외 값은 400 |

응답은 `{msr, class_name, images: [...], total}` 형태입니다.

### 4.3 `POST /api/msr-images` — 캐시 warm job 시작

| 필드(JSON body) | 필수 | 설명 |
| --- | --- | --- |
| `eqp_ip` | 예 | 장비 IP |
| `class_name` | 예 | 레시피 클래스 |
| `msr` | 예 | MSR 식별자 |
| `names` | 아니오 | 이 목록의 파일만 받아옴(scoped warm). 생략하거나 빈 배열이면 전체를 받아옵니다. **최대 500개**(`_MAX_JOB_NAMES`, `routes.py`) — 넘으면 400 |

202와 함께 `{job_id}`가 반환됩니다. 500개를 넘는 목록은 여러 번의 POST로
나눠 보내야 하며, 참조 클라이언트는 이를 자동으로 배치 처리합니다(§7).

### 4.4 `GET /api/msr-images/<job_id>` — job 상태 폴링

응답은 `{job_id, status: "running"|"done"|"error", done, total, ok, ng,
failures: [{name, error}, ...]}` 입니다. `status`가 `"running"`이 아니게 될
때까지 폴링합니다.

### 4.5 `GET /api/msr-image` — 이미지 바이트

| 파라미터 | 필수 | 설명 |
| --- | --- | --- |
| `eqp_ip` | 예 | 장비 IP |
| `class_name` | 예 | 레시피 클래스 |
| `msr` | 예 | MSR 식별자 |
| `name` | 예 | 파일명(최대 256자) |

응답 본문은 이미지 바이트이며, `Content-Disposition: inline;
filename="..."`가 붙어 있어 `curl -OJ`로 파일명을 그대로 받을 수 있습니다.

## 5. curl 예시

단일 이미지를 파일명 그대로 저장합니다.

```bash
curl -OJ \
  -H "Authorization: Bearer $SKEWNONO_TOKEN" \
  "http://skewnono.skhynix.com/api/msr-image?eqp_ip=10.44.9.153&class_name=CNT&msr=20260803_RCP01_KPB266344_ECDX285&name=001.jpg"
```

> **비-ASCII 파일명 주의**: 이미지 파일명에 한글 등 비-ASCII 문자가 있으면
> `Content-Disposition`의 ASCII `filename="..."` 파라미터는 `???.jpeg`
> 같은 자리표시자로 채워지고, 실제 이름은 `filename*=UTF-8''...` 쪽에만
> 담깁니다(RFC 6266). `curl -OJ`는 ASCII 파라미터만 읽으므로 이런 경우
> `?`가 포함된 이름으로 저장을 시도하며, 이는 Windows에서 유효한 파일명이
> 아닙니다. 비-ASCII 파일명이 섞여 있을 수 있다면 `curl -OJ` 대신
> `scripts/clients/msr_image_download.py`를 쓰는 편이 안전합니다 — 이
> 클라이언트는 `filename*=UTF-8''` 쪽이 아니라 목록 조회로 얻은 원래
> 이름을 그대로 사용해 저장하므로 이 문제를 겪지 않습니다.

`ext=jpg`로 미리보기 가능한 파일만 목록을 받습니다.

```bash
curl -H "Authorization: Bearer $SKEWNONO_TOKEN" \
  "http://skewnono.skhynix.com/api/msr-images?eqp_ip=10.44.9.153&class_name=CNT&msr=20260803_RCP01_KPB266344_ECDX285&ext=jpg"
```

받아올 파일을 `names`로 좁혀서 warm job을 시작합니다.

```bash
curl -X POST \
  -H "Authorization: Bearer $SKEWNONO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "eqp_ip": "10.44.9.153",
    "class_name": "CNT",
    "msr": "20260803_RCP01_KPB266344_ECDX285",
    "names": ["001.jpg", "002.jpg"]
  }' \
  "http://skewnono.skhynix.com/api/msr-images"
```

## 6. Python 예시

`scripts/clients/msr_image_download.py`는 표준 라이브러리만 사용하는
참조 클라이언트입니다. 사내 통제된 PC에는 `pip install`이 불가능할 수 있어,
이 파일 하나만 복사해 실행할 수 있도록 만들어졌습니다.

```bash
export SKEWNONO_TOKEN=skn_...
python scripts/clients/msr_image_download.py --lot KPB266344 --ext jpg --out ./images
```

`--lot`/`--recipe`/`--eq`/`--msr` 중 하나 이상, 그리고 `SKEWNONO_TOKEN`
환경 변수가 필요합니다. `--ext`를 생략하면 jpg와 tif 전부를 받습니다.

핵심은 `download_msr()` 하나가 한 MSR에 대해 **목록 조회 → scoped warm →
개별 fetch** 순서를 그대로 구현한다는 점입니다.

```python
def download_msr(base, token, row, out_dir, *, ext=None) -> tuple[int, int]:
    """List, warm, then fetch one MSR's images. Returns (written, failed)."""
```

즉 함수 이름 그대로: 먼저 `/api/msr-images`로 이름을 나열하고, 아직 없는
파일만 골라 500개씩 나눠 `warm()`(=`POST /api/msr-images`)을 호출한 뒤,
`/api/msr-image`로 하나씩 받아 `.part` 파일에 쓰고 원자적으로
`rename`합니다. 이미 디스크에 있는 파일은 건너뛰므로, 스크립트를 다시
실행하면 이어받기가 됩니다.

## 7. 3번(warm)을 먼저 호출하면 안 되는 이유

4단계 흐름의 순서는 "목록(2) → scoped warm(3) → fetch(4)"입니다. 이 순서를
뒤집거나 건너뛰면 다음 세 가지 방식으로 비용이 커집니다.

- **warm을 건너뛰고 4번만 반복 호출**하면 이미지 하나마다 장비 FTP로의
  직렬 왕복이 발생합니다. N개 이미지는 N번의 순차 왕복이 되며, warm job은
  같은 파일들을 여러 연결로 병렬 수신하므로 이 차이는 체감상 큽니다.
- **2번(목록) 없이 3번(warm)을 먼저 호출**하면, warm job은 `names`가 없을
  때 서버가 자체적으로 장비를 다시 나열합니다(`_run_download`가
  `names is None`이면 `data.list_images`를 호출). 이후 클라이언트가 어차피
  2번을 호출해 자기만의 목록을 받아야 하므로, 결과적으로 **FTP 목록 조회가
  한 번이 아니라 두 번** 일어납니다.
- **`names`로 범위를 좁히지 않은(unscoped) warm**은 `ext` 필터로 걸러냈어야
  할 파일까지 장비에서 받아와 캐시에 채웁니다. 예를 들어 `ext=jpg`만
  필요한데 unscoped warm을 부르면 tif 파일까지 통째로 받아오는 낭비가
  생깁니다.

그래서 참조 클라이언트는 항상 먼저 `/api/msr-images`로 이름을 얻고, 그 중
아직 캐시에 없는 이름만 `names`에 담아 warm을 요청합니다.

## 8. TIFF 안내

브라우저는 TIFF를 렌더링하지 못합니다. `<img>` 태그나 `fetch()` + blob URL로
미리보기가 필요하다면 `ext=jpg`로 받은 파일만 사용해야 합니다. tif 원본이
필요한 경우(정밀 분석 등)에는 `ext=tif` 또는 `ext` 생략으로 받되, 웹에서
직접 열어보는 용도로는 쓸 수 없다는 점을 기억해야 합니다.

## 9. 오류 표

| 상태 | 의미 | 클라이언트 동작 |
| --- | --- | --- |
| `401 invalid_token` | 토큰이 잘못되었거나 폐기됨 | `search()` 단계라면 즉시 명확한 메시지와 함께 종료(재시도는 도움이 되지 않습니다). 이미지별 fetch 단계에서 토큰이 도중에 폐기된 경우에는 즉시 멈추지 않고 남은 이미지마다 오류를 한 줄씩 출력하며 계속 진행하다가, 모든 MSR을 처리한 뒤 종료 코드 1로 끝납니다 |
| `429` | 1단계 탐색 호출(`/api/meas-hist/search`)에서만 발생 가능 | backoff 후 재시도 |
| `503` | `SourceUnavailable` — 장비 FTP 접속 불가 | 해당 MSR을 보고하고 다음 MSR로 진행 |
| `404 unknown_job` | job 만료(`SKEWNONO_MSR_IMAGE_JOB_TTL`, 기본 1시간) | warm을 건너뛰고 직접 GET으로 진행 |
| job `status: "error"` | job 전체 실패 | GET은 그대로 진행합니다 |

마지막 행은 의도된 선택입니다. job 전체 실패와 파일별 실패는 서버에서
구분되며, job이 `error`로 끝나도 캐시는 부분적으로 채워져 있고 파일별
실패는 이후 GET에서 개별적으로 드러납니다. 따라서 클라이언트는 job 실패를
치명적 오류로 취급하지 않고 그대로 4번(fetch) 단계로 넘어갑니다.

## 10. rate limit

`/api/*`는 사용자당 **50 요청 / 5초**의 앱 전체 공유 예산을 가지지만,
`msr_image` 블루프린트(`/api/msr-images`, `/api/msr-image`,
`/api/msr-images/<job_id>`)는 이 예산에서 **면제**되어 있습니다. 갤러리
UI가 이미지 하나마다 GET을 날리는 흐름을 그대로 지원하기 위한 조치이며,
스크립트로 수십~수백 개의 이미지를 받아도 이 예산과는 무관합니다.

예산을 실제로 소비하는 것은 4단계 흐름의 **1번, `/api/meas-hist/search`
뿐**입니다. 검색을 반복 호출하는 루프를 짤 때만 50 req/5s를 신경 쓰면
됩니다. 이 면제는 회귀 테스트로 고정되어 있습니다
(`tests/test_rate_limit.py:61`,
`test_msr_image_stays_exempt_from_the_application_budget`).
