"""MH3U Custom Quest Editor - launcher.  Needs Python 3.10+ (tkinter is included
with the python.org installer)."""
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def fail(message):
    print(message)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "MH3U Custom Quest Editor", 0x10)
    except Exception:
        pass
    sys.exit(1)


if sys.version_info < (3, 10):
    fail("Python 3.10 or newer is required.")
try:
    import tkinter  # noqa: F401
except ImportError:
    fail("tkinter is missing. Reinstall Python from python.org and keep the "
         "'tcl/tk and IDLE' option ticked.")

try:
    from mhqe.gui import run
    run()
except Exception:
    text = traceback.format_exc()
    try:
        with open(os.path.join(HERE, "error_log.txt"), "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass
    fail("The editor could not start:\n\n" + text[-900:])
