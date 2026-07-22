# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office Reso Center adapter — NOT CONNECTED YET.

Source: OpenSearch ``reso_center_log`` (CD-SEM only). Return raw docs
ascending by timestamp scoped to ``[start, end]``; the top-level
``providers/office.py`` dispatcher wraps them with
``normalizers.docs_payload``. Match ``reso_center/mock.py``'s doc shape
(sweep curves + best-focus scalars).
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
        "build_reso_center_docs against reso_center_log "
        "(see hardware/MIGRATION.md)."
    )
