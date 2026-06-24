#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[1/3] 检查 Python 依赖..."
pip install -r backend/requirements.txt -q

echo "[2/3] 检查前端构建..."
if [ ! -f "frontend/dist/index.html" ]; then
  echo "正在构建前端..."
  cd frontend && npm install -q && npm run build && cd ..
fi

echo "[3/3] 启动 CloakToast..."
echo "访问 http://localhost:8765"
python -m backend.main
