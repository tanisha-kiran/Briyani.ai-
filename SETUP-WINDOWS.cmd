@echo off
setlocal
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r backend\requirements-lock.txt
if errorlevel 1 goto failed
call npm ci --ignore-scripts
if errorlevel 1 goto failed
call npm run build
if errorlevel 1 goto failed
echo Dependencies are ready. Keep the fonts and public folders beside the application.
echo Run SETUP-LOCAL-MODELS.cmd once while online, then START-STUDIO.cmd.
pause
exit /b 0
:failed
echo Setup stopped. Install Python 3.12 and Node.js, then retry. Read the error above.
pause
exit /b 1
