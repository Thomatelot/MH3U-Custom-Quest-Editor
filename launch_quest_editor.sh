#!/bin/sh
# MH3U Custom Quest Editor launcher for Linux: ./launch_quest_editor.sh
# Needs Python 3.10+ with tkinter (Debian/Ubuntu/Mint: sudo apt install python3-tk).
cd "$(dirname "$0")" || exit 1
for py in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c "import sys, tkinter; sys.exit(sys.version_info < (3, 10))" 2>/dev/null; then
        exec "$py" mh3u_quest_editor.py "$@"
    fi
done
echo "Python 3.10 or newer with tkinter was not found."
echo "Debian/Ubuntu/Linux Mint: sudo apt install python3 python3-tk"
echo "Fedora: sudo dnf install python3-tkinter    Arch: sudo pacman -S tk"
exit 1
