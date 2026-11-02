"""R3 룰 표 (user-confirmed 2026-11-02 — description 표준화와 함께 개정).

- Core EV·tEV·DTV·TTV : DRAM EDGE 10 / NAND 8, EDGE_EX 0
- Core TV·PV          : EDGE 16 / EDGE_EX 16
- Pool제 (수율 후 기준으로 통합) : DRAM 10/10, NAND 8/8
- 그 외(RTC·Cubic·요소기술·기타) : RTC 룰 EDGE 10 / EDGE_EX 0
- Sample 도 같은 WAFER/LEVEL/EDGE/EDGE_EX, 기타 파라는 0 (사유 필요)
"""

import pytest

from backend.ebeam.device_statistics.providers.rules import get_rules


def _cell(recipe_class, family, phase=None, memory=None):
    """ruleEngine.selectorMatches 의 first-match 를 그대로 흉내 냅니다."""
    for c in get_rules("R3")["cells"]:
        s = c["selector"]
        if s["recipe_class"] != recipe_class or s.get("family") != family:
            continue
        if "phase_in" in s and phase not in s["phase_in"]:
            continue
        if "memory_class" in s and s["memory_class"] != memory:
            continue
        return c
    raise AssertionError(f"no cell for {recipe_class} {family} {phase} {memory}")


@pytest.mark.parametrize("recipe_class", ["Main", "Sample"])
@pytest.mark.parametrize(("family", "phase", "memory", "edge", "edge_ex"), [
    ("Core", "EV", "DRAM", 10, 0),
    ("Core", "tEV", "NAND", 8, 0),
    ("Core", "DTV", "DRAM", 10, 0),
    ("Core", "TTV", "NAND", 8, 0),
    ("Core", "TV", "DRAM", 16, 16),
    ("Core", "PV", "NAND", 16, 16),
    ("Pool", None, "DRAM", 10, 10),
    ("Pool", None, "NAND", 8, 8),
    # [Pool제 / 기타] — Pool 우선. 메모리 기타는 DRAM 쪽 cap (기본값, 2026-11-02).
    ("Pool", None, "unknown", 10, 10),
    ("Other", None, "DRAM", 10, 0),
    ("Other", "TV", "unknown", 10, 0),
])
def test_edge_caps(recipe_class, family, phase, memory, edge, edge_ex):
    caps = _cell(recipe_class, family, phase, memory)["caps"]
    assert (caps["WAFER"], caps["LEVEL"], caps["EDGE"], caps["EDGE_EX"]) == (13, 4, edge, edge_ex)
    assert caps["_other"] == (9 if recipe_class == "Main" else 0)


def test_no_yield_check_axis_left():
    # Pool 수율 전/후 구분은 폐기되었습니다 — 셀이 그 축을 요구하면 Gray-B 가 생깁니다.
    assert all("yield_check" not in c["selector"] for c in get_rules("R3")["cells"])


def test_every_r3_cell_names_a_family():
    # family 없는 셀은 description 미준수(family=None) recipe 까지 주장할 수 있습니다.
    assert all(c["selector"].get("family") for c in get_rules("R3")["cells"])
