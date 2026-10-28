@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
if not exist "renderer\dist\export.mjs" goto missing
echo Open http://127.0.0.1:53841/ in your browser.
echo Keep this window open. Press Ctrl+C to stop the local studio.
call npm run studio
pause
exit /b
:missing
echo Run SETUP-WINDOWS.cmd first using Python 3.12.
pause
exit /b 1
