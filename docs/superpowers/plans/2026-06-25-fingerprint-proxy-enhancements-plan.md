# 实现计划：指纹与代理增强（5 项功能）

设计文档：`docs/superpowers/specs/2026-06-25-fingerprint-proxy-enhancements-design.md`

---

## 执行顺序说明

- **步骤 1–3**：后端数据层，必须先做，前端依赖它
- **步骤 4**：chain_proxy 新模块，独立于其他后端改动
- **步骤 5**：browser_worker 集成，依赖步骤 3 + 4
- **步骤 6–8**：前端，依赖步骤 1–3 完成后的 API
- **步骤 9**：测试补充
- **步骤 10**：start 脚本 + CLAUDE.md 更新

---

## 步骤 1 — 数据库模型 & Schemas 新增字段

**文件**：`backend/models.py`、`backend/schemas.py`

### models.py 新增列

```python
# WebRTC 模式（替代原 fp_webrtc_ip 的单一用法）
fp_webrtc_mode = Column(String, default="")      # "" / "custom" / "mask" / "block"

# GeoIP 跟随代理 IP
geoip = Column(Boolean, default=False)

# 中继代理（链式代理第一跳）
relay_proxy_type = Column(String, default="none")  # none / http / socks5
relay_proxy_host = Column(String, default="")
relay_proxy_port = Column(Integer, nullable=True)
relay_proxy_user = Column(String, default="")
relay_proxy_pass = Column(String, default="")
```

保留 `fp_webrtc_ip`（String 字段不变），兼容旧数据。

### schemas.py 同步新增

在 `ProfileBase` 中添加同名字段：
- `fp_webrtc_mode: str = ""`
- `geoip: bool = False`
- `relay_proxy_type: str = "none"`
- `relay_proxy_host: str = ""`
- `relay_proxy_port: Optional[int] = None`
- `relay_proxy_user: str = ""`
- `relay_proxy_pass: str = ""`

**验收**：`python -m pytest tests/ -v` 全绿（现有测试不受影响）

---

## 步骤 2 — SQLite 自动迁移（Alembic-free）

CloakToast 用 `Base.metadata.create_all` 建表，不用 alembic，但新列不会自动加到已有 DB。

在 `backend/database.py` 的 `init_db()` 后（或 lifespan 里）加 ALTER TABLE 补丁：

```python
def _migrate_add_columns(engine):
    """为已有数据库补充新列，幂等。"""
    new_cols = [
        ("fp_webrtc_mode",   "TEXT DEFAULT ''"),
        ("geoip",            "INTEGER DEFAULT 0"),
        ("relay_proxy_type", "TEXT DEFAULT 'none'"),
        ("relay_proxy_host", "TEXT DEFAULT ''"),
        ("relay_proxy_port", "INTEGER"),
        ("relay_proxy_user", "TEXT DEFAULT ''"),
        ("relay_proxy_pass", "TEXT DEFAULT ''"),
    ]
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(profiles)"))}
        for col_name, col_def in new_cols:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE profiles ADD COLUMN {col_name} {col_def}"))
        conn.commit()
```

在 `main.py` lifespan 的 `init_db()` 调用后立即调用 `_migrate_add_columns(engine)`。

**验收**：删掉 data/cloaktoast.db 重建正常；用旧 DB 启动后新列存在，旧数据完整。

---

## 步骤 3 — types.ts 类型同步

**文件**：`frontend/src/types.ts`

在 `Profile` interface 新增：
```typescript
fp_webrtc_mode: string;          // "" | "custom" | "mask" | "block"
geoip: boolean;
relay_proxy_type: "none" | "http" | "socks5";
relay_proxy_host: string;
relay_proxy_port: number | null;
relay_proxy_user: string;
relay_proxy_pass: string;
```

---

## 步骤 4 — chain_proxy.py（纯 asyncio SOCKS5 链式代理）

**新建**：`backend/services/chain_proxy.py`

### 模块接口

```python
def start_chain_proxy(relay_url: str, target_url: str) -> int:
    """在后台线程启动链式代理，返回本机监听端口。"""

def stop_chain_proxy(port: int) -> None:
    """停止指定端口的链式代理（worker 退出时调用）。"""
```

### 内部架构

- 主线程调 `start_chain_proxy`，启动一个 daemon 线程运行 `asyncio.run(_serve(...))`
- `_serve` 用 `asyncio.start_server` 监听 `127.0.0.1:0`（系统分配空闲端口）
- 每个连接启动协程 `_handle(reader, writer, relay_url, target_url)`

### 连接处理流程（每条 Chromium 连接）

```
1. SOCKS5 握手（接受 Chromium，无认证）
   - 读 [VER=5, NMETHODS, METHODS]
   - 响应 [VER=5, METHOD=0x00]（无认证）

2. 读 CONNECT 请求
   - 读 [VER, CMD=1, RSV, ATYP, DST.ADDR, DST.PORT]
   - 解析出 (dest_host, dest_port) = 目标网站地址

3. 连接 relay（mihomo）
   - TCP connect to relay_host:relay_port
   - 若 relay 是 SOCKS5：完成 SOCKS5 握手，发 CONNECT relay→cliproxy_host:cliproxy_port
   - 若 relay 是 HTTP：发 HTTP CONNECT relay→cliproxy_host:cliproxy_port

4. 连接 target（cliproxy）—— 通过 relay 隧道
   - 若 target 是 SOCKS5：在 relay 隧道内完成 SOCKS5 握手（含 user/pass 认证）
                          发 CONNECT cliproxy→dest_host:dest_port
   - 若 target 是 HTTP：在 relay 隧道内发 HTTP CONNECT→dest_host:dest_port

5. 向 Chromium 返回 SOCKS5 成功响应
   [VER=5, REP=0x00, RSV=0, ATYP=1, BND.ADDR=0.0.0.0, BND.PORT=0]

6. asyncio.gather(pipe(client→remote), pipe(remote→client))
```

### 错误处理

- 任何步骤异常 → 向 Chromium 返回 SOCKS5 REP=0x01（general failure）后关闭连接
- 不抛出到主线程，记录到 worker log

**验收**：
- `test_chain_proxy.py`：mock relay + target socket，验证 SOCKS5 握手正确性
- 手动测试（可选）：`start_chain_proxy("socks5://127.0.0.1:7897", "socks5://user:pass@host:1080")` 后 curl 通过本地端口

---

## 步骤 5 — browser_worker.py 集成所有新功能

**文件**：`backend/services/browser_worker.py`

### 5a. WebRTC 模式（替换原逻辑）

在 `build_fingerprint_args` 中替换：
```python
# 旧代码
if profile.get("fp_webrtc_ip"):
    args.append(f"--fingerprint-webrtc-ip={profile['fp_webrtc_ip']}")

# 新代码
mode = profile.get("fp_webrtc_mode", "")
if not mode and profile.get("fp_webrtc_ip"):
    mode = "custom"   # 旧数据兼容：有 IP 但没 mode → 视为 custom
if mode == "custom" and profile.get("fp_webrtc_ip"):
    args.append(f"--fingerprint-webrtc-ip={profile['fp_webrtc_ip']}")
elif mode == "mask":
    args.append("--fingerprint-webrtc-ip=10.0.0.1")
# "block" 模式由后面的 add_init_script 处理
```

### 5b. WebRTC block 注入（在 install_resource_blocker 后）

```python
BLOCK_WEBRTC_JS = """
Object.defineProperty(window, 'RTCPeerConnection',
  {get: () => undefined, configurable: false});
Object.defineProperty(window, 'webkitRTCPeerConnection',
  {get: () => undefined, configurable: false});
"""

if profile.get("fp_webrtc_mode") == "block":
    try:
        context.add_init_script(BLOCK_WEBRTC_JS)
        _log(udd, "WebRTC blocked via init_script")
    except Exception as e:
        _log(udd, f"WARN: failed to inject WebRTC block script: {e!r}")
```

### 5c. GeoIP 参数传入

```python
use_geoip = bool(profile.get("geoip")) and not chain_port  # chain_proxy 时禁用
context = launch_persistent_context(
    ...
    geoip=use_geoip,
    ...
)
```

### 5d. 链式代理集成

```python
# 在 build_proxy / build_fingerprint_args 之前
chain_port = None
relay_type = profile.get("relay_proxy_type", "none")
if relay_type != "none" and profile.get("relay_proxy_host") and profile.get("proxy_type", "none") != "none":
    relay_url = _build_relay_url(profile)   # 新辅助函数
    target_url = build_proxy(profile)
    try:
        from .chain_proxy import start_chain_proxy
        chain_port = start_chain_proxy(relay_url, target_url)
        _log(udd, f"chain proxy started on 127.0.0.1:{chain_port}")
    except Exception as e:
        _log(udd, f"WARN: chain proxy failed to start: {e!r} — falling back to direct proxy")

proxy_for_browser = f"socks5://127.0.0.1:{chain_port}" if chain_port else build_proxy(profile)
```

新辅助函数 `_build_relay_url(profile) -> str`，与 `build_proxy` 逻辑相同但读 relay_proxy_* 字段。

**验收**：`python -m pytest tests/ -v` 全绿

---

## 步骤 6 — ProfileForm：屏幕分辨率 + 任务栏高度

**文件**：`frontend/src/pages/Profiles/ProfileForm.tsx`（指纹 Tab）

1. 在 `fp_screen_width` / `fp_screen_height` 之前加分辨率快速预设按钮组
2. 将两个 `InputNumber` 改为 antd `Select`（选项为常见值数组）
3. `fp_taskbar_height` 同理改为 Select

```typescript
const SCREEN_WIDTHS  = [1280, 1366, 1440, 1600, 1920, 2560, 3840];
const SCREEN_HEIGHTS = [768, 800, 900, 1024, 1080, 1200, 1440, 2160];
const TASKBAR_HEIGHTS = [0, 40, 48, 56, 80];

const SCREEN_PRESETS = [
  { label: "1920×1080", w: 1920, h: 1080 },
  { label: "2560×1440", w: 2560, h: 1440 },
  { label: "1366×768",  w: 1366, h: 768  },
  { label: "1440×900",  w: 1440, h: 900  },
  { label: "1280×800",  w: 1280, h: 800  },
];
```

预设按钮点击时：`form.setFieldsValue({ fp_screen_width: w, fp_screen_height: h })`

placeholder 统一改为"留空=使用真实显示器分辨率"。

---

## 步骤 7 — ProfileForm：品牌联动 + WebRTC 模式 + GeoIP 开关

**文件**：`frontend/src/pages/Profiles/ProfileForm.tsx`

### 7a. 高级 Tab — 品牌/版本联动

```typescript
const BRAND_VERSIONS: Record<string, string[]> = {
  "Google Chrome":   ["138","137","136","135","134","133"],
  "Microsoft Edge":  ["138","137","136","135","134","133"],
  "Brave":           ["1.77","1.76","1.75","1.74","1.73"],
  "Opera":           ["118","117","116","115"],
  "Vivaldi":         ["7.3","7.2","7.1","7.0"],
};

const PLATFORM_VERSIONS: Record<string, string[]> = {
  windows: ["10.0.0","11.0.0"],
  macos:   ["15.0","14.0","13.0","12.0"],
};
```

- `fp_brand` → `Select`（+ allowClear，留空=自动）
- `fp_brand_version` → `Select`，`shouldUpdate` 监听 `fp_brand` 变化，动态 options
- `fp_platform_version` → `Select`，`shouldUpdate` 监听 `fp_platform` 变化，动态 options
- brand 变化时若当前 brand_version 不在新列表中，自动清空

### 7b. 指纹 Tab — WebRTC 模式

将现有"WebRTC IP"字段改为两个字段：

```tsx
<Form.Item label="WebRTC 模式" name="fp_webrtc_mode">
  <Select allowClear placeholder="默认（不干预）" options={[
    { value: "custom", label: "自定义 IP" },
    { value: "mask",   label: "掩盖（覆盖为私有 IP，WebRTC 可用）" },
    { value: "block",  label: "禁止（完全禁用 RTCPeerConnection）" },
  ]} />
</Form.Item>

<Form.Item noStyle shouldUpdate={(p,c) => p.fp_webrtc_mode !== c.fp_webrtc_mode}>
  {({ getFieldValue }) =>
    getFieldValue("fp_webrtc_mode") === "custom" && (
      <Form.Item label="WebRTC IP" name="fp_webrtc_ip" extra="指定替换的 IP 地址">
        <Input placeholder="如 192.168.1.1" />
      </Form.Item>
    )
  }
</Form.Item>
```

### 7c. 常用 Tab — GeoIP 开关

在"时区"字段上方加：

```tsx
<Form.Item noStyle shouldUpdate={(p,c) =>
  p.proxy_type !== c.proxy_type || p.relay_proxy_type !== c.relay_proxy_type}>
  {({ getFieldValue }) => {
    const hasProxy = getFieldValue("proxy_type") !== "none";
    const hasRelay = getFieldValue("relay_proxy_type") !== "none";
    const disabled = !hasProxy || hasRelay;
    const tip = !hasProxy
      ? "需先配置代理"
      : hasRelay ? "链式代理模式下请手动设置时区/位置" : undefined;
    return (
      <Form.Item
        label="跟随代理 IP"
        name="geoip"
        valuePropName="checked"
        tooltip={tip}
        extra="自动从代理出口 IP 推断时区、语言、地理位置（需安装 cloakbrowser[geoip]）"
      >
        <Switch disabled={disabled} />
      </Form.Item>
    );
  }}
</Form.Item>
```

开启时，在时区和语言字段下方加灰色提示文本"已由 GeoIP 自动填充，填写后可手动覆盖"（`shouldUpdate` 联动）。

---

## 步骤 8 — ProfileForm：中继代理折叠面板

**文件**：`frontend/src/pages/Profiles/ProfileForm.tsx`（常用 Tab，代理设置区域末尾）

```tsx
<Form.Item noStyle shouldUpdate={(p,c) => p.proxy_type !== c.proxy_type}>
  {({ getFieldValue }) =>
    getFieldValue("proxy_type") !== "none" && (
      <Collapse ghost size="small" style={{ marginBottom: 16 }}>
        <Collapse.Panel header="中继代理（可选）" key="relay"
          extra={<span style={{fontSize:12,color:'#999'}}>
            用于需要先经过本地代理才能访问主代理的场景（如 mihomo → cliproxy）
          </span>}>
          <Form.Item label="中继类型" name="relay_proxy_type">
            <Select options={[
              { value: "none",   label: "不使用" },
              { value: "http",   label: "HTTP" },
              { value: "socks5", label: "SOCKS5" },
            ]} />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(p,c) => p.relay_proxy_type !== c.relay_proxy_type}>
            {({ getFieldValue: gfv }) =>
              gfv("relay_proxy_type") !== "none" && (
                <>
                  <Form.Item label="Host" name="relay_proxy_host">
                    <Input placeholder="127.0.0.1" />
                  </Form.Item>
                  <Form.Item label="Port" name="relay_proxy_port">
                    <InputNumber style={{width:"100%"}} min={1} max={65535} />
                  </Form.Item>
                  <Form.Item label="用户名" name="relay_proxy_user">
                    <Input />
                  </Form.Item>
                  <Form.Item label="密码" name="relay_proxy_pass">
                    <Input.Password />
                  </Form.Item>
                </>
              )
            }
          </Form.Item>
        </Collapse.Panel>
      </Collapse>
    )
  }
</Form.Item>
```

ProfileForm 初始值补充 relay_proxy_type: "none"。

---

## 步骤 9 — 测试补充

**文件**：`tests/test_instances.py`（或新建 `tests/test_chain_proxy.py`）

新增测试：

1. `test_webrtc_mode_custom` — `build_fingerprint_args` 在 mode=custom 时输出正确 flag
2. `test_webrtc_mode_mask` — mode=mask 时输出 `--fingerprint-webrtc-ip=10.0.0.1`
3. `test_webrtc_mode_block` — mode=block 时 fingerprint_args 无 webrtc flag
4. `test_webrtc_legacy_compat` — 旧 profile（只有 fp_webrtc_ip，无 mode）正确降级为 custom
5. `test_chain_proxy_socks5_relay` — mock TCP server 模拟 relay + target，验证握手流程
6. `test_chain_proxy_cleanup` — stop_chain_proxy 后端口释放

---

## 步骤 10 — 脚本 + 文档更新

**start.bat**：在 `pip install -e .` 或 `pip install cloakbrowser` 之后加：
```bat
pip install "cloakbrowser[geoip]" --quiet || echo [警告] GeoIP 依赖安装失败，跟随IP功能不可用
```

**start.sh**：同理加：
```bash
pip install "cloakbrowser[geoip]" --quiet || echo "[警告] GeoIP 依赖安装失败"
```

**CLAUDE.md**：
- Profile 字段表格新增 7 个字段的说明行
- 开发注意事项新增：
  - chain_proxy 在 worker 子进程内以 daemon 线程运行，父进程退出即销毁，无需额外清理
  - GeoIP 与链式代理互斥，前端强制灰色，后端 `use_geoip = geoip and not chain_port`

---

## 完成标准

- [ ] `python -m pytest tests/ -v` 全绿（含新增测试）
- [ ] `cd frontend && npm run build` 无类型错误
- [ ] 手动测试：创建含 relay 代理的 profile，启动浏览器，确认流量经链路正确路由
- [ ] 手动测试：WebRTC block 模式下 `rtcpeerconnection` 在 browser console 为 undefined
- [ ] 手动测试：GeoIP 开启后时区/语言/位置与代理出口 IP 一致
