@echo off
cd /d "%~dp0"
python -m atelier
if errorlevel 1 pause

