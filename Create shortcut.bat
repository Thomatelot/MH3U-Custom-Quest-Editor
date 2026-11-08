@echo off
rem Makes a "MH3U Quest Editor" shortcut (with the editor's icon) on the Desktop and in this folder.
cd /d "%~dp0"
set "PYW="
for /f "delims=" %%i in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW for /f "delims=" %%i in ('where pyw 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW (
    echo Python was not found. Install Python 3.10+ from python.org, then run this file again.
    pause
    exit /b 1
)
set "ARGS="
echo %PYW% | findstr /i "pyw.exe" >nul && set "ARGS=-3 "
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$w = New-Object -ComObject WScript.Shell;" ^
  "foreach ($dir in @([Environment]::GetFolderPath('Desktop'), '%~dp0')) {" ^
  "  $s = $w.CreateShortcut((Join-Path $dir 'MH3U Quest Editor.lnk'));" ^
  "  $s.TargetPath = '%PYW%';" ^
  "  $s.Arguments = '%ARGS%' + '\"%~dp0mh3u_quest_editor.py\"';" ^
  "  $s.WorkingDirectory = '%~dp0';" ^
  "  $s.IconLocation = '%~dp0assets\app_icon.ico';" ^
  "  $s.Description = 'MH3U Custom Quest Editor';" ^
  "  $s.Save() }"
echo Done: "MH3U Quest Editor" shortcut created on the Desktop and in this folder.
pause
