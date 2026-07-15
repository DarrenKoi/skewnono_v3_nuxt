# MinIO 핵심 개념 (mental model)

이 문서는 MinIO를 처음 만날 때 가장 자주 헷갈리는 개념들을 정리합니다.
용어가 머리에 잡히면 다른 문서를 읽기 훨씬 수월합니다.

## 객체 저장소란?

전통적인 저장소 종류는 셋입니다.

| 종류 | 단위 | 접근 방식 | 예시 |
| --- | --- | --- | --- |
| **Block storage** | 고정 크기 block | low-level read/write at offset | EBS, iSCSI |
| **File system** | file + directory tree | open/read/write/seek, POSIX | NTFS, ext4, NFS |
| **Object storage** | object (key + bytes + metadata) | HTTP REST: PUT/GET/DELETE | S3, MinIO, GCS |

object storage는 directory 구조가 없고, file system이 가진 lock / append /
in-place edit / inode 같은 개념도 없습니다. 대신:

- 무한히 많은 object를 일정한 latency로 저장 가능 (수십 PB 규모)
- 객체 단위 atomic write — 부분 update 없음. write는 항상 전체 교체
- HTTP API라 어디서든 접근 가능, 서명을 통해 임시 권한 위임 (presigned URL)
- 검색은 prefix listing이 전부. SQL 같은 query는 없음

이 트레이드오프를 받아들이는 순간 web/data application의 파일 저장소로
가장 적합한 종류가 됩니다.

## Bucket / Object / Key

```
[bucket]   user
[key]      2067928/reports/2026/q1.pdf
[body]     <PDF bytes>
[metadata] content-type=application/pdf, x-amz-meta-author=daeyoung
```

- **bucket**: 최상위 namespace. cluster 안에서 unique. 권한과 lifecycle은
  bucket 단위로 적용됨.
- **key**: bucket 안에서 object를 찾는 문자열 식별자. URL path와 비슷하지만
  실제 directory tree는 아님.
- **body**: 실제 byte. 0 byte ~ 5 TiB 수준까지 단일 object로 저장 가능
  (대용량은 multipart upload).
- **metadata**: 객체에 함께 저장되는 작은 key/value 사전. body와 함께 PUT
  될 때만 설정되며, 나중에 따로 수정 불가 (재 PUT 필요).

## 폴더가 없다

`a/b/c.txt`는 **하나의 key 문자열**입니다. `a/`, `a/b/`라는 객체가 따로
존재하지 않습니다. console UI나 `list(recursive=False)`가 폴더처럼 보여
주는 건 단순히 `/` 기준으로 그룹핑한 뷰일 뿐입니다.

결과적으로:

1. 미리 디렉터리를 만들 필요 없음. `put("any/depth/file.txt", ...)` 즉시 동작
2. 같은 위치에 file과 "디렉터리"가 공존 가능 — `a/b`(파일)과 `a/b/c.txt`
   동시에 존재 가능. 실제 filesystem은 이걸 거부함
3. "비어 있는 폴더"는 없음 — 마지막 객체를 지우면 prefix 자체가 사라짐
4. "폴더 이름 변경"은 없음. 모든 객체를 새 key로 copy + 원본 delete 해야 함

## Metadata와 Tag

| 종류 | 저장 시점 | 수정 | 검색에 사용 가능? | 용도 |
| --- | --- | --- | --- | --- |
| user metadata (`x-amz-meta-*`) | PUT 시점만 | 재 PUT으로만 가능 | 직접은 불가 | 작은 부가 정보 (작성자, 버전 등) |
| object tags | 언제든 변경 가능 | tag만 별도 PUT | lifecycle filter, replication에 사용 가능 | 분류, 정책 적용 대상 표시 |
| system metadata | 자동 | 일부 자동 | 직접은 불가 | content-type, etag, last-modified 등 |

규칙: **검색 / 정책에 쓸 정보는 tag**, 단순 표시 정보는 metadata. 그 외엔
key 자체에 정보를 인코딩 (예: `2067928/2026/05/file.txt`).

## Versioning

bucket에 versioning을 켜면, 같은 key로 다시 `put` 했을 때 이전 객체가
사라지지 않고 "noncurrent version"으로 보존됩니다. delete도 실제 삭제가
아니라 "delete marker"라는 묘비석이 올라가는 식으로 동작합니다.

장점:

- 실수로 덮어쓰기/삭제 복구 가능
- audit trail
- "특정 시점의 상태"를 다시 읽기 가능

단점:

- 저장 공간 증가 (lifecycle의 `noncurrent_version_expiration`로 관리 필요)
- list/get 시 version_id를 명시해야 하는 경우 발생
- delete가 즉시 사라지는 게 아니라는 점이 익숙해지기까지 헷갈림

대부분 application은 versioning을 켜지 않고, 필요할 때 key 자체에 timestamp
나 hash를 넣어 새 객체로 보관하는 패턴을 씁니다 (`data_management.md` 참고).

## Consistency model

S3 (그리고 MinIO)는 모든 동작에 **strong read-after-write consistency**를
보장합니다. 즉 `put` 직후 `get`은 항상 최신 객체를 반환합니다. 과거에는
"eventual consistency"라는 미묘한 함정이 있었지만 2020년 이후 사라졌습니다.
오래된 블로그/StackOverflow에 나오는 "PUT 직후 즉시 GET하면 못 받을 수
있다"는 더 이상 사실이 아닙니다.

다만 list 호출은 약간 다릅니다.

- prefix listing은 거의 즉시 일관됨
- versioning bucket의 list-versions는 매우 큰 prefix에서 약간의 지연 가능

## Multi-tenancy via prefix

여러 사용자가 한 bucket을 공유하는 경우, 각자에게 prefix를 할당하는 것이
가장 흔한 패턴입니다. AIstor에서 우리에게 `user/2067928/`이 부여된 것도
이 패턴입니다.

- IAM/bucket policy로 prefix 단위 권한 부여
  - "이 user는 `user/2067928/*`에만 GetObject/PutObject 가능" 식
- lifecycle/replication도 prefix filter로 분리
- `list(prefix="2067928/")`로 자기 객체만 보임

prefix는 사용자가 자유롭게 더 잘게 나눌 수 있습니다.

```
user/2067928/datasets/...
user/2067928/uploads/...
user/2067928/exports/...
```

## Permission 모델 한눈에

크게 세 층입니다.

1. **Cluster admin** — MinIO root. 모든 작업 가능. 운영자만 보유
2. **Bucket policy** — bucket 자체에 붙는 JSON document. anonymous 접근 허용
   같은 *공개 read* 정책에 주로 사용
3. **IAM user / service account policy** — credential 별로 부여되는 정책.
   "이 access_key는 어떤 bucket의 어떤 prefix에 어떤 action이 가능"을 정의

application 코드는 service account access_key/secret_key를 받아서 동작
하므로, 정책 설정은 보통 다음 사항을 포함합니다.

- `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` on `arn:aws:s3:::user/2067928/*`
- `s3:ListBucket` with prefix condition `2067928/*`

bucket admin 권한 (`s3:PutBucketLifecycle`, `s3:PutBucketPolicy`, ...)은
*추가* 권한이며 보통 가지고 있지 않습니다. 정책 변경이 필요하면 bucket 관리자
요청이 정석입니다.

## Storage class / tier (AIstor / MinIO Enterprise)

AIstor / MinIO Enterprise는 다음과 같은 추가 기능을 제공합니다 (오픈소스
MinIO에는 일부만 있음).

- **Tiering**: lifecycle rule로 일정 기간이 지난 객체를 더 저렴한 cold tier
  로 자동 이동. application은 그대로 같은 key로 접근 가능 (latency만 증가)
- **Server-side replication**: 다른 cluster로 비동기 복제 (DR/지리적 분산)
- **Object lock / WORM**: 특정 기간 동안 변경/삭제 금지 (compliance)
- **Audit log**: 누가 어떤 객체에 무엇을 했는지 기록 (forensic)

대부분의 web application은 **standard tier + lifecycle expiration** 조합으로
충분합니다.

## 다음 단계

- 데이터를 어떻게 조직해서 넣을지: `data_management.md`
- web server에서 어떻게 활용할지: `web_integration.md`
- 직접 코드를 짜고 싶다면: `usage.md`
