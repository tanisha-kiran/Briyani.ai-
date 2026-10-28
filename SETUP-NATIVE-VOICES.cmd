@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe scripts\download-native-voices.py
pause
