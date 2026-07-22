# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office BSM adapter — NOT CONNECTED YET.

Source: OpenSearch ``beam_shape`` docs with ``type: total`` (CD-SEM only).
Return raw docs ascending by timestamp scoped to ``[start, end]``; the
top-level ``providers/office.py`` dispatcher wraps them with
``normalizers.docs_payload``. Match ``bsm/mock.py``'s doc shape — the metric
list lives in ``hardware/metrics.py`` and the frontend picks filter/axis
fields from each doc, so keep field names identical.
"""

from datetime import datetime


def build_beam_shape_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    raise NotImplementedError(
        "hardware/bsm office adapter not connected yet — implement "
        "build_beam_shape_docs against beam_shape (type:total) "
        "(see hardware/MIGRATION.md)."
    )
