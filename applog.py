"""Error log for debugging: everything goes to <data>/logs/stamhad-staff.log.

The log is included when you use Settings -> Data -> Share files, so a problem on
the restaurant computer can be looked at from anywhere.
"""

from __future__ import annotations

import logging
import logging.handlers
import platform
import sys
import threading
from pathlib import Path

log = logging.getLogger("stamhad")
_LOG_FILE: Path | None = None


def log_dir(root: Path) -> Path:
    d = Path(root) / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_file() -> Path | None:
    return _LOG_FILE


def setup(root: Path, version: str):
    """Start logging to a rotating file (3 x 1 MB). Safe to call more than once."""
    global _LOG_FILE
    if _LOG_FILE is not None:
        return
    try:
        _LOG_FILE = log_dir(root) / "stamhad-staff.log"
        h = logging.handlers.RotatingFileHandler(_LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
    except Exception:
        _LOG_FILE = None
        return
    frozen = "app" if getattr(sys, "frozen", False) else "source"
    log.info("──── Stamhad Staff %s started (%s, %s %s, Python %s)", version, frozen,
             platform.system(), platform.release(), platform.python_version())

    def hook(t, v, tb):
        log.critical("Uncaught error", exc_info=(t, v, tb))
        sys.__excepthook__(t, v, tb)
    sys.excepthook = hook

    def thook(args):
        log.error("Error in background task", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    threading.excepthook = thook


def install_tk(root_window):
    """Log errors raised inside button clicks etc., and tell the user once per error."""
    from tkinter import messagebox
    shown = set()

    def report(exc, val, tb):
        log.error("Error in the window", exc_info=(exc, val, tb))
        key = (exc.__name__, str(val)[:80])
        if key in shown:
            return
        shown.add(key)
        try:
            messagebox.showerror(
                "Something went wrong",
                f"{exc.__name__}: {val}\n\nIt was saved to the log. To send it for checking:\n"
                f"Settings → Data → Share files.", parent=root_window)
        except Exception:
            pass
    root_window.report_callback_exception = report
