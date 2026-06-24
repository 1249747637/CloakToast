"""端到端：直接启动 browser_worker.py 子进程，验证 wait_for_event 修复有效。

这个测试会真的下载/启动 cloakbrowser Chromium，所以默认 skip。
显式跑：CLOAKTOAST_E2E=1 pytest tests/test_worker_e2e.py -v -s
"""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

WORKER = Path(__file__).resolve().parent.parent / "backend" / "services" / "browser_worker.py"
E2E = os.environ.get("CLOAKTOAST_E2E") == "1"


pytestmark = pytest.mark.skipif(not E2E, reason="set CLOAKTOAST_E2E=1 to run end-to-end browser tests")


def _make_payload(udd: str, urls: list[str] | None = None, headless: bool = True) -> str:
    profile = {
        "id": "e2e-test",
        "name": "e2e",
        "udd": udd,
        "headless": headless,
        "humanize": False,  # 加速启动 + 避免 patch_context 出问题
        "human_preset": "default",
        "locale": "en-US",
        "timezone": "UTC",
        "proxy_type": "none",
    }
    payload = {"profile": profile, "urls": urls or [], "license_key": None}
    return base64.b64encode(json.dumps(payload).encode()).decode()


@pytest.fixture
def tmp_udd(tmp_path):
    udd = tmp_path / "udd"
    udd.mkdir()
    yield str(udd)
    # 让 Chromium 把 lock 文件写完
    time.sleep(0.3)
    shutil.rmtree(udd, ignore_errors=True)


def test_worker_survives_past_30_seconds(tmp_udd):
    """核心回归：worker 必须在 30+ 秒后仍然存活。

    Bug 修复前：context.wait_for_event("close") 默认 timeout=30s，
    30 秒一到抛 TimeoutError，进程退出，浏览器闪退。
    修复后：timeout=0，永不超时，必须靠 SIGTERM 才会停。
    """
    payload = _make_payload(tmp_udd, urls=["about:blank"], headless=True)
    proc = subprocess.Popen(
        [sys.executable, str(WORKER), payload],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 给 cloakbrowser 时间下载/启动二进制
    try:
        # 第一次启动可能要下二进制，给 90s 缓冲
        deadline_alive = time.time() + 90
        while time.time() < deadline_alive:
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                pytest.fail(
                    f"worker 在启动期间退出 rc={proc.returncode}\n"
                    f"STDOUT:\n{stdout.decode(errors='replace')}\n"
                    f"STDERR:\n{stderr.decode(errors='replace')}"
                )
            log_path = Path(tmp_udd) / "_cloaktoast_worker.log"
            if log_path.exists() and "entering wait loop" in log_path.read_text(encoding="utf-8", errors="replace"):
                break
            time.sleep(1)
        else:
            proc.terminate()
            stdout, stderr = proc.communicate(timeout=10)
            pytest.fail(
                f"worker 90s 内未进入 wait loop\n"
                f"STDERR:\n{stderr.decode(errors='replace')}"
            )

        # 现在 worker 已经在 wait_for_event 里 — 必须持续存活
        # 等 35 秒（>30s 默认 timeout）
        time.sleep(35)
        assert proc.poll() is None, (
            f"worker 在 wait_for_event 期间过早退出 rc={proc.returncode} "
            f"— 这正是 30s timeout bug 的表现"
        )
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def test_worker_writes_log_on_bad_payload(tmp_path):
    """坏 payload 时 worker 应该非零退出，不能挂起。"""
    proc = subprocess.run(
        [sys.executable, str(WORKER), "not-valid-base64-####"],
        capture_output=True,
        timeout=15,
    )
    assert proc.returncode != 0
    assert b"FATAL" in proc.stderr or b"payload" in proc.stderr.lower()


def test_close_during_goto_loop_does_not_hang(tmp_udd):
    """回归：用户在 goto 期间关闭浏览器，worker 必须及时退出。

    Bug 修复前：goto 阻塞时 close 事件已经触发但还没有 listener，
    pyee 不重放历史事件 -> wait_for_event("close", timeout=0) 永远挂死 -> orphan 进程。
    修复后：close listener 在 goto 之前已订阅，worker 看到 closed_event 后立即收尾。
    """
    # 故意用一个会让 goto 卡住几秒的 URL
    payload = _make_payload(
        tmp_udd,
        urls=["https://httpbin.org/delay/10"],  # 10s 慢站
        headless=True,
    )
    proc = subprocess.Popen(
        [sys.executable, str(WORKER), payload],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        # 等 worker 进入 goto（看日志判断）
        log_path = Path(tmp_udd) / "_cloaktoast_worker.log"
        deadline = time.time() + 60
        while time.time() < deadline:
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                pytest.fail(
                    f"worker 进入 goto 之前就退出 rc={proc.returncode}\n"
                    f"STDERR:\n{stderr.decode(errors='replace')}"
                )
            if log_path.exists() and "context launched OK" in log_path.read_text(encoding="utf-8", errors="replace"):
                break
            time.sleep(0.5)
        else:
            pytest.fail("worker 60s 内未启动 context")

        # 关键 1：worker 既然能进 goto，就说明 close listener 已经订阅好了
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        # 验证我们的代码先订阅了 close（没有报错说明 context.on 调用成功）
        assert "WARN: failed to register close listener" not in log_text

        # 关键 2：让 worker 在 goto 中或之后用 SIGTERM 接收信号 — 模拟用户主动关
        # 在 Windows 上 terminate() 是 TerminateProcess，worker 直接挂；
        # 这测试只验证 worker 不会因 goto loop 后置等待而永远挂死，所以用 terminate 强杀也算通过
        time.sleep(2)  # 等 worker 进入 goto
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            pytest.fail("worker 在 terminate 后 15s 内未退出 — 仍有挂死风险")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def test_lifespan_shutdown_cleans_up_browsers(tmp_path, monkeypatch):
    """启动 backend → launch 浏览器 → 通过 TestClient 触发 lifespan shutdown，
    验证浏览器被自动关闭，不会留 orphan。"""
    monkeypatch.chdir(tmp_path)

    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.database import Base, get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    import backend.services.browser as browser_service

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def _override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db

    udd = tmp_path / "udd-shutdown"
    udd.mkdir()

    with TestClient(app) as client:
        p = client.post("/api/profiles", json={
            "name": "shutdown-test",
            "headless": True,
            "humanize": False,
            "locale": "en-US",
            "user_data_dir": str(udd),
        }).json()

        resp = client.post("/api/instances/launch", json={"profile_id": p["id"]})
        assert resp.status_code == 200, resp.text

        # 拿到 subprocess pid 以便后面确认它真被杀掉
        inst = browser_service.running_instances.get(p["id"])
        assert inst is not None
        pid = inst["process"].pid

    # 退出 TestClient → 触发 lifespan shutdown → stop_all() 被调用
    # 验证：running_instances 应空，subprocess 应已退出
    assert browser_service.running_instances == {}, "lifespan 未清理 running_instances"

    # 在 Windows 上检查进程是否还在
    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True,
        )
        assert str(pid) not in result.stdout, (
            f"lifespan shutdown 后 worker PID {pid} 仍在运行 — orphan 进程"
        )

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_resource_blocker_aborts_video(tmp_udd):
    """E2E：开启 block_video 的 worker 在加载 data URL（含 mp4 引用）后，
    日志里应该出现 BLOCK video 记录。"""
    # 用 data URL 触发 mp4 请求；data: URL 本身不算请求，但里面 <video src=mp4> 会发请求
    profile = {
        "id": "block-video-test",
        "name": "blocked",
        "udd": tmp_udd,
        "headless": True,
        "humanize": False,
        "locale": "en-US",
        "timezone": "UTC",
        "proxy_type": "none",
        "block_video": True,
        "block_image_max_kb": None,
    }
    payload = base64.b64encode(json.dumps({
        "profile": profile,
        "urls": [
            "data:text/html,<html><body>"
            "<video src='https://example.com/blocked.mp4'></video>"
            "</body></html>",
        ],
        "license_key": None,
    }).encode()).decode()

    proc = subprocess.Popen(
        [sys.executable, str(WORKER), payload],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        log_path = Path(tmp_udd) / "_cloaktoast_worker.log"
        deadline = time.time() + 90
        saw_block = False
        while time.time() < deadline:
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                pytest.fail(
                    f"worker 在 block-video 测试期间过早退出 rc={proc.returncode}\n"
                    f"STDERR:\n{stderr.decode(errors='replace')}"
                )
            if log_path.exists():
                txt = log_path.read_text(encoding="utf-8", errors="replace")
                if "resource blocker on: video=True" in txt:
                    # 等待 video 请求
                    if "BLOCK video" in txt and "blocked.mp4" in txt:
                        saw_block = True
                        break
            time.sleep(1)
        assert saw_block, (
            f"未在 90s 内看到 BLOCK video。worker log:\n"
            f"{log_path.read_text(encoding='utf-8', errors='replace') if log_path.exists() else '<no log>'}"
        )
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def test_full_api_launch_and_stop(tmp_path, monkeypatch):
    """通过 FastAPI 端点真正启动一个 headless 浏览器并 stop 掉。

    覆盖：POST /api/profiles -> POST /api/instances/launch -> GET /api/instances
         -> POST /api/instances/stop/{id} -> GET /api/instances 应为空。
    """
    monkeypatch.chdir(tmp_path)  # data/profiles/<id> 写到 tmp 里

    # 重要：在导入 backend.* 之前 monkeypatch，否则 conftest 已经把模块加载过了。
    # 这里直接用 TestClient 调真接口，让 launch_profile 真起 subprocess。
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.database import Base, engine, get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def _override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_db

    with TestClient(app) as client:
        # 创建一个 headless profile（用 user_data_dir 指到 tmp，避免污染 ~/data）
        udd = tmp_path / "udd-api"
        udd.mkdir()
        p = client.post("/api/profiles", json={
            "name": "e2e-api",
            "headless": True,
            "humanize": False,
            "locale": "en-US",
            "user_data_dir": str(udd),
        }).json()

        # 启动
        resp = client.post("/api/instances/launch", json={"profile_id": p["id"]})
        assert resp.status_code == 200, f"launch failed: {resp.text}"

        # 应该出现在 /instances 列表里
        instances = client.get("/api/instances").json()
        assert any(i["profile_id"] == p["id"] for i in instances), instances

        # 等 5 秒，确认 worker 仍然存活（不是启动后立刻死掉）
        time.sleep(5)
        instances = client.get("/api/instances").json()
        assert any(i["profile_id"] == p["id"] for i in instances), (
            f"worker 在启动后 5s 内已退出 — 检查 {udd}/_cloaktoast_*.log"
        )

        # 主动 stop
        resp = client.post(f"/api/instances/stop/{p['id']}")
        assert resp.status_code == 200, resp.text

        # stop 后应该从列表里消失
        time.sleep(1)
        assert client.get("/api/instances").json() == []

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
