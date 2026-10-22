"""Verify runtime isolation from working directory and optional sample data."""

import io
import os
import pickle
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from backend.app import create_app
from backend.config import ROOT
from backend.services.recognition import predict_children, prepare_image
from ml.train import train
from tests.fixtures import GalleryTestCase


class StructureTest(GalleryTestCase):
    def test_launch_from_other_directory(self):
        previous = Path.cwd()
        try:
            with tempfile.TemporaryDirectory() as directory:
                os.chdir(directory)
                with patch.dict(
                    os.environ,
                    {
                        "MODEL_PATH": os.path.relpath(self.model_path, ROOT),
                        "ROSTER_PATH": os.path.relpath(self.roster_path, ROOT),
                        "DATA_DIR": os.path.relpath(self.data_dir, ROOT),
                    },
                ):
                    app = create_app({"TESTING": True, "ENABLE_SAMPLES": True})
                self.assertEqual(app.config["MODEL_PATH"].resolve(), self.model_path)
                with app.test_client() as client:
                    self.assertEqual(client.get("/attendance").status_code, 200)
                    status = client.get("/api/status").json
                    self.assertTrue(status["samples"])
                    with client.get("/api/samples/0") as response:
                        self.assertEqual(response.status_code, 200)
                        self.assertTrue(response.mimetype.startswith("image/"))
        finally:
            os.chdir(previous)

    def test_server_without_demo_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            app = create_app(
                {"TESTING": True, "ENABLE_SAMPLES": False, "DATA_DIR": Path(directory)}
            )
            with app.test_client() as client:
                self.assertEqual(client.get("/api/status").json["samples"], [])
                self.assertEqual(client.get("/api/status").json["students"], 13)
                self.assertEqual(client.get("/api/samples/0").status_code, 404)
                self.assertEqual(client.get("/healthz").json, {"status": "ok"})
                for path in (
                    "/data/raw/students",
                    "/models/retrained.pkl",
                    "/data/metadata/students_dataset.csv",
                ):
                    self.assertEqual(client.get(path).status_code, 404)

    def test_invalid_model_fails_startup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.pkl"
            with self.assertRaises(FileNotFoundError):
                create_app({"MODEL_PATH": path})
            path.write_bytes(b"not a model")
            with self.assertRaises(pickle.UnpicklingError):
                create_app({"MODEL_PATH": path})

    def test_model_roster_mismatch_reports_both_sides(self):
        with (
            patch(
                "backend.app.load_saved_training_data", return_value=(["Alice"], np.zeros((1, 128)))
            ),
            patch("backend.app.load_roster", return_value={"Bob": "2"}),
        ):
            with self.assertRaisesRegex(
                ValueError, "missing from CSV: Alice; missing from model: Bob"
            ):
                create_app()

    def test_model_roster_mismatch_in_either_direction(self):
        for names, roster, error in (
            (["Alice", "Bob"], {"Alice": "1"}, "missing from CSV: Bob"),
            (["Alice"], {"Alice": "1", "Bob": "2"}, "missing from model: Bob"),
        ):
            with (
                self.subTest(error=error),
                patch(
                    "backend.app.load_saved_training_data",
                    return_value=(names, np.zeros((len(names), 128))),
                ),
                patch("backend.app.load_roster", return_value=roster),
            ):
                with self.assertRaisesRegex(ValueError, error):
                    create_app()

    def test_multiple_references_for_same_student_are_allowed(self):
        with (
            patch(
                "backend.app.load_saved_training_data",
                return_value=(["Alice", "Alice"], np.zeros((2, 128))),
            ),
            patch("backend.app.load_roster", return_value={"Alice": "1"}),
        ):
            self.assertEqual(create_app().config["STUDENT_ROSTER"], {"Alice": "1"})


class PrepareImageTest(unittest.TestCase):
    def test_orientation_rgb_and_resize(self):
        image = Image.new("L", (2000, 1000), 120)
        exif = Image.Exif()
        exif[274] = 6
        data = io.BytesIO()
        image.save(data, format="PNG", exif=exif)
        data.seek(0)
        prepared = prepare_image(data)
        self.assertEqual(prepared.mode, "RGB")
        self.assertEqual(prepared.size, (800, 1600))
        self.assertNotIn(274, prepared.getexif())
        self.assertEqual(prepared.getpixel((0, 0)), (120, 120, 120))

    def test_small_image_is_not_upscaled(self):
        data = io.BytesIO()
        Image.new("RGBA", (20, 10), (10, 20, 30, 255)).save(data, format="PNG")
        data.seek(0)
        prepared = prepare_image(data)
        self.assertEqual(prepared.mode, "RGB")
        self.assertEqual(prepared.size, (20, 10))

    def test_invalid_image(self):
        with self.assertRaisesRegex(ValueError, "Не удалось прочитать изображение"):
            prepare_image(io.BytesIO(b"not an image"))

    def test_training_and_inference_use_identical_pixels(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            photo = folder / "Alice.png"
            image = Image.new("L", (1800, 900), 100)
            exif = Image.Exif()
            exif[274] = 6
            image.save(photo, exif=exif)
            with (
                patch(
                    "ml.train.face_recognition.face_encodings", return_value=[np.zeros(128)]
                ) as encode,
                redirect_stdout(io.StringIO()),
            ):
                train(folder, folder / "model.pkl")
                training_pixels = encode.call_args.args[0]
            with (
                patch(
                    "backend.services.recognition.face_recognition.face_locations", return_value=[]
                ) as locate,
                patch(
                    "backend.services.recognition.face_recognition.face_encodings", return_value=[]
                ),
            ):
                predict_children(photo, folder / "model.pkl")
                inference_pixels = locate.call_args.args[0]
            np.testing.assert_array_equal(training_pixels, inference_pixels)
            self.assertEqual(training_pixels.dtype, np.uint8)
            self.assertEqual(training_pixels.shape, (1600, 800, 3))
