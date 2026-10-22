"""Portable version of the original dlib/face_recognition attendance pipeline."""

import io
import pickle
from functools import lru_cache

import face_recognition
import numpy as np
from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from backend.config import DEFAULT_MODEL_PATH, settings


class ModelUnpickler(pickle.Unpickler):
    """Accept only the numpy array types used by the supplied model."""

    def find_class(self, module, name):
        allowed = {
            ("numpy.core.multiarray", "_reconstruct"): np._core.multiarray._reconstruct,
            ("numpy._core.multiarray", "_reconstruct"): np._core.multiarray._reconstruct,
            ("numpy", "ndarray"): np.ndarray,
            ("numpy", "dtype"): np.dtype,
        }
        if (module, name) not in allowed:
            raise ValueError(f"Unsupported model type: {module}.{name}")
        return allowed[module, name]


@lru_cache(maxsize=1)
def load_saved_training_data(model_path=DEFAULT_MODEL_PATH):
    with model_path.open("rb") as stream:
        names, encodings = ModelUnpickler(stream).load()
    encodings = np.asarray(encodings, dtype=np.float64)
    if not names or encodings.shape != (len(names), 128) or not np.isfinite(encodings).all():
        raise ValueError("Invalid face model")
    return [str(name).title() for name in names], encodings


def match_face(distances, names, *, threshold=None, margin=None):
    """Return (name, rejection reason, d1, d2), ranking distinct students.

    A match has no rejection reason. With only one student, d2 is infinity.
    Optional overrides let callers use application settings without a Flask dependency.
    """
    config = settings()
    threshold = config["FACE_MATCH_THRESHOLD"] if threshold is None else threshold
    margin = config["FACE_MATCH_MARGIN"] if margin is None else margin
    candidates = {}
    for candidate, value in zip(names, distances):
        candidates[candidate] = min(candidates.get(candidate, float("inf")), float(value))
    ranked = sorted(candidates.items(), key=lambda item: item[1])
    if not ranked:
        return None, "distance", float("inf"), float("inf")
    candidate, d1 = ranked[0]
    d2 = ranked[1][1] if len(ranked) > 1 else float("inf")
    if d1 > threshold:
        return None, "distance", d1, d2
    if d2 < d1 + margin:
        return None, "ambiguous", d1, d2
    return candidate, None, d1, d2


def prepare_image(image_file):
    """Apply the same EXIF orientation, RGB conversion and size limit everywhere."""
    try:
        with Image.open(image_file) as original:
            if original.width * original.height > 30_000_000:
                raise ValueError("Изображение слишком большое: максимум 30 мегапикселей.")
            image = ImageOps.exif_transpose(original).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise ValueError("Не удалось прочитать изображение. Выберите JPG, PNG или WebP.") from error
    image.thumbnail((1600, 1600))
    return image


def predict_children(image_file, model_path=DEFAULT_MODEL_PATH, *, threshold=None, margin=None):
    names, known_encodings = load_saved_training_data(model_path)
    image = prepare_image(image_file)
    pixels = np.array(image, dtype=np.uint8)
    locations = face_recognition.face_locations(pixels, model="hog")
    encodings = face_recognition.face_encodings(pixels, locations)
    present, faces = set(), []
    draw = ImageDraw.Draw(image)
    for (top, right, bottom, left), encoding in zip(locations, encodings):
        distances = face_recognition.face_distance(known_encodings, encoding)
        name, reason, distance, _ = match_face(distances, names, threshold=threshold, margin=margin)
        if name:
            present.add(name)
        color = "#16834a" if name else "#d37514"
        draw.rectangle((left, top, right, bottom), outline=color, width=3)
        draw.text((left, max(0, top - 14)), name or "?", fill=color)
        faces.append(
            {
                "name": name,
                "status": "recognized" if name else "unknown",
                "reason": reason,
                "distance": round(distance, 4),
                "box": [top, right, bottom, left],
            }
        )
    attendance = [{"name": name, "present": name in present} for name in sorted(set(names))]
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88)
    return attendance, output.getvalue(), faces
