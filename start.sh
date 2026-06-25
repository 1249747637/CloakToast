#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[1/3] 检查 Python 依赖..."
pip install -r backend/requirements.txt -q
pip install "cloakbrowser[geoip]" -q 2>/dev/null || echo "[可选] cloakbrowser GeoIP 扩展未安装，GeoIP 跟随代理功能不可用"

echo "[2/3] 构建前端..."
cd frontend && npm install -q && npm run build && cd ..

echo "[3/3] 启动 CloakToast..."
(sleep 3 && (open http://localhost:8765 2>/dev/null || xdg-open http://localhost:8765 2>/dev/null || true)) &
python -m backend.main
