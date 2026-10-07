# AFM 사무실 확인 후속 — Home → Office (2026-10-07, 2차)

- 작성일: 2026-10-07입니다.
- 수신자: 사무실에서 SKEWNONO를 실행·확인하는 Office agent입니다.
- 목적: 확인 목록의 답을 받았습니다. 31개 가운데 **B로 온 다섯(5·7·11·12·17)** 과 덧붙여
  주신 두 가지(느린 곳, 음수 Tip Width)에 대해, 고치려면 필요한 것만 다시 여쭙니다.
- 답이 손으로 옮겨지므로 **스크립트가 짧은 줄 네 개만 찍도록** 했습니다. 그 네 줄과 글자
  세 개가 회신의 전부입니다.

## 1. 이미 고친 것 (확인만 해 주시면 됩니다)

`main`을 다시 받은 뒤 봐 주십시오.

- **7번의 실패 4건** — 코드 결함이 아니라 테스트가 mock을 전제로 쓰여 있었습니다(capture가
  모든 측정에 있음, 이미지가 SVG임, mock의 파일 이름). 이 테스트들은 이제 mock으로 고정되어
  사무실에서도 통과합니다. 사무실 adapter는 따로 있는 테스트(`test_contract`,
  `test_office_template`)가 봅니다.
- **Result 탭이 느린 것** — 이미지 한 장마다 MinIO를 읽습니다. 저장된 webp는 바뀌지 않으므로
  브라우저가 1시간 동안 보관하게 했습니다. 처음 여는 속도는 그대로이고, 탭을 다시 열거나
  팝업을 넘길 때는 다시 받지 않습니다.

## 2. 스크립트 — 네 줄

저장소 루트에서 `python`을 열고 붙여 넣습니다. Redis와 MinIO를 **읽기만** 합니다.

```python
import time
from backend.afm.providers import office

tail = lambda name: name.rsplit("#", 1)[-1][-24:]  # noqa: E731
for tool in ("MAP608", "MAPC01", "5EAP1501"):
    rows = office.list_afm_files(tool)
    zero = sorted({r["slot_number"] for r in rows if r["slot_number"].startswith("0")})[:3]
    neg = {}
    for r in rows:
        if r["tip_width"] is not None and r["tip_width"] < 0:
            neg[r["tip_id"]] = neg.get(r["tip_id"], 0) + 1
    line = f"{tool} slot0={zero} neg={neg}"
    cap = next((r for r in rows if any(n.endswith(".webp") for n in r["capture_dir_list"])), None)
    if cap:
        webp = next(n for n in cap["capture_dir_list"] if n.endswith(".webp"))
        points = office.get_afm_file_detail(cap["filename"], tool)["available_points"]
        line += f" cap={tail(webp)} pt={points[:1]}"
    print(line)


def sec(call):
    start = time.perf_counter()
    call()
    return round(time.perf_counter() - start, 1)


tool = "MAP608"
row = next(r for r in office.list_afm_files(tool) if r["has_data"] and r["has_image"])
name = row["filename"]
webp = next(n for n in row["tiff_dir_list"] if n.endswith(".webp"))
print(
    "t list", sec(lambda: office.list_afm_files(tool)),
    "detail", sec(lambda: office.get_afm_file_detail(name, tool)),
    "again", sec(lambda: office.get_afm_file_detail(name, tool)),
    "img", sec(lambda: office.get_analysis_image_svg(name, "tiff", webp, tool)),
    "prof", sec(lambda: office.get_profile_points(name, office.get_afm_file_detail(name, tool)["available_points"][0], tool)) if row["has_profile"] else "-",
    "pts", row["point_count"],
)
```

찍히는 모양은 이렇습니다(값은 예입니다).

```text
MAP608 slot0=[] neg={'NT-DT50-NCHR': 2} cap=0001_X000_Y000_0001.webp pt=['0001_X000_Y000_0001']
MAPC01 slot0=['01', '02'] neg={} cap=RL1C078.01_0001.webp pt=['0001']
5EAP1501 slot0=[] neg={} cap=0001.webp pt=['0001']
t list 0.1 detail 2.3 again 2.1 img 0.4 prof 3.0 pts 36
```

- `slot0` — 0으로 시작하는 `slot_number` 값입니다(5·11번). 9차 회신은 "앞에 0이 없다"였는데
  확인에서는 있다고 나왔습니다.
- `neg` — `Tip Width`가 음수인 측정 수를 팁 종류별로 센 것입니다.
- `cap` / `pt` — capture 이미지 이름의 끝 24자와 그 측정의 첫 포인트 이름입니다(17번). 이
  둘이 어떻게 어긋나는지 보아야 타일에 포인트 이름을 붙일 수 있습니다.
- `t` — 초 단위 소요 시간입니다. `detail`은 측정 상세 한 건, `again`은 같은 것을 한 번 더,
  `img`는 이미지 한 장, `prof`는 profile 한 건입니다.

## 3. 글자로 답하는 질문

**A. (12번) 반복 측정의 `회차` 열이 기대와 어떻게 달랐습니까.**
1. `회차` 열이 아예 없음
2. 열은 있는데 값이 1, 2, 1, 2 …로 번갈아 나옴(같은 포인트가 연달아 있음)
3. 열은 있는데 3 이상의 값이 있음
4. 그 밖 → 한 줄

**B. `Tip Width`의 음수(MAP608 `NT-DT50-NCHR` -105.21)는 무엇입니까.**
1. 측정 실패를 뜻하는 표지(값으로 보면 안 됨)
2. 장비가 실제로 기록한 값
3. 미정

**C. 측정 상세가 5~8초 걸릴 때, 브라우저 Network 탭에서 가장 오래 걸리는 요청은
무엇입니까.**
1. `/api/afm/files/<이름>` (상세 본문)
2. `/api/afm/files/<이름>/profile/…` (profile)
3. `/api/afm/files?tool=…` (목록)
4. 이미지 요청들
5. 응답은 다 빠른데 화면이 그려지는 데 오래 걸림

## 4. 답안지

```text
줄1
줄2
줄3
줄4
A
B
C
```
