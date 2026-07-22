# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office FDC adapter — NOT CONNECTED YET.

Source: OpenSearch ``network_fdc_cdsem`` (raw doc layout in
``docs/datatables/network_fdc_cdsem.txt``). Return raw docs ascending by
timestamp scoped to ``[start, end]``; the top-level ``providers/office.py``
dispatcher wraps them with ``normalizers.docs_payload``. Match
``fdc/mock.py``: one doc per (eqp_id, timestamp, values) where ``values[0]``
is the ``fdc_key`` (TemperatureEchuck / SPMVoltages / LaserPower /
ContactpinConductionInfo) and the rest follows that key's own layout.
"""

from datetime import datetime


def build_fdc_docs(
    eqp_id: str,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> list[dict]:
    raise NotImplementedError(
        "hardware/fdc office adapter not connected yet — implement "
        "build_fdc_docs against network_fdc_cdsem (see hardware/MIGRATION.md)."
    )
