@echo off
rem MH3U Custom Quest Editor launcher (needs Python 3.10+ with tkinter)
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw -3 "%~dp0mh3u_quest_editor.py"
    exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0mh3u_quest_editor.py"
    exit /b
)
python "%~dp0mh3u_quest_editor.py"
if errorlevel 1 pause
