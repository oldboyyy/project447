"""Application factory shared by local development, tests and WSGI."""

from flask import Flask

from backend.config import FRONTEND_DIR, settings
from backend.routes import routes
from backend.services.recognition import load_saved_training_data
from backend.services.roster import load_roster


def create_app(config=None):
    app = Flask(
        __name__,
        template_folder=str(FRONTEND_DIR / "templates"),
        static_folder=str(FRONTEND_DIR / "static"),
        static_url_path="/static",
    )
    app.config.from_mapping(settings())
    if config:
        app.config.update(config)
    names, _ = load_saved_training_data(app.config["MODEL_PATH"])
    roster = load_roster(app.config["ROSTER_PATH"])
    missing_from_csv = sorted(set(names) - set(roster))
    missing_from_model = sorted(set(roster) - set(names))
    if missing_from_csv or missing_from_model:
        raise ValueError(
            "Model/CSV student mismatch: "
            f"missing from CSV: {', '.join(missing_from_csv) or 'none'}; "
            f"missing from model: {', '.join(missing_from_model) or 'none'}"
        )
    app.config["STUDENT_ROSTER"] = roster
    app.register_blueprint(routes)
    return app
