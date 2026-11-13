@echo off
rem Return to the recorded compatible code version; do not restore business data.
call "%~dp0JarvisPC.bat" rollback
if errorlevel 1 (
    if not defined JARVIS_NO_PAUSE pause
    exit /b 1
)
