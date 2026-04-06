@echo off
REM ============================================================
REM  DEFENDER AI — One-Click Launcher (Windows)
REM
REM  Double-click this file to start the application.
REM  It will install dependencies, start the backend and frontend,
REM  and open the app in your default browser.
REM
REM  Prerequisites:
REM    - Node.js 18+ (https://nodejs.org)
REM    - Python 3.11+ (https://python.org)
REM
REM  To stop: close this window.
REM ============================================================

title DEFENDER AI — Public Defender Assistant

echo.
echo  ========================================
echo   DEFENDER AI — Starting Up...
echo   Public Defender AI Assistant
echo  ========================================
echo.

REM ---------- Check prerequisites ----------
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Node.js is not installed.
    echo Please download it from https://nodejs.org ^(version 18 or later^)
    pause
    exit /b 1
)

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python is not installed.
    echo Please download it from https://python.org ^(version 3.11 or later^)
    pause
    exit /b 1
)

echo [OK] Node.js found
echo [OK] Python found
echo.

REM ---------- Resolve project root ----------
set "ROOT=%~dp0"

REM ---------- Install frontend dependencies ----------
echo Installing frontend dependencies...
cd /d "%ROOT%packages\web"
if not exist node_modules (
    call npm install --no-audit --no-fund
) else (
    echo   ^(node_modules exists, skipping^)
)

REM ---------- Ensure .env.local exists ----------
if not exist .env.local (
    echo NEXT_PUBLIC_API_URL=http://localhost:8000> .env.local
    echo NEXTAUTH_SECRET=defender-ai-dev-secret-change-in-production>> .env.local
    echo NEXTAUTH_URL=http://localhost:3000>> .env.local
    echo [OK] Created .env.local with defaults
)

REM ---------- Set up Python virtual environment ----------
echo Setting up Python environment...
cd /d "%ROOT%packages\api"
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

REM ---------- Start backend in new window ----------
echo.
echo Starting backend (FastAPI) on http://localhost:8000 ...
start "DEFENDER AI — Backend" cmd /k "cd /d "%ROOT%packages\api" && call .venv\Scripts\activate.bat && uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"

REM ---------- Start frontend in new window ----------
echo Starting frontend (Next.js) on http://localhost:3000 ...
start "DEFENDER AI — Frontend" cmd /k "cd /d "%ROOT%packages\web" && npm run dev"

REM ---------- Wait and open browser ----------
echo.
echo Waiting for servers to start...
timeout /t 6 /nobreak >nul

start http://localhost:3000

echo.
echo  ========================================
echo   DEFENDER AI is running!
echo.
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000
echo.
echo   Close this window to stop.
echo  ========================================
echo.
pause
