from backend.config import DEFAULT_DATA_DIR, DEFAULT_MODEL_PATH
from backend.services.recognition import load_saved_training_data


def sample_files(data_dir=DEFAULT_DATA_DIR, model_path=DEFAULT_MODEL_PATH):
    names = set(load_saved_training_data(model_path)[0])
    samples = {}
    for file in sorted((data_dir / "students").glob("*")):
        if file.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} and file.stem.title() in names:
            samples.setdefault(file.stem.title(), file)
    return list(samples.items())
