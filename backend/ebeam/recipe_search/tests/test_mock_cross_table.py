"""The two cross-table invariants the office confirmed on 2026-07-28.

``docs/datatables/hitachi/recipe_idp.txt`` and ``MIGRATION.md`` both record them:

    Region == wafer_mp_info.P_No   (superseded 2026-10-22, see below)
    D_No == -1  ⟺  dnumber_removed == True

The first was a misreading: P_No is one measured block with one Parameter
name, and a Region groups several of them (user-confirmed 2026-10-22).

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

from backend.ebeam.recipe_search.providers import mock


def _tables(seed: int = 11):
    rng = random.Random(seed)
    idp_rows = mock.generate_idp_image_info(rng=rng)
    mp_rows = mock.generate_wafer_mp_info(rng=rng, idp_rows=idp_rows)
    return mp_rows, idp_rows


def test_p_no_names_the_block_the_point_measures():
    """P_No is what a formula's `$N` names, so it must lead to the right name.

    One P_No carries one Parameter (user-confirmed 2026-10-22); the mock takes
    the block's row position, so P_No N is row N's Parameter.
    """
    mp_rows, idp_rows = _tables()
    assert mp_rows, "the mock must emit measurement points"
    for row in mp_rows:
        assert idp_rows[row["P_No"] - 1]["Parameter"] == row["Parameter"], (
            f"P_No {row['P_No']} is {idp_rows[row['P_No'] - 1]['Parameter']!r}, "
            f"not {row['Parameter']!r}"
        )


def test_a_region_spans_several_p_nos():
    """The superseded `Region == P_No` collapsed a Region to one P_No."""
    mp_rows, idp_rows = _tables()
    p_nos_by_region: dict[int, set[int]] = {}
    for row in mp_rows:
        p_nos_by_region.setdefault(idp_rows[row["P_No"] - 1]["Region"], set()).add(row["P_No"])
    assert any(len(p_nos) > 1 for p_nos in p_nos_by_region.values())


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
