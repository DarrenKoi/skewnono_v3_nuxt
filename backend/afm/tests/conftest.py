import pytest


@pytest.fixture
def mock_provider(monkeypatch):
    """Pin `data.py` to the mock for tests that assert the mock's own facts.

    `python -m pytest backend/afm` is also run at the office, where the
    dispatcher resolves to the office adapter: a test that goes through
    `data` or the routes and expects a placeholder SVG, a capture image on
    every row or a mock file name then fails for no fault of the code. The
    office adapter has its own suites (test_contract, test_office_template).
    """
    monkeypatch.setenv("SKEWNONO_AFM_PROVIDER", "mock")
