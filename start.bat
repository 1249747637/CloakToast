@echo off
cd /d "%~dp0"

echo [1/3] 检查 Python 依赖...
pip install -r backend\requirements.txt -q

echo [2/3] 检查前端构建...
if not exist "frontend\dist\index.html" (
    echo 正在构建前端...
    cd frontend
    call npm install -q
    call npm run build
    cd ..
)

echo [3/3] 启动 CloakToast...
start "" /b cmd /c "timeout /t 3 /nobreak > nul && start http://localhost:8765"
python -m backend.main
