@echo off
call "%~dp0JarvisPC.bat" start-daily --open-browser
if errorlevel 1 (
    if not defined JARVIS_NO_PAUSE pause
    exit /b 1
)
