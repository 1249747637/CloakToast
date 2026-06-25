# CloakToast

多浏览器实例管理器，基于 [cloakbrowser](https://pypi.org/project/cloakbrowser/)（封装 Playwright 的反指纹 Chromium）。可创建多个带独立指纹、代理、流量策略的浏览器 Profile，按需启动/停止，所有 Profile 共享同一套书签。

## 功能

- **多 Profile 管理** — 每个 Profile 独立的 user_data_dir、代理、指纹配置
- **反指纹** — 屏幕分辨率、CPU/GPU、WebRTC、地理位置、UA、字体等全覆盖
- **链式代理** — 支持中继代理（mihomo 等）→ 目标代理两跳链接
- **GeoIP 自动推断** — 根据代理出口 IP 自动设置时区/语言/地理位置
- **省流模式** — 拦截视频流（mp4/HLS/DASH）和超限图片，节省代理流量
- **共享书签** — 统一管理书签，启动时自动写入 Chromium 原生书签栏
- **WebRTC 防泄露** — 支持自定义 IP、mask（10.0.0.1）、完全禁用三种模式

## 快速启动（Windows）

双击 `start.bat`，或在命令行执行：

```bat
start.bat
```

流程：安装依赖 → 杀占用 8765 的进程 → 构建前端 → 后台启动 server → 探活就绪后自动打开浏览器。

## 开发模式

```bash
# Terminal 1 — backend（热重载）
uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload

# Terminal 2 — frontend（HMR）
cd frontend && npm run dev
# → http://localhost:5173，API 自动代理到 :8765
```

## 依赖安装

```bash
pip install -r backend/requirements.txt
pip install "cloakbrowser[geoip]"   # 可选，启用 GeoIP 自动推断
cd frontend && npm install
```

## 测试

```bash
python -m pytest tests/ -v                      # 单元 + 集成（~2s）
CLOAKTOAST_E2E=1 python -m pytest tests/ -v    # 含真实 Chromium（~55s）
```

## 技术栈

| 层 | 技术 |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy · SQLite · uvicorn |
| Frontend | Vite · React 18 · TypeScript · Ant Design 5 |
| 浏览器 | cloakbrowser（Playwright + 反指纹 Chromium） |

## 数据目录

运行时数据存放在 `data/`（已 gitignore）：

```
data/
├── cloaktoast.db          # SQLite 数据库
├── config.json            # license key 等配置
└── profiles/<id>/         # 每个 Profile 的 user_data_dir
    ├── Default/Bookmarks  # 启动时自动写入的 Chromium 书签文件
    └── _cloaktoast_worker.log
```
