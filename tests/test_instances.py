import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import backend.services.browser as browser_service
import pytest


@pytest.fixture(autouse=True)
def clear_state():
    """每个测试前后都把进程注册表和退出历史清干净。"""
    browser_service.running_instances.clear()
    browser_service.recent_exits.clear()
    browser_service._launch_locks.clear()
    yield
    browser_service.running_instances.clear()
    browser_service.recent_exits.clear()
    browser_service._launch_locks.clear()


def _make_alive_process():
    """伪造一个永不退出的 asyncio subprocess。

    launch_profile() 会 wait_for(process.wait(), timeout=STARTUP_PROBE_SECONDS)，
    所以 wait() 必须是一个永远 pending 的 coroutine — TimeoutError 触发"启动成功"分支。
    returncode = None 表示"仍在运行"。
    """
    mock = MagicMock()
    mock.returncode = None
    mock._stopped = asyncio.Event()

    async def _wait():
        await mock._stopped.wait()
        return mock.returncode if mock.returncode is not None else 0

    mock.wait = _wait

    def _terminate():
        # 模拟收到 SIGTERM：标记 returncode，让 wait() 立刻返回
        if mock.returncode is None:
            mock.returncode = -15
        mock._stopped.set()

    def _kill():
        if mock.returncode is None:
            mock.returncode = -9
        mock._stopped.set()

    mock.terminate = MagicMock(side_effect=_terminate)
    mock.kill = MagicMock(side_effect=_kill)
    return mock


def _make_failed_process(exit_code: int = 1):
    mock = MagicMock()
    mock.returncode = exit_code

    async def _done():
        return exit_code

    mock.wait = _done
    return mock


def test_get_instances_empty(client):
    resp = client.get("/api/instances")
    assert resp.status_code == 200
    assert resp.json() == []


def test_launch_unknown_profile(client):
    resp = client.post("/api/instances/launch", json={"profile_id": "nonexistent"})
    assert resp.status_code == 404


def test_stop_not_running(client):
    p = client.post("/api/profiles", json={"name": "P"}).json()
    resp = client.post(f"/api/instances/stop/{p['id']}")
    assert resp.status_code == 400


def test_launch_profile(client, monkeypatch, tmp_path):
    p = client.post("/api/profiles", json={"name": "P"}).json()
    monkeypatch.setattr(browser_service, "STARTUP_PROBE_SECONDS", 0.05)
    monkeypatch.chdir(tmp_path)

    mock_process = _make_alive_process()
    with patch(
        "backend.services.browser.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=mock_process,
    ):
        resp = client.post("/api/instances/launch", json={"profile_id": p["id"]})
    assert resp.status_code == 200, resp.text
    instances = client.get("/api/instances").json()
    assert len(instances) == 1
    assert instances[0]["profile_id"] == p["id"]
    assert instances[0]["state"] == "running"


def test_launch_already_running(client, monkeypatch, tmp_path):
    """连续启动同一个 profile 应该 400。"""
    p = client.post("/api/profiles", json={"name": "P"}).json()
    monkeypatch.setattr(browser_service, "STARTUP_PROBE_SECONDS", 0.05)
    monkeypatch.chdir(tmp_path)

    with patch(
        "backend.services.browser.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=_make_alive_process(),
    ):
        assert client.post("/api/instances/launch", json={"profile_id": p["id"]}).status_code == 200
        resp = client.post("/api/instances/launch", json={"profile_id": p["id"]})
    assert resp.status_code == 400


def test_launch_worker_immediate_exit(client, monkeypatch, tmp_path):
    """worker 在 probe 时间窗口内退出 -> 启动失败，前端收到 400 + 错误信息。"""
    p = client.post("/api/profiles", json={"name": "P"}).json()
    monkeypatch.setattr(browser_service, "STARTUP_PROBE_SECONDS", 0.05)
    monkeypatch.chdir(tmp_path)

    with patch(
        "backend.services.browser.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=_make_failed_process(exit_code=2),
    ):
        resp = client.post("/api/instances/launch", json={"profile_id": p["id"]})
    assert resp.status_code == 400
    assert "exit code=2" in resp.text
    # 失败后 running_instances 不应留下条目
    assert client.get("/api/instances").json() == []
    # 但 recent_exits 里应有一条记录
    exits = client.get("/api/instances/recent_exits").json()
    assert any(e["returncode"] == 2 and e["profile_id"] == p["id"] for e in exits)


def test_stop_running_instance(client, monkeypatch, tmp_path):
    p = client.post("/api/profiles", json={"name": "P"}).json()
    monkeypatch.setattr(browser_service, "STARTUP_PROBE_SECONDS", 0.05)
    monkeypatch.chdir(tmp_path)

    mock_process = _make_alive_process()
    with patch(
        "backend.services.browser.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=mock_process,
    ):
        assert client.post("/api/instances/launch", json={"profile_id": p["id"]}).status_code == 200
        resp = client.post(f"/api/instances/stop/{p['id']}")

    assert resp.status_code == 200
    assert client.get("/api/instances").json() == []
    # stop 应该写一条退出记录
    exits = client.get("/api/instances/recent_exits").json()
    assert any(e["profile_id"] == p["id"] for e in exits)


def test_watcher_auto_cleans_on_external_exit(client, monkeypatch, tmp_path):
    """如果 worker 自己退出（例如用户关掉浏览器），watcher 应立即从 running_instances 移走。"""
    p = client.post("/api/profiles", json={"name": "P"}).json()
    monkeypatch.setattr(browser_service, "STARTUP_PROBE_SECONDS", 0.05)
    monkeypatch.chdir(tmp_path)

    mock_process = _make_alive_process()
    with patch(
        "backend.services.browser.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=mock_process,
    ):
        client.post("/api/instances/launch", json={"profile_id": p["id"]})

    assert len(client.get("/api/instances").json()) == 1

    # 模拟 worker 在外部正常退出 — 触发 watcher
    async def _trigger_exit():
        mock_process.returncode = 0
        mock_process._stopped.set()
        # 让 watcher 跑完
        await asyncio.sleep(0)
        watcher = browser_service.running_instances.get(p["id"], {}).get("watcher") if p["id"] in browser_service.running_instances else None
        if watcher:
            try:
                await watcher
            except Exception:
                pass

    asyncio.get_event_loop().run_until_complete(_trigger_exit()) if False else None
    # 上面的 run_until_complete 在 pytest 里不合适 — 用 asyncio.run 替代
    asyncio.run(_trigger_exit())

    assert client.get("/api/instances").json() == []
    exits = client.get("/api/instances/recent_exits").json()
    assert any(e["returncode"] == 0 and e["profile_id"] == p["id"] for e in exits)


def test_cleanup_removes_exited_processes(client, monkeypatch, tmp_path):
    """惰性 _cleanup 兜底：watcher 万一没跑，下次 GET /instances 仍能清理。"""
    p = client.post("/api/profiles", json={"name": "P"}).json()
    monkeypatch.setattr(browser_service, "STARTUP_PROBE_SECONDS", 0.05)
    monkeypatch.chdir(tmp_path)

    mock_process = _make_alive_process()
    with patch(
        "backend.services.browser.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=mock_process,
    ):
        client.post("/api/instances/launch", json={"profile_id": p["id"]})

    # 把 watcher 取消掉，模拟"它没跑"
    inst = browser_service.running_instances[p["id"]]
    watcher = inst.get("watcher")
    if watcher:
        watcher.cancel()

    # 直接改 returncode + 触发停止事件
    mock_process.returncode = 0
    mock_process._stopped.set()

    # 下次查询应触发 _cleanup
    assert client.get("/api/instances").json() == []


def test_build_fingerprint_args_empty_profile():
    """空 profile 应得到空参数（避免传入空字符串当值）。"""
    from backend.services.browser_worker import build_fingerprint_args
    args = build_fingerprint_args({})
    assert args == []


def test_build_fingerprint_args_seed_zero():
    """fingerprint_seed=0 是合法值，必须输出。"""
    from backend.services.browser_worker import build_fingerprint_args
    args = build_fingerprint_args({"fingerprint_seed": 0})
    assert "--fingerprint=0" in args


def test_build_fingerprint_args_full_profile():
    from backend.services.browser_worker import build_fingerprint_args
    args = build_fingerprint_args({
        "fingerprint_seed": 12345,
        "fp_noise_enabled": False,
        "fp_platform": "Win32",
        "fp_hardware_concurrency": 8,
        "fp_location_lat": 39.9,
        "fp_location_lng": 116.4,
        "extra_args": ["--foo=bar"],
    })
    assert "--fingerprint=12345" in args
    assert "--fingerprint-noise=false" in args
    assert "--fingerprint-platform=Win32" in args
    assert "--fingerprint-hardware-concurrency=8" in args
    assert "--fingerprint-location=39.9,116.4" in args
    assert args[-1] == "--foo=bar"  # extra_args appended last


def test_is_video_url():
    from backend.services.browser_worker import _is_video_url
    assert _is_video_url("https://x.com/a.mp4")
    assert _is_video_url("https://x.com/a.mp4?foo=bar")
    assert _is_video_url("https://x.com/segment.ts")
    assert _is_video_url("https://x.com/playlist.m3u8")
    assert _is_video_url("https://x.com/stream.mpd")
    assert _is_video_url("https://x.com/audio.M4A?token=1#frag")
    assert not _is_video_url("https://x.com/image.png")
    assert not _is_video_url("https://x.com/api/data")
    assert not _is_video_url("https://x.com/page.html")


def test_install_resource_blocker_no_op():
    """没有任何规则时不应安装 handler — 避免 per-request 开销。"""
    from backend.services.browser_worker import install_resource_blocker
    from unittest.mock import MagicMock
    ctx = MagicMock()
    assert install_resource_blocker(ctx, block_video=False, block_image_max_kb=None) is False
    ctx.route.assert_not_called()


def test_install_resource_blocker_installs_when_video_blocked():
    from backend.services.browser_worker import install_resource_blocker
    from unittest.mock import MagicMock
    ctx = MagicMock()
    assert install_resource_blocker(ctx, block_video=True, block_image_max_kb=None) is True
    ctx.route.assert_called_once()


def test_resource_handler_blocks_video_media():
    """模拟一次 media 请求：应当 abort，不应 continue。"""
    from backend.services.browser_worker import install_resource_blocker
    from unittest.mock import MagicMock
    ctx = MagicMock()
    captured = {}

    def _route(pattern, handler):
        captured["handler"] = handler

    ctx.route = _route
    install_resource_blocker(ctx, block_video=True, block_image_max_kb=None)

    route = MagicMock()
    request = MagicMock()
    request.resource_type = "media"
    request.url = "https://x.com/video.mp4"
    captured["handler"](route, request)
    route.abort.assert_called_once()
    route.continue_.assert_not_called()


def test_resource_handler_blocks_hls_segment_via_url():
    from backend.services.browser_worker import install_resource_blocker
    from unittest.mock import MagicMock
    ctx = MagicMock()
    captured = {}
    ctx.route = lambda p, h: captured.update(handler=h)
    install_resource_blocker(ctx, block_video=True, block_image_max_kb=None)

    route = MagicMock()
    request = MagicMock()
    request.resource_type = "fetch"  # HLS 段通常是 xhr/fetch，不是 media
    request.url = "https://cdn.example.com/segment_001.ts?token=x"
    captured["handler"](route, request)
    route.abort.assert_called_once()


def test_resource_handler_blocks_all_images_when_max_kb_zero():
    from backend.services.browser_worker import install_resource_blocker
    from unittest.mock import MagicMock
    ctx = MagicMock()
    captured = {}
    ctx.route = lambda p, h: captured.update(handler=h)
    install_resource_blocker(ctx, block_video=False, block_image_max_kb=0)

    route = MagicMock()
    request = MagicMock()
    request.resource_type = "image"
    request.url = "https://x.com/icon.png"
    captured["handler"](route, request)
    route.abort.assert_called_once()
    route.fetch.assert_not_called()  # 0 KB 应该跳过 HEAD


def test_resource_handler_blocks_large_image_via_head():
    from backend.services.browser_worker import install_resource_blocker
    from unittest.mock import MagicMock
    ctx = MagicMock()
    captured = {}
    ctx.route = lambda p, h: captured.update(handler=h)
    install_resource_blocker(ctx, block_video=False, block_image_max_kb=100)

    route = MagicMock()
    request = MagicMock()
    request.resource_type = "image"
    request.url = "https://x.com/huge.jpg"

    head_response = MagicMock()
    head_response.headers = {"content-length": str(500 * 1024)}  # 500 KB > 100 KB
    route.fetch.return_value = head_response

    captured["handler"](route, request)
    route.fetch.assert_called_once_with(method="HEAD")
    route.abort.assert_called_once()
    route.continue_.assert_not_called()


def test_resource_handler_lets_small_image_through():
    from backend.services.browser_worker import install_resource_blocker
    from unittest.mock import MagicMock
    ctx = MagicMock()
    captured = {}
    ctx.route = lambda p, h: captured.update(handler=h)
    install_resource_blocker(ctx, block_video=False, block_image_max_kb=100)

    route = MagicMock()
    request = MagicMock()
    request.resource_type = "image"
    request.url = "https://x.com/small.png"

    head_response = MagicMock()
    head_response.headers = {"content-length": str(20 * 1024)}  # 20 KB < 100 KB
    route.fetch.return_value = head_response

    captured["handler"](route, request)
    route.abort.assert_not_called()
    route.continue_.assert_called_once()


def test_resource_handler_head_failure_passes_through():
    """HEAD 失败时不应误伤 — 默认放行。"""
    from backend.services.browser_worker import install_resource_blocker
    from unittest.mock import MagicMock
    ctx = MagicMock()
    captured = {}
    ctx.route = lambda p, h: captured.update(handler=h)
    install_resource_blocker(ctx, block_video=False, block_image_max_kb=100)

    route = MagicMock()
    request = MagicMock()
    request.resource_type = "image"
    request.url = "https://x.com/image.png"
    route.fetch.side_effect = RuntimeError("server doesn't allow HEAD")

    captured["handler"](route, request)
    route.abort.assert_not_called()
    route.continue_.assert_called_once()


def test_resource_handler_non_image_non_video_passes():
    from backend.services.browser_worker import install_resource_blocker
    from unittest.mock import MagicMock
    ctx = MagicMock()
    captured = {}
    ctx.route = lambda p, h: captured.update(handler=h)
    install_resource_blocker(ctx, block_video=True, block_image_max_kb=100)

    route = MagicMock()
    request = MagicMock()
    request.resource_type = "stylesheet"
    request.url = "https://x.com/style.css"
    captured["handler"](route, request)
    route.continue_.assert_called_once()
    route.abort.assert_not_called()


def test_build_proxy():
    from backend.services.browser_worker import build_proxy
    assert build_proxy({"proxy_type": "none"}) is None
    assert build_proxy({"proxy_type": "http"}) is None  # no host
    assert build_proxy({
        "proxy_type": "http",
        "proxy_host": "127.0.0.1",
        "proxy_port": 8080,
    }) == "http://127.0.0.1:8080"
    assert build_proxy({
        "proxy_type": "socks5",
        "proxy_host": "1.2.3.4",
        "proxy_port": 1080,
        "proxy_user": "alice",
        "proxy_pass": "secret",
    }) == "socks5://alice:secret@1.2.3.4:1080"


# ---------------------------------------------------------------------------
# WebRTC 模式测试
# ---------------------------------------------------------------------------

def test_webrtc_mode_custom_with_ip():
    from backend.services.browser_worker import build_fingerprint_args
    args = build_fingerprint_args({"fp_webrtc_mode": "custom", "fp_webrtc_ip": "1.2.3.4"})
    assert "--fingerprint-webrtc-ip=1.2.3.4" in args


def test_webrtc_mode_custom_without_ip():
    """mode=custom 但没填 IP，不应输出 flag（避免传空值给 cloakbrowser）。"""
    from backend.services.browser_worker import build_fingerprint_args
    args = build_fingerprint_args({"fp_webrtc_mode": "custom", "fp_webrtc_ip": ""})
    assert not any("webrtc" in a for a in args)


def test_webrtc_mode_mask():
    from backend.services.browser_worker import build_fingerprint_args
    args = build_fingerprint_args({"fp_webrtc_mode": "mask"})
    assert "--fingerprint-webrtc-ip=10.0.0.1" in args


def test_webrtc_mode_block_no_flag():
    """block 模式通过 add_init_script 注入 JS，不传 cloakbrowser flag。"""
    from backend.services.browser_worker import build_fingerprint_args
    args = build_fingerprint_args({"fp_webrtc_mode": "block"})
    assert not any("webrtc" in a for a in args)


def test_webrtc_legacy_compat_ip_without_mode():
    """旧数据：有 fp_webrtc_ip 但无 fp_webrtc_mode → 自动视为 custom。"""
    from backend.services.browser_worker import build_fingerprint_args
    args = build_fingerprint_args({"fp_webrtc_mode": "", "fp_webrtc_ip": "5.6.7.8"})
    assert "--fingerprint-webrtc-ip=5.6.7.8" in args


def test_webrtc_default_no_intervention():
    """mode 为空 + 无 IP → 不输出任何 webrtc flag。"""
    from backend.services.browser_worker import build_fingerprint_args
    args = build_fingerprint_args({"fp_webrtc_mode": "", "fp_webrtc_ip": ""})
    assert not any("webrtc" in a for a in args)


# ---------------------------------------------------------------------------
# 中继代理 URL 构建
# ---------------------------------------------------------------------------

def test_build_relay_url_none_type():
    from backend.services.browser_worker import _build_relay_url
    assert _build_relay_url({"relay_proxy_type": "none"}) is None


def test_build_relay_url_no_host():
    from backend.services.browser_worker import _build_relay_url
    assert _build_relay_url({"relay_proxy_type": "socks5", "relay_proxy_host": ""}) is None


def test_build_relay_url_basic():
    from backend.services.browser_worker import _build_relay_url
    url = _build_relay_url({
        "relay_proxy_type": "socks5",
        "relay_proxy_host": "127.0.0.1",
        "relay_proxy_port": 7897,
    })
    assert url == "socks5://127.0.0.1:7897"


def test_build_relay_url_with_credentials():
    from backend.services.browser_worker import _build_relay_url
    url = _build_relay_url({
        "relay_proxy_type": "http",
        "relay_proxy_host": "proxy.example.com",
        "relay_proxy_port": 8080,
        "relay_proxy_user": "alice",
        "relay_proxy_pass": "s3cr3t",
    })
    assert url == "http://alice:s3cr3t@proxy.example.com:8080"
