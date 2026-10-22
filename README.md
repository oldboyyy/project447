# Automatic Attendance System

[Русская версия](README.ru.md)

A local classroom attendance prototype built with Flask and dlib face recognition.
Upload a photograph or capture a camera frame, review recognized students, and export
an attendance CSV. The interface includes an SDU-style home page and an attendance portal.

**Private student photos, roster records and identity models are not included.**
A fresh clone can run the public tests immediately after installing dependencies.
Running the attendance app requires your own matching model and roster.

## Features

- Photo upload, single camera capture and live recognition every three seconds.
- Face annotations and explicit unconfirmed-identity results.
- Configurable distance threshold and separation from the next distinct student.
- Student IDs loaded from a semicolon-delimited roster.
- Browser CSV export with `ID`, `Name` and `Status` columns.
- Optional local sample images, disabled in the example environment and server launcher.
- Separate training command, Flask application factory and Gunicorn entry point.

Results describe the latest frame only. There is no login, database or persistent attendance
history. “Not detected” does not establish absence. Uploaded images are processed in memory.
Training-image demonstrations do not measure accuracy on unseen people or photographs.

## Technology

Python 3.11, Flask, dlib / face-recognition, NumPy, Pillow and Gunicorn.
The frontend uses HTML, CSS and vanilla JavaScript; it has no npm dependencies or build step.
Tests use `unittest`; Ruff checks Python code. Node.js executes the real CSV-export code in tests.

## Project structure

```text
backend/                  Flask factory, routes, configuration and services
frontend/templates/       Home page and attendance portal
frontend/static/          JavaScript, CSS and existing SDU visual assets
ml/train.py               Build face embeddings from your own photographs
data/raw/students/        Local photos only; .gitkeep is the only tracked file
data/metadata/            Local roster only; .gitkeep is the only tracked file
models/                   Local identity model only; .gitkeep is the only tracked file
tests/                    Synthetic public tests and opt-in private-data tests
requirements/             Pinned runtime, server, development and build dependencies
deploy/gunicorn.conf.py    Local WSGI server configuration
scripts/serve.sh           Gunicorn launcher using .venv
start.command             macOS local Flask launcher using .venv
docs/                     Architecture, API and deployment notes
.github/                  CI workflow and contribution templates
.env.example              Non-secret environment template
.python-version           Recommended Python version: 3.11
```

## Requirements

- Python **3.11** on macOS or Linux.
- A C++ compiler and CMake for dlib if a compatible wheel is unavailable. On macOS,
  install Xcode Command Line Tools; on Debian/Ubuntu, install the `build-essential` package.
  The pinned Python build requirements provide CMake.
- Node.js **22** for the full public test suite; it is not needed to serve the app.
  Without Node.js, the CSV-export test is skipped.
- A browser with camera permission for camera capture. Use localhost or HTTPS.
- Git; GitHub CLI is convenient for cloning a private repository after signing in.

## Installation

After the repository has been created on GitHub, sign in to GitHub CLI as its owner.
`gh repo clone project447` resolves the repository under that authenticated account.
Collaborators should use the actual owner/repository name from the GitHub page instead.

```sh
gh repo clone project447
cd project447
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/build.txt
python -m pip install -r requirements/development.txt
cp .env.example .env
```

`requirements/development.txt` includes the runtime, Gunicorn and Ruff. For a local runtime
only, install `requirements.txt`; for a server without development tools, install
`requirements/production.txt`. Install build requirements first, with the virtual environment
activated so dlib can find CMake.

Edit `.env` locally. It is ignored by Git. The application does **not** load it automatically;
load it into your shell before launching:

```sh
set -a
. ./.env
set +a
```

All configuration values are documented in `.env.example`. No API keys or external services
are required. `DISPLAY_NAME` is a display label, not an authenticated identity. If you put
spaces in a value, quote it using shell syntax. Source only an environment file you trust.

## Supply your own private data

There is no public download of the student dataset or identity model. Obtain consented
photos and a roster from your own authorized source, or use an authorized existing model.
The upstream pretrained dlib models are installed by `face-recognition-models`; those are
separate from your own student identity embeddings.

1. Put one clear, single-face image per student into `data/raw/students/`. Supported extensions
   are `.jpg`, `.jpeg`, `.png` and `.webp`. The filename stem becomes the student name.
2. Create `data/metadata/students_dataset.csv` with `ID;Name` columns. IDs and names must be
   nonempty and unique. Names are normalized with Python's title-casing and must match the
   model. This example contains fictional values only:

   ```csv
   ID;Name
   DEMO-001;Student One
   DEMO-002;Student Two
   ```

3. With the virtual environment activated, train your own model:

   ```sh
   python -m ml.train data/raw/students --output models/retrained.pkl
   ```

   For the example above, the input files would be `Student One.jpg` and `Student Two.jpg`.
   Images with zero or multiple faces are skipped; an entirely unusable input set does not
   replace an existing model. Training prints the filenames it processes: keep these logs private.
4. The model and roster must contain exactly the same student names. The server rejects missing
   files and mismatches at startup. Restart the server after training or replacing a model.
   Load only models from a trusted source.

Photos, roster CSVs, embeddings and local logs are excluded from Git. **Do not use `git add -f`
or Git LFS to publish them.** To test without personal data, use the synthetic public suite below.

## Run

After supplying the model and roster and loading `.env`:

```sh
python -m backend
```

Open <http://127.0.0.1:8000>. On macOS, `./start.command` also launches the local app from `.venv`.
Use `Ctrl+C` to stop. Change the port with `PORT=8001 python -m backend`.

For Gunicorn, using `.venv` in the project directory:

```sh
./scripts/serve.sh
```

Gunicorn binds to `127.0.0.1:8000` by default. The server launcher defaults to disabled photo
samples; an explicit `ENABLE_SAMPLES` environment value takes precedence. This does not
publish a website. See [deployment notes](docs/DEPLOYMENT.md) before external access.
GitHub Pages cannot run this Python backend and is not configured.

## Usage

1. Open the home page and choose **Take Attendance**.
2. Choose **Upload photo** or **Live camera**. Upload a clear image, capture one frame, or
   start live recognition. Uploaded files are limited to 12 MiB and 30 megapixels.
3. Review the annotated image and unconfirmed faces. Each new scan replaces the previous results.
4. Open **Attendance** and download the CSV before closing or reloading the page.
5. For local demonstrations, set `ENABLE_SAMPLES=1` and restart. Samples use your private
   `data/raw/students/` images; do not enable this on an externally accessible server.

_Screenshot placeholder: a dashboard using fictional data. No real student screenshots are included._

## Tests and code quality

These checks do not require a model, roster, student photo, `.env` file or GitHub secret:

```sh
ruff check .
ruff format --check .
node --check frontend/static/app.js
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
python -m pip check
```

Public tests create temporary fictional rosters, random embedding arrays and blank images.
They exercise matching rules, image preprocessing, API errors, roster validation, CSV export,
real Flask-process startup and Gunicorn configuration. They do not claim face-recognition accuracy.
Two private-data tests are skipped unless explicitly enabled:

```sh
PYTHONDONTWRITEBYTECODE=1 RUN_PRIVATE_DATA_TESTS=1 python -m unittest discover -s tests -v
```

Only run that command locally with your authorized model, roster and matching training photos.
Its failure output can contain student names; do not upload it. The GitHub Actions workflow runs
lint, formatting, dependency checks and public tests on pushes and pull requests to `main`.

## Roadmap

- Authentication and access controls before exposing recognition or sample endpoints.
- Persistent attendance records and review workflows.
- Evaluation on an independent, consented dataset.
- Operational configuration, monitoring and physical-camera testing on target devices.

## Contributing, authors and license

Maintainer: **oldboyyy**, taken from the project's Git author configuration.
See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution rules.

Project source code is provided under the [MIT License](LICENSE). Existing SDU branding and
third-party assets are not relicensed by it. Their original licenses were not supplied;
obtain permission or replace them before making a public release. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
