"""Gate for the align-image lookup live_alarm calls.

The question this answers is narrow: an ALIGNMENT FAIL alarm names a tool and
a recipe, and the screen wants that recipe's two align reference images (OM and
SEM) as THAT tool holds them. So the seam takes an eqp_id and reports which
tool the answer actually came from -- a substitution has to be visible, because
tools hold different versions of the same recipe.

The names are DISCOVERED from the raw folder, not computed. Until 2026-08-22
this seam returned both optics unconditionally and dialed no tool at all; a
recipe with only P.No 1 therefore published an IMAP0002.jpeg that does not
exist, and the browser found out as a 404 on `recipe-image`. One listing round
trip buys the answer. A tool that cannot be listed is SourceUnavailable (503),
not an empty set -- a dead tool has to report itself as dead rather than as a
recipe with nothing to align to.
"""

import pytest

from back_dev_home.ebeam.recipe_search.providers import mock
from back_dev_home.ebeam.recipe_search.providers import office_example as oe
from back_dev_home.msr_image.errors import SourceUnavailable


def _names(payload) -> list[str]:
    return [img["name"] for img in payload["images"]]


@pytest.fixture(scope="module")
def home_payloads():
    """Enough recipes to see every shape the mock can produce.

    Built once: the three tests below differ only in what they assert about
    the same set, and rebuilding it per test made the formula for a recipe
    name a thing written three times.
    """
    return [
        mock.get_align_images("cd-sem", f"MONITOR/CD_TOP_{n:02d}", "M14A", "CG6300_01")
        for n in range(1, 25)
    ]


class TestMockAlignImages:
    def test_names_the_two_optics(self):
        payload = mock.get_align_images(
            "cd-sem", "MONITOR/CD_TOP_01", "M14A", "CG6300_01"
        )
        assert [(img["p_no"], img["optic"], img["name"]) for img in payload["images"]] == [
            (1, "OM", "IMAP0001.jpeg"),
            (2, "SEM", "IMAP0002.jpeg"),
        ]

    def test_home_produces_all_three_shapes_the_screen_has(self, home_payloads):
        # The value-domain guard, and the one this feature actually needed.
        # A mock that gave every recipe both points made the office's OM-only
        # recipes unreachable at home -- so the 404 they produce could not be
        # seen, written a test for, or fixed, until production reported it.
        # The empty case earns its place the same way: the modal renders a
        # branch for it, and a branch home cannot reach is a branch nobody
        # develops.
        assert {len(p["images"]) for p in home_payloads} == {0, 1, 2}

    def test_every_published_name_is_fetchable(self, home_payloads):
        # The round trip the screen makes. Home used to pass this for free --
        # fetch_recipe_image served any name it was handed -- which is exactly
        # why it proved nothing.
        for payload in home_payloads:
            for name in _names(payload):
                data, content_type = mock.fetch_recipe_image(payload["locator"], name)
                assert data and content_type

    def test_an_align_file_the_folder_lacks_is_refused(self, home_payloads):
        # The office property home was missing. Without it nothing at home can
        # go red on the 404 the route documents.
        om_only = next(p for p in home_payloads if len(p["images"]) == 1)
        assert _names(om_only) == ["IMAP0001.jpeg"]
        with pytest.raises(LookupError):
            mock.fetch_recipe_image(om_only["locator"], "IMAP0002.jpeg")

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


def _listing(monkeypatch, entries):
    """Stand in for the one NLST round trip get_align_images now makes."""
    monkeypatch.setattr(oe, "_list_raw_dirs", lambda keys: dict.fromkeys(keys, entries))


class TestOfficeAlignImages:
    def test_only_the_points_the_folder_holds_are_published(self, wired, monkeypatch):
        # The production bug. This recipe aligns on the OM alone, and the
        # computed IMAP0002.jpeg was a 404 every time the screen opened.
        _listing(monkeypatch, ["IMAP0001.jpeg", "ENAP0001", "IMMS0001.jpeg"])
        payload = oe.get_align_images("cd-sem", RECIPE, "R3", "CG6300_01")
        assert _names(payload) == ["IMAP0001.jpeg"]

    def test_an_unlistable_tool_is_reported_as_unavailable_not_as_empty(
        self, wired, monkeypatch
    ):
        # A tool that cannot be listed is DOWN, not a recipe without align
        # images. Returning [] would send the engineer looking for a recipe
        # defect; returning the derived pair -- which this did until
        # 2026-08-22 -- queues two <img> requests that cannot succeed. 503 is
        # what this surface already answers for a connect/login/listing
        # failure (docs/datatables/hitachi/recipe_idp.txt).
        _listing(monkeypatch, None)
        with pytest.raises(SourceUnavailable):
            oe.get_align_images("cd-sem", RECIPE, "R3", "CG6300_01")

    def test_a_split_align_image_is_found_rather_than_missed(
        self, wired, monkeypatch
    ):
        # Whether any tool family splits ALIGN images the way HV-SEM splits its
        # measurement slots is OFFICE-VERIFY. Discovery answers it either way.
        # Driven through cd-sem because the family is not what decides this --
        # the folder is -- and the fixture registry only holds the CD keys.
        _listing(monkeypatch, ["IMAP0001-U.jpeg", "IMAP0001-L.jpeg"])
        payload = oe.get_align_images("cd-sem", RECIPE, "R3", "CG6300_01")
        assert _names(payload) == ["IMAP0001-U.jpeg", "IMAP0001-L.jpeg"]

    def test_the_listing_is_taken_from_the_tool_that_answered(
        self, wired, monkeypatch
    ):
        # A substitution changes which folder holds the answer. Listing the
        # requested tool's path on the substitute's host would describe a
        # folder nobody is going to fetch from.
        seen: list[set] = []

        def spy(keys):
            seen.append(set(keys))
            return dict.fromkeys(keys, ["IMAP0001.jpeg"])

        monkeypatch.setattr(oe, "_list_raw_dirs", spy)
        payload = oe.get_align_images("cd-sem", RECIPE, "R3", "GONE_99")
        assert payload["from_requested_tool"] is False
        assert seen == [{(payload["locator"]["eqp_ip"], "ADI", "ADI_CD_BIAS_001",
                          "ADI_CD_BIAS_001")}]

    def test_the_locator_points_at_the_requested_tool_even_when_offline(self, wired, monkeypatch):
        _listing(monkeypatch, ["IMAP0001.jpeg", "IMAP0002.jpeg"])
        # The bug this whole seam exists to prevent. CG6380_02 is available=Off
        # and sorts LAST in the ordinary candidate walk, so without a
        # preference the answer would be CG6300_01's copy of the recipe --
        # silently, and about a different file than the one that failed.
        payload = oe.get_align_images("cd-sem", RECIPE, "R3", "CG6380_02")
        assert payload["locator"]["eqp_ip"] == "10.1.2.2"
        assert payload["eqp_id"] == "CG6380_02"
        assert payload["from_requested_tool"] is True

    def test_an_unroutable_request_is_reported_not_hidden(self, wired, monkeypatch):
        _listing(monkeypatch, ["IMAP0001.jpeg", "IMAP0002.jpeg"])
        # GONE_99 is not in the roster, so there is no IP to dial and the
        # answer necessarily comes from a sibling. Saying so is the point:
        # a silent substitution reads as "this recipe's align target looks
        # fine" when the file examined was never the failing tool's.
        payload = oe.get_align_images("cd-sem", RECIPE, "R3", "GONE_99")
        assert payload["eqp_id"] == "CG6300_01"
        assert payload["requested_eqp_id"] == "GONE_99"
        assert payload["from_requested_tool"] is False

    def test_opening_a_recipe_without_a_tool_is_not_a_substitution(self, wired, monkeypatch):
        _listing(monkeypatch, ["IMAP0001.jpeg", "IMAP0002.jpeg"])
        payload = oe.get_align_images("cd-sem", RECIPE, "R3", None)
        assert payload["from_requested_tool"] is True

    def test_both_providers_answer_the_same_contract(self, wired, monkeypatch):
        # Both sides are pinned to the SAME folder here. Comparing them while
        # each invented its own align set is what let the two agree on a name
        # neither had checked -- parity by construction, about nothing.
        _listing(monkeypatch, ["IMAP0001.jpeg", "IMAP0002.jpeg"])
        monkeypatch.setattr(
            mock, "_mock_raw_listing", lambda locator: ["IMAP0001.jpeg", "IMAP0002.jpeg"]
        )
        office = oe.get_align_images("cd-sem", RECIPE, "R3", "CG6300_01")
        home = mock.get_align_images("cd-sem", RECIPE, "R3", "CG6300_01")
        assert office.keys() == home.keys()
        assert office["images"] == home["images"]
        assert office["locator"].keys() == home["locator"].keys()
