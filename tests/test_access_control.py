"""Access-control policy tests (X-prefixed member ids + admin exception list).

Run: .venv/bin/python -m unittest discover tests
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

# Point the exception store at a throwaway file BEFORE the app modules load.
_TMP_DIR = tempfile.mkdtemp(prefix="skn-access-test-")
_STORE = Path(_TMP_DIR) / "access_exceptions.json"
os.environ["SKEWNONO_ACCESS_EXCEPTIONS_FILE"] = str(_STORE)

from back_dev_home import create_app  # noqa: E402
from back_dev_home.access_control import data as ac_data  # noqa: E402
from back_dev_home.access_control.providers import mock as ac_mock  # noqa: E402

ADMIN = "local-dev"  # home-phase default admin
NORMAL = "1234567"
BLOCKED = "X999888"


def _client():
    app = create_app()
    app.config["TESTING"] = True
    # The shared limiter state persists across create_app() calls within one
    # process; disable it so assertion-heavy tests don't trip 429s.
    # (flask-limiter keeps a set of Limiter instances in app.extensions.)
    for limiter in app.extensions["limiter"]:
        limiter.enabled = False
    return app.test_client()


class AccessControlBase(unittest.TestCase):
    def setUp(self):
        ac_mock.reset_for_tests()
        if _STORE.exists():
            _STORE.unlink()
        self.client = _client()

    def _get(self, path: str, user: str | None):
        if user is not None:
            self.client.set_cookie("LASTUSER", user)
        else:
            self.client.delete_cookie("LASTUSER")
        return self.client.get(path)


class TestStorePath(unittest.TestCase):
    def test_default_store_is_scoped_to_access_control(self):
        override = os.environ.pop("SKEWNONO_ACCESS_EXCEPTIONS_FILE", None)
        try:
            expected = (
                Path(ac_data.__file__).resolve().parent
                / "state"
                / "access_exceptions.json"
            )
            self.assertEqual(ac_mock._store_path(), expected)
        finally:
            if override is not None:
                os.environ["SKEWNONO_ACCESS_EXCEPTIONS_FILE"] = override


class TestBlockingRule(AccessControlBase):
    def test_normal_user_passes(self):
        res = self._get("/api/activity/me", NORMAL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["user_id"], NORMAL)

    def test_x_user_blocked_on_api(self):
        res = self._get("/api/activity/me", BLOCKED)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"]["code"], "access_denied")

    def test_lowercase_x_also_blocked(self):
        res = self._get("/api/activity/me", "x999888")
        self.assertEqual(res.status_code, 403)

    def test_denied_attempt_recorded(self):
        self._get("/api/activity/me", BLOCKED)
        self._get("/api/activity/me", BLOCKED)
        denied = ac_data.list_denied()
        self.assertEqual(len(denied), 1)  # deduped
        self.assertEqual(denied[0]["user_id"], BLOCKED)

    def test_admin_is_never_blocked(self):
        # Force an X-prefixed admin via env override to prove the bypass.
        os.environ["SKEWNONO_ADMIN_USERS"] = "X-ADMIN"
        try:
            res = self._get("/api/activity/me", "X-ADMIN")
            self.assertEqual(res.status_code, 200)
        finally:
            del os.environ["SKEWNONO_ADMIN_USERS"]


class TestExceptionList(AccessControlBase):
    def _grant(self, user_id: str):
        self.client.set_cookie("LASTUSER", ADMIN)
        return self.client.post("/api/admin/access/exceptions", json={"user_id": user_id})

    def test_grant_unblocks_and_revoke_reblocks(self):
        self.assertEqual(self._get("/api/activity/me", BLOCKED).status_code, 403)

        self.assertEqual(self._grant(BLOCKED).status_code, 201)
        self.assertEqual(self._get("/api/activity/me", BLOCKED).status_code, 200)

        self.client.set_cookie("LASTUSER", ADMIN)
        res = self.client.delete(f"/api/admin/access/exceptions/{BLOCKED}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self._get("/api/activity/me", BLOCKED).status_code, 403)

    def test_grant_is_case_insensitive(self):
        self._grant("x999888")
        self.assertEqual(self._get("/api/activity/me", "X999888").status_code, 200)

    def test_grant_persists_to_disk(self):
        self._grant(BLOCKED)
        raw = json.loads(_STORE.read_text(encoding="utf-8"))
        self.assertEqual(raw["exceptions"][0]["user_id"], BLOCKED)

        # Fresh in-memory state (as after a server restart) must reload it.
        ac_mock.reset_for_tests()
        self.assertEqual(self._get("/api/activity/me", BLOCKED).status_code, 200)

    def test_non_x_id_rejected(self):
        res = self._grant(NORMAL)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.get_json()["error"]["code"], "invalid_member_id")

    def test_corrupt_store_fails_safe(self):
        _STORE.write_text("{not json", encoding="utf-8")
        ac_mock.reset_for_tests()
        self.assertEqual(ac_data.list_exceptions(), [])
        self.assertEqual(self._get("/api/activity/me", BLOCKED).status_code, 403)

    def test_corrupt_store_refuses_mutation(self):
        # A grant while the store is unreadable must fail loudly (503), not
        # report success and later clobber the real file with a partial view.
        self._grant(BLOCKED)
        _STORE.write_text("{not json", encoding="utf-8")
        ac_mock.reset_for_tests()
        res = self._grant("X777777")
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.get_json()["error"]["code"], "store_unavailable")
        self.assertIn("not json", _STORE.read_text(encoding="utf-8"))  # untouched

    def test_external_file_change_is_picked_up(self):
        # Another WSGI worker writing the file must be visible here without a
        # restart (mtime-based reload).
        self._grant(BLOCKED)
        raw = json.loads(_STORE.read_text(encoding="utf-8"))
        raw["exceptions"].append({"user_id": "X555555", "granted_at": "2026-07-14T00:00:00Z"})
        _STORE.write_text(json.dumps(raw), encoding="utf-8")
        os.utime(_STORE, (0, 0))  # force a distinct mtime
        self.assertEqual(self._get("/api/activity/me", "X555555").status_code, 200)

    def test_admin_check_is_case_insensitive(self):
        os.environ["SKEWNONO_ADMIN_USERS"] = "X-Admin"
        try:
            self.assertEqual(self._get("/api/activity/me", "x-admin").status_code, 200)
        finally:
            del os.environ["SKEWNONO_ADMIN_USERS"]


class TestAdminGating(AccessControlBase):
    def test_non_admin_cannot_read_access_config(self):
        self.client.set_cookie("LASTUSER", NORMAL)
        res = self.client.get("/api/admin/access")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.get_json()["error"]["code"], "forbidden")

    def test_non_admin_cannot_grant(self):
        self.client.set_cookie("LASTUSER", NORMAL)
        res = self.client.post("/api/admin/access/exceptions", json={"user_id": BLOCKED})
        self.assertEqual(res.status_code, 403)

    def test_non_admin_cannot_read_admin_logs(self):
        self.client.set_cookie("LASTUSER", NORMAL)
        res = self.client.get("/api/admin/logs")
        self.assertEqual(res.status_code, 403)

    def test_admin_reads_overview(self):
        self._get("/api/activity/me", BLOCKED)  # produce one denied attempt
        self.client.set_cookie("LASTUSER", ADMIN)
        res = self.client.get("/api/admin/access")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()
        self.assertEqual(body["rule"]["blocked_prefix"], "X")
        self.assertEqual(body["exceptions"], [])
        self.assertEqual(body["denied"][0]["user_id"], BLOCKED)


if __name__ == "__main__":
    unittest.main()
