"""Gate for the align-image lookup live_alarm calls.

The question this answers is narrow: an ALIGNMENT FAIL alarm names a tool and
a recipe, and the screen wants that recipe's two align reference images (OM and
SEM) as THAT tool holds them. So the seam takes an eqp_id and reports which
tool the answer actually came from -- a substitution has to be visible, because
tools hold different versions of the same recipe.

No FTP happens here. The names are computed (user-confirmed 2026-08-21: HV-SEM
align images carry the same IMAP{p:04d}.jpeg names as CD-SEM, with none of the
-U/-T/-M/-L splitting its measurement slots have), so this seam is pure
resolution and the tool is only dialed when the bytes are requested.
"""

import pytest

from back_dev_home.ebeam.recipe_search.providers import mock
from back_dev_home.ebeam.recipe_search.providers import office_example as oe


class TestMockAlignImages:
    def test_names_the_two_optics(self):
        payload = mock.get_align_images(
            "cd-sem", "MONITOR/CD_TOP_01", "M14A", "CG6300_01"
        )
        assert [(img["p_no"], img["optic"], img["name"]) for img in payload["images"]] == [
            (1, "OM", "IMAP0001.jpeg"),
            (2, "SEM", "IMAP0002.jpeg"),
        ]

    def test_the_serving_tool_is_reported_alongside_the_requested_one(self):
        payload = mock.get_align_images(
            "cd-sem", "MONITOR/CD_TOP_01", "M14A", "CG6300_01"
        )
        assert payload["requested_eqp_id"] == "CG6300_01"
        assert payload["from_requested_tool"] == (
            payload["eqp_id"] == payload["requested_eqp_id"]
        )

    def test_both_substitution_outcomes_occur_at_home(self):
        # The value-domain guard. Office-side a sibling answers only when the
        # registry omits the requested tool or the roster cannot route to it,
        # which is rare -- and a mock that always honoured the request would
        # leave the screen's "다른 장비 사본" branch unreachable at home, so
        # nobody would ever see it until the office.
        seen = {
            mock.get_align_images(
                "cd-sem", "MONITOR/CD_TOP_01", "M14A", f"CG6300_{n:02d}"
            )["from_requested_tool"]
            for n in range(1, 25)
        }
        assert seen == {True, False}

    def test_no_requested_tool_is_not_a_substitution(self):
        # recipe-search opens a recipe without naming a tool. Reporting that
        # as a substitution would make its screen claim a mismatch that has no
        # meaning there.
        payload = mock.get_align_images("cd-sem", "MONITOR/CD_TOP_01", "M14A", None)
        assert payload["requested_eqp_id"] == ""
        assert payload["from_requested_tool"] is True


ROSTER = {
    "CG6300_01": ("10.1.2.1", "On"),
    "CG6380_02": ("10.1.2.2", "Off"),
}
LOC_KEY = "v3_cdsem_rcp_loc_r3"
TOOLS_KEY = "v3_cdsem_tools_in_rcp_r3"
RECIPE = "ADI/ADI_CD_BIAS_001"
STORE = {
    LOC_KEY: {RECIPE: '["/Recipe/ADI/ADI_CD_BIAS_001.idw",'
                      ' "/Recipe/ADI/ADI_CD_BIAS_001.idp"]'},
    TOOLS_KEY: {RECIPE: '["CG6300_01", "CG6380_02"]'},
}


class _FakeRedis:
    def __init__(self, store):
        self.store = store

    def hget(self, key, field):
        return self.store.get(key, {}).get(field)


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setattr(oe, "_redis_client", lambda: _FakeRedis(STORE))
    monkeypatch.setattr(oe, "_eqp_ip_index", lambda: ROSTER)


class TestOfficeAlignImages:
    def test_the_locator_points_at_the_requested_tool_even_when_offline(self, wired):
        # The bug this whole seam exists to prevent. CG6380_02 is available=Off
        # and sorts LAST in the ordinary candidate walk, so without a
        # preference the answer would be CG6300_01's copy of the recipe --
        # silently, and about a different file than the one that failed.
        payload = oe.get_align_images("cd-sem", RECIPE, "R3", "CG6380_02")
        assert payload["locator"]["eqp_ip"] == "10.1.2.2"
        assert payload["eqp_id"] == "CG6380_02"
        assert payload["from_requested_tool"] is True

    def test_an_unroutable_request_is_reported_not_hidden(self, wired):
        # GONE_99 is not in the roster, so there is no IP to dial and the
        # answer necessarily comes from a sibling. Saying so is the point:
        # a silent substitution reads as "this recipe's align target looks
        # fine" when the file examined was never the failing tool's.
        payload = oe.get_align_images("cd-sem", RECIPE, "R3", "GONE_99")
        assert payload["eqp_id"] == "CG6300_01"
        assert payload["requested_eqp_id"] == "GONE_99"
        assert payload["from_requested_tool"] is False

    def test_opening_a_recipe_without_a_tool_is_not_a_substitution(self, wired):
        payload = oe.get_align_images("cd-sem", RECIPE, "R3", None)
        assert payload["from_requested_tool"] is True

    def test_both_providers_answer_the_same_contract(self, wired):
        office = oe.get_align_images("cd-sem", RECIPE, "R3", "CG6300_01")
        home = mock.get_align_images("cd-sem", RECIPE, "R3", "CG6300_01")
        assert office.keys() == home.keys()
        assert office["images"] == home["images"]
        assert office["locator"].keys() == home["locator"].keys()
