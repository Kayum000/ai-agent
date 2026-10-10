@echo off
setlocal
cd /d "%~dp0.."
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 pc_agent\server.py
) else (
  python pc_agent\server.py
)
echo.
echo My PC AI Agent stopped. Press any key to close.
pause >nul
