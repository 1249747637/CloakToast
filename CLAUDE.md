# CloakToast — AI 协作文档

> **每次修改代码后必须更新本文件对应章节，以及 `.claude/projects/.../memory/` 下的记忆文件。**

---

## 项目概述

**CloakToast** 是一个多浏览器实例管理器，基于 `cloakbrowser`（封装 Playwright 的反指纹 Chromium）。用户可以创建多个带独立指纹/代理/流量策略的浏览器 Profile，按需启动/停止，并可以批量挂载 URL 任务让不同 Profile 依次打开指定网页。

**技术栈**
- Backend: Python + FastAPI + SQLAlchemy (SQLite) + uvicorn
- Frontend: Vite + React 18 + TypeScript + Ant Design 5 + react-router
- 浏览器进程: `cloakbrowser.launch_persistent_context` → 独立 subprocess (`browser_worker.py`)
- 运行平台: Windows (主要)；Linux/macOS 部分支持

---

## 目录结构

```
CloakToast/
├── backend/
│   ├── main.py              # FastAPI app + lifespan shutdown hook
│   ├── database.py          # SQLite, SQLAlchemy engine, get_db
│   ├── models.py            # Profile, URLTask, TaskProfile ORM 模型
│   ├── schemas.py           # Pydantic schemas (ProfileBase/Create/Update/Response…)
│   ├── config.py            # data/config.json 读写, license key
│   ├── routers/
│   │   ├── profiles.py      # GET/POST/PUT/DELETE /api/profiles[/{id}[/duplicate]]
│   │   ├── instances.py     # GET /api/instances, POST /launch, /stop/{id}, /recent_exits
│   │   ├── tasks.py         # URL 任务 CRUD + 进度追踪
│   │   └── system.py        # /info, /update (SSE), /license, /shutdown
│   └── services/
│       ├── browser.py       # 进程管理: launch_profile / stop_profile / watcher task
│       └── browser_worker.py # 独立子进程: launch_persistent_context + 资源拦截
├── frontend/
│   ├── src/
│   │   ├── main.tsx         # 入口, ConfigProvider (Toasted Amber 主题), AntdApp
│   │   ├── App.tsx          # 布局: Sider (logo+nav+icon) + Content (maxWidth 1440)
│   │   ├── types.ts         # Profile, URLTask, URLTaskDetail, RunningInstance, SystemInfo
│   │   ├── api/             # apiFetch wrapper + profiles/instances/tasks/system 模块
│   │   ├── components/
│   │   │   └── StatusBadge.tsx  # 绿 Tag "运行 12m" / 灰 Tag "已停止"
│   │   └── pages/
│   │       ├── Profiles/    # ProfileCard (自渲染 footer, 左色条) + ProfileForm + index
│   │       ├── Tasks/       # 任务列表 + TaskDetail (进度表格)
│   │       └── Settings/    # License key + cloakbrowser 更新日志 (SSE)
│   └── vite.config.ts       # dev proxy /api → 8765
├── tests/
│   ├── conftest.py          # SQLite 内存 DB + TestClient fixture
│   ├── test_profiles.py
│   ├── test_instances.py    # mock + 真实进程逻辑测试 (13 项)
│   ├── test_tasks.py
│   ├── test_system.py
│   └── test_worker_e2e.py   # 真实 Chromium E2E (需 CLOAKTOAST_E2E=1)
├── data/                    # 运行时数据 (gitignored)
│   ├── cloaktoast.db
│   ├── config.json          # {"license_key": "..."}
│   └── profiles/<id>/       # 每个 profile 的 user_data_dir
│       ├── _cloaktoast_subprocess.log
│       └── _cloaktoast_worker.log
├── start.bat / start.sh     # 一键启动 (pip install + build frontend + run)
├── CLAUDE.md                # ← 本文件
└── .claude/projects/.../memory/  # AI 记忆文件
```

---

## 快速启动

```bash
# 生产模式 (Windows)
start.bat

# 开发模式
# Terminal 1 — backend (热重载)
uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload

# Terminal 2 — frontend (HMR)
cd frontend && npm run dev   # → http://localhost:5173, API 代理到 :8765

# 测试
python -m pytest tests/ -v                        # 单元+集成 (快, ~2s)
CLOAKTOAST_E2E=1 python -m pytest tests/ -v      # 全量含真实 Chromium (~55s)
```

---

## 核心数据模型

### Profile (`backend/models.py`, `backend/schemas.py`)

| 字段 | 类型 | 说明 |
|------|------|------|
| id | String (UUID) | 主键 |
| name | String | 显示名称 |
| color_tag | String | 十六进制色值，用于卡片左侧色条 |
| proxy_type | String | `none` / `http` / `socks5` |
| proxy_host/port/user/pass | String/Int | 代理凭证 |
| timezone / locale | String | IANA 时区 / BCP47 语言 |
| headless | Boolean | 无头模式 |
| humanize | Boolean | 拟人鼠标/键盘行为 |
| human_preset | String | `default` / `careful` |
| fingerprint_seed | Integer? | 指纹种子；0 是合法值，`None`=每次随机 |
| fp_* | 多字段 | 指纹覆盖 (屏幕/CPU/GPU/WebRTC/地理位置等) |
| extension_paths | JSONList | Chrome 扩展目录 |
| user_data_dir | String | 空 = 自动 `data/profiles/<id>` |
| extra_args | JSONList | 额外 Chromium 启动参数 |
| **block_video** | Boolean | 拦截视频/HLS/DASH 流量，省代理流量 |
| **block_image_max_kb** | Integer? | `None`=不限 / `0`=全屏蔽 / `N`=超 N KB abort |
| created_at / updated_at | DateTime | 自动管理 |

### URLTask / TaskProfile

- `URLTask`: 一组 URL（name + urls[] + notes）
- `TaskProfile`: 多对多关联，记录每个 Profile 对此任务的进度 (`pending`/`done`/`skipped`)

---

## 进程架构

```
uvicorn (FastAPI)
 └── browser.py: running_instances dict (in-memory)
      └── asyncio.create_subprocess_exec(python browser_worker.py <base64_payload>)
           ↓ stdout/stderr → data/profiles/<id>/_cloaktoast_subprocess.log
           └── cloakbrowser.launch_persistent_context()
                └── playwright node driver → Chromium
```

**关键设计决策：**

1. **`wait_for_event("close", timeout=0)`** — 必须 `timeout=0`，否则 Playwright 默认 30s 超时会强杀浏览器。`timeout=0` 对应 Playwright 源码 `reject_on_timeout: if timeout == 0: return`（永不超时）。

2. **close listener 必须在 goto loop 之前订阅** — pyee 不重放历史事件，若 goto 期间用户关浏览器，close 已触发，`wait_for_event` 后注册永远挂死。因此用 `threading.Event` + `context.on("close", ...)` 在 goto 之前订阅，goto 内用 `closed_event.is_set()` 提前退出。

3. **per-profile asyncio.Lock** — 防 TOCTOU：并发两个 launch 请求同一 profile 会撞 Chromium SingletonLock。锁在 `launch_profile` 和 `stop_profile` 内持有。

4. **watcher task** — `asyncio.create_task(_watch(...))` 在 launch 后挂起，一旦 worker 退出立即从 `running_instances` 移走并写 `recent_exits`，避免状态延迟（前端 5s 轮询无需等到下次才感知到浏览器关闭）。

5. **startup probe** — `launch_profile` 在 spawn 后等待 `STARTUP_PROBE_SECONDS=1.5`；若 worker 在此窗口内退出（配置错误/许可失败/参数无效），立刻抛 `ValueError` 给前端，显示错误而非"启动成功"。

6. **资源拦截** — `install_resource_blocker(context, block_video, block_image_max_kb)` 在 goto 之前调用，通过 Playwright `context.route("**/*", handler)` 实现。`block_video=False` 且 `block_image_max_kb=None` 时不安装 handler，零开销。

---

## API 路由速查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/profiles` | 列表（含运行状态） |
| POST | `/api/profiles` | 创建 |
| GET | `/api/profiles/{id}` | 单条 |
| PUT | `/api/profiles/{id}` | 更新全字段 |
| DELETE | `/api/profiles/{id}` | 删除（运行中时 400） |
| POST | `/api/profiles/{id}/duplicate` | 克隆（加" 副本"后缀） |
| GET | `/api/instances` | 运行中的进程列表 |
| GET | `/api/instances/recent_exits` | 最近退出记录（含 returncode） |
| POST | `/api/instances/launch` | 启动 `{profile_id, task_id?}` |
| POST | `/api/instances/stop/{id}` | 停止 |
| GET | `/api/tasks` | 任务列表 |
| GET | `/api/tasks/{id}` | 任务详情（含 Profile 进度） |
| POST | `/api/tasks` | 创建任务 |
| PUT | `/api/tasks/{id}` | 更新任务 |
| DELETE | `/api/tasks/{id}` | 删除任务 |
| POST | `/api/tasks/{id}/profiles` | 关联 profiles `{profile_ids[]}` |
| DELETE | `/api/tasks/{id}/profiles/{pid}` | 移出 profile |
| PATCH | `/api/tasks/{id}/profiles/{pid}/status` | 更新进度 `{status, notes}` |
| GET | `/api/system/info` | 版本 + license |
| PUT | `/api/system/license` | 保存 license key |
| POST | `/api/system/update` | 更新 cloakbrowser（SSE 流） |
| POST | `/api/system/shutdown` | 关闭 backend |

---

## 前端页面结构

```
/ → Profiles/index.tsx
    ├── ProfileCard.tsx       每张卡片
    │   ├── 左 4px 色条 (color_tag)
    │   ├── Header: 名称 + StatusBadge Tag
    │   ├── Body: 代理/Locale·TZ/省流 tag/辅助 tag (grid)
    │   └── Footer: 主按钮(启动/停止) + 圆形 icon 次按钮(编辑/复制/删除)
    └── ProfileForm.tsx       Drawer 600px, Tabs(常用/指纹/高级)
        ├── 常用: 名称/颜色/备注/代理/时区语言/省流(block_video+block_image_max_kb)/无头/Humanize
        ├── 指纹: seed/噪声/平台/屏幕/CPU/GPU/WebRTC/位置/字体...
        └── 高级: UA/Brand/扩展路径/UDD/CDP/extra_args

/tasks → Tasks/index.tsx
/tasks/:id → Tasks/TaskDetail.tsx

/settings → Settings/index.tsx
```

**主题**: Toasted Amber (`#D97706`) + Dark Roast sider (`#1F1A17`) + 暖羊皮纸背景 (`#FAF7F2`)，在 `frontend/src/main.tsx` 的 `ctTheme` ConfigProvider 中定义。

---

## 测试策略

| 层级 | 文件 | 说明 |
|------|------|------|
| 单元 | `test_instances.py` | mock subprocess，覆盖 launch/stop/watcher/TOCTOU/资源拦截逻辑 |
| 集成 | `test_profiles.py` / `test_tasks.py` / `test_system.py` | 真实 SQLite in-memory DB + TestClient |
| E2E | `test_worker_e2e.py` | 真实 Chromium，需 `CLOAKTOAST_E2E=1`，~50s |

E2E 测试覆盖：
- 30s 存活回归（验证 `timeout=0` 修复）
- close-during-goto 不挂死（验证 close listener 前置）
- lifespan shutdown 不留 orphan
- block_video 真实 abort `.mp4` 请求
- 完整 API launch → 存活 5s → stop

---

## 已知限制 / 待做

- **argv 32KB 限制** (Windows): profile payload 通过 base64 argv 传给 worker，极端情况（超长 notes + 大量 URLs + 多扩展路径）可能超出 CreateProcessW 32767 字符限制。长期应改为 stdin 传输。
- **secrets 暴露在 argv**: license_key / proxy_pass 在 base64 payload 里，系统上同用户进程可读。临时缓解：license_key 同时走 env var；长期应改 stdin。
- **running_instances 跨重启丢失**: backend 重启后 in-memory dict 清空，但 Chromium 仍在运行，持有 SingletonLock，导致重启后无法再次 launch 同一 profile（需手动关闭浏览器或删除 SingletonLock 文件）。长期应持久化 `{profile_id: pid}` 到 SQLite 并在 startup 用 psutil 检测。
- **前端无搜索/过滤**: Profile 管理页无搜索、无运行状态过滤。
- **前端 chunk 体积**: vite build 输出单 chunk 1.2MB（gzip 377KB），超出 500KB 警告，应做代码分割。

---

## 开发注意事项

1. **新增 Profile 字段**: 需同步修改 `models.py`、`schemas.py`、`types.ts`、`ProfileForm.tsx`（表单默认值）、`ProfileCard.tsx`（卡片展示按需）、`browser_worker.py`（若影响 worker 行为）。

2. **fingerprint_seed = 0 合法**: 用 `is not None` 判断，不能用 truthiness。其他整数指纹字段 0 无意义可用 truthiness。

3. **资源拦截 handler 异常必须 catch**: handler 内任何 exception 都要 `try/except` + `route.continue_()`，否则浏览器请求卡死。

4. **stop_profile 先标记 state="stopping"**: 在 pop 前标记，让 `is_running()` 把 stopping 视为占用，防止 stop 期间并发 launch 撞 SingletonLock。

5. **antd ConfigProvider 主题**: 组件内用 `theme.useToken()` 取颜色/间距 token，**不要硬编码** hex 颜色（包括 `color: 'red'`），保留暗色模式扩展能力。

6. **ProfileCard 不用 `actions` prop**: antd Card.actions 等宽列 + text-danger hover 会贴卡片圆角，用自渲染 footer `<div>` 替代。
