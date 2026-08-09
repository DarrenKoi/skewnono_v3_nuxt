"""M-fab 스텝 정렬 규칙 테스트.

핵심은 longest-prefix 입니다 — 목록에 SNC/SNC2/SN 과 M2/M2C 가 함께 있어서, 순진한
startswith 스캔은 "SNC2 ..." 를 SNC 나 SN 으로 잡습니다. 그 실수는 조용히 잘못된
순서를 만들 뿐 예외를 던지지 않으므로 테스트로 고정합니다.
"""

from back_dev_home.ebeam.device_statistics.oper_order import (
    OPER_PREFIX_ORDER,
    UNKNOWN_RANK,
    oper_prefix,
    oper_rank,
    sort_oper_descs,
    unknown_prefixes,
)


class TestLongestPrefix:
    def test_snc2_is_not_snc_or_sn(self):
        assert oper_prefix("SNC2 CELL OPEN ETCH CLN CD") == "SNC2"

    def test_snc_still_matches_snc(self):
        assert oper_prefix("SNC SOMETHING") == "SNC"

    def test_sn_matches_sn_only_when_nothing_longer_fits(self):
        assert oper_prefix("SN PLAIN") == "SN"

    def test_m2c_is_not_m2(self):
        assert oper_prefix("M2C METAL 2 CONTACT") == "M2C"

    def test_m2_still_matches_m2(self):
        assert oper_prefix("M2 METAL 2") == "M2"

    def test_every_listed_prefix_resolves_to_itself(self):
        # 목록에 새 접두사를 추가했을 때 기존 항목을 가려 버리지 않는지 확인합니다.
        for prefix in OPER_PREFIX_ORDER:
            assert oper_prefix(f"{prefix} DESC") == prefix


class TestRank:
    def test_rank_follows_the_declared_order(self):
        assert oper_rank("ISO START") == 0
        assert oper_rank("RDL LAST") == len(OPER_PREFIX_ORDER) - 1

    def test_snc2_ranks_after_m0c_as_declared(self):
        # 선언 순서가 ... SNC, M0C, SNC2, SN ... 이라 알파벳 직관과 다릅니다.
        assert oper_rank("SNC X") < oper_rank("M0C X") < oper_rank("SNC2 X")
        assert oper_rank("SNC2 X") < oper_rank("SN X")

    def test_unknown_prefix_sorts_last_but_is_kept(self):
        assert oper_rank("ZZZ UNLISTED STEP") == UNKNOWN_RANK
        assert UNKNOWN_RANK == len(OPER_PREFIX_ORDER)

    def test_blank_is_unknown(self):
        assert oper_rank("") == UNKNOWN_RANK

    def test_matching_is_case_insensitive(self):
        assert oper_prefix("snc2 lower case") == "SNC2"
        assert oper_rank("snc2 lower") == oper_rank("SNC2 UPPER")

    def test_leading_whitespace_tolerated(self):
        assert oper_prefix("  ILD GAP FILL") == "ILD"


class TestSort:
    def test_sorts_into_declared_process_order(self):
        descs = ["RDL X", "ISO X", "GT X", "CW X"]
        assert sort_oper_descs(descs) == ["ISO X", "CW X", "GT X", "RDL X"]

    def test_unknown_steps_land_at_the_end_not_dropped(self):
        descs = ["ZZZ NEW STEP", "ISO X"]
        result = sort_oper_descs(descs)
        assert result == ["ISO X", "ZZZ NEW STEP"]
        assert len(result) == len(descs)

    def test_same_prefix_is_ordered_deterministically(self):
        # 같은 접두사끼리는 입력 순서에 좌우되지 않아야 합니다.
        forward = sort_oper_descs(["M2 B", "M2 A"])
        backward = sort_oper_descs(["M2 A", "M2 B"])
        assert forward == backward == ["M2 A", "M2 B"]

    def test_duplicates_are_preserved(self):
        # 중복 제거는 호출자(unique oper_det_desc 집계)의 책임입니다.
        assert sort_oper_descs(["ISO X", "ISO X"]) == ["ISO X", "ISO X"]


class TestUnknownReporting:
    def test_reports_only_unlisted_steps(self):
        descs = ["ISO X", "QQQ A", "ZZZ B", "SNC2 C"]
        assert unknown_prefixes(descs) == ["QQQ A", "ZZZ B"]

    def test_empty_when_all_known(self):
        assert unknown_prefixes(["ISO X", "SNC2 Y"]) == []

    def test_deduplicates(self):
        assert unknown_prefixes(["QQQ A", "QQQ A"]) == ["QQQ A"]
