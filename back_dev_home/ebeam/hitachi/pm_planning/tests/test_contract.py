"""Contract gate for pm_planning. Runs against the ACTIVE provider via data.py.

Home:   .venv/bin/pytest back_dev_home/ebeam/hitachi/pm_planning
Office: SKEWNONO_PM_PLANNING_PROVIDER=office .venv/bin/pytest back_dev_home/ebeam/hitachi/pm_planning
"""

from back_dev_home._core.contract_check import assert_matches
from back_dev_home.ebeam.hitachi.pm_planning import data
from back_dev_home.ebeam.hitachi.pm_planning.contracts import FleetPayload


def test_get_pm_planning_fleet_matches_contract():
    # fab_id copied from routes.py's own call shape (a plain query-string
    # fab_id, upper/lower-cased by the mock — see pm_planning_fleet() in
    # routes.py, which just forwards request.args["fab_id"] unchanged).
    fleet = data.get_pm_planning_fleet("M14")
    assert fleet
    assert_matches(fleet, FleetPayload)
