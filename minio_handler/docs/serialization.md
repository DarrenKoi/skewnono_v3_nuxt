# DataFrame과 이미지 다루기

MinIO는 **bytes**만 저장합니다. `pandas.DataFrame`이나 `PIL.Image` 같은
Python 객체를 그대로 넘길 수는 없으므로, 업로드 전에 직렬화하고 다운로드
후에 역직렬화하는 한 단계가 필요합니다.

이 문서는 두 가지 흔한 payload를 다룹니다.

- `pandas.DataFrame` ↔ Parquet (pyarrow)
- `PIL.Image` ↔ PNG / JPEG / WebP / TIFF

## DataFrame

### 왜 Parquet인가

| 형식 | 크기 | 속도 | 타입 보존 | 다른 언어 | 안전성 |
| --- | --- | --- | --- | --- | --- |
| Parquet (pyarrow) | 작음 (snappy 기본) | 빠름 | 강함 (dtypes/categorical/tz 보존) | 가능 (Spark/DuckDB/Polars) | 안전 |
| pickle | 큼 | 빠름 | 완벽 | 불가능 (Python 전용) | **위험** (untrusted load 시 RCE) |
| CSV | 매우 큼 | 느림 | 약함 (dtype 손실) | 가능 | 안전 |

**기본은 Parquet.** Python 전용 객체(custom class instance, fitted ML
model 등)가 cell에 들어 있는 경우에만 pickle을 고려하세요.

### Wrapper 메서드

```python
def put_dataframe(self, key, df, *, bucket=None, metadata=None) -> Any
def get_dataframe(self, key, *, bucket=None) -> pd.DataFrame
```

- `put_dataframe`: `df.to_parquet(buf, engine="pyarrow")`로 직렬화한 뒤
  `application/vnd.apache.parquet` content-type으로 업로드
- `get_dataframe`: bytes를 받아 `pd.read_parquet(..., engine="pyarrow")`로
  복원

`pyarrow`와 `pandas`는 caller 환경에 설치되어 있어야 합니다. wrapper 자체는
이 두 패키지를 import하지 않으므로, DataFrame 기능을 안 쓰는 caller는
영향이 없습니다.

### 가장 짧은 사용

```python
import pandas as pd

from minio_handler import MinioObject

mo = MinioObject()                      # bucket=user, prefix=2067928/

df = pd.DataFrame({"sku": ["A", "B"], "qty": [10, 20]})
mo.put_dataframe("orders/2026-05-04.parquet", df)

restored = mo.get_dataframe("orders/2026-05-04.parquet")
assert restored.equals(df)
```

### 큰 DataFrame, 또는 옵션이 필요한 경우

`put_dataframe`은 의도적으로 옵션이 없습니다. compression, partitioning,
column selection 같은 세부 제어가 필요하면 직접 `to_parquet`을 부르고
`put` / `upload`로 보냅니다.

```python
import io

buf = io.BytesIO()
df.to_parquet(
    buf,
    engine="pyarrow",
    compression="zstd",         # snappy(default) / gzip / brotli / zstd / None
    index=False,
)
mo.put(
    "orders/2026-05-04.parquet",
    buf.getvalue(),
    content_type="application/vnd.apache.parquet",
)
```

수 GB 이상이라면 BytesIO 대신 임시 파일에 쓰고 `upload`로 multipart 분할
업로드하는 편이 메모리에 안전합니다.

```python
from pathlib import Path
import tempfile

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
    tmp = Path(f.name)
df.to_parquet(tmp, engine="pyarrow")
mo.upload(
    "orders/2026-05-04.parquet",
    tmp,
    content_type="application/vnd.apache.parquet",
    part_size=64 * 1024 * 1024,   # 64 MiB
)
tmp.unlink()
```

### Column projection (다운로드 비용 줄이기)

전체 파일을 한 번 받아 와서 `pd.read_parquet`에 `columns=`를 주면 wire
비용은 그대로지만 RAM은 절약됩니다.

```python
import io

raw = mo.get("orders/2026-05-04.parquet")
df = pd.read_parquet(io.BytesIO(raw), columns=["sku", "qty"])
```

진짜로 wire 비용을 줄이고 싶다면 partitioned dataset (`year=.../month=.../`
구조) 으로 prefix를 나눠 두고 필요한 prefix만 list/get 하는 방식으로
설계하세요. 단일 parquet 파일은 byte-range 조회로 column을 골라 받기가
까다롭습니다.

### Round-trip 시 주의

- **Timezone-naive `datetime64[ns]`**: tz-aware source에서 왔다면 저장 전에
  `df["ts"] = df["ts"].dt.tz_convert("UTC")` 같은 식으로 명시적 정규화를
  해 두세요. naive로 떨어진 채 저장되면 의미가 모호해집니다.
- **Index**: `to_parquet`은 기본적으로 RangeIndex(0..N-1)는 저장하지 않고,
  의미 있는 index만 보존합니다. 명시적 통제가 필요하면 `index=True/False`를
  직접 지정하세요.
- **Object dtype 혼합 컬럼**: 한 컬럼에 `str`, `int`, `None`이 섞여 있으면
  pyarrow가 추론에 실패합니다. 저장 전에 `astype("string")` 등으로 정리.
- **Categorical 유지**: pyarrow는 `category` dtype을 dictionary type으로
  보존합니다. round-trip 후에도 category로 돌아옵니다.

## 이미지: PNG / JPEG / WebP / TIFF

이미지에는 별도 wrapper 메서드를 두지 않았습니다. 이미 직렬화된 파일은
`upload`로, 메모리 안의 `PIL.Image`는 `BytesIO`를 거쳐 `put`으로 보내면
충분합니다.

### Format별 content-type

브라우저와 MinIO Console에서 미리보기/다운로드를 올바르게 처리하도록 항상
명시해 주세요. extension만으로는 추측되지 않습니다.

| 확장자 | content-type | 비고 |
| --- | --- | --- |
| `.png` | `image/png` | lossless, alpha 지원 |
| `.jpg`, `.jpeg` | `image/jpeg` | lossy, alpha 없음, EXIF 메타 흔함 |
| `.webp` | `image/webp` | lossy/lossless 둘 다, alpha 지원 |
| `.tif`, `.tiff` | `image/tiff` | multi-page, 과학용 16/32-bit 가능 |

### 로컬 파일 그대로 업로드

가장 단순한 케이스입니다. 디스크에 이미 파일이 있다면 그냥 `upload`.

```python
from pathlib import Path

mo.upload(
    "wafers/2026/05/04/lot-AB12.png",
    Path("/data/captures/lot-AB12.png"),
    content_type="image/png",
)
```

### PIL Image → MinIO

`Pillow`로 만든/편집한 이미지를 메모리에서 바로 보낼 때입니다.

```python
import io

from PIL import Image

img = Image.open("/data/captures/lot-AB12.png")
img = img.convert("RGB").resize((1024, 768))

buf = io.BytesIO()
img.save(buf, format="JPEG", quality=85, optimize=True)
mo.put(
    "wafers/2026/05/04/lot-AB12.jpg",
    buf.getvalue(),
    content_type="image/jpeg",
)
```

### MinIO → PIL Image

```python
import io

from PIL import Image

raw = mo.get("wafers/2026/05/04/lot-AB12.jpg")
img = Image.open(io.BytesIO(raw))
img.load()    # 즉시 디코딩 (BytesIO가 닫혀도 안전)
```

`Image.open`은 lazy합니다. 이미지를 사용할 시점에 BytesIO가 이미 GC된 상태
라면 `IOError`가 납니다. 다운로드 직후 `img.load()`를 한 번 부르거나, with
블록 안에서 사용을 끝내는 편이 안전합니다.

### Format별 옵션 메모

**JPEG**
- `quality`: 1~95 (기본 75). 사진은 80~85가 무난, archive면 90+
- `optimize=True`: 약간 더 작은 파일 (인코딩은 느려짐)
- `progressive=True`: 점진 로딩 (웹용)
- alpha 채널 없음. RGBA → JPEG로 저장하면 alpha가 검정색 위에 합성됨.
  먼저 `.convert("RGB")`.

**PNG**
- lossless. compression level은 `compress_level=0..9` (기본 6)
- 큰 PNG는 압축 시간이 무시할 수 없음. 캡처 직후 즉시 저장이 잦으면 0~3
- alpha 보존됨

**WebP**
- `lossless=True`로 PNG 대체 (보통 더 작음)
- lossy 모드: `quality=80`이 무난
- `method=0..6`: 인코딩 노력 (높을수록 느리고 작음, 기본 4)
- alpha 보존됨

**TIFF**
- multi-page 저장: `img.save(buf, format="TIFF", save_all=True, append_images=[...])`
- 압축: `compression="tiff_lzw"`, `"tiff_deflate"`, `"jpeg"` 등. 기본은
  무압축이라 매우 큼. 과학용 high-bit 이미지는 `"tiff_lzw"` 권장
- 16/32-bit 모드(`I;16`, `F`) 지원 — JPEG/WebP로 변환하면 손실됨

### 큰 이미지 / multi-page TIFF

수십 MB 이상이거나 multi-page TIFF는 메모리 안에서 BytesIO에 다 쓰지 말고
임시 파일을 거치는 편이 안전합니다.

```python
from pathlib import Path
import tempfile

with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
    tmp = Path(f.name)

frames = [Image.open(p) for p in source_files]
frames[0].save(
    tmp,
    format="TIFF",
    save_all=True,
    append_images=frames[1:],
    compression="tiff_lzw",
)
mo.upload(
    "wafers/2026/05/04/lot-AB12.tif",
    tmp,
    content_type="image/tiff",
    part_size=32 * 1024 * 1024,
)
tmp.unlink()
```

### byte-range로 헤더만 미리 읽기

이미지의 dimension/format만 빠르게 알고 싶다면 앞 4~64 KiB만 받아서 PIL에
넘기면 충분합니다.

```python
import io

from PIL import Image

head = mo.get("wafers/2026/05/04/lot-AB12.tif", offset=0, length=64 * 1024)
with Image.open(io.BytesIO(head)) as img:
    print(img.format, img.size, img.mode)
```

전체 픽셀 데이터를 디코딩하지는 못하지만 metadata는 보통 첫 몇 KiB 안에
있습니다. TIFF는 IFD 위치에 따라 더 받아야 할 수도 있습니다.

### Browser에서 이미지 직접 업로드 / 다운로드

`presigned_get_url` / `presigned_put_url`은 이미지에도 그대로 쓸 수
있습니다 (`web_integration.md`, `usage.md` 참조). content-type은 PUT 시점에
브라우저가 보내는 값을 따라가므로, 클라이언트에서 `fetch(url, { method:
"PUT", body: file, headers: { "Content-Type": file.type } })`처럼 명시해
주세요.

## 자주 하는 실수

- **content-type 누락.** `put_dataframe`은 자동으로 채우지만 일반 이미지
  `put`/`upload`는 caller가 지정해야 합니다. 안 주면 모든 객체가
  `application/octet-stream`이 되어 브라우저가 다운로드 다이얼로그만 띄움.
- **JPEG에 alpha를 그대로 저장.** `OSError: cannot write mode RGBA as
  JPEG`. 저장 전 `.convert("RGB")`.
- **`Image.open` 후 BytesIO 폐기.** lazy decoding 때문에 `img.load()` 또는
  `with Image.open(...) as img:` 패턴을 쓰세요.
- **DataFrame을 매번 pickle로 저장.** Python 버전 업그레이드/패키지 변경 시
  load 실패가 누적됩니다. 표 데이터는 parquet이 기본입니다.
- **partition 없이 단일 거대 parquet.** 매일 쌓는 데이터를 한 파일로 키우면
  업데이트 비용이 폭발합니다. `prefix/year=2026/month=05/day=04/part.parquet`
  처럼 날짜 prefix로 쪼개는 편이 lifecycle / column projection 모두에
  유리합니다 (`data_management.md` 참조).
