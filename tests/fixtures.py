"""Temporary, fictional student data; no real faces or identifiers."""

import csv
import os
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from backend.services.recognition import load_saved_training_data


class GalleryTestCase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name).resolve()
        self.model_path = self.folder / "model.pkl"
        self.roster_path = self.folder / "students.csv"
        self.data_dir = self.folder / "data"
        photos = self.data_dir / "students"
        photos.mkdir(parents=True)
        self.names = [f"Student {i:02d}" for i in range(1, 14)]
        encodings = np.random.default_rng(447).normal(size=(len(self.names), 128))
        with self.model_path.open("wb") as stream:
            pickle.dump((self.names, encodings), stream)
        with self.roster_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, delimiter=";")
            writer.writerow(["ID", "Name"])
            writer.writerows((f"DEMO-{i:03d}", name) for i, name in enumerate(self.names, 1))
        # A blank image exercises sample serving without publishing a face.
        Image.new("RGB", (100, 100), "white").save(photos / f"{self.names[0]}.png")
        environment = patch.dict(
            os.environ,
            {
                "MODEL_PATH": str(self.model_path),
                "ROSTER_PATH": str(self.roster_path),
                "DATA_DIR": str(self.data_dir),
                "FACE_MATCH_THRESHOLD": "0.45",
                "FACE_MATCH_MARGIN": "0.05",
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.addCleanup(load_saved_training_data.cache_clear)
