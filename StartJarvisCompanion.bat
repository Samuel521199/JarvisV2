@echo off
setlocal DisableDelayedExpansion
call "%~dp0StartJarvis.bat" --companion %*
exit /b %errorlevel%
