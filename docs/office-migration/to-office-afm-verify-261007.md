# AFM 사무실 확인 목록 — Home → Office (2026-10-07)

- 작성일: 2026-10-07입니다.
- 수신자: 사무실에서 SKEWNONO를 실행·확인하는 Office agent입니다.
- 목적: 7차~9차 회신을 반영한 AFM 변경은 **집의 mock 데이터로만** 확인했습니다. 실제
  Redis·MinIO 데이터에서 같은 결과가 나오는지 사무실에서 확인해 주십시오.
- 기준 commit: `main`의 `98d9b4bc` 이후입니다.
- 회신 기한: 날짜 기한은 없습니다. 본 것부터 부분 회신해 주시면 됩니다.

## 1. 답하는 방법

답이 손으로 옮겨지므로 대부분 **글자 하나**로 답할 수 있게 했습니다.

- **A = 적힌 기대 결과 그대로입니다.**
- **B = 다릅니다.** 뒤에 본 것을 한 줄 적어 주십시오.
- **? = 확인하지 못했습니다**(해당 데이터가 없음 등). 이유를 한 단어로 적어 주시면 됩니다.
- 맨 끝의 **답안지**를 채워 주십시오.

```text
1 A
7 B has_tip이 False
12 ? repeat 측정 없음
```

## 2. 준비

확인 전에 한 번만 하면 됩니다. 답안지의 0번입니다.

1. `main`을 `98d9b4bc` 이후로 받습니다.
2. `backend/afm/providers/office_example.py`를 `office.py`로 **다시 복사**합니다. 오늘
   adapter가 여러 번 바뀌었습니다(새 열 두 개, 원본 파일 판별, fab 표).
3. 프런트엔드를 다시 빌드하고 Flask를 다시 띄웁니다.
4. boot log에 `STALE office.py: afm`이 **나오지 않는지** 봅니다.

**0. 위 네 단계를 마쳤고 `STALE` 경고가 없습니다.**
A. 마침 · B. 경고가 남음 →

## 3. 데이터 — 스크립트 한 번

저장소 루트에서 `python`을 열고 아래를 붙여 넣습니다(파일로 저장한다면 저장소 루트에
두어야 `backend`를 찾습니다). 출력 전체를 회신에 붙여 주십시오 — 1~6번의 근거입니다.
Redis만 읽고 아무것도 쓰지 않습니다.

```python
from backend.afm.providers import office

for tool in ("MAP608", "MAPC01", "5EAP1501"):
    rows = office.list_afm_files(tool)
    n = len(rows)
    count = lambda pick: sum(1 for r in rows if pick(r))  # noqa: E731
    print(f"== {tool}: {n} rows")
    print("  measured_time null   :", count(lambda r: r["measured_time"] is None))
    print("  measured_time != time:", count(lambda r: r["measured_time"] not in (None, r["time"])))
    print("  measured_time bad    :", count(lambda r: r["measured_time"] and not (r["measured_time"].isdigit() and len(r["measured_time"]) == 6)))
    print("  pick-up null         :", count(lambda r: r["last_pick_up_time"] is None))
    print("  pick-up sample       :", next((r["last_pick_up_time"] for r in rows if r["last_pick_up_time"]), None))
    print("  tip_id null          :", count(lambda r: r["tip_id"] is None))
    print("  tip_width null       :", count(lambda r: r["tip_width"] is None))
    print("  slot empty           :", count(lambda r: r["slot_number"] == ""))
    print("  slot leading zero    :", count(lambda r: r["slot_number"].startswith("0")))
    print("  point_count null     :", count(lambda r: r["point_count"] is None))
    for kind in ("tiff", "align", "tip", "capture"):
        names = [name for r in rows for name in r[f"{kind}_dir_list"]]
        ext = sorted({name.rsplit(".", 1)[-1].lower() for name in names})
        print(f"  {kind:8}: {len(names)} files, extensions {ext}")
print(office.get_tools())
```

**1. 오류 없이 끝까지 실행됩니다.**
A. 실행됨 · B. 오류 → 마지막 줄

**2. `measured_time bad`가 세 장비 모두 0입니다(값이 있으면 6자리 숫자).**
A. 모두 0 · B. 0이 아님 → 장비와 값 한 건

**3. MAP608만 `measured_time != time`이 0보다 크고, MAPC01·5EAP1501은 0입니다.**
A. 맞음 · B. 다름 →

**4. `pick-up sample`이 날짜와 시각이 있는 값으로 나옵니다(세 장비 가운데 하나 이상).**
A. 나옴 · B. 모두 None

**5. `slot leading zero`가 세 장비 모두 0입니다.**
A. 모두 0 · B. 0이 아님 →

**6. 마지막 줄의 fab이 MAP608 = `PKG`, MAPC01 = `R3`, 5EAP1501 = `M15`입니다.**
A. 맞음 · B. 다름 →

## 4. 테스트와 API

**7. `python -m pytest backend/afm -q`가 실패 없이 끝납니다.** 통과·skip 건수를 적어 주십시오.
A. 실패 없음 → 건수 · B. 실패 있음 → 테스트 이름

**8. `GET /api/health/providers`에서 `afm`이 `office`입니다.**
A. office · B. mock

**9. `GET /api/afm/files?tool=MAP608`의 첫 행에 `measured_time`과 `last_pick_up_time` key가
있습니다(값은 null이어도 됩니다).**
A. 둘 다 있음 · B. 없음 → 어느 것

## 5. 화면 — 측정 목록과 상세

MAP608, MAPC01, 5EAP1501 가운데 데이터가 있는 장비로 확인합니다.

**10. 측정 목록(`/afm/map608`)에서 같은 날 같은 세션의 측정들이 서로 다른 시각으로
보입니다.** 전에는 한 세션의 측정이 모두 같은 시각이었습니다.
A. 다른 시각 · B. 여전히 같은 시각

**11. 목록의 SLOT 칸이 `3`, `10`처럼 앞에 0 없이 보이고, 값이 없는 행은 빈 칸입니다.**
A. 맞음 · B. 다름 →

**12. 반복 측정(repeat recipe) 한 건의 상세를 열면 "측정 포인트 표"에 `회차` 열이 있고,
오른쪽 위에서 "전체"를 누르면 1회차 행들 다음에 2회차 행들이 나옵니다.**
A. 맞음 · B. 다름 → · ? repeat 측정이 없음

**13. 같은 표 위에 `회차` 필터(전체 / 1 / 2)가 있고, `2`를 누르면 2회차 행만 남습니다.**
A. 맞음 · B. 다름 →

**14. 반복이 없는 측정의 상세에는 `회차` 열이 없습니다.**
A. 없음 · B. 있음

**15. 상세 왼쪽 "측정 정보"의 LOT 옆 SLOT이 채워져 있습니다(MAP608·5EAP1501은 `Sample
Location`의 `Port 1 Slot N`에서, MAPC01은 `Slot No`에서 읽습니다).**
A. 세 장비 모두 채워짐 · B. 비어 있는 장비가 있음 → 장비

## 6. 화면 — 이미지와 원본

이미지가 있는 측정 한 건의 상세에서 "분석 이미지" 카드를 봅니다. 가능하면 이미지가 가장
많은 측정(MAP608 `WID_REAL`, 약 133장)으로 확인해 주십시오.

**16. Align·Tip·Capture·Result 네 탭 모두 이미지가 그려집니다(깨진 그림 없음).**
A. 모두 그려짐 · B. 깨지는 탭이 있음 → 탭

**17. Capture 탭의 타일 아래에 포인트 이름(`0001` 또는 `0001_X000_Y000_0001`)이 보이고,
타일을 누르면 그 포인트가 선택됩니다.**
A. 맞음 · B. 파일명이 그대로 보임

**18. Tip 탭은 포인트마다 한 장(`_C_PR`)과 마지막에 포인트 이름 없는 한 장(`C_Result`)이
있습니다.**
A. 맞음 · B. 다름 →

**19. 탭마다 "원본 전체 · N장" 버튼이 있고, 눌러 받은 zip에 Result는 `.tiff`, Align은
`.bmp`, Capture는 `.png`, Tip은 `.png`와 `.bmp`가 들어 있습니다.**
A. 네 탭 모두 맞음 · B. 다름 → 탭과 본 것

**20. 이미지를 눌러 연 팝업의 "원본 다운로드"로 받은 파일이 이미지 뷰어에서 열립니다(Align
`.bmp` 한 장, Capture `.png` 한 장이면 충분합니다).**
A. 둘 다 열림 · B. 안 열림 → 종류

**21. 이미지가 많은 측정에서 탭을 빠르게 끝까지 스크롤해도 깨진 그림이 없고, 브라우저
Network 탭에 `429` 응답이 없습니다.**
A. 없음 · B. 429가 보임

**22. 5EAP1501의 Result 탭에 "원본 전체" 버튼이 나옵니다.** 원본 재적재가 끝났는지를 보는
항목입니다. 아직이면 버튼이 없는 것이 정상입니다.
A. 나옴(재적재 끝남) · B. 없음(재적재 전)

## 7. 화면 — 팁 모니터링, 가동 현황, 시계열 비교

**23. 세 장비의 `/afm/<장비>/tips`가 "팁 값이 있는 측정이 없습니다"가 아니라 팁 종류별
목록으로 나옵니다.**
A. 세 장비 모두 · B. 비어 있는 장비가 있음 → 장비

**24. 이름에 `MCNT`가 든 종류의 머리줄에 "Tip Width 관리선은 팁마다"가 적혀 있고, 그 밖의
종류에는 `Tip Width 70.00 – 70.00` 같은 범위가 적혀 있습니다.**
A. 맞음 · B. 다름 →

**25. 5EAP1501의 `OMCL-AC160TS`가 오류 없이 나오고 머리줄이 "관리선 없음"이거나 범위입니다.**
A. 나옴 · B. 화면이 깨짐 · ? 그 종류가 없음

**26. 팁 하나를 골랐을 때 "Mileage 평균" 차트가 그 팁 안에서 오른쪽으로 갈수록 커집니다.**
A. 커짐 · B. 오르내림 → 팁 이름

**27. `/afm/map608/usage`의 "시간대별 측정"에서 한 세션의 측정이 한 칸에 몰리지 않고 실제
측정 시각대로 퍼져 있습니다.**
A. 퍼져 있음 · B. 여전히 한 칸에 몰림

**28. 측정 목록에서 20건쯤 담아 "함께 보기"를 열면, 아래 "장비 건강"의 Mileage 차트가
톱니 모양이고(팁마다 올라갔다 떨어짐) 떨어지는 자리에 세로선이 있습니다.**
A. 맞음 · B. 세로선이 없는 하락이 있음 · C. 하락 없는 자리에 세로선이 있음

**29. 28번에서 B나 C였다면, 그 자리 앞뒤 측정의 `Tip ID`·카세트·포트·슬롯·Mileage 평균·
`Last Pick Up Time`을 적어 주십시오.**
형식: `앞: DT-NCHR_CM/TC1/1/9, 1430483, 01:33:39 → 뒤: DT-NCHR_CM/TC1/1/1, 3520, 09:10:02`

**30. 위 화면들을 여는 동안 브라우저 console에 오류가 없었습니다.**
A. 없음 · B. 있음 → 화면과 메시지 한 줄

## 8. 답안지

```text
0
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24
25
26
27
28
29
30
```

## 9. 함께 알려 주시면 좋은 것

- 3절 스크립트의 출력 전체입니다.
- 화면이 열리는 데 눈에 띄게 오래 걸린 곳이 있으면 화면 이름과 대략의 시간입니다.
- 여기에 없지만 값이 이상해 보인 곳이 있으면 화면과 측정 이름 한 건입니다.
