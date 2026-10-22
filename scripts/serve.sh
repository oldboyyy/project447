#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec .venv/bin/gunicorn --config deploy/gunicorn.conf.py backend.wsgi:app
