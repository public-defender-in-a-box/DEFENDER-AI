@echo off
REM DEFENDER AI — Docker Launcher (Windows)
REM Double-click to start.

title DEFENDER AI — Docker

echo.
echo   DEFENDER AI — Starting with Docker...
echo.

where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Docker is not installed.
    echo Download Docker Desktop from https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

cd /d "%~dp0"
docker compose up --build -d

timeout /t 4 /nobreak >nul
start http://localhost:3000

echo.
echo   DEFENDER AI is running!
echo   Open http://localhost:3000 in your browser.
echo.
echo   To stop: run 'docker compose down' or close Docker Desktop.
echo.
pause
