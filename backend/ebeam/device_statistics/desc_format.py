"""R3 device description 표준 포맷 파서 — 계측 룰 축(family·phase·memory)의 단일 원천.

합의 포맷 (user-confirmed 2026-11-02)::

    [(개발 phase) / (DRAM | NAND | 기타)] (Tech 이름) (개발 phase) (Cell/Peri)

    [EV / DRAM] Cubit EV Cell&PEri
    [Pool제 / NAND] Petra PV Peri
    [TV / 기타] SC-MRAM TV Cell&Peri

룰을 가르는 것은 **앞 괄호뿐**입니다. 본문에 phase 가 한 번 더 나오는 이유는
아직 설명받지 않았으므로(user 2026-11-02 "나중에 설명") 읽지 않습니다 — 예시
``[TV / DRAM] Spica DPEX PV Peri`` 처럼 둘이 다를 수 있습니다. Cell/Peri/Dummy
꼬리도 아직 룰에 쓰이지 않아 읽지 않습니다.

분류:

- **Core**  — 괄호 phase 가 EV·tEV·DTV·TTV·TV·PV 이고 메모리가 DRAM/NAND.
- **Pool**  — 괄호 phase 가 Pool제. 메모리와 무관하게 **Pool 이 우선**합니다
  (user-confirmed 2026-11-02) — ``[Pool제 / 기타]`` 도 Pool 입니다.
- **Other** — 나머지 전부(RTC·Cubic·요소기술·Core phase 인데 메모리 기타 …).
  모두 RTC 룰.
- ``None``  — 괄호가 없는 합의 이전 포맷. 룰 미정(Gray)으로 판정합니다 — 예전
  토큰 추론(Pool/VG 단어 찾기)으로 되돌아가지 않기로 했습니다(user 2026-11-02).

office 어댑터와 mock 이 **같이** 이 함수를 씁니다 — 한쪽만 고쳐지는 drift 를
막기 위해서입니다.
"""

import re
import unicodedata
from typing import Literal, TypedDict

Family = Literal["Core", "Pool", "Other"]
Phase = Literal["EV", "tEV", "DTV", "TTV", "TV", "PV"]


class DescAxes(TypedDict):
    family: Family
    phase: Phase | None  # Core phase 일 때만. Pool·RTC·요소기술 은 None.
    memory_class: Literal["DRAM", "NAND", "unknown"]


_BRACKET = re.compile(r"^\s*\[\s*([^/\]]+?)\s*/\s*([^\]]+?)\s*\]")

# 공백·하이픈을 지우고 대문자로 맞춘 키 → 정규 표기. "t-EV" 도 tEV 로 받습니다.
_CORE_PHASES: dict[str, Phase] = {
    "EV": "EV", "TEV": "tEV", "DTV": "DTV", "TTV": "TTV", "TV": "TV", "PV": "PV",
}


def parse_device_desc(desc: str | None) -> DescAxes | None:
    # NFKC — 사람이 치는 칸이라 전각 ［／］ 가 섞입니다. 프론트 extractStage 도 같습니다.
    m = _BRACKET.match(unicodedata.normalize("NFKC", desc or ""))
    if not m:
        return None
    phase_key = re.sub(r"[\s\-]", "", m.group(1)).upper()
    mem = m.group(2).strip().upper()
    memory = mem if mem in ("DRAM", "NAND") else None
    phase = _CORE_PHASES.get(phase_key)

    family: Family
    if phase_key.startswith("POOL"):
        family = "Pool"
    elif memory and phase:
        family = "Core"
    else:
        family = "Other"
    return {"family": family, "phase": phase, "memory_class": memory or "unknown"}
