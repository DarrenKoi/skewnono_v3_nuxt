# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office adapter for pm_planning — NOT CONNECTED YET.

Implement get_pm_planning_fleet in pm_planning/MIGRATION.md against the
office data source. Normalize results to pm_planning/contracts.py shapes.
"""


def _not_connected():
    raise NotImplementedError(
        "The pm_planning office adapter has not been connected yet. "
        "Set SKEWNONO_PM_PLANNING_PROVIDER=mock until it is ready."
    )


def get_pm_planning_fleet(*args, **kwargs):
    return _not_connected()