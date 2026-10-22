"""Paths are resolved relative to the project, never the current directory."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"
DEFAULT_MODEL_PATH = ROOT / "models/retrained.pkl"
DEFAULT_ROSTER_PATH = ROOT / "data/metadata/students_dataset.csv"
DEFAULT_DATA_DIR = ROOT / "data/raw"


def project_path(value):
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def settings():
    return {
        "DISPLAY_NAME": os.environ.get("DISPLAY_NAME", "Instructor"),
        "MODEL_PATH": project_path(os.environ.get("MODEL_PATH", str(DEFAULT_MODEL_PATH))),
        "ROSTER_PATH": project_path(os.environ.get("ROSTER_PATH", str(DEFAULT_ROSTER_PATH))),
        "DATA_DIR": project_path(os.environ.get("DATA_DIR", str(DEFAULT_DATA_DIR))),
        "MAX_CONTENT_LENGTH": 12 * 1024 * 1024,
        "ENABLE_SAMPLES": os.environ.get("ENABLE_SAMPLES", "1") == "1",
        "FACE_MATCH_THRESHOLD": float(os.environ.get("FACE_MATCH_THRESHOLD", "0.45")),
        "FACE_MATCH_MARGIN": float(os.environ.get("FACE_MATCH_MARGIN", "0.05")),
    }
