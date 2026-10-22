"""Run from any directory; bind locally behind an HTTPS reverse proxy."""

import os
from pathlib import Path

chdir = str(Path(__file__).resolve().parents[1])
bind = os.environ.get("BIND", "127.0.0.1:8000")
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "sync"
timeout = 120
accesslog = "-"
errorlog = "-"
capture_output = True
raw_env = ["ENABLE_SAMPLES=" + os.environ.get("ENABLE_SAMPLES", "0")]
