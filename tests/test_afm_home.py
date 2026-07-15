"""Home-safe AFM route and deterministic mock contract coverage."""

from __future__ import annotations

import unittest
import os
from urllib.parse import quote

from flask import Flask

from back_dev_home.afm.data import list_afm_files
from back_dev_home.afm.routes import bp


class TestAfmRoutes(unittest.TestCase):
    def setUp(self):
        self._provider = os.environ.pop("SKEWNONO_AFM_PROVIDER", None)
        app = Flask(__name__)
        app.register_blueprint(bp, url_prefix="/api")
        self.client = app.test_client()

    def tearDown(self):
        if self._provider is None:
            os.environ.pop("SKEWNONO_AFM_PROVIDER", None)
        else:
            os.environ["SKEWNONO_AFM_PROVIDER"] = self._provider

    def test_measurement_list_is_deterministic(self):
        first = list_afm_files("MAP608")
        second = list_afm_files("MAP608")

        self.assertEqual(first, second)
        self.assertGreater(len(first), 0)
        self.assertEqual(first[0]["tool_name"], "MAP608")

    def test_list_detail_profile_and_image_contracts(self):
        files_response = self.client.get("/api/afm/files?tool=MAP608")
        files_payload = files_response.get_json()
        row = files_payload["data"][0]
        filename = quote(row["filename"], safe="")
        point = quote(row["profile_dir_list"][0], safe="")

        detail = self.client.get(
            f"/api/afm/files/{filename}?tool=MAP608"
        )
        profile = self.client.get(
            f"/api/afm/files/{filename}/profile/{point}?tool=MAP608"
        )
        image = self.client.get(
            f"/api/afm/files/{filename}/image/{point}?tool=MAP608"
        )

        self.assertEqual(files_response.status_code, 200)
        self.assertEqual(files_payload["total"], len(files_payload["data"]))
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.get_json()["success"])
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.get_json()["count"], len(profile.get_json()["data"]))
        self.assertEqual(image.status_code, 200)
        self.assertTrue(image.get_json()["data"]["url"].startswith("/api/afm/files/"))

    def test_missing_measurement_keeps_the_404_shape(self):
        response = self.client.get("/api/afm/files/not-found?tool=MAP608")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "Measurement file not found")
        self.assertFalse(response.get_json()["success"])

    def test_office_provider_fails_explicitly_until_connected(self):
        os.environ["SKEWNONO_AFM_PROVIDER"] = "office"

        with self.assertRaisesRegex(NotImplementedError, "AFM office adapter"):
            list_afm_files("MAP608")


if __name__ == "__main__":
    unittest.main()
