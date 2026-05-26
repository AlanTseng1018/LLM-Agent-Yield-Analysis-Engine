"""
One-command launcher for LLM Yield Engine.

    python run.py                 # start everything, open browser
    python run.py --no-browser    # start everything, don't auto-open
    python run.py --rebuild       # force rebuild the frontend

What it does:
  1. Verify Ollama is reachable at :11434 (does NOT start it for you).
  2. If frontend/dist/ is missing, run `npm install` + `npm run build` once.
  3. Spawn the MCP server (:8001) and the FastAPI backend (:8000) as children.
     The backend serves the built frontend from /, so the whole UI is at :8000.
  4. Open http://localhost:8000 in the default browser.
  5. Stream both children's stdout/stderr into this terminal with colored
     [hh:mm:ss][scope] prefixes, so MCP and backend logs are easy to tell apart.
  6. On Ctrl+C, terminate both children cleanly.

For frontend hot-reload during development, skip this script and run the
three services in separate terminals (see README · "Development").
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
OLLAMA_URL = "http://127.0.0.1:11434/api/tags"
BACKEND_URL = "http://127.0.0.1:8000/health"
IS_WINDOWS = os.name == "nt"

# ── Colors ─────────────────────────────────────────────────────────────────
# Standard ANSI. Windows 10/11 terminals enable VT processing by default in
# 2026, so no colorama needed for fresh installs.
RESET = "\033[0m"
COLORS = {
    # launcher's own statuses
    "info":     "\033[96m",   # cyan
    "ok":       "\033[92m",   # green
    "warn":     "\033[93m",   # yellow
    "err":      "\033[91m",   # red
    # child scopes
    "launcher": "\033[95m",   # magenta
    "mcp":      "\033[96m",   # cyan
    "backend":  "\033[92m",   # green
    # stderr highlight
    "stderr":   "\033[91m",   # red, used for the [scope!] prefix
}

# Uniform prefix width so columns line up regardless of scope name.
_PREFIX_W = 8


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def log(level: str, msg: str) -> None:
    """Launcher's own log line, distinct prefix from child output."""
    color = COLORS.get(level, "")
    tag = f"{color}[{_ts()}][{'launcher':<{_PREFIX_W}}]{RESET}"
    print(f"{tag} {color}{level.upper():<4}{RESET} {msg}", flush=True)


# ── Ollama / health checks ─────────────────────────────────────────────────

def check_ollama() -> bool:
    try:
        with urllib.request.urlopen(OLLAMA_URL, timeout=2.0) as r:
            return r.status == 200
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        return False


def wait_for(url: str, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


# ── Frontend build ─────────────────────────────────────────────────────────

def build_frontend(force: bool) -> None:
    if DIST.is_dir() and not force:
        log("info", f"Frontend already built: {DIST.relative_to(ROOT)}")
        return

    npm = shutil.which("npm")
    if not npm:
        log("err", "`npm` not found on PATH. Install Node.js 18+ first.")
        sys.exit(1)

    node_modules = FRONTEND / "node_modules"
    if not node_modules.is_dir():
        log("info", "Installing frontend deps (one-time, ~1 min)...")
        subprocess.check_call([npm, "install"], cwd=FRONTEND, shell=IS_WINDOWS)

    log("info", "Building frontend...")
    subprocess.check_call([npm, "run", "build"], cwd=FRONTEND, shell=IS_WINDOWS)
    log("ok", f"Frontend built → {DIST.relative_to(ROOT)}")


# ── Child process plumbing ─────────────────────────────────────────────────

def _pipe_reader(scope: str, stream, is_stderr: bool) -> None:
    """Forward one child's pipe line-by-line with a colored prefix.

    Lines from the child may already contain ANSI escapes (uvicorn's INFO is
    colored). We leave the line body untouched so those colors survive.
    """
    color = COLORS.get(scope, "")
    # stderr lines get [scope!] in red so they pop out at a glance.
    if is_stderr:
        tag_color = COLORS["stderr"]
        scope_label = f"{scope}!"
    else:
        tag_color = color
        scope_label = scope

    try:
        for line in iter(stream.readline, ""):
            if not line:
                break
            ts = _ts()
            prefix = f"{tag_color}[{ts}][{scope_label:<{_PREFIX_W}}]{RESET}"
            sys.stdout.write(f"{prefix} {line.rstrip()}\n")
            sys.stdout.flush()
    except Exception as e:
        log("warn", f"Reader for [{scope}{'!' if is_stderr else ''}] died: {e}")
    finally:
        try:
            stream.close()
        except Exception:
            pass


def spawn(scope: str, cmd: list[str], cwd: Path) -> subprocess.Popen:
    """Spawn a child process and stream its output through _pipe_reader.

    - New process group so Ctrl+C in this script doesn't tear children
      before we run graceful shutdown.
    - PYTHONUNBUFFERED=1 so Python children flush each line immediately
      (otherwise they buffer 4KB+ and the terminal looks frozen).
    """
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    kwargs: dict = {
        "cwd": str(cwd),
        "env": env,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "bufsize": 1,                 # line-buffered
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",          # don't crash on weird bytes
    }
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    p = subprocess.Popen(cmd, **kwargs)

    threading.Thread(
        target=_pipe_reader, args=(scope, p.stdout, False), daemon=True
    ).start()
    threading.Thread(
        target=_pipe_reader, args=(scope, p.stderr, True), daemon=True
    ).start()
    return p


def terminate(p: subprocess.Popen) -> None:
    if p.poll() is not None:
        return
    try:
        if IS_WINDOWS:
            p.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            p.terminate()
        p.wait(timeout=5)
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open the browser.")
    parser.add_argument("--rebuild", action="store_true", help="Force `npm run build` even if dist/ exists.")
    args = parser.parse_args()

    # 1. Ollama check (we don't start it; that's the user's responsibility)
    log("info", "Checking Ollama at :11434 ...")
    if not check_ollama():
        log("err", "Ollama is not reachable. Start it first:")
        log("err", "    ollama serve")
        log("err", "and make sure the required models are pulled:")
        log("err", "    ollama pull qwen3.5:4b")
        log("err", "    ollama pull qwen3:8b")
        return 1
    log("ok", "Ollama reachable.")

    # 2. Frontend build
    build_frontend(force=args.rebuild)

    # 3. Spawn children
    procs: list[subprocess.Popen] = []
    try:
        log("info", "Starting MCP server (:8001) ...")
        procs.append(spawn("mcp", [sys.executable, "mcp/server.py"], cwd=ROOT))

        log("info", "Starting backend (:8000) ...")
        procs.append(spawn(
            "backend",
            [sys.executable, "-m", "uvicorn", "backend.app.main:app",
             "--host", "127.0.0.1", "--port", "8000"],
            cwd=ROOT,
        ))

        # 4. Wait for backend to come up, then open browser
        log("info", "Waiting for backend to be ready ...")
        if not wait_for(BACKEND_URL, timeout=30.0):
            log("err", "Backend did not become ready in 30s. Check logs above.")
            return 2
        log("ok", "Backend is up.")

        url = "http://localhost:8000"
        if not args.no_browser:
            webbrowser.open(url)
        log("ok", f"All services running. Open {url}")
        log("info", "Press Ctrl+C to stop everything.")

        # 5. Block until any child exits or user hits Ctrl+C
        while True:
            for p in procs:
                if p.poll() is not None:
                    log("warn", f"Child PID {p.pid} exited with {p.returncode}. Shutting down others.")
                    return p.returncode or 0
            time.sleep(0.5)

    except KeyboardInterrupt:
        log("info", "Ctrl+C received. Shutting down ...")
        return 0
    finally:
        for p in procs:
            terminate(p)
        log("ok", "All children terminated.")


if __name__ == "__main__":
    sys.exit(main())
