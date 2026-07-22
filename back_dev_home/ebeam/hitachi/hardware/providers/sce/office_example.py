# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office SCE adapter — NOT CONNECTED YET.

Source: SCE settings collection (CD-SEM only; used in 양산 M-fab). Return an
as-of snapshot for the selected tool AND its in-fab siblings keyed by eqp_id,
matching ``sce/mock.py``'s ``build_sce_settings`` (file info, SEM/image
conditions, SCE params, coefficient curves 0-359). The top-level
``providers/office.py`` dispatcher wraps it with
``normalizers.settings_payload`` (no ``docs`` for SCE).
"""

from datetime import datetime


def build_sce_settings(
    eqp_id: str,
    fab_name: str | None,
    as_of: datetime,
) -> dict[str, dict]:
    raise NotImplementedError(
        "hardware/sce office adapter not connected yet — implement "
        "build_sce_settings (see hardware/MIGRATION.md)."
    )
