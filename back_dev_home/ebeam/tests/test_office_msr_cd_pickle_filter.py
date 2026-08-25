"""A run is worth opening when it HAS A PICKLE, not when msr_check says "Yes".

`msr_check` is "Yes" on all 2,250,652 office documents (office 확인
2026-08-20), so the clause that used to express "skip runs whose MSR file
never landed" filtered nothing at all. The property it was always reaching for
is the one the next step actually needs: `minio_pkl`, the path this code then
opens.

Two call sites must agree — `recent_runs` (the payload) and tttm's
`get_tttm_recipes` (the picker that offers recipes for it). A picker scoped
more loosely than its payload offers recipes that come back empty, which is
why both go through the same shared clause rather than each spelling it out.
"""

from datetime import datetime

from back_dev_home.ebeam import _office_msr_cd
from back_dev_home.ebeam._office_msr_cd import has_pickle_clause


def _clauses_from(monkeypatch) -> list[dict]:
    captured = {}

    def fake_aggregate(_index, _aggs, query):
        captured["query"] = query
        return {}

    monkeypatch.setattr(_office_msr_cd, "aggregate", fake_aggregate)
    _office_msr_cd.recent_runs(
        tool_type="cd-sem",
        fab_name="R3",
        eqp_ids=["ECXDX001"],
        start=datetime(2026, 8, 1),
        end=datetime(2026, 8, 20),
    )
    return captured["query"]["bool"]["filter"]


def test_the_shared_clause_asks_for_the_pickle_path():
    assert has_pickle_clause() == {"exists": {"field": "minio_pkl"}}


def test_each_call_gets_its_own_dict_so_a_caller_cannot_mutate_the_shared_one():
    first = has_pickle_clause()
    first["exists"]["field"] = "tampered"
    assert has_pickle_clause() == {"exists": {"field": "minio_pkl"}}


def test_recent_runs_filters_on_the_pickle_and_no_longer_on_msr_check(monkeypatch):
    clauses = _clauses_from(monkeypatch)

    assert has_pickle_clause() in clauses
    assert "msr_check" not in str(clauses)


def test_the_recipe_picker_uses_the_same_clause_as_the_payload(monkeypatch):
    """Drift here is invisible: the picker still returns rows, they just
    resolve to empty payloads once selected."""
    office = __import__(
        "back_dev_home.ebeam.tttm.providers.office_example",
        fromlist=["get_tttm_recipes"],
    )
    captured = {}

    def fake_composite(_index, _field, _sub, query):
        captured["query"] = query
        return []

    monkeypatch.setattr(office, "composite_buckets", fake_composite)
    monkeypatch.setattr(office, "get_anchor_time", lambda: datetime(2026, 8, 20))
    office.get_tttm_recipes("cdsem", "R3", 2)

    clauses = captured["query"]["bool"]["filter"]
    assert has_pickle_clause() in clauses
    assert "msr_check" not in str(clauses)
    # And the same WINDOW as the payload: a picker counting over a wider span
    # offers recipes the check then finds nothing for.
    [window] = [clause["range"] for clause in clauses if "range" in clause]
    [(_field, bounds)] = window.items()
    assert bounds["gte"] == "2026-08-06T00:00:00"
    assert bounds["lte"] == "2026-08-20T00:00:00"
