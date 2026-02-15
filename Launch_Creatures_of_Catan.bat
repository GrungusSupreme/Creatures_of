@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Python virtual environment not found at .venv\Scripts\python.exe
  echo Create it first, then install dependencies if needed.
  pause
  exit /b 1
)

"%PYTHON_EXE%" "%~dp0play_gui.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Game exited with code %EXIT_CODE%.
  pause
)

exit /b %EXIT_CODE%
