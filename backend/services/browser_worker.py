"""
独立子进程脚本，由 browser.py 以 subprocess 启动。
用法: python browser_worker.py <base64_json_payload>

退出码：
    0 — 浏览器被用户关闭（正常退出）
    1 — payload 解析失败
    2 — cloakbrowser/Playwright 启动失败
    3 — 运行时其他异常
"""
import sys
import json
import base64
import hashlib
import threading
import traceback
import uuid
from pathlib import Path
from datetime import datetime, timezone


BLOCK_WEBRTC_JS = """
Object.defineProperty(window, 'RTCPeerConnection',
  {get: () => undefined, configurable: false});
Object.defineProperty(window, 'webkitRTCPeerConnection',
  {get: () => undefined, configurable: false});
"""


def _build_relay_url(profile: dict) -> str | None:
    """构建中继代理 URL（relay_proxy_* 字段）。"""
    rtype = profile.get("relay_proxy_type", "none")
    if rtype == "none" or not profile.get("relay_proxy_host"):
        return None
    creds = ""
    if profile.get("relay_proxy_user"):
        creds = f"{profile['relay_proxy_user']}:{profile.get('relay_proxy_pass', '')}@"
    return f"{rtype}://{creds}{profile['relay_proxy_host']}:{profile['relay_proxy_port']}"


def build_fingerprint_args(profile: dict) -> list[str]:
    args = []
    # fingerprint_seed = 0 是合法值（32 位整数 seed 之一），不能用 truthiness。
    # 其他整数字段如 hardware_concurrency / device_memory / screen_* 0 是无意义的，保留 truthiness。
    if profile.get("fingerprint_seed") is not None:
        args.append(f"--fingerprint={profile['fingerprint_seed']}")
    if not profile.get("fp_noise_enabled", True):
        args.append("--fingerprint-noise=false")
    if profile.get("fp_platform"):
        args.append(f"--fingerprint-platform={profile['fp_platform']}")
    if profile.get("fp_hardware_concurrency"):
        args.append(f"--fingerprint-hardware-concurrency={profile['fp_hardware_concurrency']}")
    if profile.get("fp_device_memory"):
        args.append(f"--fingerprint-device-memory={profile['fp_device_memory']}")
    if profile.get("fp_screen_width"):
        args.append(f"--fingerprint-screen-width={profile['fp_screen_width']}")
    if profile.get("fp_screen_height"):
        args.append(f"--fingerprint-screen-height={profile['fp_screen_height']}")
    if profile.get("fp_taskbar_height"):
        args.append(f"--fingerprint-taskbar-height={profile['fp_taskbar_height']}")
    if profile.get("fp_gpu_vendor"):
        args.append(f"--fingerprint-gpu-vendor={profile['fp_gpu_vendor']}")
    if profile.get("fp_gpu_renderer"):
        args.append(f"--fingerprint-gpu-renderer={profile['fp_gpu_renderer']}")
    # WebRTC 模式（兼容旧数据：有 fp_webrtc_ip 但无 fp_webrtc_mode → 视为 custom）
    _webrtc_mode = profile.get("fp_webrtc_mode") or ""
    if not _webrtc_mode and profile.get("fp_webrtc_ip"):
        _webrtc_mode = "custom"
    if _webrtc_mode == "custom" and profile.get("fp_webrtc_ip"):
        args.append(f"--fingerprint-webrtc-ip={profile['fp_webrtc_ip']}")
    elif _webrtc_mode == "mask":
        args.append("--fingerprint-webrtc-ip=10.0.0.1")
    # "block" 由 add_init_script 处理；"" 不传 flag
    lat = profile.get("fp_location_lat")
    lng = profile.get("fp_location_lng")
    if lat is not None and lng is not None:
        args.append(f"--fingerprint-location={lat},{lng}")
    if profile.get("fp_storage_quota") is not None:
        args.append(f"--fingerprint-storage-quota={profile['fp_storage_quota']}")
    if profile.get("fp_fonts_dir"):
        args.append(f"--fingerprint-fonts-dir={profile['fp_fonts_dir']}")
    if profile.get("fp_brand"):
        args.append(f"--fingerprint-brand={profile['fp_brand']}")
    if profile.get("fp_brand_version"):
        args.append(f"--fingerprint-brand-version={profile['fp_brand_version']}")
    if profile.get("fp_platform_version"):
        args.append(f"--fingerprint-platform-version={profile['fp_platform_version']}")
    return args + (profile.get("extra_args") or [])


VIDEO_EXTENSIONS = (
    ".mp4", ".webm", ".mov", ".m4s", ".m4v", ".m4a",
    ".ts", ".mp3", ".aac", ".flv", ".mkv", ".avi",
)
VIDEO_MANIFEST_EXTENSIONS = (".m3u8", ".mpd")


def _is_video_url(url: str) -> bool:
    """识别视频/音频流 URL。media resource_type 已覆盖 <video>/<audio>，
    但 HLS/DASH 的 m3u8/mpd/ts 通常走 xhr/fetch，需要按扩展名补抓。"""
    path = url.split("?", 1)[0].split("#", 1)[0].lower()
    if path.endswith(VIDEO_EXTENSIONS):
        return True
    if path.endswith(VIDEO_MANIFEST_EXTENSIONS):
        return True
    return False


def install_resource_blocker(
    context,
    block_video: bool,
    block_image_max_kb: int | None,
    on_log=None,
) -> bool:
    """在 BrowserContext 上挂载一个 route handler，按规则 abort 请求。
    返回是否真的安装了 handler — 没有任何规则时不安装，避免 per-request 开销。

    block_video: 屏蔽 <video>/<audio> + HLS/DASH 流。
    block_image_max_kb:
        None — 不限制
        0    — 屏蔽所有图片（HEAD 都不发）
        N>0  — 先 HEAD 探 Content-Length，>N KB 时 abort
    """
    if not block_video and block_image_max_kb is None:
        return False

    def _log(msg):
        if on_log:
            try:
                on_log(msg)
            except Exception:
                pass

    def handler(route, request):
        try:
            rt = request.resource_type
            url = request.url

            if block_video:
                if rt == "media" or _is_video_url(url):
                    _log(f"BLOCK video [{rt}] {url[:120]}")
                    route.abort()
                    return

            if rt == "image" and block_image_max_kb is not None:
                if block_image_max_kb == 0:
                    _log(f"BLOCK image (all) {url[:120]}")
                    route.abort()
                    return
                # HEAD 探一下大小 — HEAD 不被支持时直接放行
                try:
                    resp = route.fetch(method="HEAD")
                    cl = resp.headers.get("content-length")
                    if cl and int(cl) > block_image_max_kb * 1024:
                        _log(f"BLOCK image ({int(cl)//1024}KB > {block_image_max_kb}KB) {url[:120]}")
                        route.abort()
                        return
                except Exception:
                    # HEAD 失败 —— 服务器不支持 / 网络错误，保守放行
                    pass

            route.continue_()
        except Exception as e:
            # 任何 route handler 异常都不能让浏览器卡死 — 尽力放行
            try:
                route.continue_()
            except Exception:
                pass

    try:
        context.route("**/*", handler)
        return True
    except Exception as e:
        _log(f"failed to install resource blocker: {e!r}")
        return False


def _write_bookmarks(udd: str, bookmarks: list[dict]) -> None:
    """将共享书签写入 Chromium 的 Default/Bookmarks 文件。"""
    import time as _time

    def _cr_time():
        return str(int((_time.time() + 11644473600) * 1_000_000))

    t = _cr_time()
    children = []
    for i, bm in enumerate(bookmarks, start=4):
        children.append({
            "date_added": t, "date_last_used": "0",
            "guid": str(uuid.uuid4()), "id": str(i),
            "name": bm["name"], "type": "url", "url": bm["url"],
        })

    roots = {
        "bookmark_bar": {
            "children": children,
            "date_added": t, "date_last_used": "0", "date_modified": t,
            "guid": "0bc5d13f-2cba-48a8-9788-d21b4db8f192",
            "id": "1", "name": "Bookmarks bar", "type": "folder",
        },
        "other": {
            "children": [],
            "date_added": t, "date_last_used": "0", "date_modified": "0",
            "guid": "82e3080f-f0b8-4a86-875c-b77e53e84082",
            "id": "2", "name": "Other bookmarks", "type": "folder",
        },
        "synced": {
            "children": [],
            "date_added": t, "date_last_used": "0", "date_modified": "0",
            "guid": "4cf2e351-0e85-532b-bb37-df045d8f8d0f",
            "id": "3", "name": "Mobile bookmarks", "type": "folder",
        },
    }

    def _checksum(r):
        md5 = hashlib.md5()

        def walk(node):
            if node["type"] == "url":
                md5.update(node["name"].encode())
                md5.update(node["id"].encode())
                md5.update(node["url"].encode())
            else:
                md5.update(node["name"].encode())
                md5.update(node["id"].encode())
                for c in node.get("children", []):
                    walk(c)

        for k in ("bookmark_bar", "other", "synced"):
            walk(r[k])
        return md5.hexdigest()

    data = {"checksum": _checksum(roots), "roots": roots, "version": 1}
    default_dir = Path(udd) / "Default"
    default_dir.mkdir(parents=True, exist_ok=True)
    (default_dir / "Bookmarks").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_proxy(profile: dict) -> str | None:
    if profile.get("proxy_type", "none") == "none" or not profile.get("proxy_host"):
        return None
    creds = ""
    if profile.get("proxy_user"):
        creds = f"{profile['proxy_user']}:{profile['proxy_pass']}@"
    return f"{profile['proxy_type']}://{creds}{profile['proxy_host']}:{profile['proxy_port']}"


def _log(udd: str | None, msg: str) -> None:
    """把 worker 日志追加到 profile 自身的 log 文件，便于排查闪退。"""
    try:
        if udd:
            log_path = Path(udd) / "_cloaktoast_worker.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as f:
                f.write(f"[{datetime.now(timezone.utc).isoformat()}] {msg}\n")
    except Exception:
        pass
    print(msg, file=sys.stderr, flush=True)


def main() -> int:
    udd = None
    try:
        payload = json.loads(base64.b64decode(sys.argv[1]))
    except Exception:
        print("FATAL: 无法解析 payload", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return 1

    profile = payload.get("profile") or {}
    bookmarks = payload.get("bookmarks") or []
    license_key = payload.get("license_key")
    udd = profile.get("udd")

    _log(udd, f"worker started, profile={profile.get('id')!r}, bookmarks={len(bookmarks)}, license={'set' if license_key else 'none'}")

    try:
        from cloakbrowser import launch_persistent_context
    except Exception:
        _log(udd, "FATAL: import cloakbrowser failed\n" + traceback.format_exc())
        return 2

    # 链式代理：relay_proxy_* 字段有效时启动本地 SOCKS5 中转，再通过它连 cliproxy
    chain_port = None
    relay_url = _build_relay_url(profile)
    target_url = build_proxy(profile)
    if relay_url and target_url:
        try:
            try:
                from backend.services.chain_proxy import start_chain_proxy
            except ImportError:
                from chain_proxy import start_chain_proxy  # standalone script mode
            chain_port = start_chain_proxy(relay_url, target_url)
            _log(udd, f"chain proxy started on 127.0.0.1:{chain_port}")
        except Exception as e:
            _log(udd, f"WARN: chain proxy failed to start: {e!r} — using direct proxy")

    proxy_for_browser = f"socks5://127.0.0.1:{chain_port}" if chain_port else build_proxy(profile)

    try:
        _write_bookmarks(udd, bookmarks)
        _log(udd, f"bookmarks written: {len(bookmarks)} items")
    except Exception as e:
        _log(udd, f"WARN: failed to write bookmarks: {e!r}")

    try:
        context = launch_persistent_context(
            user_data_dir=profile["udd"],
            proxy=proxy_for_browser,
            timezone=profile.get("timezone") or None,
            locale=profile.get("locale") or None,
            humanize=profile.get("humanize", True),
            human_preset=profile.get("human_preset", "default"),
            headless=profile.get("headless", False),
            user_agent=profile.get("user_agent") or None,
            args=build_fingerprint_args(profile),
            extension_paths=profile.get("extension_paths") or None,
            license_key=license_key,
            geoip=bool(profile.get("geoip")),
        )
    except Exception:
        _log(udd, "FATAL: launch_persistent_context failed\n" + traceback.format_exc())
        return 2

    _log(udd, "context launched OK")

    # 节约代理流量：根据 profile 配置安装资源拦截 handler。
    block_video = bool(profile.get("block_video"))
    block_image_max_kb = profile.get("block_image_max_kb")
    if install_resource_blocker(
        context,
        block_video=block_video,
        block_image_max_kb=block_image_max_kb,
        on_log=lambda m: _log(udd, m),
    ):
        _log(udd, f"resource blocker on: video={block_video} image_max_kb={block_image_max_kb}")

    if profile.get("fp_webrtc_mode") == "block":
        try:
            context.add_init_script(BLOCK_WEBRTC_JS)
            _log(udd, "WebRTC blocked via init_script")
        except Exception as e:
            _log(udd, f"WARN: failed to inject WebRTC block script: {e!r}")

    # 关键：在打开任何 URL 之前先订阅 close 事件。
    # 否则若用户在 goto 期间关闭浏览器，close 事件已触发但还没有 listener，
    # pyee 不会重放历史事件 — 后面再调 wait_for_event("close") 会永远挂死
    # （Playwright 的 expect_event 对 Close 事件本身刻意跳过 reject_on_event 分支）。
    closed_event = threading.Event()

    def _on_close(_ctx):
        _log(udd, "context.close event fired")
        closed_event.set()

    try:
        context.on("close", _on_close)
    except Exception:
        _log(udd, "WARN: failed to register close listener\n" + traceback.format_exc())

    try:
        if not context.is_closed() and not context.pages:
            try:
                context.new_page()
            except Exception as e:
                _log(udd, f"new_page (blank) failed: {e!r}")

        if closed_event.is_set() or context.is_closed():
            _log(udd, "already closed before wait loop, exiting")
            return 0

        _log(udd, "entering wait loop")

        # timeout=0 表示永不超时（Playwright 源码：reject_on_timeout 在 timeout==0 时直接 return）。
        # 不传 timeout 会用默认 30s，到时间抛 TimeoutError → 进程退出 → Chromium 跟着关闭。
        # 但即便 timeout=0，如果 close 事件已经在我们调到这里之前触发，pyee 不会重放，
        # wait_for_event 会永远挂死 — 因此上面用 threading.Event 提前订阅，并在这里 fall back 到 closed_event.wait()。
        if closed_event.is_set():
            return 0
        try:
            context.wait_for_event("close", timeout=0)
        except Exception as e:
            _log(udd, f"wait_for_event raised, falling back to threading.Event: {e!r}")
            closed_event.wait()

        _log(udd, "context closed by user, exiting")
        return 0
    except KeyboardInterrupt:
        _log(udd, "interrupted, closing context")
        try:
            context.close()
        except Exception:
            pass
        return 0
    except Exception:
        _log(udd, "FATAL: runtime error in wait loop\n" + traceback.format_exc())
        try:
            context.close()
        except Exception:
            pass
        return 3


if __name__ == "__main__":
    sys.exit(main())
