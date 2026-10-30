@echo off
setlocal DisableDelayedExpansion
pushd "%~dp0" || exit /b 1
title Jarvis Development
if defined JARVIS_PYTHON (
    set "JARVIS_DEV_PYTHON=%JARVIS_PYTHON%"
    goto launch
)
if exist ".venv\Scripts\python.exe" (
    set "JARVIS_DEV_PYTHON=%~dp0.venv\Scripts\python.exe"
    goto launch
)
python -I -B -c "import sys; sys.exit(sys.version_info < (3,13))" >nul 2>&1
if not errorlevel 1 (
    set "JARVIS_DEV_PYTHON=python"
    goto launch
)
py -3.13 -X utf8 -I -B "apps\development\manage.py" --open-browser %*
goto result
:launch
"%JARVIS_DEV_PYTHON%" -X utf8 -I -B "apps\development\manage.py" --open-browser %*
:result
if errorlevel 1 goto failure
popd
exit /b 0
:failure
echo [Jarvis] Development startup failed. Production was not stopped.
if not defined JARVIS_NO_PAUSE pause
popd
exit /b 1
