# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office sharpness adapter — NOT CONNECTED YET.

Source: OpenSearch ``network_sharpness_cdsem``. Return raw docs ascending by
timestamp scoped to ``[start, end]``; the top-level ``providers/office.py``
dispatcher wraps them with ``normalizers.docs_payload``. Match
``sharpness/mock.py``'s doc shape (chamber-stub sharpness profiles plus
``summ_beam`` / beam-condition blocks).
"""

from datetime import datetime


def build_network_sharpness_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    raise NotImplementedError(
        "hardware/sharpness office adapter not connected yet — implement "
        "build_network_sharpness_docs against network_sharpness_cdsem "
        "(see hardware/MIGRATION.md)."
    )
