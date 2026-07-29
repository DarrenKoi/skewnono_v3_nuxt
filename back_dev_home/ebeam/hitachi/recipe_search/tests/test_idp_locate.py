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
from back_dev_home.msr_image.errors import InvalidToolIp


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


def _hit(eqp_id, ts, **overrides):
    hit = {
        "eqp_id": eqp_id,
        "eqp_ip": f"10.9.9.{eqp_id[-1]}",
        "class_name": "ADI",
        "idw_name": "/Recipe/ADI/ADI_CD_BIAS_001.idw",
        "idp_name": "/Recipe/ADI/ADI_CD_BIAS_001.idp",
        "timestamp": ts,
    }
    hit.update(overrides)
    return hit


class TestLocateViaMeasHist:
    def test_returns_every_complete_hit_newest_first(self, monkeypatch):
        monkeypatch.setattr(oe, "fetch_hits", lambda *a, **k: [
            _hit("CG6300_1", "2026-07-28T10:00:00"),
            _hit("CG6300_2", "2026-07-27T10:00:00"),
        ])
        locations = oe._locate_via_meas_hist("cd-sem", RECIPE, "R3")
        assert [location.eqp_id for location in locations] == [
            "CG6300_1", "CG6300_2",
        ]

    def test_incomplete_documents_are_skipped_not_fatal(self, monkeypatch):
        monkeypatch.setattr(oe, "fetch_hits", lambda *a, **k: [
            _hit("CG6300_1", "2026-07-28T10:00:00", eqp_ip=""),
            _hit("CG6300_2", "2026-07-27T10:00:00"),
        ])
        locations = oe._locate_via_meas_hist("cd-sem", RECIPE, "R3")
        assert [location.eqp_id for location in locations] == ["CG6300_2"]

    def test_no_document_is_a_lookup_error(self, monkeypatch):
        monkeypatch.setattr(oe, "fetch_hits", lambda *a, **k: [])
        with pytest.raises(LookupError, match="has never been measured"):
            oe._locate_via_meas_hist("cd-sem", RECIPE, "R3")

    def test_all_documents_incomplete_is_a_lookup_error(self, monkeypatch):
        monkeypatch.setattr(oe, "fetch_hits", lambda *a, **k: [
            _hit("CG6300_1", "2026-07-28T10:00:00", eqp_ip=""),
        ])
        with pytest.raises(LookupError, match="none carries every field"):
            oe._locate_via_meas_hist("cd-sem", RECIPE, "R3")

    def test_duplicate_documents_from_the_same_tool_collapse_to_one(self, monkeypatch):
        # meas_hist's grain is one document per measurement RUN, so the
        # newest N documents for a recipe are usually the SAME tool measuring
        # N different lots — same eqp_id, same idw/idp paths, only the
        # timestamp differs. Without collapsing these, _download_first would
        # re-dial that one host N times instead of trying N different tools.
        monkeypatch.setattr(oe, "fetch_hits", lambda *a, **k: [
            _hit("CG6300_01", "2026-07-28T10:00:00"),
            _hit("CG6300_01", "2026-07-28T09:00:00"),
            _hit("CG6300_01", "2026-07-28T08:00:00"),
        ])
        locations = oe._locate_via_meas_hist("cd-sem", RECIPE, "R3")
        assert [location.eqp_id for location in locations] == ["CG6300_01"]


class TestLocateIdpDispatch:
    def test_redis_wins_and_opensearch_is_never_queried(self, monkeypatch):
        sentinel = [oe._IdpLocation("CG6300_01", "10.1.2.1", "ADI", "A", "A")]
        monkeypatch.setattr(oe, "_locate_via_redis", lambda *a: sentinel)
        monkeypatch.setattr(oe, "_locate_via_meas_hist", lambda *a: pytest.fail(
            "meas_hist must not be queried when the registry answered"
        ))
        assert oe._locate_idp("cd-sem", RECIPE, "R3") == sentinel

    def test_registry_miss_falls_through_to_meas_hist(self, monkeypatch):
        sentinel = [oe._IdpLocation("CG6300_02", "10.9.9.2", "ADI", "A", "A")]
        monkeypatch.setattr(oe, "_locate_via_redis", lambda *a: None)
        monkeypatch.setattr(oe, "_locate_via_meas_hist", lambda *a: sentinel)
        assert oe._locate_idp("cd-sem", RECIPE, "R3") == sentinel


class TestLocateFailureNamesBothSources:
    """The 502 body has to say what the registry did, not just what meas_hist did.

    When both sources come up empty the client sees one string, and until now
    that string named only meas_hist ("No document in meas_hist_cdsem has
    full_name=..."). From outside the office three very different situations
    produce it and the message told them apart in none:

      * the registry declined for a nameable reason (no entry, no tool, no IP),
      * the registry was never consulted because the deployed ``office.py`` is a
        STALE copy that predates it,
      * the recipe genuinely has neither a registry entry nor a measurement.

    So the reason now travels with the error instead of only reaching the log,
    which the person reading a browser Network tab does not have.
    """

    @staticmethod
    def _no_meas_hist(*args):
        raise LookupError(
            f"No document in meas_hist_cdsem has full_name={RECIPE!r} for fab 'R3'."
        )

    def test_registry_bail_reason_travels_into_the_error(self, wired, monkeypatch):
        # A real bail: the location hash has no entry for this recipe.
        wired({TOOLS_KEY: {RECIPE: '["CG6300_01"]'}})
        monkeypatch.setattr(oe, "_locate_via_meas_hist", self._no_meas_hist)

        with pytest.raises(LookupError) as excinfo:
            oe._locate_idp("cd-sem", RECIPE, "R3")

        message = str(excinfo.value)
        assert "No document in meas_hist_cdsem" in message  # what it always said
        assert LOC_KEY in message  # ...and now WHICH registry key came up empty
        assert "no usable [idw, idp] entry" in message

    def test_every_registry_bail_path_is_reportable(self, wired, monkeypatch):
        # Not just the one above: whichever of the bail paths fires, the
        # operator must be able to read it off the response.
        wired({
            LOC_KEY: {RECIPE: '["/R/A.idw", "/R/A.idp"]'},
            TOOLS_KEY: {RECIPE: '["GONE_99"]'},  # not in the sem_list roster
        })
        monkeypatch.setattr(oe, "_locate_via_meas_hist", self._no_meas_hist)

        with pytest.raises(LookupError, match="resolves to an IP"):
            oe._locate_idp("cd-sem", RECIPE, "R3")

    def test_stays_a_bare_lookup_error_so_the_factory_maps_it_to_502(
        self, wired, monkeypatch
    ):
        # back_dev_home/__init__.py handles LookupError with
        # `if type(err) is not LookupError: return _internal_500(err)`, so
        # re-raising as any subclass would turn this 502 into an opaque 500.
        wired({})
        monkeypatch.setattr(oe, "_locate_via_meas_hist", self._no_meas_hist)

        with pytest.raises(LookupError) as excinfo:
            oe._locate_idp("cd-sem", RECIPE, "R3")
        assert type(excinfo.value) is LookupError

    def test_no_registry_clause_when_the_registry_answered(self, wired, monkeypatch):
        # Nothing to explain when the registry succeeded — and no error at all.
        wired({
            LOC_KEY: {RECIPE: '["/R/A.idw", "/R/A.idp"]'},
            TOOLS_KEY: {RECIPE: '["CG6300_01"]'},
        })
        monkeypatch.setattr(oe, "_locate_via_meas_hist", self._no_meas_hist)
        assert oe._locate_idp("cd-sem", RECIPE, "R3")


THREE = [
    oe._IdpLocation("CG6300_01", "10.1.2.1", "ADI", "A", "A"),
    oe._IdpLocation("CG6300_07", "10.1.2.7", "ADI", "A", "A"),
    oe._IdpLocation("CG6380_02", "10.1.2.2", "ADI", "A", "A"),
]


def _always_raise(exception_type, message):
    """A _download_idp stand-in that fails on every tool."""
    def _download(location, dest_dir):
        raise exception_type(f"{message} ({location.eqp_id})")
    return _download


class TestDownloadFirst:
    def test_first_success_wins_and_stops(self, monkeypatch, tmp_path):
        dialed = []

        def _download(location, dest_dir):
            dialed.append(location.eqp_id)
            if location.eqp_id != "CG6300_07":
                raise LookupError("connection refused")
            return dest_dir / "A.idp"

        monkeypatch.setattr(oe, "_download_idp", _download)
        assert oe._download_first(THREE, tmp_path)[0] == tmp_path / "A.idp"
        # Stopped at the first success — the third tool was never dialed.
        assert dialed == ["CG6300_01", "CG6300_07"]

    def test_it_returns_the_tool_that_actually_served_the_file(
        self, monkeypatch, tmp_path
    ):
        """Not the first candidate — the one that WON.

        RecipeDetailResponse.locator sends the client back to this tool for the
        raw-recipe folder (param-detail / align-detail / recipe-image). Naming
        the first candidate instead would point every follow-up call at a tool
        that did not have the recipe.
        """
        def _download(location, dest_dir):
            if location.eqp_id != "CG6300_07":
                raise LookupError("connection refused")
            return dest_dir / "A.idp"

        monkeypatch.setattr(oe, "_download_idp", _download)
        _path, location = oe._download_first(THREE, tmp_path)
        assert location.eqp_id == "CG6300_07"
        assert location is THREE[1]

    def test_every_tool_failing_names_each_one(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            oe, "_download_idp", _always_raise(LookupError, "no such file")
        )
        with pytest.raises(LookupError) as excinfo:
            oe._download_first(THREE, tmp_path)
        message = str(excinfo.value)
        assert "Tried 3 tool(s)" in message
        assert "CG6300_01" in message and "CG6380_02" in message

    def test_one_blocked_ip_is_skipped_not_fatal(self, monkeypatch, tmp_path):
        def _download(location, dest_dir):
            if location.eqp_id == "CG6300_01":
                raise InvalidToolIp("outside the allowed subnets")
            return dest_dir / "A.idp"

        monkeypatch.setattr(oe, "_download_idp", _download)
        # A single stale roster IP must not fail a recipe held on three tools.
        assert oe._download_first(THREE, tmp_path)[0] == tmp_path / "A.idp"

    def test_every_ip_blocked_reraises_the_guard(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            oe, "_download_idp", _always_raise(InvalidToolIp, "outside subnets")
        )
        # Not a fetch failure — this is the misconfiguration MIGRATION.md
        # documents InvalidToolIp for, so it must survive as itself. Matching
        # on the FIRST candidate's id (CG6300_01) pins this to `raise
        # blocked[0]` specifically — a bare `pytest.raises(InvalidToolIp)`
        # cannot tell that apart from a freshly constructed InvalidToolIp.
        with pytest.raises(InvalidToolIp, match=r"\(CG6300_01\)"):
            oe._download_first(THREE, tmp_path)

    def test_mixed_blocked_and_failed_raises_lookup_error_naming_both(
        self, monkeypatch, tmp_path
    ):
        # THREE = [CG6300_01, CG6300_07, CG6380_02]. If `blocked` truthiness
        # ever replaced the `len(blocked) == len(candidates)` guard, this
        # mixed case would wrongly raise InvalidToolIp instead of LookupError
        # — silently turning an informative 502 into a generic 500.
        def _download(location, dest_dir):
            if location.eqp_id == "CG6300_01":
                raise InvalidToolIp("outside the allowed subnets")
            raise LookupError("no such file")

        monkeypatch.setattr(oe, "_download_idp", _download)
        with pytest.raises(LookupError) as excinfo:
            oe._download_first(THREE, tmp_path)
        message = str(excinfo.value)
        # Not InvalidToolIp: excinfo.type asserts the exact raised type since
        # pytest.raises(LookupError) alone would also accept a subclass.
        assert excinfo.type is LookupError
        assert "IP blocked" in message  # the blocked candidate is named
        assert "no such file" in message  # the failed candidates are named
