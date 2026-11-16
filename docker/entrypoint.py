#!/usr/bin/env python3
"""CampusFix — Unified Container Process Supervisor & Entrypoint.

Manages Nginx and FastAPI (Uvicorn) within a single unprivileged container:
- Dynamically binds Nginx to Render's dynamic $PORT (defaults to 8080).
- Binds FastAPI strictly to internal loopback (127.0.0.1:8000).
- Forwards SIGTERM and SIGINT to child processes with a 10s graceful shutdown window.
- Implements fail-fast behavior: if either child process terminates unexpectedly,
  the surviving process is immediately terminated and the container exits with an error.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Configuration paths
NGINX_CONF_TEMPLATE = Path("/etc/nginx/nginx.conf.template")
NGINX_CONF_ACTIVE = Path("/tmp/nginx.conf")
BACKEND_DIR = Path("/app/backend")

# Required writable directories for unprivileged Nginx execution
TEMP_DIRS = [
    Path("/tmp/client_temp"),
    Path("/tmp/proxy_temp"),
    Path("/tmp/fastcgi_temp"),
    Path("/tmp/uwsgi_temp"),
    Path("/tmp/scgi_temp"),
]

GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS = 10.0


def log(message: str) -> None:
    """Formatted operational supervisor logger."""
    print(f"[supervisor] {message}", flush=True)


def ensure_temp_directories() -> None:
    """Ensures unprivileged write paths exist under /tmp."""
    for temp_dir in TEMP_DIRS:
        temp_dir.mkdir(parents=True, exist_ok=True)


def configure_nginx(port: str) -> None:
    """Renders the active nginx.conf from template by injecting the dynamic $PORT."""
    if not NGINX_CONF_TEMPLATE.exists():
        log(f"FATAL: Nginx template not found at {NGINX_CONF_TEMPLATE}")
        sys.exit(1)

    template_text = NGINX_CONF_TEMPLATE.read_text(encoding="utf-8")
    # Replace ${PORT} placeholder without disturbing Nginx variables ($host, $uri, etc.)
    rendered = template_text.replace("${PORT}", port)
    NGINX_CONF_ACTIVE.write_text(rendered, encoding="utf-8")
    log(f"Configured Nginx to listen on dynamic port {port} (written to {NGINX_CONF_ACTIVE})")

    # Validate Nginx configuration syntax
    result = subprocess.run(
        ["nginx", "-t", "-c", str(NGINX_CONF_ACTIVE)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log(f"FATAL: Nginx configuration test failed:\n{result.stderr}")
        sys.exit(1)
    log("Nginx configuration syntax test successful.")


def wait_for_backend_ready(backend_proc: subprocess.Popen, port: int = 8000, timeout: float = 15.0) -> bool:
    """Waits for FastAPI /healthz probe to return HTTP 200 before routing traffic."""
    url = f"http://127.0.0.1:{port}/healthz"
    start_time = time.monotonic()
    log(f"Probing backend health at {url}...")

    while time.monotonic() - start_time < timeout:
        if backend_proc.poll() is not None:
            log(f"FATAL: Backend process terminated during startup with exit code {backend_proc.returncode}!")
            return False

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Supervisor-Probe/1.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    elapsed = time.monotonic() - start_time
                    log(f"Backend probe verified healthy in {elapsed:.2f}s.")
                    return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.2)

    log(f"WARNING: Backend probe timed out after {timeout}s; proceeding with Nginx launch.")
    return False


class UnifiedSupervisor:
    """Manages the lifecycle, health, and signal propagation for Nginx and FastAPI."""

    def __init__(self, backend_proc: subprocess.Popen, nginx_proc: subprocess.Popen) -> None:
        self.backend_proc = backend_proc
        self.nginx_proc = nginx_proc
        self.received_signal: int | None = None
        self.shutting_down = False
        self.exit_code = 0

    def on_signal(self, signum: int, frame: Any) -> None:
        """Signal handler catching SIGTERM and SIGINT for graceful shutdown."""
        sig_name = signal.Signals(signum).name
        log(f"Caught signal {sig_name}. Initiating graceful shutdown sequence...")
        self.received_signal = signum
        self.shutting_down = True

    def terminate_children(self, timeout: float = GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS) -> None:
        """Sends termination signals and waits for child processes to exit cleanly."""
        procs = [
            ("Nginx", self.nginx_proc),
            ("FastAPI", self.backend_proc),
        ]

        # Step 1: Send SIGTERM to both processes
        for name, proc in procs:
            if proc.poll() is None:
                log(f"Sending SIGTERM to {name} (PID {proc.pid})...")
                try:
                    proc.terminate()
                except OSError as err:
                    log(f"Could not signal {name}: {err}")

        # Step 2: Await graceful termination within bounded window
        start_time = time.monotonic()
        for name, proc in procs:
            if proc.poll() is None:
                remaining = max(0.1, timeout - (time.monotonic() - start_time))
                try:
                    proc.wait(timeout=remaining)
                    log(f"{name} exited cleanly with code {proc.returncode}.")
                except subprocess.TimeoutExpired:
                    log(f"WARNING: {name} did not exit within {timeout}s window; sending SIGKILL...")
                    try:
                        proc.kill()
                        proc.wait(timeout=2.0)
                        log(f"{name} killed.")
                    except OSError:
                        pass
            else:
                log(f"{name} already stopped with code {proc.returncode}.")

    def run(self) -> int:
        """Main monitoring loop with fail-fast detection and signal interception."""
        signal.signal(signal.SIGTERM, self.on_signal)
        signal.signal(signal.SIGINT, self.on_signal)

        log("Unified supervisor active. Monitoring child processes...")

        while not self.shutting_down:
            time.sleep(0.5)

            # Fail-fast check: Did FastAPI backend crash?
            backend_code = self.backend_proc.poll()
            if backend_code is not None:
                log(f"FAIL-FAST: FastAPI backend exited unexpectedly with code {backend_code}!")
                self.exit_code = backend_code if backend_code != 0 else 1
                self.shutting_down = True
                self.terminate_children(timeout=5.0)
                break

            # Fail-fast check: Did Nginx crash?
            nginx_code = self.nginx_proc.poll()
            if nginx_code is not None:
                log(f"FAIL-FAST: Nginx web server exited unexpectedly with code {nginx_code}!")
                self.exit_code = nginx_code if nginx_code != 0 else 1
                self.shutting_down = True
                self.terminate_children(timeout=5.0)
                break

        # Handle planned signal shutdown if triggered
        if self.received_signal is not None:
            self.terminate_children(timeout=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS)
            self.exit_code = 0

        log(f"Unified supervisor exiting with code {self.exit_code}.")
        return self.exit_code


def main() -> None:
    port = os.environ.get("PORT", "8080").strip()
    log(f"Initializing CampusFix unified container on port {port}...")

    ensure_temp_directories()
    configure_nginx(port)

    # 1. Start FastAPI backend (bound strictly to loopback 127.0.0.1:8000)
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    log(f"Launching FastAPI backend: {' '.join(backend_cmd)}")
    backend_proc = subprocess.Popen(backend_cmd, cwd=str(BACKEND_DIR))

    # 2. Verify backend probe before starting Nginx
    backend_ready = wait_for_backend_ready(backend_proc, port=8000, timeout=15.0)
    if not backend_ready and backend_proc.poll() is not None:
        log("Backend failed to start. Exiting.")
        sys.exit(backend_proc.returncode or 1)

    # 3. Start Nginx web server
    nginx_cmd = ["nginx", "-c", str(NGINX_CONF_ACTIVE), "-g", "daemon off;"]
    log(f"Launching Nginx web server: {' '.join(nginx_cmd)}")
    nginx_proc = subprocess.Popen(nginx_cmd)

    # 4. Supervise both processes
    supervisor = UnifiedSupervisor(backend_proc=backend_proc, nginx_proc=nginx_proc)
    exit_code = supervisor.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
