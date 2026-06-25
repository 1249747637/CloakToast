@echo off
setlocal
cd /d "%~dp0"

echo [1/4] Installing Python dependencies...
pip install -r backend\requirements.txt -q
pip install "cloakbrowser[geoip]" -q 2>nul

echo [2/4] Stopping any existing server on port 8765...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr "0.0.0.0:8765"') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [3/4] Building frontend...
cd frontend
call npm install -q
call npm run build
if errorlevel 1 (
    echo.
    echo ERROR: frontend build failed. See above for details.
    cd ..
    pause
    exit /b 1
)
cd ..

echo [4/4] Starting CloakToast...
start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8765"
python -m backend.main
if errorlevel 1 (
    echo.
    echo Server exited with an error. Press any key to close.
    pause
)
