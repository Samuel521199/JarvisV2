@echo off
setlocal DisableDelayedExpansion
pushd "%~dp0" || exit /b 1
if defined JARVIS_PYTHON goto custom_python
if exist ".venv\Scripts\python.exe" (
    set "JARVIS_PC_PYTHON=%~dp0.venv\Scripts\python.exe"
    goto launch
)
set "JARVIS_PC_PYTHON=python"
goto launch
:custom_python
set "JARVIS_PC_PYTHON=%JARVIS_PYTHON%"
:launch
if "%~1"=="" (
    "%JARVIS_PC_PYTHON%" -X utf8 -B -m tools.workstation status
) else (
    "%JARVIS_PC_PYTHON%" -X utf8 -B -m tools.workstation %*
)
set "JARVIS_PC_RESULT=%errorlevel%"
popd
exit /b %JARVIS_PC_RESULT%
