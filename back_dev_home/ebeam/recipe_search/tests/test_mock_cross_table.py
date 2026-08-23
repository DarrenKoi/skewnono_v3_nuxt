"""The two cross-table invariants the office confirmed on 2026-07-28.

``docs/datatables/hitachi/recipe_idp.txt`` and ``MIGRATION.md`` both record them:

    Region == wafer_mp_info.P_No
    D_No == -1  ⟺  dnumber_removed == True

They were written down and then not acted on, so the mock kept drawing
``Parameter`` and ``P_No`` from independent draws and ``D_No`` from
``randint(1, 100)`` — meaning ``D_No == -1`` never occurred at home at all.
Anything that renders or branches on the suppressed-data case therefore ran
against data that contradicted the office on every single row.

These tests pin the relations rather than the values: the mock is still free to
fabricate whatever numbers it likes, as long as the two tables agree the way the
office says they do.
"""

import random

from back_dev_home.ebeam.recipe_search.providers import mock


def _tables(seed: int = 11):
    rng = random.Random(seed)
    idp_rows = mock.generate_idp_image_info(rng=rng)
    mp_rows = mock.generate_wafer_mp_info(rng=rng, idp_rows=idp_rows)
    return mp_rows, idp_rows


def test_region_equals_p_no_for_the_parameter_the_point_measures():
    """The documented integer join key must agree with the Parameter join.

    A developer following the doc joins on Region; at home that returned rows
    belonging to a different parameter, which reads as "the doc is wrong".
    """
    mp_rows, idp_rows = _tables()
    region_of = {row["Parameter"]: row["Region"] for row in idp_rows}
    assert mp_rows, "the mock must emit measurement points"
    for row in mp_rows:
        assert row["Parameter"] in region_of, f"unjoinable Parameter {row['Parameter']!r}"
        assert region_of[row["Parameter"]] == row["P_No"], (
            f"Region {region_of[row['Parameter']]} != P_No {row['P_No']} "
            f"for {row['Parameter']!r}"
        )


def test_d_no_minus_one_iff_the_parameter_is_dnumber_removed():
    mp_rows, idp_rows = _tables()
    removed = {row["Parameter"]: row["dnumber_removed"] for row in idp_rows}
    for row in mp_rows:
        assert (row["D_No"] == -1) is removed[row["Parameter"]], (
            f"D_No {row['D_No']} contradicts dnumber_removed "
            f"{removed[row['Parameter']]} for {row['Parameter']!r}"
        )


def test_the_suppressed_case_actually_occurs_at_home():
    """Guards the reason this matters: -1 must be reachable without the office.

    An invariant the mock satisfies vacuously (because no parameter is ever
    suppressed) leaves the branch as untested as it was before.
    """
    seen = {row["D_No"] == -1 for _ in range(5) for row in _tables(_)[0]}
    assert seen == {True, False}, "both the suppressed and normal paths must occur"


def test_dnumber_removed_is_a_property_of_the_parameter_not_the_row():
    """Rows repeat a Parameter (Para_13 at SEQ 4 and 6) — they must agree.

    The doc records dnumber_removed as parameter-level. A per-row coin flip made
    the same parameter both suppressed and not, which makes the ⟺ above
    ill-defined and would make any per-parameter UI grouping flicker.
    """
    _, idp_rows = _tables()
    by_parameter: dict[str, set[bool]] = {}
    for row in idp_rows:
        by_parameter.setdefault(row["Parameter"], set()).add(row["dnumber_removed"])
    repeated = {p: v for p, v in by_parameter.items() if len(v) > 1}
    assert not repeated, f"parameters disagree with themselves: {repeated}"


def test_region_is_also_a_property_of_the_parameter():
    _, idp_rows = _tables()
    by_parameter: dict[str, set[int]] = {}
    for row in idp_rows:
        by_parameter.setdefault(row["Parameter"], set()).add(row["Region"])
    repeated = {p: v for p, v in by_parameter.items() if len(v) > 1}
    assert not repeated, f"parameters carry more than one Region: {repeated}"


def test_img_meas2_still_copies_p_no():
    """Unchanged by the above, and easy to break while rewiring P_No."""
    mp_rows, _ = _tables()
    for row in mp_rows:
        assert row["img_meas2"] == row["P_No"]


def test_slots_stay_row_level_so_a_repeated_parameter_names_different_files():
    """The deliberate trap from docs/datatables/hitachi/recipe_idp.txt must survive.

    Making Region and dnumber_removed parameter-level must NOT drag the img_*
    slots along: those belong to the row, and the param-detail cache bug of
    2026-07-30 is only reproducible at home while they differ.
    """
    _, idp_rows = _tables()
    by_parameter: dict[str, set[str]] = {}
    for row in idp_rows:
        by_parameter.setdefault(row["Parameter"], set()).add(row["img_add1"])
    assert any(len(v) > 1 for v in by_parameter.values()), (
        "no parameter appears on two rows with different slots — the trap is gone"
    )
