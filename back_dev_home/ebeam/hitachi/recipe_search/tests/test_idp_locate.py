"""Gate for the .idp LOCATION step of the office adapter (Redis + OpenSearch).

`test_idp_mapping.py` covers the step after the download; this file covers the
step before it. Same reason for existing: locate -> download are the two links
in the chain that home cannot reach, so every part of them that can be made a
pure function is, and gated here.

It imports `providers/office_example.py` — the tracked template — never
`providers/office.py`, which is gitignored and absent on a clean checkout.
Redis, OpenSearch, sem_list and FTP are all stubbed; nothing here does I/O.
"""

import logging

import pytest

from back_dev_home.ebeam.hitachi.recipe_search.providers import office_example as oe


class TestFabHash:
    def test_lowercases_the_fab_at_the_redis_boundary(self):
        assert oe._fab_hash("rcp_loc", "cd-sem", "R3") == "v3_cdsem_rcp_loc_r3"

    def test_strips_surrounding_whitespace(self):
        assert oe._fab_hash("tools_in_rcp", "hv-sem", " M14A ") == (
            "v3_hvsem_tools_in_rcp_m14a"
        )

    def test_unknown_tool_type_is_a_value_error(self):
        with pytest.raises(ValueError, match="Unknown tool_type"):
            oe._fab_hash("rcp_loc", "ebeam", "R3")


class TestClassName:
    def test_prefix_before_the_first_slash(self):
        assert oe._class_name("ADI/ADI_CD_BIAS_001") == "ADI"

    def test_numeric_class_is_a_class(self):
        # Real catalog names look like this (user-confirmed 2026-07-29).
        assert oe._class_name("1/AC_M2_TAT") == "1"

    def test_only_the_first_segment_is_the_class(self):
        assert oe._class_name("OVL/SUB/DEEP_001") == "OVL"

    def test_no_slash_yields_empty_rather_than_the_whole_name(self):
        # Returning the name itself would build /HD/AC_M2_TAT/data/... — a
        # plausible path that does not exist. Empty forces the caller to bail.
        assert oe._class_name("AC_M2_TAT") == ""


class TestParseStrList:
    def test_json_list(self):
        assert oe._parse_str_list('["/Recipe/A.idw", "/Recipe/A.idp"]') == [
            "/Recipe/A.idw", "/Recipe/A.idp",
        ]

    def test_python_repr_list(self):
        assert oe._parse_str_list("['CG6300_01', 'CG6380_02']") == [
            "CG6300_01", "CG6380_02",
        ]

    def test_bytes_are_decoded(self):
        assert oe._parse_str_list(b'["CG6300_01"]') == ["CG6300_01"]

    def test_blank_is_empty(self):
        assert oe._parse_str_list("") == []


ROSTER = {
    "CG6300_01": ("10.1.2.1", "On"),
    "CG6300_07": ("10.1.2.7", "On"),
    "CG6380_02": ("10.1.2.2", "Off"),
}


class TestOrderCandidates:
    def test_available_tools_come_first(self):
        assert oe._order_candidates(["CG6380_02", "CG6300_01"], ROSTER) == [
            ("CG6300_01", "10.1.2.1"),
            ("CG6380_02", "10.1.2.2"),
        ]

    def test_registry_order_is_preserved_within_a_group(self):
        # The registry carries no ranking, so a stable order keeps the same
        # recipe hitting the same tool run after run.
        assert oe._order_candidates(["CG6300_07", "CG6300_01"], ROSTER) == [
            ("CG6300_07", "10.1.2.7"),
            ("CG6300_01", "10.1.2.1"),
        ]

    def test_tools_absent_from_the_roster_are_dropped(self):
        assert oe._order_candidates(["GONE_99", "CG6300_01"], ROSTER) == [
            ("CG6300_01", "10.1.2.1"),
        ]

    def test_all_unknown_yields_nothing(self):
        assert oe._order_candidates(["GONE_99"], ROSTER) == []

    def test_whitespace_around_an_id_still_resolves(self):
        assert oe._order_candidates([" CG6300_01 "], ROSTER) == [
            ("CG6300_01", "10.1.2.1"),
        ]


class TestEqpIpIndex:
    def test_builds_the_index_from_the_sem_list_roster(self, monkeypatch):
        monkeypatch.setattr(oe, "get_sem_list", lambda: [
            {"eqp_id": "CG6300_01", "eqp_ip": "10.1.2.1", "available": "On"},
            {"eqp_id": "CG6380_02", "eqp_ip": "10.1.2.2", "available": "Off"},
        ])
        oe._eqp_ip_index.cache_clear()
        assert oe._eqp_ip_index() == {
            "CG6300_01": ("10.1.2.1", "On"),
            "CG6380_02": ("10.1.2.2", "Off"),
        }
        oe._eqp_ip_index.cache_clear()

    def test_rows_without_an_ip_are_skipped(self, monkeypatch):
        # A fleet row with no IP cannot be dialed; keeping it would produce a
        # candidate that always fails the SSRF guard.
        monkeypatch.setattr(oe, "get_sem_list", lambda: [
            {"eqp_id": "CG6300_01", "eqp_ip": "", "available": "On"},
        ])
        oe._eqp_ip_index.cache_clear()
        assert oe._eqp_ip_index() == {}
        oe._eqp_ip_index.cache_clear()


class _FakeRedis:
    """Minimal `hget` stand-in. `store` is {key: {field: value}}."""

    def __init__(self, store):
        self.store = store

    def hget(self, key, field):
        return self.store.get(key, {}).get(field)


LOC_KEY = "v3_cdsem_rcp_loc_r3"
TOOLS_KEY = "v3_cdsem_tools_in_rcp_r3"
RECIPE = "ADI/ADI_CD_BIAS_001"


@pytest.fixture
def wired(monkeypatch):
    """Both hashes populated and the roster resolvable — the happy path."""
    def _wire(store):
        monkeypatch.setattr(oe, "_redis_client", lambda: _FakeRedis(store))
        monkeypatch.setattr(oe, "_eqp_ip_index", lambda: ROSTER)
    return _wire


class TestLocateViaRedis:
    def test_builds_candidates_from_both_hashes(self, wired):
        wired({
            LOC_KEY: {RECIPE: '["/Recipe/ADI/ADI_CD_BIAS_001.idw",'
                              ' "/Recipe/ADI/ADI_CD_BIAS_001.idp"]'},
            TOOLS_KEY: {RECIPE: '["CG6380_02", "CG6300_01"]'},
        })
        locations = oe._locate_via_redis("cd-sem", RECIPE, "R3")
        assert locations == [
            oe._IdpLocation("CG6300_01", "10.1.2.1", "ADI",
                            "ADI_CD_BIAS_001", "ADI_CD_BIAS_001"),
            oe._IdpLocation("CG6380_02", "10.1.2.2", "ADI",
                            "ADI_CD_BIAS_001", "ADI_CD_BIAS_001"),
        ]

    def test_paths_are_reduced_to_stems(self, wired):
        # The registry stores paths; the FTP tree wants bare names.
        wired({
            LOC_KEY: {RECIPE: '["/Recipe/ADI/A.idw", "/Recipe/ADI/B.idp"]'},
            TOOLS_KEY: {RECIPE: '["CG6300_01"]'},
        })
        location = oe._locate_via_redis("cd-sem", RECIPE, "R3")[0]
        assert (location.idw_stem, location.idp_stem) == ("A", "B")

    def test_blank_fab_falls_back(self, wired):
        wired({})
        assert oe._locate_via_redis("cd-sem", RECIPE, None) is None

    def test_recipe_without_a_class_prefix_falls_back(self, wired):
        wired({
            LOC_KEY: {"AC_M2_TAT": '["/R/A.idw", "/R/A.idp"]'},
            TOOLS_KEY: {"AC_M2_TAT": '["CG6300_01"]'},
        })
        assert oe._locate_via_redis("cd-sem", "AC_M2_TAT", "R3") is None

    def test_missing_location_field_falls_back(self, wired):
        wired({TOOLS_KEY: {RECIPE: '["CG6300_01"]'}})
        assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is None

    def test_one_sided_location_value_falls_back(self, wired):
        # Read positionally, so a 1-entry list is unusable rather than partial.
        wired({
            LOC_KEY: {RECIPE: '["/Recipe/ADI/A.idw"]'},
            TOOLS_KEY: {RECIPE: '["CG6300_01"]'},
        })
        assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is None

    def test_missing_tool_field_falls_back(self, wired):
        wired({LOC_KEY: {RECIPE: '["/R/A.idw", "/R/A.idp"]'}})
        assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is None

    def test_no_tool_resolves_falls_back(self, wired):
        wired({
            LOC_KEY: {RECIPE: '["/R/A.idw", "/R/A.idp"]'},
            TOOLS_KEY: {RECIPE: '["GONE_99"]'},
        })
        assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is None

    def test_uppercase_fab_reaches_the_lowercase_key(self, wired):
        wired({
            LOC_KEY: {RECIPE: '["/R/A.idw", "/R/A.idp"]'},
            TOOLS_KEY: {RECIPE: '["CG6300_01"]'},
        })
        assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is not None

    def test_empty_path_component_falls_back(self, wired, caplog):
        # "/" survives the parse filter (it is not empty) but PurePosixPath("/")
        # has an empty stem, so the assembled path would be data//B.idp — a
        # plausible path to nothing. Asserting on the log pins WHICH of the
        # seven bail paths fired; a bare `is None` cannot tell them apart.
        wired({
            LOC_KEY: {RECIPE: '["/", "/Recipe/ADI/B.idp"]'},
            TOOLS_KEY: {RECIPE: '["CG6300_01"]'},
        })
        with caplog.at_level(logging.INFO, logger=oe.__name__):
            assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is None
        assert "has an empty path component" in caplog.text
