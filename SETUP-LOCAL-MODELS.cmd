@echo off
setlocal
cd /d "%~dp0"
ollama pull qwen3.5:4b
if errorlevel 1 goto failed
".venv\Scripts\python.exe" scripts\download-piper-voices.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" scripts\download-native-voices.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" scripts\download-asr-model.py
if errorlevel 1 goto failed
echo Local models are ready. Runtime generation does not require internet.
pause
exit /b 0
:failed
echo Setup failed. Check the error above. Install Ollama and run SETUP-WINDOWS first.
pause
exit /b 1
