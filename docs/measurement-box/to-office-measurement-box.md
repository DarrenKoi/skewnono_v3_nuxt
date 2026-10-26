# parameter 이미지 cond.txt 마크 확인 — Home → Office (2026-10-26)

- 작성일: 2026-10-26입니다.
- 수신자: 사무실에서 SKEWNONO를 실행·확인하는 Office agent입니다.
- 목적: recipe-search 의 align 이미지(OM/SEM)에는 cond.txt 의 `!Cursor_info` 줄로
  십자선, white box 중심, 이미지 중심을 덧그리고 있습니다. 같은 기능을 parameter
  이미지(addressing `IMMP` · `I2MP`, 측정 `IMMS`)로 넓히려고 합니다. 그런데 집에서
  확인한 표본은 모두 align 이미지라서, **parameter 이미지의 cond.txt 에 그 줄이
  있는지, 있다면 어느 자리에 무엇이 들어 있는지**를 모릅니다. 특히 측정 이미지에서
  box 자리에 **측정 박스**가 들어 있다면, 지금 화면은 그것을 정렬 offset 으로 잘못
  그리게 됩니다. 코드를 고치기 전에 실제 파일로 확인하려는 요청입니다.
- 범위: 장비 FTP 와 OpenSearch 를 **읽기만** 합니다. 받은 파일은 저장소 루트의
  `.ftp-probe` 폴더 아래에 장비 경로 그대로 저장됩니다.
- 답이 손으로 옮겨지므로 스크립트가 **짧은 줄만** 찍도록 했습니다. 대부분의 질문은
  글자 하나로 답합니다. `?` 는 "모름" 입니다.

## 1. 알고 있는 것 (집의 가정)

- `!Cursor_info`(장비에 따라 `!Cursor_inf`)는 콤마로 구분한 숫자열입니다.
  0부터 세어 `[4],[5]` 가 십자선, `[6..9]` 가 box (left, top, right, bottom)이고,
  `-1` 은 "없음" 입니다.
- 좌표는 이미지 px 의 **10배** 프레임입니다. `Pixel 512,512` 이면 값의 범위는
  0~5120 입니다.
- align 표본에는 `[10]` 이후에도 자리가 더 있었고 모두 `-1` 또는 `""` 였습니다.
  측정 이미지에서는 그 자리에 값이 들어 있을 수 있다고 봅니다.

## 2. 조회 스크립트

**저장소 루트**의 `python` 에 붙여 넣습니다. 기존 recipe FTP probe 를 조용히 실행한 뒤,
받은 cond.txt 마다 `Pixel` 과 `!` 로 시작하는 줄만 찍습니다. `!Cursor_info` 는
`-1` 과 빈 값을 뺀 **자리:값** 목록으로 줄여 찍습니다. align 이미지(`IMAP`)의 cond 도
함께 찍히며, 이것은 비교 기준(control)입니다.

```python
import contextlib, io
from scripts.probes.probe_recipe_ftp import main
from backend._core.cond_cursor import cond_lines, is_cursor_key

ARGS = ["--tool", "cdsem"]   # HV-SEM: ["--tool", "hvsem"] / 다른 문서: ARGS + ["--pick", "1"]
PARAM = None                 # None 이면 recipe 의 첫 parameter

def run(args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        p = main(args)
    return p, buf.getvalue()

probe, log = run(ARGS + (["--param", PARAM] if PARAM else []))
if not probe.param_rows and probe.idp_image_info is not None:
    PARAM = str(probe.idp_image_info["Parameter"].iloc[0])
    probe, log = run(ARGS + ["--param", PARAM])
doc = probe.doc or {}
print("doc", doc.get("eqp_id"), doc.get("recipe_name"), "param", probe.parameter)

conds = sorted(n for n in probe.raw_files if n.endswith("cond.txt"))
if not conds:
    print("cond.txt 없음 — probe 출력 끝부분:")
    print("\n".join(log.splitlines()[-15:]))
for name in conds:
    lines = cond_lines(probe.raw_files[name].decode("utf-8", "replace"))
    pixel = lines.get("Pixel", "")
    print("==", name, "Pixel", pixel)
    for key, value in lines.items():
        if not key.startswith("!"):
            continue
        if not is_cursor_key(key):
            print("  ", key, value[:60])
            continue
        toks = [t.strip() for t in value.split(",")]
        keep = [f"{i}:{t}" for i, t in enumerate(toks) if t not in ("-1", "", '""')]
        nums = [int(t) for t in toks if t.lstrip("-").isdigit() and t != "-1"]
        try:
            frame = max(int(v) for v in pixel.split(",")) * 10
            fits = max(nums, default=0) <= frame
        except ValueError:
            fits = "?"
        print("  ", key, f"n={len(toks)}", f"fits_x10={fits}", " ".join(keep))

for name, parsed in probe.raw_parsed.items():
    if name.startswith("PRMS") and hasattr(parsed, "get"):
        print("AMP", name, " ".join(f"{k}={parsed.get(k)!r}" for k in
              ("Kind", "Measurement", "Measurement_Point", "Search_Area", "Inspect_Area")))
```

찍히는 모양은 이렇습니다(값은 예입니다).

```text
doc MCD719 ADI/ADI_CD_001 param WAFER
== .IMAP0001.jpeg/cond.txt Pixel 512,512
   !Cursor_info n=40 fits_x10=True 6:1770 7:1770 8:3380 9:3330
== .IMMP0001.jpeg/cond.txt Pixel 512,512
   !Mag_high_res 104000
   !Cursor_info n=40 fits_x10=True 0:0 1:0 2:0 3:0 6:1600 7:1600 8:3520 9:3520
== .IMMS0000.jpeg/cond.txt Pixel 1024,1024
   !Cursor_info n=40 fits_x10=True 4:5120 5:5120 10:4800 11:3000 12:5440 13:7200
AMP PRMS0000 Kind='Multi_Point' Measurement='Width' Measurement_Point='32' Search_Area='…' Inspect_Area='…'
```

스크립트가 받은 jpeg 는 `.ftp-probe` 아래 같은 이름으로 저장되어 있습니다. 질문 5·6 은
그 파일(또는 화면의 확대 창)을 눈으로 보고 답합니다.

## 3. 질문

### 파일 (스크립트 출력으로 답합니다)

**1.** `.IMMP…` 또는 `.I2MP…` cond.txt 아래에 `!Cursor_inf…` 줄이 찍혔습니까?
A 예 · B 아니오(줄 없음) · ?
**2.** `.IMMS…` cond.txt 아래에 `!Cursor_inf…` 줄이 찍혔습니까?
A 예 · B 아니오(줄 없음) · ?
**3.** 1·2 가 A 이면, 그 줄을 **찍힌 그대로** 옮겨 적어 주십시오. 한 파일에 한 줄입니다.
예: `IMMS n=40 4:5120 5:5120 10:4800 11:3000 12:5440 13:7200`
**4.** `!Cursor_info` 외에 `!` 로 시작하는 key 가 찍혔다면 key 이름만 적어 주십시오.
예: `IMMS !Mag_high_res, !Meas_area`. 없으면 `없음`.

### 이미지 (눈으로 봅니다)

**5.** 측정 이미지(`IMMS…jpeg`)에 **장비가 그려 넣은** 표시가 보입니까?
A 사각형(박스) · B 십자선만 · C 사각형과 십자선 둘 다 · D 아무것도 없음 · ?
**6.** 보이는 사각형은 몇 개입니까? 숫자 하나로 적습니다. 예: `2`. 없으면 `0`.

### 좌표계

**7.** 모든 cond 줄에 `fits_x10=True` 가 찍혔습니까? 그리고 `Pixel 1024,1024` 파일이
있었습니까?
A 모두 True, 1024 파일 있음 · B 모두 True, 1024 파일 없음 · C False 가 있음 · ?

### AMP

**8.** `AMP` 줄을 **찍힌 그대로** 옮겨 적어 주십시오. 줄이 없으면 `없음`.

### 화면 (recipe_search 의 office.py 가 최신일 때만, 아니면 `?`)

**9.** HV-SEM recipe 에서 측정 이미지(`-U` · `-T` 등 suffix 가 붙은 이미지)를 확대했을 때,
오른쪽 위에 "측정점 십자선 표시" 토글이 있습니까?
A 모든 suffix 이미지에 있음 · B 일부에만 있음 · C 없음 · ?
**10.** CD-SEM recipe 에서 측정 이미지를 확대했을 때 같은 토글이 있습니까?
A 있음 · B 없음 · ?
**11.** 10 이 A 일 때 토글을 켜면, 덧그린 선·점이 장비가 그려 넣은 표시와 겹칩니까?
A 정확히 겹침 · B 어긋남 · C 장비 표시가 없어 비교할 수 없음 · ?

## 4. 답안지

질문 번호는 위에서부터 1~11 입니다. 3·4·8 은 한 줄 값, 나머지는 글자 하나입니다.

```text
1
2
3 IMMP
3 IMMS
4
5
6
7
8
9
10
11
```
