"""R3 device description 표준 포맷 파서 (user-confirmed 2026-11-02).

포맷: ``[(개발 phase) / (DRAM|NAND|기타)] (Tech) (개발 phase) (Cell/Peri)``.
정답은 합의 문서의 예시 그대로입니다.
"""

import pytest

from backend.ebeam.device_statistics.desc_format import parse_device_desc


@pytest.mark.parametrize(("desc", "family", "phase", "memory"), [
    ("[EV / DRAM] Cubit EV Cell&PEri", "Core", "EV", "DRAM"),
    ("[Pool제 / NAND] Petra PV Peri", "Pool", None, "NAND"),
    # 괄호 phase 가 기준입니다 — 본문의 두 번째 phase(PV)가 아닙니다.
    ("[TV / DRAM] Spica DPEX PV Peri", "Core", "TV", "DRAM"),
    # 메모리가 기타면 Core 가 아닙니다 → RTC 룰.
    ("[TV / 기타] SC-MRAM TV Cell&Peri", "Other", "TV", "unknown"),
    ("[RTC / DRAM] VIRGO RTC Cell&PEri", "Other", None, "DRAM"),
    ("[요소기술 / NAND] SSL Cut Cell", "Other", None, "NAND"),
    ("[EV / NAND] AI-N B EV Cell", "Core", "EV", "NAND"),
    ("[TV / DRAM] PMG1.0 TV Peri", "Core", "TV", "DRAM"),
])
def test_agreed_examples(desc, family, phase, memory):
    assert parse_device_desc(desc) == {"family": family, "phase": phase, "memory_class": memory}


@pytest.mark.parametrize(("desc", "phase"), [
    ("[tEV / DRAM] X tEV Cell", "tEV"),
    ("[t-EV / DRAM] X Cell", "tEV"),
    ("[DTV / DRAM] X DTV Cell", "DTV"),
    ("[TTV/NAND] X TTV Peri", "TTV"),
    ("[pv / dram] X PV Peri", "PV"),
])
def test_core_phase_spellings(desc, phase):
    assert parse_device_desc(desc)["phase"] == phase
    assert parse_device_desc(desc)["family"] == "Core"


def test_full_width_brackets_and_slash_are_accepted():
    # 한글 IME 로 치면 ［／］ 전각이 섞이기 쉽습니다. 사람이 쓰는 칸이라 NFKC 로 받습니다.
    assert parse_device_desc("［TV ／ DRAM］ Spica TV Peri") == {
        "family": "Core", "phase": "TV", "memory_class": "DRAM",
    }


def test_pool_in_bracket_wins_even_with_non_core_memory():
    # 괄호에 Pool제 가 있으면 Pool 이 우선합니다 (user-confirmed 2026-11-02).
    assert parse_device_desc("[Pool제 / 기타] X PV Cell") == {
        "family": "Pool", "phase": None, "memory_class": "unknown",
    }


@pytest.mark.parametrize("desc", [
    "DRAM Pool제 (@Spica PV)",  # 합의 이전 포맷
    "PV DRAM T1Y lot",
    "",
    None,
    "  [EV DRAM] 슬래시 없음",
])
def test_legacy_or_malformed_desc_is_unparsed(desc):
    # None = 룰 미정(Gray). 예전 토큰 추론으로 되돌아가지 않습니다.
    assert parse_device_desc(desc) is None
