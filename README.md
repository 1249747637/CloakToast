# CloakToast

[English](README_EN.md) | 中文

多浏览器实例管理器，基于 [cloakbrowser](https://pypi.org/project/cloakbrowser/)（封装 Playwright 的反指纹 Chromium）。创建多个带独立指纹、代理、流量策略的浏览器 Profile，按需启动/停止，所有 Profile 共享同一套书签。

## 功能特性

- **多 Profile 管理** — 每个 Profile 独立 user_data_dir、代理、指纹配置，支持拖拽排序
- **反指纹浏览器** — 屏幕分辨率、CPU/GPU、WebRTC、地理位置、UA、字体等全覆盖
- **代理 & 链式代理** — HTTP/SOCKS5 代理 + 中继代理（如 mihomo → 目标代理两跳链路）
- **资源拦截** — 屏蔽视频流（MP4/HLS/DASH）、限制图片大小，节省代理带宽
- **WebRTC 防泄露** — 自定义 IP / 掩码（10.0.0.1） / 完全禁用三种模式
- **GeoIP 自动推断** — 根据代理出口 IP 自动设置时区、语言、地理位置
- **共享书签** — 统一管理书签，启动时自动写入 Chromium 原生书签栏
- **标签筛选** — 自定义标签，多标签 AND 过滤
- **导入/导出** — Profile 配置 JSON 导入导出，支持跨机器迁移

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+

### 一键启动（Windows）

```bat
start.bat
```

流程：安装依赖 → 杀占用 8765 的进程 → 构建前端 → 后台启动服务 → 探活就绪后自动打开浏览器访问 `http://localhost:8765`

### 开发模式

```bash
# 安装依赖
pip install -r backend/requirements.txt
pip install "cloakbrowser[geoip]"   # 可选，启用 GeoIP 自动推断
cd frontend && npm install

# Terminal 1 — 后端（热重载）
uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload

# Terminal 2 — 前端（HMR）
cd frontend && npm run dev
# → http://localhost:5173，API 代理到 :8765
```

## 测试

```bash
# 单元 + 集成测试（~2s）
python -m pytest tests/ -v

# 全量测试，含真实 Chromium E2E（~55s）
CLOAKTOAST_E2E=1 python -m pytest tests/ -v
```

## 技术栈

| 层 | 技术 |
|---|------|
| Backend | Python · FastAPI · SQLAlchemy · SQLite · uvicorn |
| Frontend | Vite · React 18 · TypeScript · Ant Design 5 · react-router |
| 浏览器引擎 | cloakbrowser（Playwright Chromium） |
| 平台 | Windows（主要）；Linux / macOS 部分支持 |

## 项目结构

```
CloakToast/
├── backend/
│   ├── main.py                # FastAPI 应用入口
│   ├── database.py            # SQLite + SQLAlchemy + 自动迁移
│   ├── models.py              # ORM 模型
│   ├── schemas.py             # Pydantic 校验
│   ├── routers/
│   │   ├── profiles.py        # Profile CRUD / 排序 / 导入导出
│   │   ├── instances.py       # 浏览器实例启动 / 停止
│   │   ├── bookmarks.py       # 共享书签 CRUD
│   │   └── system.py          # 系统信息 / 更新 / License
│   └── services/
│       ├── browser.py         # 进程管理
│       ├── browser_worker.py  # 浏览器子进程
│       └── chain_proxy.py     # SOCKS5 链式代理
├── frontend/src/
│   ├── pages/
│   │   ├── Profiles/          # Profile 管理页（卡片网格 + 拖拽排序）
│   │   ├── Bookmarks/         # 共享书签表格
│   │   └── Settings/          # 设置页
│   ├── api/                   # API 客户端
│   └── components/            # 通用组件
├── tests/                     # 测试套件
├── data/                      # 运行时数据（gitignored）
└── start.bat                  # Windows 一键启动
```

## 进程架构

```
uvicorn (FastAPI :8765)
 └── browser.py: 进程管理 + watcher
      └── subprocess: browser_worker.py
           └── [可选] chain_proxy (relay → target)
                └── cloakbrowser → Chromium
```

浏览器实例作为独立子进程运行，主进程通过 watcher task 监控生命周期。链式代理支持 relay → target 两跳路径（如 mihomo → 目标代理 → Internet）。

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/profiles` | Profile 列表 / 创建 |
| PUT/DELETE | `/api/profiles/{id}` | 更新 / 删除 |
| POST | `/api/profiles/{id}/duplicate` | 克隆 |
| POST | `/api/profiles/reorder` | 批量排序 |
| GET/POST | `/api/profiles/export` `/import` | 导入导出 |
| POST | `/api/instances/launch` | 启动浏览器 |
| POST | `/api/instances/stop/{id}` | 停止浏览器 |
| GET/POST/PUT/DELETE | `/api/bookmarks` | 书签 CRUD |
| GET | `/api/system/info` | 版本 + License |

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
