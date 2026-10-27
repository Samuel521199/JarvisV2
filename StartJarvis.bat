@echo off
setlocal DisableDelayedExpansion
pushd "%~dp0" || exit /b 1
title Jarvis Workbench

if defined JARVIS_PYTHON goto custom_python
if exist ".venv\Scripts\python.exe" (
    set "JARVIS_LAUNCH_PYTHON=%~dp0.venv\Scripts\python.exe"
    goto use_python
)
python -I -B -c "import sys; sys.exit(sys.version_info < (3,13))" >nul 2>&1
if not errorlevel 1 (
    set "JARVIS_LAUNCH_PYTHON=python"
    goto use_python
)
py -3.13 -I -B -c "import sys" >nul 2>&1
if not errorlevel 1 goto use_py
echo [Jarvis] Python 3.13 or newer was not found.
echo Install Python, or set JARVIS_PYTHON to the full python.exe path.
goto failure

:custom_python
set "JARVIS_LAUNCH_PYTHON=%JARVIS_PYTHON%"
:use_python
"%JARVIS_LAUNCH_PYTHON%" -X utf8 -I -B "apps\workbench\launch.py" %*
goto result

:use_py
py -3.13 -X utf8 -I -B "apps\workbench\launch.py" %*
:result
if errorlevel 1 goto failure
popd
exit /b 0

:failure
echo.
echo [Jarvis] Startup failed. See the message above.
if not defined JARVIS_NO_PAUSE pause
popd
exit /b 1
