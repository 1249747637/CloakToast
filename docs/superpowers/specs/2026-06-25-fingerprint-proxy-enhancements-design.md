# CloakToast 指纹与代理增强设计文档

**日期**: 2026-06-25  
**范围**: 5 项功能增强，全部在现有架构内扩展，无破坏性变更

---

## 1. 屏幕分辨率预设下拉

### 现状
`fp_screen_width` / `fp_screen_height` 均为 `InputNumber`，留空时取真实显示器分辨率（直接暴露本机）。

### 设计

**前端 (ProfileForm.tsx — 指纹 Tab)**

将屏幕宽度/高度从 `InputNumber` 改为 antd `Select`（`showSearch`、`allowClear`），选项来自常见值列表，**同时允许用户直接输入自定义数字**（`mode` 不填，`filterOption` 自定义）。

上方加一排"分辨率快速预设"按钮（`Button.Group`），点击自动填充宽高两个字段：

```
[1920×1080]  [2560×1440]  [1366×768]  [1440×900]  [1280×800]
```

宽度可选值：`1280 / 1366 / 1440 / 1600 / 1920 / 2560 / 3840`  
高度可选值：`768 / 800 / 900 / 1024 / 1080 / 1200 / 1440 / 2160`  
任务栏高度可选值：`0 / 40 / 48 / 56 / 80`（Windows 默认 40px）

**提示文案**：`placeholder="留空=使用真实显示器分辨率"`（修正原来误导性的"随机"说法）

**后端 / worker**：无需改动，字段类型不变（Integer nullable）。

---

## 2. 浏览器品牌 / 版本 / 系统版本 联动下拉

### 现状
三个字段均为 `Input` 文本框，容易填出不一致的组合。

### 设计

**前端 (ProfileForm.tsx — 高级 Tab)**

**`fp_brand`** → `Select`，选项：

| 值 | 标签 |
|---|---|
| `Google Chrome` | Google Chrome |
| `Microsoft Edge` | Microsoft Edge |
| `Brave` | Brave |
| `Opera` | Opera |
| `Vivaldi` | Vivaldi |

**`fp_brand_version`** → `Select`，根据 `fp_brand` 动态筛选：

```typescript
const BRAND_VERSIONS: Record<string, string[]> = {
  "Google Chrome": ["138", "137", "136", "135", "134", "133"],
  "Microsoft Edge": ["138", "137", "136", "135", "134", "133"],
  "Brave":          ["1.77", "1.76", "1.75", "1.74", "1.73"],
  "Opera":          ["118", "117", "116", "115"],
  "Vivaldi":        ["7.3", "7.2", "7.1", "7.0"],
};
```

选品牌后版本列表随即更新；版本列表变动时清空已选版本（若原值不在新列表中）。

**`fp_platform_version`** → `Select`，根据 `fp_platform` 动态筛选：

```typescript
const PLATFORM_VERSIONS: Record<string, string[]> = {
  windows: ["10.0.0", "11.0.0"],
  macos:   ["15.0", "14.0", "13.0", "12.0"],
};
```

留空 = 跟随种子（任意字段均可清空回到自动模式）。

**后端 / worker**：无需改动，三个字段仍为 String。

---

## 3. WebRTC 模式升级

### 现状
`fp_webrtc_ip`（String）：填 IP 则传 `--fingerprint-webrtc-ip=<ip>`，否则 cloakbrowser 默认行为（不保证不泄露）。

### 设计

**新增字段 `fp_webrtc_mode`**（String，默认 `""`）：

| 值 | 含义 | 实现 |
|---|---|---|
| `""` | 默认 — 不干预 | 不传 webrtc flag |
| `"custom"` | 自定义 IP | 传 `--fingerprint-webrtc-ip=<fp_webrtc_ip>` |
| `"mask"` | 掩盖 — WebRTC 可用，但 IP 覆盖为私有地址 | 传 `--fingerprint-webrtc-ip=10.0.0.1` |
| `"block"` | 禁止 — 完全禁用 RTCPeerConnection | `context.add_init_script(BLOCK_WEBRTC_JS)` |

`BLOCK_WEBRTC_JS`（注入 JS）：
```javascript
Object.defineProperty(window, 'RTCPeerConnection', {get: () => undefined, configurable: false});
Object.defineProperty(window, 'webkitRTCPeerConnection', {get: () => undefined, configurable: false});
```

`fp_webrtc_ip` 字段仅在 `mode == "custom"` 时显示（原字段继续复用）。

**数据库**：新增 `fp_webrtc_mode` String 列，默认 `""`（原有 `fp_webrtc_ip` 保留，迁移兼容：原来填了 IP 的 profile 默认 mode 视为 `"custom"`）。

**backend/models.py**：新增 `fp_webrtc_mode = Column(String, default="")`  
**backend/schemas.py**：新增 `fp_webrtc_mode: str = ""`  
**backend/services/browser_worker.py**：`build_fingerprint_args` 中替换原 webrtc 逻辑：

```python
mode = profile.get("fp_webrtc_mode", "")
if mode == "custom" and profile.get("fp_webrtc_ip"):
    args.append(f"--fingerprint-webrtc-ip={profile['fp_webrtc_ip']}")
elif mode == "mask":
    args.append("--fingerprint-webrtc-ip=10.0.0.1")
# "block" 模式在 install_webrtc_block() 中通过 add_init_script 注入
```

`main()` 中在 `install_resource_blocker` 后添加：
```python
if profile.get("fp_webrtc_mode") == "block":
    context.add_init_script(BLOCK_WEBRTC_JS)
```

---

## 4. GeoIP — 时区 / 语言 / 位置跟随代理 IP

### 现状
cloakbrowser 原生支持 `geoip=True`，但 CloakToast 未暴露此参数。

### 设计

**新增字段 `geoip`**（Boolean，默认 False）。

**依赖**：`pip install "cloakbrowser[geoip]"`（含 `geoip2` + `httpx`）。  
在 `start.bat` / `start.sh` 中加入此安装命令（可选依赖，如安装失败不阻断启动）。

**worker 修改**：
```python
context = launch_persistent_context(
    ...
    geoip=bool(profile.get("geoip")),
    ...
)
```

cloakbrowser 在 `geoip=True` 时自动：
1. 通过代理解析出口 IP（使用 httpx 经代理访问 IP echo 服务）
2. 查 GeoLite2 DB → 时区 + locale + 经纬度
3. 自动注入 `--fingerprint-timezone` / `--lang` / `--fingerprint-location` / `--fingerprint-webrtc-ip`
4. 用户手动填的字段优先级更高（显式覆盖）

**前端逻辑**：
- 仅当 `proxy_type != "none"` 时显示 GeoIP 开关（无代理时置灰并提示"需配置代理"）
- 开启时：时区、语言、经纬度字段显示为灰色 + 提示"由 GeoIP 自动填充，可手动覆盖"
- 链式代理开启时：GeoIP 开关强制灰色 + tooltip "链式代理模式下请手动设置"

**迁移**：新增布尔列，现有记录默认 False，无感知升级。

---

## 5. 链式代理（Proxy Chaining）

### 需求背景
用户所在地区无法直连 cliproxy，需先通过本地 mihomo 出去再访问 cliproxy。

目标链路：`Chromium → 本地链式代理 → mihomo → 订阅节点 → cliproxy → 目标网站`

### 设计

#### 5.1 新增字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `relay_proxy_type` | String | `"none"` / `"http"` / `"socks5"`，默认 `"none"` |
| `relay_proxy_host` | String | 中继 host，如 `127.0.0.1` |
| `relay_proxy_port` | Integer nullable | 中继端口，如 `7897` |
| `relay_proxy_user` | String | 可选认证 |
| `relay_proxy_pass` | String | 可选认证 |

#### 5.2 本地链式代理服务（chain_proxy.py）

新建 `backend/services/chain_proxy.py`，实现一个纯 Python asyncio SOCKS5 代理服务：

**启动**：`start_chain_proxy(relay, target) -> int`（返回本机监听端口）  
**停止**：`stop_chain_proxy(port)`（关闭 asyncio server，worker 退出时调用）

**协议流程（每条连接）**：

```
1. 接受来自 Chromium 的 SOCKS5 握手（无认证）
2. 读取 SOCKS5 CONNECT 请求 → 得到 (dest_host, dest_port)
   - 此处 dest = cliproxy_host:cliproxy_port
   Wait: Chromium 不会直接 CONNECT 到 cliproxy，它会 CONNECT 到目标网站
   
实际流程:
1. 接受 Chromium SOCKS5 握手
2. 读取 CONNECT 目标 (target_host, target_port) = 网站地址
3. 打开到 relay (mihomo) 的 SOCKS5 连接
4. 通过 relay，CONNECT 到 cliproxy_host:cliproxy_port
5. 完成与 cliproxy 的认证握手 (SOCKS5 user/pass auth)
6. 通过 cliproxy，CONNECT 到 target_host:target_port
7. 双向 pipe Chromium ↔ cliproxy（通过 relay）
```

**注意**：Chromium 配置的代理是本地链式代理端口。Chromium 会直接向"代理"发 SOCKS5 CONNECT(target_host:port)，链式代理内部再处理多跳路由。

**实现要点**：
- 无第三方依赖，纯 asyncio + struct（SOCKS5 握手约 100 行）
- 链式代理在 browser_worker.py 启动时以后台线程 + asyncio.run 运行
- 监听 `127.0.0.1:<随机空闲端口>`（`socket.bind((host, 0))`）
- worker 进程退出时 asyncio server 随线程一起销毁，无残留

#### 5.3 browser_worker.py 集成

```python
chain_port = None
if profile.get("relay_proxy_type", "none") != "none" and profile.get("relay_proxy_host"):
    chain_port = start_chain_proxy(
        relay=build_relay_proxy(profile),   # relay_proxy_* 字段
        target=build_proxy(profile),        # 原 proxy_* 字段（cliproxy）
    )

proxy_for_browser = f"socks5://127.0.0.1:{chain_port}" if chain_port else build_proxy(profile)

context = launch_persistent_context(
    proxy=proxy_for_browser,
    geoip=False if chain_port else bool(profile.get("geoip")),  # 链式代理时禁用 geoip
    ...
)
```

#### 5.4 前端 UI

在"代理设置"Divider 下，现有代理字段之后，加"中继代理（可选）"折叠面板（`antd Collapse`）：

- 仅当主代理类型 ≠ `none` 时显示折叠面板
- 展开后显示：中继类型（Select） + Host + Port + 用户名 + 密码
- 当中继代理开启时，GeoIP 开关变灰 + tooltip 提示

#### 5.5 约束与限制

- **协议支持**：relay 支持 HTTP / SOCKS5；target（cliproxy）支持 HTTP CONNECT / SOCKS5（两种最终握手路径在 chain_proxy.py 中均实现）
- **GeoIP 互斥**：链式代理开启时 GeoIP 不可用（本地链式代理 URL 无法探测真实出口 IP）
- **argv 大小**：链式代理不增加额外 payload 体积，relay 字段与 proxy 字段并列传入 worker

---

## 受影响文件清单

| 文件 | 变更类型 |
|---|---|
| `backend/models.py` | 新增列：`fp_webrtc_mode`, `geoip`, `relay_proxy_*`（5字段） |
| `backend/schemas.py` | 同步新增字段 |
| `backend/services/browser_worker.py` | WebRTC 逻辑替换，geoip 参数传入，chain_proxy 集成 |
| `backend/services/chain_proxy.py` | **新建**：asyncio SOCKS5 链式代理服务 |
| `frontend/src/types.ts` | 新增字段类型 |
| `frontend/src/pages/Profiles/ProfileForm.tsx` | 屏幕下拉、品牌联动、WebRTC 模式、GeoIP 开关、中继代理折叠面板 |
| `start.bat` / `start.sh` | 加 `pip install "cloakbrowser[geoip]"` |
| `tests/test_instances.py` | 补充 WebRTC block / chain_proxy 单元测试 |
| `CLAUDE.md` | 更新字段文档 |
