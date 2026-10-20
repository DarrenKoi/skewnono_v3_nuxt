import pytest


@pytest.fixture(autouse=True)
def roomy_permits(monkeypatch):
    """Fresh, roomy permits per test. The test client never closes a response
    it was not asked to buffer, so a real cap of 1 would stay taken after the
    first download; the permit tests install their own small ones."""
    from backend.ebeam.tool_files import routes

    monkeypatch.setattr(routes, "_FTP_SESSIONS", routes._Permits(1000, "ftp_busy", ""))
    monkeypatch.setattr(routes, "_TRANSFERS", routes._Permits(1000, "transfers_busy", ""))
