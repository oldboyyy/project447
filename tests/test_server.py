"""Start the actual entry points with temporary, fictional data."""

import json
import os
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from backend.config import ROOT
from tests.fixtures import GalleryTestCase


class ServerTest(GalleryTestCase):
    def test_local_server_starts(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        with subprocess.Popen(
            [sys.executable, "-m", "backend"],
            cwd=ROOT,
            env={**os.environ, "PORT": str(port), "ENABLE_SAMPLES": "0"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ) as process:
            try:
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail(process.communicate()[0])
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as response:
                            self.assertEqual(json.load(response), {"status": "ok"})
                        break
                    except (URLError, TimeoutError):
                        time.sleep(0.1)
                else:
                    self.fail("Local server did not become ready")
                with urlopen(f"http://127.0.0.1:{port}/api/status", timeout=2) as response:
                    status = json.load(response)
                    self.assertEqual(status["students"], len(self.names))
                    self.assertEqual(status["samples"], [])
                with urlopen(f"http://127.0.0.1:{port}/attendance", timeout=2) as response:
                    self.assertEqual(response.status, 200)
            finally:
                process.terminate()
                try:
                    process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()

    def test_wsgi_configuration(self):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "gunicorn",
                "--check-config",
                "--config",
                "deploy/gunicorn.conf.py",
                "backend.wsgi:app",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
