"""Rebuild the face encodings from a folder of Name Surname.jpg files."""

import argparse
import pickle
from pathlib import Path

import face_recognition
import numpy as np

from backend.config import DEFAULT_MODEL_PATH
from backend.services.recognition import prepare_image


def train(folder, output):
    names, encodings = [], []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        image = np.array(prepare_image(path), dtype=np.uint8)
        faces = face_recognition.face_encodings(image)
        if len(faces) != 1:
            print(f"Skipped {path.name}: expected one face, found {len(faces)}")
            continue
        names.append(path.stem.title())
        encodings.append(faces[0])
        print(f"Encoded {path.name}")
    if not encodings:
        raise ValueError("No usable faces found; existing model has not been changed.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    with temporary.open("wb") as stream:
        pickle.dump((names, encodings), stream)
    temporary.replace(output)
    print(f"Saved {len(names)} students to {output}. Restart the server to load this model.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_MODEL_PATH)
    args = parser.parse_args()
    train(args.folder, args.output)
