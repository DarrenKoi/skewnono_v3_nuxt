"""The roster is the only thing that knows which fab an alarm belongs to.

Every case here uses M16, never R3 alone: R3 is the single value where fac_id
and fab_name coincide, so an R3-only test proves nothing about the mapping.
"""

from back_dev_home.ebeam.live_alarm import roster


def _row(eqp_id, fab_name, fac_id, model="CG6300"):
    return {
        "eqp_id": eqp_id,
        "fab_name": fab_name,
        "fac_id": fac_id,
        "eqp_model_cd": model,
    }


ROWS = [
    _row("MCD101", "M16A", "M16"),
    _row("MCD102", "M16B", "M16"),
    _row("MCD103", "R3", "R3"),
    _row("MCD104", "R4", "R3"),
    _row("TP0421", "M16A", "M16", model="TP3000"),
    _row("VS9001", "M16A", "M16", model="VERITYSEM_5"),  # AMAT: not our tool
]


def test_sibling_fabs_share_one_fac_id():
    index = roster.build_index(ROWS)
    assert index.fac_id_for("M16A", "cd-sem") == "M16"
    assert index.fac_id_for("M16B", "cd-sem") == "M16"
    # R3 and R4 are different fabs in ONE facility — this is the pairing that
    # makes the cache key coarse enough to matter.
    assert index.fac_id_for("R4", "cd-sem") == "R3"


def test_fab_name_is_normalized():
    assert roster.build_index(ROWS).fac_id_for(" m16a ", "cd-sem") == "M16"


def test_unknown_fab_has_no_fac_id():
    assert roster.build_index(ROWS).fac_id_for("ZZZ", "cd-sem") is None


def test_fac_id_is_per_tool_family():
    # M16B holds only a CD-SEM, so the hv-sem board there is not configured —
    # and the same call that says so is the one that yields the cache key, so
    # the two answers cannot disagree.
    index = roster.build_index(ROWS)
    assert index.fac_id_for("M16A", "hv-sem") == "M16"
    assert index.fac_id_for("M16B", "hv-sem") is None


def test_a_row_with_no_fac_id_does_not_make_the_fab_look_servable():
    # fac_id names the cache key. A fab that resolved without one would build
    # skewnono:live_alarm:None:events and call the office with fac_id=None.
    rows = [_row("MCD888", "M16D", "")]
    assert roster.build_index(rows).fac_id_for("M16D", "cd-sem") is None


def test_placement_carries_fab_and_tool_family():
    index = roster.build_index(ROWS)
    assert index.placement_of("MCD101") == ("M16A", "cd-sem")
    assert index.placement_of("TP0421") == ("M16A", "hv-sem")


def test_unrostered_equipment_has_no_placement():
    assert roster.build_index(ROWS).placement_of("MCD999") is None


def test_amat_tools_are_not_placed():
    # model_to_tool_type now classifies VERITYSEM_5 as "veritysem" instead of
    # returning None, but the roster is Hitachi-only (cd-sem/hv-sem) by
    # design, so build_index filters on SEM_TOOL_TYPES membership and AMAT
    # tools still get no placement. Placing them would put an AMAT alarm on
    # a Hitachi board.
    assert roster.build_index(ROWS).placement_of("VS9001") is None


def test_a_row_with_no_fab_is_not_placed():
    # sem_list's PendingToolRow documents fab_name as "" for a tool with no
    # fab assignment yet. Placing it under the empty-string fab would let it
    # match a request whose fab_name normalized to "".
    rows = [_row("MCD777", "", "M16")]
    assert roster.build_index(rows).placement_of("MCD777") is None


def test_eqp_ids_in_lists_only_that_fab_and_family():
    index = roster.build_index(ROWS)
    assert index.eqp_ids_in("M16A", "cd-sem") == ["MCD101"]
    assert index.eqp_ids_in("M16A", "hv-sem") == ["TP0421"]
    assert index.eqp_ids_in("ZZZ", "cd-sem") == []
