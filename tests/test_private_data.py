"""Optional local integration tests. Never upload their input data or logs."""

import os
import unittest

from backend.app import create_app
from backend.services.samples import sample_files


@unittest.skipUnless(
    os.environ.get("RUN_PRIVATE_DATA_TESTS") == "1",
    "Set RUN_PRIVATE_DATA_TESTS=1 with your private model, roster and photos",
)
class PrivateDataTest(unittest.TestCase):
    def setUp(self):
        app = create_app({"TESTING": True, "ENABLE_SAMPLES": True})
        self.client = app.test_client()
        self.samples = sample_files(app.config["DATA_DIR"], app.config["MODEL_PATH"])
        self.assertTrue(self.samples, "Private integration tests require student photos")

    def test_new_roster_and_training_photos(self):
        from backend.config import settings
        from backend.services.roster import load_roster

        roster = load_roster(settings()["ROSTER_PATH"])
        samples = self.samples
        self.assertGreater(len(roster), 0)
        self.assertEqual({name for name, _ in samples}, set(roster))
        for name, path in samples:
            with self.subTest(student=name), path.open("rb") as photo:
                response = self.client.post("/upload", data={"photo": (photo, path.name)})
                response.request.close()
                self.assertEqual(response.status_code, 200)
                rows = response.json["attendance"]
                self.assertEqual({row["name"]: row["id"] for row in rows}, roster)
                self.assertEqual([row["name"] for row in rows if row["present"]], [name])

    def test_real_recognition(self):
        name, path = self.samples[0]
        with path.open("rb") as photo:
            response = self.client.post("/upload", data={"photo": (photo, path.name)})
            response.request.close()
        self.assertEqual(response.status_code, 200)
        self.assertGreater(response.json["detected"], 0)
        self.assertIn(name, [row["name"] for row in response.json["attendance"] if row["present"]])
        self.assertTrue(response.json["image"].startswith("data:image/jpeg;base64,"))
