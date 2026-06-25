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
for /f "delims=" %%p in ('where python 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%p"
if not defined PYTHON_EXE (
    echo ERROR: python not found in PATH.
    pause
    exit /b 1
)

powershell -NoProfile -NonInteractive -Command "Start-Process -FilePath '%PYTHON_EXE%' -ArgumentList '-m','backend.main' -WorkingDirectory '%~dp0' -WindowStyle Hidden"

powershell -NoProfile -NonInteractive -Command "$u='http://localhost:8765';for($i=0;$i-lt30;$i++){try{(New-Object Net.WebClient).DownloadString($u)|Out-Null;break}catch{Start-Sleep 1}};Start-Process $u"

echo CloakToast started. This window will close.
timeout /t 2 /nobreak >nul
exit /b 0
