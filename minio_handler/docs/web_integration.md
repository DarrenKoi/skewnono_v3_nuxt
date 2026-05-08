# MinIO를 웹 서버와 통합하기

이 문서는 Flask (또는 다른 web framework) 위에서 MinIO를 어떻게 활용해
파일을 받고 / 보관하고 / 내려주는가를 패턴 단위로 정리합니다.

가정:

- web server: Flask (이 repo의 `api/` blueprint)
- storage: AIstor / MinIO at `aistor-api.lake.skhynix.com`
- bucket = `user`, prefix = `2067928/`
- application은 `MinioObject(bucket="user", prefix="2067928/")` 사용

## 아키텍처 결정: 누가 byte를 만지는가

가장 먼저 정해야 할 것: **파일 byte가 backend를 통과하는가, 아니면 클라이언트가
MinIO와 직접 통신하는가.**

```
[Pattern A: backend proxies]
client ─── multipart/form-data ──→ Flask ─── put_object ──→ MinIO
client ←──── streamed bytes ───── Flask ←─── get_object ──── MinIO

[Pattern B: client direct via presigned URL]
client ──── POST /upload-url ──→ Flask
       ←─── presigned PUT URL ───
client ──── PUT raw bytes ──────────────────→ MinIO

client ──── GET /download/<id> ──→ Flask
       ←─── 302 redirect to presigned GET ──
client ──── GET signed URL ──────────────────→ MinIO
```

Pattern A를 선택하는 경우:

- 작은 파일 (< 수 MB) 이고 빈도가 낮음
- byte를 backend에서 가공/검증해야 함 (이미지 리사이즈, 바이러스 스캔)
- 사용자 인증/권한 체크가 byte 처리와 결합되어 있어야 함

Pattern B를 선택하는 경우:

- 큰 파일 (수십 MB ~ GB)
- 트래픽이 큼 (backend가 대역폭 병목)
- byte 변형이 필요 없음 (raw 저장)

대부분의 production application은 **둘 다** 씁니다. 사용자 첨부 파일은 B,
어드민이 올리는 정형 파일은 A 같은 식.

## Pattern A1: backend가 form upload 받기 (작은 파일)

```python
# api/routes.py
from flask import request
from minio_handler import MinioObject, load_config
from datetime import datetime, timezone
from uuid import uuid4

mo = MinioObject(config=load_config())   # bucket/prefix from minio_config.py

@api_bp.post("/upload")
def upload_file():
    f = request.files.get("file")
    if f is None:
        return {"error": "no file"}, 400

    timestamp = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    key = f"uploads/{timestamp}/{uuid4().hex}__{f.filename}"

    mo.put(
        key,
        f.read(),
        content_type=f.content_type or "application/octet-stream",
        metadata={
            "x-amz-meta-original-name": f.filename or "",
            "x-amz-meta-uploader": str(current_user_id()),
        },
    )
    return {"key": key}, 201
```

**주의점:**

- `f.read()`는 메모리에 전부 읽습니다. 파일 크기에 한도가 없으면 stream
  방식 (`f.stream`)으로 넘기세요. minio SDK는 file-like object를 받습니다.
- `f.filename`은 사용자가 보낸 값이라 신뢰할 수 없습니다. key의 일부로 쓸
  거면 sanitize: 영숫자/`_`/`-`/`.` 외 문자는 제거.
- Flask의 `MAX_CONTENT_LENGTH`로 application 단 size limit을 거세요.

## Pattern A2: backend가 download stream 내려주기

권한 체크 후 직접 stream으로 내려주고 싶을 때:

```python
from flask import Response, abort, stream_with_context

@api_bp.get("/files/<path:key>")
def download_file(key: str):
    if not user_can_read(current_user_id(), key):
        abort(403)
    if not mo.exists(key):
        abort(404)

    stat = mo.stat(key)
    response = mo.client.get_object("user", mo._resolve_key(key))

    @stream_with_context
    def gen():
        try:
            for chunk in response.stream(amt=64 * 1024):
                yield chunk
        finally:
            response.close()
            response.release_conn()

    return Response(
        gen(),
        mimetype=stat.content_type,
        headers={
            "Content-Length": str(stat.size),
            "Content-Disposition": f'attachment; filename="{key.rsplit("/", 1)[-1]}"',
        },
    )
```

`response.stream()`을 yield 하면 큰 파일도 메모리 적게 사용. `try/finally`로
connection 반드시 닫아 주세요.

## Pattern B1: 브라우저가 MinIO에 직접 업로드 (presigned PUT)

backend는 짧은 시간만 살아 있는 PUT URL만 발급하고, 브라우저는 그걸 직접
사용합니다.

```python
from datetime import timedelta
from uuid import uuid4

@api_bp.post("/upload-url")
def issue_upload_url():
    body = request.get_json() or {}
    filename = body.get("filename", "upload.bin")
    content_type = body.get("content_type", "application/octet-stream")

    today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    key = f"uploads/{today}/{uuid4().hex}__{sanitize(filename)}"

    url = mo.presigned_put_url(key, expires=timedelta(minutes=10))
    return {"url": url, "key": key, "content_type": content_type}
```

```js
// frontend
const file = inputEl.files[0];
const meta = await fetch("/api/upload-url", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({filename: file.name, content_type: file.type}),
}).then(r => r.json());

await fetch(meta.url, {method: "PUT", body: file});
// 업로드 완료 후 backend에 알리고 싶으면 별도 endpoint 호출
await fetch("/api/upload-complete", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({key: meta.key}),
});
```

장점:

- backend가 byte를 처리하지 않음 → CPU/대역폭/메모리 절약
- 큰 파일도 그대로 동작
- backend는 인증/권한 체크와 key 발급만 담당

단점:

- 진행률 / 검증을 backend가 모름. 클라이언트가 끝났는지 알리는 단계가 추가됨
- file size limit을 강제하려면 presigned POST policy를 써야 함 (PUT URL은
  size 제한이 없음). 작은 위험은 있음

## Pattern B2: 브라우저가 MinIO에서 직접 다운로드 (presigned GET)

```python
@api_bp.get("/download/<file_id>")
def redirect_download(file_id: str):
    record = lookup_file_record(file_id)        # DB에서 메타데이터/권한 조회
    if not record or not user_can_read(current_user_id(), record.key):
        abort(403)

    url = mo.presigned_get_url(
        record.key,
        expires=timedelta(minutes=5),
        response_headers={
            "response-content-disposition":
                f'attachment; filename="{record.original_name}"',
        },
    )
    return redirect(url, code=302)
```

브라우저는 `/download/<id>` URL을 bookmark/공유하고, 클릭마다 새 5분 URL이
발급되며 MinIO로 redirect. backend는 byte를 한 번도 만지지 않습니다.

## CORS 설정 — 브라우저 직접 통신을 허용하기 위한 필수 단계

브라우저에서 `fetch(presignedUrl, ...)`를 직접 호출하려면 MinIO bucket의
CORS 설정이 우리 web app origin을 허용해야 합니다. CORS는 server-side
정책으로 bucket 단위에 등록합니다.

```python
# bucket admin 권한이 있을 때
import json

cors = {
    "CORSRules": [
        {
            "AllowedOrigins": ["https://app.lake.skhynix.com"],
            "AllowedMethods": ["GET", "PUT"],
            "AllowedHeaders": ["*"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 3000,
        }
    ]
}

# minio-py에는 set_bucket_cors 헬퍼가 있음
mo.client.set_bucket_cors("user", json.dumps(cors))
```

**준비물 체크리스트:**

- [ ] `AllowedOrigins`에 우리 web app의 정확한 origin (`http://`/`https://`,
      포트 포함)
- [ ] `AllowedMethods`: PUT(upload), GET(download)
- [ ] `AllowedHeaders`: `*` 또는 적어도 `Content-Type`, `Authorization` 등
- [ ] `ExposeHeaders`: 클라이언트가 읽을 응답 header. multipart upload하면
      `ETag` 필수

CORS 권한도 bucket admin 권한이 필요합니다. 없다면 bucket 관리자에 요청.

## 큰 파일: multipart upload

5 GiB 이상은 multipart upload만 가능합니다. 그 이하라도 수십 MB부터는
multipart가 빠르고 안정적이며, 일부 part가 실패해도 그 part만 재시도
가능합니다.

minio-py의 `put_object` / `fput_object`는 자동으로 multipart로 분할합니다
(`part_size`로 조정). 그러나 브라우저에서 직접 업로드하면서 multipart의
이점을 누리려면 backend가 part별 presigned URL을 발급해 주어야 합니다.

```python
# 1. backend: multipart upload 시작
upload_id = mo.client._create_multipart_upload("user", key, headers={...})

# 2. backend: 각 part마다 presigned URL 발급
part_urls = [
    mo.client.get_presigned_url(
        "PUT", "user", key, expires=timedelta(hours=1),
        extra_query_params={"uploadId": upload_id, "partNumber": str(i)},
    )
    for i in range(1, num_parts + 1)
]

# 3. 클라이언트: 각 URL에 PUT, ETag 받음

# 4. backend: parts 정보 받아 complete
mo.client._complete_multipart_upload("user", key, upload_id, parts)
```

minio-py에서 multipart 저레벨 API는 internal하게 분류되어 있어 안정성이
조금 떨어집니다. 프로덕션에서 브라우저 multipart가 필요하면 다음 두 가지를
고려하세요.

1. boto3 (`generate_presigned_url("upload_part", ...)`)를 같이 사용 — S3
   compatible이라 그대로 동작
2. browser SDK (예: AWS SDK for JavaScript의 `Upload` 클래스)를 사용

대부분의 application은 단일 PUT으로 충분 — 일반 첨부, 사진, 문서 등은
모두 단일 PUT 범위입니다.

## 비동기 처리 패턴 (worker queue)

업로드 직후 무거운 작업 (썸네일 생성, OCR, ML 추론)이 필요하면 다음 흐름이
표준입니다.

```
client ──→ backend ──→ MinIO PUT
                  └──→ Redis/SQS에 "process this key" 메시지
                              ↓
                       worker process (별도 컨테이너)
                              ├ MinIO get_object
                              ├ 처리
                              └ MinIO put_object (결과 key)
```

장점:

- web request 응답은 즉시 (key + status="processing")
- worker는 독립적으로 scale, 실패 시 재시도 / dead-letter queue
- byte는 항상 MinIO에 있고, 메시지는 key만 들고 다님 → 가볍고 안전

이 repo의 `airflow_mgmt`도 이 패턴을 응용한 형태입니다 (Airflow가 worker
역할). Redis queue를 쓰면 RQ / Dramatiq, AWS-style이면 SQS / Celery.

## ETag와 conditional GET (cache)

MinIO가 돌려주는 `ETag` header는 객체 body의 hash입니다. `get_object`에
`If-None-Match` header를 보내면 같은 객체일 때 `304 Not Modified`를 받아
대역폭을 아낄 수 있습니다.

CDN을 앞에 두면 자동으로 활용됩니다. backend가 byte를 stream할 때 ETag를
응답에 그대로 forward 하면 브라우저 캐시도 효율적으로 동작합니다.

```python
stat = mo.stat(key)
response_headers = {
    "ETag": stat.etag,
    "Cache-Control": "public, max-age=3600",
    ...
}
```

## Range request — video / 큰 파일 streaming

video player는 파일을 byte range로 잘라 받습니다. backend가 mediating할 때:

```python
@api_bp.get("/video/<key>")
def stream_video(key: str):
    range_header = request.headers.get("Range")  # "bytes=1024-65535"
    if range_header:
        start, end = parse_range(range_header)
        length = end - start + 1
        body = mo.get(key, offset=start, length=length)
        return Response(body, status=206, headers={
            "Content-Range": f"bytes {start}-{end}/{stat.size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Content-Type": stat.content_type,
        })
    # 전체 다운로드 fallback
    ...
```

또는 그냥 presigned GET URL을 주면 MinIO가 직접 range request를 처리합니다.
간단하고 backend 부하가 없어 더 권장됩니다.

## CDN 앞에 두기

같은 객체를 여러 사용자가 자주 읽는다면 CDN(예: CloudFront, Akamai, 또는
사내 CDN)을 MinIO 앞에 두면 latency와 비용이 모두 줄어듭니다.

흐름:

```
client ──→ CDN edge ──cache hit──→ client
                  └──cache miss──→ MinIO origin
```

핵심 설정:

- presigned URL을 CDN 너머로 패스하려면 CDN이 query string을 cache key에
  포함하지 않도록 설정 (대부분 default가 그렇지 않음)
- public 객체라면 plain URL이 가장 단순. CDN cache hit률 최고
- private 객체라면 CDN 자체에서 인증을 처리 (signed cookies / signed URL)
  하거나, 짧은 presigned URL을 매번 발급

기업 내부망 사용이면 CDN 없이 MinIO만으로도 충분합니다.

## 보안 함정

### SSRF — 사용자 입력으로 임의의 URL을 fetch

> "이 URL의 파일을 받아서 저장해 줘" 같은 기능을 만들면, 공격자가 internal
> 주소(`http://169.254.169.254/`, `http://localhost:8080/`)를 보내 우리
> infra의 metadata나 사내 service에 접근할 수 있습니다.

대응: URL을 받아 fetch하기 전 host를 allowlist로 검사. 가능하면 사용자가
직접 PUT하게 만들고 backend는 fetch하지 않음.

### Path traversal in keys

> 사용자 입력을 key에 그대로 넣으면 `../../../other-tenant/file`처럼
> 빠져나갈 수 있습니다.

S3는 `/`를 단순 character로 다루므로 traversal이 file system처럼 동작하진
않지만, application logic이 key의 좌측을 신뢰하면 권한 우회가 됩니다.

대응: 사용자 입력은 key의 *오른쪽 끝*(filename 부분)에만 두고, 좌측은
backend가 강제. 그리고 좌측 prefix를 server-side에서 다시 검증.

```python
# ✗ 위험
key = f"uploads/{request.json['key']}"

# ✓ 안전
filename = sanitize_filename(request.json.get("filename", "upload.bin"))
key = f"uploads/{user_id}/{datetime.now(timezone.utc):%Y/%m/%d}/{uuid4().hex}__{filename}"
```

### Content-type spoofing

브라우저는 `Content-Type` 응답 header를 보고 inline 렌더링을 할지 판단
합니다. 사용자 업로드를 그대로 다른 사용자에게 보여 주는 application은:

- HTML 파일을 업로드하면 XSS 가능
- SVG는 JavaScript 포함 가능

대응:

- 업로드 시 server-side에서 magic bytes 검사
- 응답 시 `Content-Disposition: attachment`로 강제 다운로드
- 별도 storage origin을 사용 (`*.usercontent.example.com`처럼) — XSS가
  생겨도 main domain의 cookie에 접근 못 함

### Presigned URL leak

URL은 누구든 만료 전까지 사용 가능한 자격증명입니다. 로깅/스크린샷/
북마크/이메일에 그대로 남으면 위험. 짧은 만료 + audit log + 필요한 경우
access key 회전이 정석.

## 실용 체크리스트 — production 가기 전

- [ ] CORS 설정 완료 (해당 origin만 허용)
- [ ] Flask `MAX_CONTENT_LENGTH` 설정
- [ ] 사용자 입력으로 만든 key는 sanitize / 좌측 prefix 강제
- [ ] presigned URL 만료 짧게, 권한 체크 후 발급
- [ ] 큰 파일은 backend stream 또는 presigned PUT 사용 (메모리 폭발 방지)
- [ ] Lifecycle 또는 cron으로 임시 객체 정리
- [ ] download/upload 응답에 적절한 `Content-Type` / `Content-Disposition`
- [ ] 에러 시 MinIO error code를 노출하지 말고 application-level 메시지로
- [ ] secret key는 환경 변수 또는 secret manager에서, 코드에 하드코드 금지

## 다음 단계

- 코드 사용 예와 wrapper API: `usage.md`
- 개념 정리: `concepts.md`
- 데이터 조직 패턴: `data_management.md`
