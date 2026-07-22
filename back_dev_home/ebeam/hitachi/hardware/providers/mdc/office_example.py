# TEMPLATE — copy to office.py at the office, then implement the function bodies.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office MDC adapter — NOT CONNECTED YET.

Source: MDC settings/calibration collection. Two builders, matching
``mdc/mock.py``:

- ``build_mdc_settings`` — as-of snapshot for the selected tool AND its
  in-fab siblings (keyed by eqp_id), used for the 비교 sub-tab.
- ``build_mdc_history`` — timestamped recalibration history for the selected
  tool only across ``[start, end]``, ascending, long format (one record per
  beam_condition), used for the 시계열 sub-tab.

The top-level ``providers/office.py`` dispatcher combines both via
``normalizers.settings_payload`` (settings + docs).
"""

from datetime import datetime


def build_mdc_settings(
    eqp_id: str,
    fab_name: str | None,
    as_of: datetime,
) -> dict[str, dict[str, str]]:
    raise NotImplementedError(
        "hardware/mdc office adapter not connected yet — implement "
        "build_mdc_settings (see hardware/MIGRATION.md)."
    )


def build_mdc_history(
    eqp_id: str,
    start: datetime,
    end: datetime,
) -> list[dict[str, str | float]]:
    raise NotImplementedError(
        "hardware/mdc office adapter not connected yet — implement "
        "build_mdc_history (see hardware/MIGRATION.md)."
    )
