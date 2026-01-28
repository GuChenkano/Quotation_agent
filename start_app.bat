@echo off
cd /d "%~dp0"

echo ===================================================
echo      Quotation Agent Launcher
echo ===================================================

:: Set Python Path
set "PYTHON_EXE=D:\anaconda3\envs\langchainV2\python.exe"

echo.
echo [1/2] Starting Backend (FastAPI)...
echo -----------------------------------

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python interpreter not found at:
    echo %PYTHON_EXE%
    echo Please check the path.
    pause
    exit /b
)

start "Quotation Agent Backend" cmd /k "%PYTHON_EXE% api.py"
echo Backend started.

echo.
echo [2/2] Starting Frontend (Vue3 + Vite)...
echo -----------------------------------

if not exist "web-ui" (
    echo [ERROR] 'web-ui' directory not found!
    echo Current directory: %cd%
    pause
    exit /b
)

cd web-ui
start "Quotation Agent Frontend" cmd /k "npm run dev"
cd ..
echo Frontend started.

echo.
echo ===================================================
echo Done!
echo.
echo - Backend Docs: http://localhost:8000/docs
echo - Frontend URL: http://localhost:5173
echo.
echo Please do not close the popped up CMD windows.
echo ===================================================
pause
