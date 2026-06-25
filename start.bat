@echo off
cd /d "%~dp0"

echo [1/3] 检查 Python 依赖...
pip install -r backend\requirements.txt -q
pip install "cloakbrowser[geoip]" -q 2>nul || echo [可选] cloakbrowser GeoIP 扩展未安装，GeoIP 跟随代理功能不可用

echo [2/3] 构建前端...
cd frontend
call npm install -q
call npm run build
cd ..

echo [3/3] 启动 CloakToast...
start "" /b cmd /c "timeout /t 3 /nobreak > nul && start http://localhost:8765"
python -m backend.main
