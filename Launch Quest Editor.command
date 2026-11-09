#!/bin/sh
# MH3U Custom Quest Editor launcher for macOS (double-click it in the Finder).
# Needs Python 3.10+ with tkinter: the installer from python.org includes it.
cd "$(dirname "$0")" || exit 1
for py in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" 2>/dev/null; then
        exec "$py" mh3u_quest_editor.py "$@"
    fi
done
echo "Python 3.10 or newer with tkinter was not found. Install it from https://www.python.org/downloads/"
read -r _
