@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%start-codex-usage-widget.ps1"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%"

set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo Launcher exited with code %EXIT_CODE%.
    echo.
    pause
)

endlocal
exit /b %EXIT_CODE%
