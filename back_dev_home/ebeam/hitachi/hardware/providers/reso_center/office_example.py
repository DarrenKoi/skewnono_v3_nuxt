# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office Reso Center adapter — NOT CONNECTED YET.

Source: OpenSearch alias ``reso_center_cdsem`` (CD-SEM only). Return raw docs
ascending by ``timestamp`` scoped to ``[start, end]``; the top-level
``providers/office.py`` dispatcher wraps them with
``normalizers.docs_payload``.

NOTE ``reso_center_log`` is the value of each doc's ``category`` field, NOT
the index name — querying it as an index gets index_not_found at the office.
Source of truth: ``docs/datatables/hardware_reso_center_data.txt``.

Match ``reso_center/mock.py``'s flat doc shape — the 13 scalar/metadata
fields, no focus-sweep objects:

    category, CenterX, CenterY, BestReso, ResoIScenter, ResoDelta,
    beam_condition, timestamp, timestamp_date, eqp_ip, eqp_id, fac_id, fab_name

``ResoDelta`` is the stored difference ``ResoIScenter - BestReso`` (>= 0) —
pass it through as indexed; do not recompute. The wide ``Resolution_Range`` /
``Resolution_Range_Raw`` / ``Resolution_Range_Smooth`` objects and
``fdc_category`` are intentionally NOT returned (Focus Sweep was removed);
even though they still ride along in ``_source`` (mapped ``enabled: false``),
drop them from each doc so the office payload matches the mock.

Resolve ``eqp_id -> eqp_ip`` the same way the other hardware adapters do (the
index is keyed on ``eqp_ip``), and filter on ``fab_name`` when given. See
``hardware/MIGRATION.md`` and ``bsm/office_example.py`` for the query pattern.
"""

from datetime import datetime


def build_reso_center_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    raise NotImplementedError(
        "hardware/reso_center office adapter not connected yet — implement "
        "build_reso_center_docs against the reso_center_cdsem alias "
        "(see hardware/MIGRATION.md)."
    )
