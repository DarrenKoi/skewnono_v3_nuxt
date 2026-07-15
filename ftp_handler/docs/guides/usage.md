# ftp_handler — 케이스별 사용법

FTP 서버에 어떻게, 어느 규모로 접근하는지에 맞는 서브패키지를 고른다. 각
서브패키지는 re-export 허브라서 리프 이름을 import 한다. 아래 모든 코드의 실행
가능한 버전은 각 폴더의 `examples.py`에 있다.

| 케이스 | 가진 것 | 사용 | import 위치 |
|------|-----------|-----|-------------|
| 1. 단일 서버, 즉석 | 호스트 하나, 대화형/스크립트 | `FtpClient` | `ftp_handler.core` |
| 2. 다수 서버, 직접 | FTP 플릿에 닿는 프로세스 | `FtpFleetDownloader` | `ftp_handler.direct_downloader` |
| 3. 다수 서버, 방화벽 안 | FTP엔 못 닿지만 프록시엔 닿는 PC | `FtpFleetDownloader` (HTTP) | `ftp_handler.proxy` |
| 4. 웹 앱, 논블로킹 | HTTP 요청이 플릿 실행을 시작해야 함 | `BackgroundJobs` | `ftp_handler.web_app` |
| 5. Airflow / 스케줄 | 주기적 작업 | `collect_fleet` (direct) | `ftp_handler.direct_downloader` |

심(seam): 케이스 2와 3은 **같은 이름**을 노출하므로 direct ↔ proxy 교체는 import
한 줄이고 그 외엔 아무것도 바뀌지 않는다.

---

## 케이스 1 — 단일 서버 (`core.FtpClient`)

연결 하나를 재사용하며 컨텍스트 매니저로 쓴다. 즉석 연산 네 가지이며, 서버 오류는
그대로 전파된다(흡수해 줄 플릿 리포트가 없다).

```python
from ftp_handler.core import FtpClient

with FtpClient(host="10.0.0.1", user="u", password="p") as ftp:
    names = ftp.list_dir("/MEAS", pattern="*.dat")     # NLST (names)
    entries = ftp.list_entries("/MEAS")                # MLSD (dirs vs files)
    details = ftp.list_details("/MEAS")                # LIST (size + mtime, KST)
    data = ftp.download(names[0])                      # RETR -> bytes
    ftp.upload("/INBOX/report.csv", b"a,b\n")          # STOR
    ftp.remove("/MEAS/stale.dat")                      # DELE
```

목록 방식: `list_dir`는 어디서나 동작한다. `list_entries`는 MLSD(RFC 3659)가
필요하며 구형 데몬에서는 `error_perm`을 던진다 — 그럴 땐 `list_details`로
대체하라. 이것은 Unix `ls -l` / MS-DOS 텍스트를 파싱해 타입드 `FileInfo`를 반환한다.

---

## 케이스 2 — 동시 플릿, 직접 FTP (`direct_downloader.FtpFleetDownloader`)

서버에 닿을 수 있는 프로세스용(방화벽 없는 호스트, Airflow 워커). 동기식이며 이벤트
루프가 없어 스크립트, 스레드, async 컨텍스트 어디서나 안전하다. 두 단계:

```python
from ftp_handler.direct_downloader import FtpFleetDownloader, HostSpec, ListDir, specs_from_hosts

dl = FtpFleetDownloader(user="u", password="p", max_concurrency=48)

# 고정된 알려진 경로 (목록 없이):
report = dl.download([HostSpec("10.0.0.1", files=["/HITACHI/SYSFILE/LOG.log"])])

# 먼저 탐색하고, 그 다음 다운로드 ("내려받기 전에 살펴보기" 패스):
discover = specs_from_hosts(hosts, listings=[ListDir("/MEAS", "*.dat")])
listing = dl.list_dirs(discover)            # 가져오지는 않음
report = dl.download(listing.to_specs())    # 선택된 경로를 가져옴

print(report.ok, report.ng, report.failure_ratio)
```

**제한된 RAM:** `on_file`을 넘기면 파일이 도착하는 즉시 밖으로 흘려보내므로, 플릿
전체를 메모리에 모으지 않는다:

```python
from ftp_handler.direct_downloader import save_to_dir
dl.download(specs, on_file=save_to_dir("/data/eqp"))   # 최대 RAM ~ concurrency x 파일 크기
```

**로컬 저장 경로 고르기 (`keep_last`):** 기본 `save_to_dir`은 원격 트리를 그대로
미러링한다 — `/data/eqp/<host>/<원격 경로 전체>`. 원격 부모 디렉터리가 깊거나
(`/IMAGES/20260615/sub/...`) 날짜 폴더를 로컬에 옮기고 싶지 않을 때, `keep_last`로
경로의 뒤쪽 N개 성분만 남긴다(`<host>` 단계는 항상 유지). `keep_last=1`이면 파일명만,
`2`면 `<부모>/<파일>`만 남는다:

```python
# 원격: /IMAGES/20260615/sub/S09-01AP.jpeg
dl.download(specs, on_file=save_to_dir("/data/eqp", keep_last=2))
# 저장: /data/eqp/<host>/sub/S09-01AP.jpeg   (/IMAGES/20260615 제거)

dl.download(specs, on_file=save_to_dir("/data/eqp", keep_last=1))
# 저장: /data/eqp/<host>/S09-01AP.jpeg        (파일명만)
```

**앞 부분만 떼기 (`strip_components`):** `keep_last`가 "뒤에서 N개를 남긴다"라면,
`strip_components`는 "앞에서 N개를 버린다"이다(tar의 `--strip-components`). 떼어낼
공통 접두 경로의 깊이는 같지만 그 아래 구조 깊이가 파일마다 다를 때, 단일 `keep_last`로는
안 되는 것을 해낸다 — 접두부만 일률적으로 지우고 나머지 구조는 그대로 보존한다:

```python
# 원격: /mnt/ftp/A/sub/x.dat  와  /mnt/ftp/A/B/y.dat (깊이가 다름)
dl.download(specs, on_file=save_to_dir("/data/eqp", strip_components=2))
# 저장: /data/eqp/<host>/A/sub/x.dat   및   /data/eqp/<host>/A/B/y.dat
#       (/mnt/ftp 만 제거, 그 아래 서로 다른 구조는 유지)
```

`strip_components`와 `keep_last`를 함께 주면 앞쪽(`strip_components`)을 먼저, 그다음
뒤쪽(`keep_last`)을 적용한다. 둘 다 `<host>` 단계는 항상 유지한다. 저장 경로는 같은
인자로 `local_target`을 호출해 되찾는다.

`keep_last`/`strip_components`로 표현되지 않는 임의의 레이아웃(예: 사이드카 파일을 별도 폴더로 가르기)이
필요하면 `on_file`을 직접 쓴다 — `(host, remote_path, data)`를 받아 원하는 곳에
`write_bytes` 하면 되고, 다운로더는 로컬 경로를 전혀 건드리지 않는다. `then=`으로
저장과 처리(parse+index)를 한 번에 엮을 수도 있다:

```python
dl.download(specs, on_file=save_to_dir("/data/eqp", keep_last=2, then=index_one))
```

**저장된 로컬 경로 되찾기 (`local_target`):** `save_to_dir`은 경로를 돌려주지 않고
`DownloadReport.files`도 `host`/`remote_path`만 담는다(스트리밍 모드에선 `data`도 비어
있다). 저장 위치는 `(host, remote_path)`에서 결정론적으로 정해지므로, 다운로드를 넘긴
것과 같은 `dest_dir`/`keep_last`로 `local_target`을 호출해 되계산하면 된다:

```python
from ftp_handler.direct_downloader import save_to_dir, local_target

report = dl.download(specs, on_file=save_to_dir("/data/eqp", keep_last=2))
paths = [
    local_target("/data/eqp", f.host, f.remote_path, keep_last=2)
    for f in report.files                      # 성공한 파일만 들어 있다
]
```

`local_target`은 `save_to_dir`이 내부에서 쓰는 바로 그 매핑 함수라 경로가 항상 일치한다.

**이미지 + 사이드카(cond.txt) 저장 (`save_image_with_sidecar`):** 장비 이미지 폴더는
이미지마다 그 이미지명을 딴 하위 폴더에 사이드카 파일을 둔다(예: `S09-01AP.jpeg`와
`.S09-01AP.jpeg/cond.txt`). 이 경우 균일한 `keep_last`로는 잘 안 된다 — `keep_last=1`은
모든 cond.txt를 같은 `cond.txt` 한 경로로 뭉개 서로 덮어쓴다. `save_image_with_sidecar`는
둘을 비대칭으로 가른다: 이미지는 `dest` 바로 아래, 사이드카는 원래의 이미지별 폴더를
살려 충돌을 막는다(`<host>` 단계는 붙이지 않는 평탄 레이아웃):

```python
from ftp_handler.direct_downloader import save_image_with_sidecar, image_sidecar_target

# spec.files에 이미지와 .../<사이드카 폴더>/cond.txt를 함께 담아 내려받는다
report = dl.download(specs, on_file=save_image_with_sidecar("/data/eqp_images"))
# /data/eqp_images/S09-01AP.jpeg
# /data/eqp_images/.S09-01AP.jpeg/cond.txt

# 저장 경로 되찾기 — local_target의 사이드카용 짝
paths = [image_sidecar_target("/data/eqp_images", f.remote_path) for f in report.files]
```

사이드카 파일명이 `cond.txt`가 아니면 `sidecar_name=`으로 바꾼다.

**내려받기 전에 크기 재기 (`size_dirs`):** `list_dirs`가 "어떤 파일이 있나"를
답한다면, `size_dirs`는 "그것들을 메모리에 담으면 몇 바이트인가"를 답한다. 가져오는
대신 FTP `SIZE` 명령으로 각 파일 크기만 묻는다(바이트 전송 없음). `download`와 똑같이
경로를 해석하므로(고정 `files` + `listings`가 탐색하는 것), `total_bytes`는 수집
모드 `download`가 한 번에 들고 있을 최대 RAM과 같다. `by_host()`로 무거운 호스트를
찾아 큰 실행을 RAM 한도에 맞춰 나누고, `to_specs()`로 잰 집합을 그대로 `download`에
넘긴다:

```python
sizing = dl.size_dirs(discover)                 # SIZE만 — 가져오지 않음
print(f"{sizing.total_bytes / 1024**2:.1f} MiB, {sizing.ok} files")
print(sizing.by_host())                          # {host: bytes}

if sizing.total_bytes < 500 * 1024**2:
    report = dl.download(sizing.to_specs())                       # RAM에 들어감
else:
    report = dl.download(sizing.to_specs(), on_file=save_to_dir("/data/eqp"))  # 스트리밍
```

`SIZE`가 실패하거나(서버가 미지원) 디렉터리를 가리키면 0으로 묵살하지 않고
`failures`에 기록되므로, `total_bytes`는 실제로 잰 파일만 더한다. 한 번 호출로 끝나는
함수 래퍼는 `size_fleet(specs, user=..., password=...)`.

**튜닝:** `connect_timeout`은 죽은 호스트를 빠르게 포기시키고, `host_timeout`은
연결 후 멈춰버린 호스트를 backstop 하며, `max_concurrency`는 연결 수(및 RAM)를
제한한다. `download_fleet` / `list_fleet`은 한 번 호출로 끝나는 함수 래퍼다.

**업로드(쓰기 방향):** 같은 fan-out으로 원격 FTP에 파일을 올린다. `UploadFile`은
디스크 파일이 아니라 raw `bytes`를 받아 `BytesIO`로 곧장 STOR 하므로 디스크를 거치지
않는다. 호스트 단위뿐 아니라 파일 단위로도 실패가 격리된다. `upload_specs_from_hosts`는
같은 파일을 여러 호스트에 올리는 흔한 경우의 헬퍼다:

```python
from ftp_handler.direct_downloader import (
    FtpFleetDownloader, UploadSpec, UploadFile, upload_specs_from_hosts,
)

payload = df.to_csv().encode()   # 메모리상의 바이트 — 디스크에 쓰지 않음
specs = upload_specs_from_hosts(hosts, files=[UploadFile("/INBOX/report.csv", payload)])
report = FtpFleetDownloader(user="u", password="p").upload(specs)
print(report.ok, report.ng, report.grouped())   # {host: [remote_path, ...]}
```

호스트마다 다른 파일을 올리려면 `UploadSpec`을 직접 만든다. `upload_fleet`은 한 번
호출로 끝나는 함수 래퍼다.

---

## 케이스 3 — HTTP 프록시 경유의 방화벽 안 클라이언트 (`proxy`)

당신의 PC는 FTP 서버에 못 닿지만, 방화벽 없는 호스트의 프록시에는 닿는다. 프록시가
실제 FTP를 수행하고, 클라이언트는 HTTP로 바이트를 받는다.

```
client PC ──HTTP──> Flask proxy ──FTP──> equipment servers
(firewalled)        (firewall-free)
```

**서버 절반** (방화벽 없는 호스트에서) — 블루프린트를 마운트하거나 단독 실행한다.
신뢰하는 단일 사용자라면 인증 없이(`FTP_PROXY_TOKEN` 미설정) 쓰고, 포트만 신뢰할 수
없는 네트워크에 노출하지 않으면 된다:

```python
from ftp_handler.proxy.flask_proxy import ftp_proxy_sknn_v3   # 또는 create_app()
app.register_blueprint(ftp_proxy_sknn_v3)
```

**클라이언트 절반** — direct 다운로더와 동일하고, import만 다르다. 프록시 위치/토큰은
생성자 인자가 아니라 `proxy_downloader.py` 상단의 모듈 상수(`PROXY_URL`,
`PROXY_TOKEN`)로 준다. 그래야 생성자 시그니처가 direct와 똑같아져 import 한 줄만
바꿔도 호출부가 깨지지 않는다:

```python
# proxy_downloader.py 상단에서 한 번만 편집: PROXY_URL = "http://proxy.host:8080"
from ftp_handler.proxy import FtpFleetDownloader, HostSpec, ListDir, save_to_dir

dl = FtpFleetDownloader(user="u", password="p")   # 프록시 위치는 PROXY_URL 상수
report = dl.download(specs, on_file=save_to_dir(r"C:\eqp"))  # on_file은 로컬에서 실행
```

데이터클래스(`HostSpec`, `DownloadReport`, …)는 direct 다운로더의 것과 동일한
객체라서 `report.grouped()`, `to_specs()` 등이 똑같이 동작한다. copy-out: 이 쌍에
`fleet_downloader.py`와 `listing.py`를 더하면 클라이언트 PC에 평평하게 떨궈 bare
이름으로 import 할 수 있다.

`download` / `list_dirs` / `size_dirs`와 마찬가지로 `upload`도 같은 표면으로 프록시
너머에서 동작한다(케이스 2의 예제에서 import만 `ftp_handler.proxy`로 바꾸면 된다).
클라이언트가 바이트를 base64로 실어 보내면 프록시가 풀어서 STOR 한다. `size_dirs`는
`list_dirs`처럼 바이트를 싣지 않으므로 가볍다.

---

## 케이스 4 — 웹 서버에서의 논블로킹 실행 (`web_app.BackgroundJobs`)

`download()`는 실행 내내 블로킹하므로 요청 안에서 인라인으로 호출하면 안 된다.
`BackgroundJobs`는 그것을 백그라운드 스레드에서 돌리고 즉시 job id를 반환한다. 결과는
폴링한다.

```python
from ftp_handler.web_app import BackgroundJobs, create_jobs_blueprint
from ftp_handler.direct_downloader import FtpFleetDownloader, build_host_specs, save_to_dir

jobs = BackgroundJobs()                       # 한 번에 플릿 실행 하나 (max_workers=1)

def start(body: dict) -> str:                 # 앱이 specs/creds를 만든다
    specs = build_host_specs(body["fleet"])
    dl = FtpFleetDownloader(user="u", password="p")
    return jobs.submit(lambda: dl.download(specs, on_file=save_to_dir(body["dest"])))

app.register_blueprint(create_jobs_blueprint(jobs, start=start))
# POST /fleet/jobs {fleet,dest} -> 202 {"job_id"}
# GET  /fleet/jobs/<id>         -> 200 {status, result-counts, error}
```

**범위:** 레지스트리는 인프로세스다. `gunicorn -w N` 아래서는 상태 폴링이 그 job을
본 적 없는 워커에 닿을 수 있다 — 수집기는 전용 프로세스 하나에서 돌리거나(또는
레지스트리를 Redis로 백업). 상태 응답은 카운트만 담고 파일 바이트는 절대 담지 않는다.

**순수 스케줄 실행에는 필요 없음:** APScheduler 잡은 이미 요청 스레드 밖에서 도므로,
스케줄된 함수에서 그냥 `dl.download(specs)`를 호출하면 된다.

---

## 케이스 5 — 인메모리 수집 → MinIO → OpenSearch (`direct_downloader.collect_fleet`)

엔드투엔드 ingest 패턴: 플릿에서 파일을 끌어오고, **파일이 도착할 때마다** 원시
바이트를 MinIO에 보관하고, 그것을 문서로 파싱해 OpenSearch에 색인한다. Airflow
DAG이 실행하는 것이 바로 이것이며(`airflow_mgmt/dags/eqp_ftp/eqp_ftp_collector_dag.py`),
순수 함수이므로 스크립트나 노트북에서도 똑같이 쓸 수 있다.

### 디스크 없음 — 바이트는 RAM을 거쳐 흘러나간다

`collect_fleet`은 `on_file` 콜백을 연결하므로(케이스 2의 "제한된 RAM"), 파일
바이트는 **로컬 디스크에도 워커 디스크에도 결코 쓰이지 않는다**. 다운로더는 각 파일을
FTP에서 곧장 메모리의 `BytesIO` 버퍼로 읽어, 그 바이트를 당신의 세 콜러블에 넘긴 뒤
버린다. 최대 RAM은 플릿 전체가 아니라 `concurrency x 파일 크기`에 머문다. 영속
상태는 MinIO(원시)와 OpenSearch(파싱)에 산다 — 로컬 FS가 휘발성이고 호스트별로
격리되는 Airflow 워커에 맞는 모델이다.

```
one file:  FTP bytes ──► RAM (BytesIO)
                          ├─ archive ─► MinIO   (returns storage key)
                          ├─ parse ───► list[dict]   (YOUR logic)
                          └─ index ───► OpenSearch    (each doc stamped minio_key)
                          (bytes released)
```

`archive`가 먼저 실행되므로, 원시 소스가 저장되지 않은 레코드를 색인하는 일은 결코
없다(collect.py:15). 어느 단계에서 예외가 나든 **파일 단위로** 잡혀 그 파일의 실패로
기록되며, 다른 파일이나 호스트를 중단시키지 않는다.

### 당신이 제공하는 세 개의 심

| 콜러블 | 시그니처 | 역할 |
|----------|-----------|-----|
| `archive` | `(host, remote_path, bytes) -> str` | 원시 바이트 저장, 키 반환 |
| `parse`   | `(host, remote_path, bytes) -> list[dict]` | 바이트 → 0개 이상의 문서 |
| `index`   | `(list[dict]) -> None` | 문서를 전송 |

`collect_fleet`은 `index` 직전에 모든 문서에 `minio_key`(즉 `archive`가 반환한 값)를
찍어, 각 OpenSearch 레코드를 MinIO의 원시 블롭과 연결한다.

### 전체 예제

```python
from ftp_handler.direct_downloader import collect_fleet, build_host_specs
from minio_handler import MinioObject
from ops_store import OSDoc

# minio-py와 opensearch-py 클라이언트는 스레드 안전(풀링)하므로, 각각 하나씩만 만들어
# 동시 on_file 콜백들에서 공유한다.
storage = MinioObject(bucket="eqp-raw")
doc = OSDoc()

def archive(host: str, remote_path: str, data: bytes) -> str:
    key = f"{host}/{remote_path.lstrip('/')}"
    storage.put(key, data)            # put(key, data) — 원시 바이트를 MinIO로
    return key                        # doc["minio_key"]가 됨

def parse_records(host: str, remote_path: str, data: bytes) -> list[dict]:
    # 당신의 처리 심. remote_path / 파일 타입으로 분기하고, 디코딩하고, 문서를 만든다.
    # 각 문서에 결정적(deterministic) id 필드를 부여하면 재실행 시 중복 대신 덮어쓴다
    # (멱등성). 아래 index()가 그 필드를 OpenSearch _id로 승격시킨다.
    text = data.decode("utf-8", errors="replace")
    return [{
        "doc_id": f"{host}:{remote_path}",   # 결정적 -> 멱등
        "host": host,
        "remote_path": remote_path,
        "line": line,
    } for line in text.splitlines() if line]

def index(docs: list[dict]) -> None:
    # index는 키워드 전용 인자다. id_field가 docs["doc_id"]를 _id로 승격시켜,
    # 같은 파일을 다시 실행하면 추가가 아니라 덮어쓴다.
    doc.bulk_index(docs, index="eqp_meas", id_field="doc_id")

specs = build_host_specs(fleet_json)          # fleet_json은 Airflow Variable / 설정에서
report = collect_fleet(
    specs, user=u, password=p,
    archive=archive, parse=parse_records, index=index,
    max_concurrency=48, connect_timeout=8.0, host_timeout=60.0,
)
print(report.ok, report.ng, report.failure_ratio)
```

### 텍스트 vs 바이너리 (이미지 등)

`f.data`(또는 `parse`의 `data`)는 언제나 원시 `bytes`다. **무엇으로 다루느냐**만
파일 종류에 따라 다르다:

- **텍스트 로그** → `data.decode("utf-8", errors="replace")`로 `str`로 디코딩한다
  (위 `parse_records` 참고). 한국어 Windows 툴이 CP949를 내보내면 `data.decode("cp949")`.
- **이미지·압축 파일·`.dat` 블롭** → **디코딩하지 않는다.** 이미지는 어떤 인코딩의
  텍스트도 아니므로 UTF-8 디코딩은 `UnicodeDecodeError`를 내거나(또는 `errors=`로
  뭉개서) 데이터를 망가뜨린다. `bytes` 그대로 두고 `io.BytesIO`로 감싸 라이브러리에
  넘긴다.

이미지 파일을 다루는 예 — 디코딩 없이 메타데이터를 뽑아 색인하고, 원시 바이트는
`archive`가 이미 MinIO에 그대로 저장한다:

```python
import io
from PIL import Image

def parse_records(host: str, remote_path: str, data: bytes) -> list[dict]:
    if remote_path.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
        # 디코딩하지 않음 — bytes를 그대로 이미지 라이브러리에 넘긴다.
        img = Image.open(io.BytesIO(data))
        return [{
            "doc_id": f"{host}:{remote_path}",
            "host": host,
            "remote_path": remote_path,
            "width": img.width,
            "height": img.height,
            "format": img.format,
            # 픽셀이 아니라 메타데이터만 색인한다; 원시 이미지는 archive가 MinIO에 보관.
        }]
    # 그 외(텍스트 로그)는 디코딩 경로로.
    text = data.decode("utf-8", errors="replace")
    return [{"doc_id": f"{host}:{remote_path}", "host": host,
             "remote_path": remote_path, "line": line}
            for line in text.splitlines() if line]
```

원시 바이트를 정확한 MIME 타입으로 보관하려면 `archive`에서 `content_type`을 지정한다:

```python
def archive(host: str, remote_path: str, data: bytes) -> str:
    key = f"{host}/{remote_path.lstrip('/')}"
    ctype = "image/png" if remote_path.lower().endswith(".png") else "application/octet-stream"
    storage.put(key, data, content_type=ctype)   # bytes 그대로 — 디코딩 없음
    return key
```

(케이스 5 밖에서, 리포트의 바이트를 직접 쓸 때도 같다: 텍스트는
`f.data.decode(...)`, 이미지는 `Image.open(io.BytesIO(f.data))` 또는
`Path("out.png").write_bytes(f.data)`.)

### 결과 읽기 & 알림

`collect_fleet`은 `download`과 같은 `DownloadReport`를 반환한다. 호스트별/파일별
실패는 **정상**이므로(장비는 오프라인이 된다) 어떤 실패에든 작업을 실패시키지 말고,
대신 `failure_ratio`로 게이트하라:

```python
if report.ok == 0 or report.failure_ratio > 0.2:
    raise RuntimeError(f"systemic failure: ok={report.ok} ng={report.ng}")
```

여기서 `report.files`의 `data`는 비어 있다(스트리밍 모드가 바이트를 소비함). 따라서
바이트가 아니라 카운트/`failures`를 살펴라 — 바이트는 이미 MinIO/OpenSearch에 있다.

### 사전 조건 & Airflow venv의 주의점

- **워커에 `opensearch-py` 필요.** `OSDoc`은 이것을 지연 import 하므로, 없으면 작업이
  `OSDoc()`에서 런타임에 실패한다. 회사 워커에는 기본 탑재되지 않으므로, DAG은 수집
  단계를 `PythonVirtualenvOperator`에서 돌려 사내 Nexus 미러로부터 `opensearch-py`를
  pip 설치한다(`minio` + `airflow`는 `system_site_packages`에서 옴).
- **설정은 venv *밖*에서 해석한다.** venv 서브프로세스는 Airflow의 `Variable` /
  `Connection` API에 닿을 수 없고 DAG 모듈의 전역도 보지 못한다. 그래서 일반 상위
  `@task`(`load_config`)가 플릿 스펙 + FTP 자격증명을 해석해 `op_kwargs`로 평범한 값을
  넘기고, `parse_records`는 모듈 스코프가 아니라 venv 콜러블 *안*에 정의한다. 전체
  형태는 DAG을 참고하라.
