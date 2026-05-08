# MinIO 데이터 관리 패턴

이 문서는 MinIO에 객체를 어떻게 *조직해서* 넣을 것인가를 다룹니다.
storage 자체는 자유로워도, key 설계와 정책을 잘못 잡으면 6개월 뒤
"이 파일을 어떻게 다시 찾지"라는 문제로 돌아옵니다.

기본 환경 가정:

- bucket: `user`
- 우리 prefix: `2067928/`
- application은 `MinioObject(bucket="user", prefix="2067928/")`를 사용

## Key naming: 이름 한 줄로 의미를 담는다

### 핵심 원칙

1. **key는 변경 불가능하다고 가정한다.** rename이 없는 세계라, 일단 PUT 한
   key는 그 이름 그대로 살아간다. 의미가 바뀌면 새 key로 copy해야 한다.
2. **prefix listing이 빈번한 path를 앞에 둔다.** S3는 prefix-based listing이
   유일한 query 수단이다. 자주 묶어서 보는 차원이 prefix의 좌측에 있어야 한다.
3. **사람이 읽을 수 있게.** key가 url에 그대로 박히는 경우가 많다. URL-safe
   문자만 사용 (ASCII 영숫자, `-`, `_`, `.`, `/`).
4. **고정 width segment를 쓴다.** `2026/05` ↔ `2026/5` 같은 건 정렬과
   listing 일관성을 깨뜨린다. 항상 zero-padding.

### 좋은 key 예시와 나쁜 key 예시

```
✓ 2067928/datasets/wafer/2026/05/04/lot-AB12.parquet
✓ 2067928/uploads/2026-05-04T13-22-08Z__user-1234__report.pdf
✓ 2067928/sha256/ab/cd/abcd1234...ef.bin    (content-addressed)

✗ 2067928/Daeyoung's reports/Final v2 (copy).pdf   (공백, 한글, 특수문자)
✗ 2067928/2026/5/4/file.parquet                     (zero-pad 빠짐)
✗ user.2067928.datasets.wafer.parquet                (prefix 활용 못함)
```

### 흔한 좌측 prefix 차원

| 차원 | 예시 segment | 사용 시점 |
| --- | --- | --- |
| 사용자 / tenant | `2067928/` | multi-tenant bucket의 격리 |
| 도메인 / app | `datasets/`, `uploads/`, `exports/` | 같은 사용자가 여러 카테고리를 가질 때 |
| 엔티티 종류 | `wafers/`, `users/`, `experiments/` | 도메인 안에서 분류 |
| 시간 | `2026/05/04/` 또는 `2026-W18/` | 시간 기반 lookup, partitioning |
| 식별자 | `lot-AB12/`, `userid-9991/` | 같은 entity의 여러 파일을 묶음 |

좌측에 가까울수록 *권한 / lifecycle / replication 정책*에 사용되기 쉬우므로,
이런 정책 단위가 무엇인지를 먼저 정한 뒤 좌측 차원을 결정합니다.

## 시간 기반 partitioning

데이터 분석 / 로그 / 일별 산출물은 시간을 prefix에 넣는 것이 거의 항상
정답입니다. 이유:

- listing이 빨라짐 (자연스러운 sharding)
- lifecycle 적용 단위가 깔끔함 (prefix 단위로 N일 retention)
- 분석 도구(Spark, DuckDB 등)가 partition discovery를 자동으로 함

### 권장 형태

```
2067928/datasets/<domain>/year=2026/month=05/day=04/<file>
2067928/logs/<service>/2026/05/04/<file>.jsonl
```

`year=...` 형태는 Hive partitioning이라 부르며 분석 도구 친화적입니다.
단순 사용에는 그냥 `/2026/05/04/`가 짧고 충분합니다.

### 시간 vs 식별자, 어느 쪽을 좌측에?

- 시간이 좌측: 로그/지표처럼 "최근 N일을 자주 본다" → `2026/05/04/<id>.json`
- 식별자가 좌측: 한 entity의 history를 묶어 본다 → `wafers/lot-AB12/2026/05/04.json`

용도가 둘 다라면 둘 중 하나로 통일하고, 다른 한 쪽은 검색 인덱스(예:
OpenSearch)나 DB에 따로 두는 편이 깔끔합니다. S3 안에서 두 차원을 동시에
지원하려면 객체를 두 번 저장하거나 alias 시스템을 자체 구현해야 하는데,
대개 그럴 가치가 없습니다.

## Content-addressable storage (hash-based key)

같은 파일이 여러 사용자/요청에 의해 업로드되는 application은 SHA-256 hash를
key로 쓰는 패턴이 강력합니다.

```
2067928/sha256/ab/cd/abcd1234ef.....bin
```

장점:

- 같은 내용을 두 번 올려도 동일 key → 자동 dedup
- key가 곧 무결성 검증 (다운로드 후 hash 재계산)
- "이 hash의 파일 있어?"라는 fast lookup 가능 (`exists`)

단점:

- 파일 이름이 의미 없는 hash라, 별도 metadata DB가 필수
- streaming write 어렵 (전체를 받기 전까지 hash가 안 정해짐) — 임시 key에
  쓴 뒤 hash 계산 후 copy하는 두 단계가 필요

웹 application에서 사용자가 같은 첨부 파일을 여러 곳에 올릴 가능성이 있다면
거의 항상 권장됩니다.

## Tags vs metadata vs prefix — 언제 무엇을 쓰는가

세 가지가 모두 "객체에 부가 정보를 붙인다"는 점에서 비슷해 보이지만, 의도와
한계가 다릅니다.

### 결정 기준

| 정보의 특징 | 권장 |
| --- | --- |
| 자주 검색/필터의 기준이 됨 | **prefix** (key의 좌측 segment) |
| lifecycle / replication / policy의 적용 대상 식별 | **tag** |
| 객체 자체에 영원히 붙어 다닐 작은 부가 정보 | **metadata** |
| 변경 가능성이 있음 | **tag** (metadata는 재 PUT 필요) |
| 큰 텍스트, 검색이 필요한 풍부한 메타 | **외부 DB / 검색 엔진** |

### 예시

```python
# user_id, project_id로 자주 묶어서 본다 → prefix에 넣음
"2067928/projects/proj-001/datasets/wafer.parquet"

# "민감 정보 포함 여부"는 lifecycle/replication에 영향 → tag
mo.client.set_object_tags("user", "2067928/.../report.pdf",
    Tags(for_object_tagging=True).update({"sensitivity": "internal"}))

# 작성자 / 업로드 클라이언트 버전 → metadata
mo.put("doc.pdf", body, metadata={"x-amz-meta-author": "daeyoung",
                                  "x-amz-meta-client-version": "1.4.2"})

# 풍부한 검색 (전문 검색, 복잡한 query) → OpenSearch
# (SK hynix 환경에서는 ops_store 패키지를 함께 사용)
```

## Versioning을 쓸 것인가, key에 timestamp를 박을 것인가

같은 논리적 파일의 여러 버전을 보관하고 싶을 때 두 선택지가 있습니다.

| | bucket versioning | timestamped key |
| --- | --- | --- |
| 사용성 | "같은 path"로 항상 최신 보임 | URL이 항상 정확한 버전 가리킴 |
| 복구 | 손쉬움 | 단순 — 그냥 다른 key를 GET |
| storage 소비 | versioning lifecycle 필요 | 자체 cleanup 필요 |
| audit | bucket-wide, 자동 | 직접 metadata DB로 관리 |
| 권한 | bucket admin 필요 | 누구나 사용 가능 |

application 단의 단순함이 최우선이라면 **timestamped key**를 권장합니다.

```
2067928/configs/app.json                          (포인터, 항상 최신)
2067928/configs/history/app__2026-05-04T13-22.json (보관본)
```

PUT 시 두 곳에 모두 쓰거나, history만 쓴 뒤 latest를 가리키는 작은 metadata
record(다른 DB)를 갱신합니다. application이 한두 개뿐이라면 아예 history
key 하나로 끝내고 latest 조회는 `list(prefix=...)` 후 가장 최신 timestamp를
선택하는 방법도 단순합니다.

## Retention 정책

사내 환경에서는 lifecycle 정책을 직접 등록할 권한이 없으므로, 아래 표는
"각 prefix를 어느 주기로 cleanup할지" 결정하는 가이드입니다. 실제 삭제는
`recipes.md`의 "정기 cleanup (lifecycle 대용)" 패턴(Airflow DAG / cron)으로
돌립니다.

| 데이터 종류 | retention 추천 | 비고 |
| --- | --- | --- |
| application 로그 | 7~30일 | 분석 끝난 뒤 가치 급감 |
| 분석 임시 산출물 | 7일 | DAG가 재계산 가능하다면 |
| 사용자 업로드 | 영구 또는 사용자 삭제 시점에만 | 함부로 자동 삭제 금지 |
| 보고서 / 결과물 | 180일 ~ 3년 | 비즈니스 요구에 맞춤 |
| 감사 로그 | 365일+ | 법적 요건 |
| ML training data snapshot | 영구 (혹은 archive tier) | reproducibility |

기본 default는 "영구 보관 + cleanup 미적용"이고, **명시적인 retention
요구사항이 있을 때만** cleanup DAG에 prefix를 추가합니다. 자동 삭제는
일반적인 data loss bug보다 더 조용히 사고를 만듭니다.

## Soft delete 패턴

사용자가 "삭제"를 누른 직후 즉시 삭제하지 않고, 일정 기간 복구 가능 상태로
두는 패턴입니다.

방법 1: **prefix 이동**

```python
# "삭제"는 trash prefix로 copy + 원본 delete
mo.client.copy_object("user", "2067928/trash/2026/05/04/report.pdf",
                       CopySource("user", "2067928/active/report.pdf"))
mo.delete("active/report.pdf")
```

`2067928/trash/`는 cleanup DAG에 30일 retention으로 등록해 두면 자동 정리
(사내 환경에서는 lifecycle 권한이 없으므로 `recipes.md`의 `purge_older_than`
패턴으로 처리합니다).

방법 2: **tag로 표시**

```python
mo.client.set_object_tags("user", "2067928/active/report.pdf",
    Tags(for_object_tagging=True).update({"deleted": "true",
                                          "deleted_at": "2026-05-04T13:22"}))
```

사내 환경에서는 tag-기반 lifecycle filter를 등록할 권한이 없어 이 방법은
별도 cleanup job에서 list + tag 검사 + delete를 직접 구현해야 합니다.
prefix 이동(방법 1)이 cleanup도 한 줄로 끝나고 권한/storage 분리에도
유리해 사실상 우리 환경의 기본 선택지입니다.

## Idempotency: 같은 key 덮어쓰기 vs 새 key

같은 PUT을 두 번 호출하면 어떻게 되는가는 application 의도에 따라 다릅니다.

- **idempotent overwrite를 원할 때** — 같은 의미의 데이터, 같은 key:
  `2067928/configs/app.json`. 두 번째 PUT은 첫 번째를 silently 교체.
  네트워크 재시도가 안전.
- **append/log를 원할 때** — 새 key 마다 timestamp/UUID:
  `2067928/events/2026-05-04T13:22:08.123Z__<uuid>.json`. 충돌 없이
  자연스럽게 append됨.

S3 자체는 append를 지원하지 않으므로, "실시간 로그를 한 객체에 계속 쓰기"
같은 시나리오는 batch로 모아 한 번에 PUT하거나, key를 시간 단위로 나누는
패턴으로 우회합니다.

## 자주 하는 실수

- **공백·한글·특수문자.** key는 URL/CLI/로그에 그대로 노출됩니다. 가능하면
  `[A-Za-z0-9._-/]` 범위로 제한하고, 사용자 입력을 받으면 미리 sanitize.
- **사람 이름이나 조직명을 좌측에.** 사람과 조직은 바뀝니다. 좌측에는 변하지
  않을 차원만 둡니다. 사람/조직은 metadata DB에 둬서 mapping을 유연하게.
- **확장자 의존.** `.csv`라고 진짜 CSV란 보장은 없습니다. content-type은
  metadata로 따로 명시하고, 안전이 중요하면 처음 몇 byte를 검사 (magic bytes).
- **무한 versioning.** versioning만 켜고 옛 버전 cleanup을 안 걸면 storage가
  영원히 증가합니다. 사내 환경에선 `noncurrent_version_expiration` lifecycle
  rule을 등록할 권한이 없으므로, versioning을 쓰려면 처음부터 cleanup DAG
  설계를 같이 하세요. 사실 versioning 자체가 거의 필요 없는 환경이면 켜지
  않는 편이 단순합니다.
- **비밀번호/토큰을 metadata에.** metadata는 평문이고 audit log에 남습니다.
  비밀은 별도 secret manager / encrypted column에 두고, key/metadata에는
  참조만.
- **수십만 개 객체를 한 prefix에 평면 저장.** listing 비용이 폭증합니다.
  최소한 한 단계라도 쪼개세요 (`/2026/`, `/sha256/ab/`).

## 다음 단계

- 웹 서버에서의 활용 패턴: `web_integration.md`
- 코드 사용 예: `usage.md`
- mental model이 흔들린다면: `concepts.md`
