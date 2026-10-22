"""HTTP interface; inference and dataset lookup live in services."""

import base64

from flask import Blueprint, current_app, jsonify, render_template, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

from backend.services.recognition import load_saved_training_data, predict_children
from backend.services.samples import sample_files

routes = Blueprint("attendance", __name__)


def _samples():
    if not current_app.config["ENABLE_SAMPLES"]:
        return []
    return sample_files(current_app.config["DATA_DIR"], current_app.config["MODEL_PATH"])


@routes.get("/healthz")
def health():
    return jsonify(status="ok")


@routes.get("/")
@routes.get("/index.php")
def index():
    return render_template("home.html")


@routes.get("/attendance")
def attendance_page():
    return render_template("index.html")


@routes.get("/api/status")
def status():
    names, _ = load_saved_training_data(current_app.config["MODEL_PATH"])
    return jsonify(
        students=len(set(names)),
        model="dlib / face_recognition",
        tolerance=current_app.config["FACE_MATCH_THRESHOLD"],
        margin=current_app.config["FACE_MATCH_MARGIN"],
        samples=[{"id": i, "name": name} for i, (name, _) in enumerate(_samples())],
    )


@routes.get("/api/samples/<int:sample_id>")
def sample(sample_id):
    samples = _samples()
    if sample_id >= len(samples):
        return jsonify(error="Пример не найден."), 404
    return send_file(samples[sample_id][1])


@routes.post("/upload")
def upload():
    photo = request.files.get("photo")
    if not photo or not photo.filename:
        return jsonify(error="Выберите изображение."), 400
    try:
        attendance, image, faces = predict_children(
            photo.stream,
            current_app.config["MODEL_PATH"],
            threshold=current_app.config["FACE_MATCH_THRESHOLD"],
            margin=current_app.config["FACE_MATCH_MARGIN"],
        )
        for student in attendance:
            student["id"] = current_app.config["STUDENT_ROSTER"][student["name"]]
        return jsonify(
            attendance=attendance,
            faces=faces,
            image="data:image/jpeg;base64," + base64.b64encode(image).decode("ascii"),
            detected=len(faces),
            unknown=sum(face["name"] is None for face in faces),
        )
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except Exception:
        current_app.logger.exception("Recognition failed")
        return jsonify(error="Ошибка распознавания. Подробности в терминале сервера."), 500


@routes.app_errorhandler(RequestEntityTooLarge)
def too_large(error):
    return jsonify(error="Файл слишком большой. Максимум 12 МБ."), 413
