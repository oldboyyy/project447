"""Exercise matching, HTTP handling and CSV export with synthetic student data."""

import csv
import io
import json
import os
import shutil
import subprocess
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from backend.app import create_app
from backend.config import ROOT, settings
from backend.services.recognition import load_saved_training_data, match_face
from tests.fixtures import GalleryTestCase


class AttendanceTest(GalleryTestCase):
    def setUp(self):
        super().setUp()
        self.client = create_app({"TESTING": True, "ENABLE_SAMPLES": True}).test_client()

    def test_interface_and_model(self):
        for path in (
            "/",
            "/attendance",
            "/index.php",
            "/healthz",
            "/static/sdu/all.css",
            "/static/sdu/sdu_logo.png",
            "/static/app.js",
            "/static/styles.css",
            "/api/status",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()
        self.assertEqual(self.client.get("/api/status").json["students"], 13)

    def test_home_to_attendance_flow(self):
        home = self.client.get("/").get_data(as_text=True)
        self.assertIn("Student Information System", home)
        self.assertIn('href="/attendance" id="take-attendance"', home)
        self.assertNotIn('data-page="dashboard"', home)
        self.assertEqual(home, self.client.get("/index.php").get_data(as_text=True))
        portal = self.client.get("/attendance").get_data(as_text=True)
        self.assertIn('data-page="dashboard"', portal)
        self.assertIn("SDU Home page", portal)

    def test_bad_upload(self):
        self.assertEqual(self.client.post("/upload").status_code, 400)
        response = self.client.post(
            "/upload", data={"photo": (io.BytesIO(b"not an image"), "photo.jpg")}
        )
        self.assertEqual(response.status_code, 400)

    def test_size_limit(self):
        response = self.client.post(
            "/upload", data=b"x" * (12 * 1024 * 1024 + 1), content_type="application/octet-stream"
        )
        response.request.close()
        self.assertEqual(response.status_code, 413)

    def test_blank_image(self):
        data = io.BytesIO()
        Image.new("RGB", (200, 200), "white").save(data, format="PNG")
        data.seek(0)
        response = self.client.post("/upload", data={"photo": (data, "blank.png")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["detected"], 0)
        self.assertFalse(any(row["present"] for row in response.json["attendance"]))

    def test_unknown_sample(self):
        self.assertEqual(self.client.get("/api/samples/99999").status_code, 404)

    def mocked_frame(self, distances, config=None):
        """Exercise real matching, HTTP serialization and roster IDs with controlled scores."""
        client = create_app({"TESTING": True, **(config or {})}).test_client()
        data = io.BytesIO()
        Image.new("RGB", (120, 60), "white").save(data, format="PNG")
        data.seek(0)
        locations = [(20, 20 + i * 30, 40, i * 30) for i in range(len(distances))]
        with (
            patch(
                "backend.services.recognition.face_recognition.face_locations",
                return_value=locations,
            ),
            patch(
                "backend.services.recognition.face_recognition.face_encodings",
                return_value=[np.zeros(128)] * len(distances),
            ),
            patch(
                "backend.services.recognition.face_recognition.face_distance", side_effect=distances
            ),
        ):
            response = client.post("/upload", data={"photo": (data, "frame.png")})
        self.assertEqual(response.status_code, 200)
        result = response.json
        response.request.close()
        response.close()
        return result

    def test_status_and_recognition_share_configuration(self):
        config = {"FACE_MATCH_THRESHOLD": 0.4, "FACE_MATCH_MARGIN": 0.1}
        status = create_app({"TESTING": True, **config}).test_client().get("/api/status").json
        self.assertEqual(status["tolerance"], 0.4)
        self.assertEqual(status["margin"], 0.1)
        names, _ = load_saved_training_data(self.model_path)
        scores = np.full(len(names), 0.9)
        scores[0] = 0.44
        result = self.mocked_frame([scores], config)
        self.assertEqual(result["faces"][0]["reason"], "distance")
        scores[:2] = [0.3, 0.38]
        result = self.mocked_frame([scores], config)
        self.assertEqual(result["faces"][0]["reason"], "ambiguous")

    def test_mixed_frame_and_unknown_only(self):
        names, _ = load_saved_training_data(self.model_path)
        accepted = np.full(len(names), 0.9)
        accepted[0] = 0.44
        distant = np.full(len(names), 0.9)
        distant[1] = 0.46
        ambiguous = np.full(len(names), 0.9)
        ambiguous[1:3] = [0.4, 0.43]
        for scores, present_names in (
            ([accepted, distant, ambiguous], [names[0]]),
            ([distant, ambiguous], []),
        ):
            with self.subTest(present=present_names):
                result = self.mocked_frame(scores)
                self.assertEqual(result["detected"], len(scores))
                self.assertEqual(result["unknown"], 2)
                self.assertEqual(
                    [r["name"] for r in result["attendance"] if r["present"]], present_names
                )
                self.assertEqual({r["name"] for r in result["attendance"]}, set(names))
                self.assertTrue(all(r["id"] for r in result["attendance"]))
                rejected = [f for f in result["faces"] if f["status"] == "unknown"]
                self.assertEqual([f["reason"] for f in rejected], ["distance", "ambiguous"])
                self.assertTrue(all(f["name"] is None for f in rejected))
                self.assertEqual([f["distance"] for f in rejected], [0.46, 0.4])
                recognized = [f for f in result["faces"] if f["status"] == "recognized"]
                self.assertEqual([f["name"] for f in recognized], present_names)
                self.assertTrue(all(f["reason"] is None for f in recognized))

    @unittest.skipUnless(
        shutil.which("node"), "Node.js is required to execute the real CSV exporter"
    )
    def test_unknown_excluded_from_frontend_csv(self):
        names, _ = load_saved_training_data(self.model_path)
        accepted = np.full(len(names), 0.9)
        accepted[0] = 0.44
        distant = np.full(len(names), 0.9)
        distant[1] = 0.46
        ambiguous = np.full(len(names), 0.9)
        ambiguous[1:3] = [0.4, 0.43]
        # Run the production script and export click handler with a minimal DOM.
        script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const elements = new Map();
const created = [];
let exported;
function element() {
    const node = {
        textContent: '', style: {}, listeners: {}, classList: {add() {}, toggle() {}},
        setAttribute() {}, removeAttribute() {}, replaceChildren() {}, append() {},
        addEventListener(name, fn) {this.listeners[name] = fn;},
        insertRow() {return element();}, insertCell() {return element();}, click() {}
    };
    created.push(node);
    return node;
}
function get(id) {
    if (!elements.has(id)) elements.set(id, element());
    return elements.get(id);
}
const context = vm.createContext({
    payload, Intl, Date, Blob, location: {hash: ''},
    document: {getElementById: get, querySelector: get, querySelectorAll: () => [], createElement: element},
    window: {addEventListener() {}}, fetch: () => new Promise(() => {}),
    URL: {createObjectURL(blob) {exported = blob; return 'blob:test';}, revokeObjectURL() {}},
    setTimeout: fn => fn()
});
vm.runInContext(fs.readFileSync('frontend/static/app.js', 'utf8'), context);
vm.runInContext('showResults(payload)', context);
get('export-csv').listeners.click();
exported.text().then(csv => process.stdout.write(JSON.stringify({
    csv, labels: created.map(node => node.textContent)
})));
"""
        for scores, present_names in (
            ([accepted, distant, ambiguous], [names[0]]),
            ([distant, ambiguous], []),
        ):
            with self.subTest(present=present_names):
                result = self.mocked_frame(scores)
                process = subprocess.run(
                    [shutil.which("node"), "-e", script],
                    input=json.dumps(result),
                    text=True,
                    capture_output=True,
                    cwd=ROOT,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                exported = json.loads(process.stdout)
                rows = list(csv.DictReader(io.StringIO(exported["csv"].lstrip("\ufeff"))))
                self.assertEqual(len(rows), len(names))
                self.assertEqual({r["Name"] for r in rows}, set(names))
                self.assertEqual(
                    [r["Name"] for r in rows if r["Status"] == "Present"], present_names
                )
                self.assertTrue(all(r["ID"] for r in rows))
                self.assertNotIn("Unknown", exported["csv"])
                self.assertNotIn("личность не подтверждена", exported["csv"])
                self.assertIn("личность не подтверждена", exported["labels"])


class MatchFaceTest(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ, {"FACE_MATCH_THRESHOLD": "0.45", "FACE_MATCH_MARGIN": "0.05"}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_default_and_environment_settings(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(settings()["FACE_MATCH_THRESHOLD"], 0.45)
            self.assertEqual(settings()["FACE_MATCH_MARGIN"], 0.05)
        with patch.dict(os.environ, {"FACE_MATCH_THRESHOLD": "0.4", "FACE_MATCH_MARGIN": "0.1"}):
            self.assertEqual(settings()["FACE_MATCH_THRESHOLD"], 0.4)
            self.assertEqual(settings()["FACE_MATCH_MARGIN"], 0.1)
            self.assertEqual(match_face([0.44, 0.9], ["Alice", "Bob"])[:2], (None, "distance"))

    def test_threshold_boundaries(self):
        for distance, expected in (
            (0.44, ("Alice", None)),
            (0.45, ("Alice", None)),
            (0.46, (None, "distance")),
        ):
            with self.subTest(distance=distance):
                self.assertEqual(
                    match_face([0.9, distance], ["Bob", "Alice"]), (*expected, distance, 0.9)
                )

    def test_ambiguity_and_margin_boundary(self):
        for second, expected in (
            (0.49, (None, "ambiguous")),
            (0.5, ("Alice", None)),
            (0.51, ("Alice", None)),
            (0.45, (None, "ambiguous")),
        ):
            with self.subTest(second=second):
                self.assertEqual(match_face([0.45, second], ["Alice", "Bob"])[:2], expected)

    def test_margin_compares_distinct_students(self):
        self.assertEqual(
            match_face([0.44, 0.45, 0.7], ["Alice", "Alice", "Bob"]), ("Alice", None, 0.44, 0.7)
        )
        self.assertEqual(
            match_face([0.7, 0.44, 0.46], ["Alice", "Alice", "Bob"]),
            (None, "ambiguous", 0.44, 0.46),
        )

    def test_single_student_and_empty_gallery(self):
        self.assertEqual(
            match_face([0.44, 0.45], ["Alice", "Alice"]), ("Alice", None, 0.44, float("inf"))
        )
        self.assertEqual(match_face([], [])[:2], (None, "distance"))

    def test_distance_rejection_takes_precedence(self):
        self.assertEqual(match_face([0.46, 0.47], ["Alice", "Bob"])[:2], (None, "distance"))


if __name__ == "__main__":
    unittest.main()
