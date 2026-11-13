@echo off
rem Apply only an already prepared and independently checked candidate.
call "%~dp0JarvisPC.bat" apply-update
if errorlevel 1 (
    if not defined JARVIS_NO_PAUSE pause
    exit /b 1
)
