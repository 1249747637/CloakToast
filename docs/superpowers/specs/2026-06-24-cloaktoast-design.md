# CloakToast — 设计文档

**日期：** 2026-06-24  
**项目：** CloakToast — 基于 CloakBrowser 的指纹浏览器实例管理 WebUI  
**状态：** 已审批，待实现

---

## 1. 项目概述

CloakToast 是一个本地 Web 管理平台，用于管理 CloakBrowser 指纹浏览器实例。核心功能：

- 创建和管理浏览器 Profile（每个 Profile 对应独立指纹 + 持久化登录状态）
- 创建 URL 任务，将任务分配给多个 Profile，追踪完成进度
- 启动/停止浏览器实例（浏览器在系统桌面运行，WebUI 管理生命周期）
- 检查和更新 CloakBrowser 版本

**目标规模：** 本地单机，保存数十个 Profile，同时运行 5 个以内实例。  
**访问方式：** 无登录认证，本地直接访问 `http://localhost:8765`。

---

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+ · FastAPI · SQLAlchemy · SQLite |
| 前端 | React 18 · TypeScript · Ant Design 5 · Vite |
| 进程管理 | Python `subprocess`（异步） |
| 数据存储 | SQLite（`data/cloaktoast.db`）|
| 部署 | 单进程，FastAPI serve 前端静态文件 |

---

## 3. 目录结构

```
CloakToast/
├── backend/
│   ├── main.py                 # FastAPI 入口 + 静态文件 serve
│   ├── database.py             # SQLAlchemy engine + session
│   ├── models.py               # ORM 模型
│   ├── schemas.py              # Pydantic 请求/响应模型
│   ├── routers/
│   │   ├── profiles.py         # Profile CRUD
│   │   ├── instances.py        # 实例启动/停止/状态
│   │   ├── tasks.py            # URL 任务 CRUD + 进度管理
│   │   └── system.py           # CloakBrowser 版本/更新
│   ├── services/
│   │   └── browser.py          # CloakBrowser 进程管理
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Profiles/       # Profile 列表 + 编辑
│   │   │   ├── Tasks/          # URL 任务列表 + 详情
│   │   │   └── Settings/       # 系统设置
│   │   ├── components/         # 公共组件
│   │   ├── api/                # API fetch 封装
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── data/
│   ├── cloaktoast.db           # SQLite 数据库
│   └── profiles/               # 每个 Profile 的 user_data_dir
│       └── {profile_id}/       # Chromium 用户数据（持久化登录）
├── start.bat                   # Windows 一键启动
└── start.sh                    # Linux/macOS 一键启动
```

---

## 4. 数据模型

### Profile

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键，同时作为 user_data_dir 文件夹名 |
| name | str | 显示名称 |
| color_tag | str | 颜色标签（十六进制色值） |
| notes | str | 备注 |
| **── 代理 ──** | | |
| proxy_type | enum | http / socks5 / none |
| proxy_host | str | 代理主机 |
| proxy_port | int | 代理端口 |
| proxy_user | str | 代理用户名（可空） |
| proxy_pass | str | 代理密码（可空） |
| **── 常用 ──** | | |
| timezone | str | 时区（空=传 None，CloakBrowser 通过 GeoIP 自动匹配代理出口） |
| locale | str | 语言（如 zh-CN） |
| headless | bool | 无头模式（默认 False） |
| humanize | bool | 人性化模式（默认 True） |
| human_preset | str | humanize 预设：default / careful（空=default） |
| **── 指纹 ──** | | |
| fingerprint_seed | int | 指纹种子，控制全局随机身份（空=每次随机） |
| fp_noise_enabled | bool | 噪声注入开关，对应 `--fingerprint-noise=false`（默认 True） |
| fp_platform | enum | 平台伪装：windows / macos / 空=跟随种子 |
| fp_hardware_concurrency | int | CPU 核心数（空=跟随种子） |
| fp_device_memory | int | 设备内存 GB（空=跟随种子） |
| fp_screen_width | int | 屏幕宽度（空=跟随种子，默认区间 1280-1920） |
| fp_screen_height | int | 屏幕高度（空=跟随种子） |
| fp_taskbar_height | int | 任务栏高度（空=跟随种子） |
| fp_gpu_vendor | str | WebGL 厂商字符串（空=跟随种子） |
| fp_gpu_renderer | str | WebGL 渲染器字符串（空=跟随种子） |
| fp_webrtc_ip | str | WebRTC ICE 候选 IP（空=不覆盖） |
| fp_location_lat | float | 地理位置纬度（空=不覆盖） |
| fp_location_lng | float | 地理位置经度（空=不覆盖） |
| fp_storage_quota | int | 存储配额 MB（空=跟随种子） |
| fp_fonts_dir | str | 自定义字体目录路径（空=不覆盖） |
| **── 高级 ──** | | |
| user_agent | str | User-Agent（空=自动） |
| fp_brand | str | 浏览器品牌字符串（空=自动） |
| fp_brand_version | str | 品牌版本号（空=自动） |
| fp_platform_version | str | 操作系统版本字符串（空=自动） |
| extension_paths | JSON | 扩展路径列表 |
| user_data_dir | str | 自定义 user_data_dir（空=自动用 id） |
| cdp_port | int | CDP 端口（空=自动分配） |
| extra_args | JSON | 额外启动参数列表 |
| created_at | datetime | |
| updated_at | datetime | |

### URLTask

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | str | 任务名称 |
| urls | JSON | URL 列表（字符串数组） |
| notes | str | 备注 |
| created_at | datetime | |

### TaskProfile（M2M 进度表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| task_id | FK → URLTask | |
| profile_id | FK → Profile | |
| status | enum | pending / done / skipped |
| notes | str | 单条备注 |
| updated_at | datetime | |

### 运行实例（内存，不持久化）

```python
# browser.py 中维护的全局字典
running_instances: dict[str, {
    "process": subprocess.Popen,
    "started_at": datetime,
    "task_id": str | None,
}]  # key = profile_id
```

---

## 5. API 设计

### Profiles
```
GET    /api/profiles              # 列表（含运行状态）
POST   /api/profiles              # 新建
GET    /api/profiles/{id}         # 详情
PUT    /api/profiles/{id}         # 更新
DELETE /api/profiles/{id}         # 删除（需先停止实例）
POST   /api/profiles/{id}/duplicate  # 复制
```

### Instances
```
POST   /api/instances/launch      # 启动 {profile_id, task_id?}
POST   /api/instances/stop/{profile_id}  # 停止
GET    /api/instances             # 所有运行中实例状态
```

### Tasks
```
GET    /api/tasks                 # 列表
POST   /api/tasks                 # 新建
GET    /api/tasks/{id}            # 详情（含 Profile 进度）
PUT    /api/tasks/{id}            # 更新
DELETE /api/tasks/{id}            # 删除
POST   /api/tasks/{id}/profiles   # 添加 Profile 到任务
DELETE /api/tasks/{id}/profiles/{profile_id}  # 从任务移除
PATCH  /api/tasks/{id}/profiles/{profile_id}/status  # 更新进度状态
```

### System
```
GET    /api/system/info           # CloakBrowser 当前版本
POST   /api/system/update         # 执行更新（streaming 响应）
PUT    /api/system/license        # 保存 License Key
```

---

## 6. 页面设计

### 导航结构
左侧固定侧边栏：
- **Profile 管理**（默认页）
- **URL 任务**
- **系统设置**

### Profile 管理页

**列表视图：**
- 卡片或表格展示所有 Profile
- 每个 Profile 显示：名称（带颜色标签）、代理地址、运行状态徽标（绿色「运行中」+ 时长 / 灰色「已停止」）
- 操作：启动（运行中则变为「停止」按钮）、编辑、复制、删除
- 右上角「新建 Profile」按钮

**新建/编辑页（抽屉或独立页，三个 Tab）：**

Tab 一「常用」：
- 名称、颜色标签、备注
- 代理类型（HTTP/SOCKS5/不使用）、Host、Port、用户名、密码
- 时区（下拉选择，留空=跟随代理 GeoIP）、语言/Locale
- Headless 开关、Humanize 开关、Humanize 预设（default/careful）

Tab 二「指纹」：
- 指纹 Seed（留空=每次随机，填写后生成一致身份）
- 噪声注入开关（默认开启）
- 平台：Windows / macOS / 跟随种子
- CPU 核心数（留空=跟随种子）
- 设备内存 GB（留空=跟随种子）
- 屏幕分辨率 宽 × 高（留空=跟随种子）
- 任务栏高度（留空=跟随种子）
- WebGL 厂商（留空=跟随种子）
- WebGL 渲染器（留空=跟随种子）
- WebRTC IP（留空=不覆盖）
- 地理位置 纬度 / 经度（留空=不覆盖）
- 存储配额 MB（留空=跟随种子）
- 字体目录路径（留空=不覆盖）

Tab 三「高级」：
- User Agent（留空=自动）
- 浏览器品牌 / 品牌版本 / 系统版本字符串（留空=自动）
- 扩展路径列表（动态添加/删除）
- User Data Dir（留空=自动管理）
- CDP 端口（留空=自动分配）
- 额外启动参数（多行文本，每行一条）

### URL 任务页

**列表视图：**
- 表格：任务名、URL 数量、Profile 总数、完成进度（`3 / 10`）、创建时间
- 操作：查看详情、删除
- 右上角「新建任务」按钮

**任务详情页：**
- 顶部：任务名（可编辑）、URL 列表（多行文本编辑）、备注
- 下方 Profile 进度表格：
  - 列：Profile 名称、颜色标签、代理、状态（待完成/已完成/已跳过）、操作
  - 操作：「启动」（带任务 URL 拉起）、「标记完成」、「标记跳过」、「移出任务」
  - 运行中的 Profile 高亮显示，启动按钮变为「停止」
- 底部：「添加 Profile」按钮 → 弹出多选对话框（从现有 Profile 中选）

### 系统设置页
- 当前 CloakBrowser 版本号
- 「检查更新」按钮 → 显示最新版本对比
- 「执行更新」按钮 → 实时显示更新日志（通过 Server-Sent Events 流式推送到前端）
- License Key 输入框 + 保存按钮（保存到 `data/config.json`，后端启动子进程时作为 `CLOAKBROWSER_LICENSE_KEY` 环境变量注入）

---

## 7. CloakBrowser 集成

### 启动逻辑（`services/browser.py`）

```python
async def launch_profile(profile: Profile, task_id: str | None, urls: list[str]):
    # 1. 防止重复启动
    if profile.id in running_instances:
        raise AlreadyRunningError()

    # 2. 确定 user_data_dir
    udd = profile.user_data_dir or f"./data/profiles/{profile.id}"

    # 3. 生成启动脚本（临时文件）
    script = generate_launch_script(profile, udd, urls)

    # 4. subprocess 启动
    process = await asyncio.create_subprocess_exec("python", script_path)

    # 5. 记录到内存
    running_instances[profile.id] = {
        "process": process,
        "started_at": datetime.utcnow(),
        "task_id": task_id,
    }
```

### 指纹参数到启动标志的转换

`browser.py` 中的 `build_fingerprint_args(profile)` 函数将 Profile 指纹字段转换为 `--fingerprint-*` 标志列表：

```python
def build_fingerprint_args(profile) -> list[str]:
    args = []
    if profile.fingerprint_seed:
        args.append(f"--fingerprint={profile.fingerprint_seed}")
    if not profile.fp_noise_enabled:
        args.append("--fingerprint-noise=false")
    if profile.fp_platform:
        args.append(f"--fingerprint-platform={profile.fp_platform}")
    if profile.fp_hardware_concurrency:
        args.append(f"--fingerprint-hardware-concurrency={profile.fp_hardware_concurrency}")
    if profile.fp_device_memory:
        args.append(f"--fingerprint-device-memory={profile.fp_device_memory}")
    if profile.fp_screen_width:
        args.append(f"--fingerprint-screen-width={profile.fp_screen_width}")
    if profile.fp_screen_height:
        args.append(f"--fingerprint-screen-height={profile.fp_screen_height}")
    if profile.fp_taskbar_height:
        args.append(f"--fingerprint-taskbar-height={profile.fp_taskbar_height}")
    if profile.fp_gpu_vendor:
        args.append(f"--fingerprint-gpu-vendor={profile.fp_gpu_vendor}")
    if profile.fp_gpu_renderer:
        args.append(f"--fingerprint-gpu-renderer={profile.fp_gpu_renderer}")
    if profile.fp_webrtc_ip:
        args.append(f"--fingerprint-webrtc-ip={profile.fp_webrtc_ip}")
    if profile.fp_location_lat and profile.fp_location_lng:
        args.append(f"--fingerprint-location={profile.fp_location_lat},{profile.fp_location_lng}")
    if profile.fp_storage_quota:
        args.append(f"--fingerprint-storage-quota={profile.fp_storage_quota}")
    if profile.fp_fonts_dir:
        args.append(f"--fingerprint-fonts-dir={profile.fp_fonts_dir}")
    if profile.fp_brand:
        args.append(f"--fingerprint-brand={profile.fp_brand}")
    if profile.fp_brand_version:
        args.append(f"--fingerprint-brand-version={profile.fp_brand_version}")
    if profile.fp_platform_version:
        args.append(f"--fingerprint-platform-version={profile.fp_platform_version}")
    return args + (profile.extra_args or [])
```

### 启动脚本模板

```python
from cloakbrowser import launch_persistent_context

context = launch_persistent_context(
    user_data_dir="{udd}",
    proxy={proxy_config},
    timezone="{timezone}",      # None 时 CloakBrowser 自动 GeoIP
    locale="{locale}",
    humanize={humanize},
    human_preset="{human_preset}",
    headless={headless},
    user_agent="{user_agent}",  # None 时自动
    args={fingerprint_args},    # build_fingerprint_args() 的结果
)

pages = []
for url in {urls}:
    page = context.new_page()
    page.goto(url)
    pages.append(page)

context.wait_for_close()
```

### 状态同步

- `GET /api/instances` 遍历 `running_instances`，检查 `process.returncode` 是否为 None（仍在运行）
- 已退出的进程自动从字典移除
- 前端轮询间隔：5 秒

---

## 8. 启动方式

```bash
# 安装依赖（首次）
cd backend && pip install -r requirements.txt
cd frontend && npm install && npm run build

# 启动
python backend/main.py
# 访问 http://localhost:8765
```

`start.bat` / `start.sh` 封装以上命令，并在前端未构建时自动触发构建。
