import asyncio
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# profile_id -> {
#   process: asyncio.subprocess.Process,
#   started_at: datetime,
#   log_file: file handle,
#   log_path: str,
#   state: 'running' | 'stopping',
#   watcher: asyncio.Task | None,
# }
running_instances: dict[str, dict] = {}

# 最近退出的 worker — 让 UI 能看到 "crashed (rc=2)" 而不是 "悄无声息地消失"。
# 不持久化，进程重启就丢，但保留期间足够让用户在轮询周期内看到状态。
recent_exits: list[dict] = []
RECENT_EXITS_MAX = 50

WORKER = Path(__file__).parent / "browser_worker.py"

# 启动后多少秒还活着才算"启动成功"。低于这个值就抛错给前端。
# 之所以要等：cloakbrowser 第一次跑要做 license 校验 + 二进制下载/校验，
# 但通常在本地缓存命中后 1s 内 process 已经在跑 Chromium 了；
# 如果在这个时间窗口内 returncode 非 None，说明 worker 因配置/许可/参数错误立刻退出。
STARTUP_PROBE_SECONDS = 1.5

# 每个 profile 一把 asyncio.Lock，序列化 launch / stop，避免 TOCTOU 双开撞 SingletonLock。
_launch_locks: dict[str, asyncio.Lock] = {}


def _lock_for(profile_id: str) -> asyncio.Lock:
    lock = _launch_locks.get(profile_id)
    if lock is None:
        lock = asyncio.Lock()
        _launch_locks[profile_id] = lock
    return lock


def _close_log_file(inst: dict) -> None:
    log_file = inst.get("log_file")
    if log_file:
        try:
            log_file.close()
        except Exception:
            pass


def _record_exit(profile_id: str, inst: dict, returncode: int | None) -> None:
    recent_exits.append({
        "profile_id": profile_id,
        "started_at": inst["started_at"].isoformat(),
        "stopped_at": datetime.now(timezone.utc).isoformat(),
        "returncode": returncode,
        "log_path": inst.get("log_path"),
    })
    # ring buffer
    if len(recent_exits) > RECENT_EXITS_MAX:
        del recent_exits[: len(recent_exits) - RECENT_EXITS_MAX]


def _cleanup() -> None:
    """惰性清理：把已退出且没人擦干净的 entry 移走。
    通常 _watch 协程会负责清理；这是兜底（例如 watcher 因异常未跑或被取消）。"""
    to_remove = [
        pid for pid, inst in running_instances.items()
        if inst["process"].returncode is not None
    ]
    for pid in to_remove:
        inst = running_instances.pop(pid)
        _close_log_file(inst)
        _record_exit(pid, inst, inst["process"].returncode)


def is_running(profile_id: str) -> bool:
    """state == 'stopping' 也视为占用：在 stop_profile 完成 terminate+wait 之前，
    Chromium 仍持有 user_data_dir 的 SingletonLock，不能让新 launch 进来。"""
    _cleanup()
    return profile_id in running_instances


def get_running_instances() -> dict:
    _cleanup()
    return {
        pid: {
            "profile_id": pid,
            "started_at": inst["started_at"].isoformat(),
            "state": inst.get("state", "running"),
        }
        for pid, inst in running_instances.items()
    }


def get_recent_exits() -> list[dict]:
    return list(recent_exits)


def _serialize_profile(profile_dict: dict, udd: str) -> dict:
    """SQLAlchemy 模型字段可能包含 datetime，要先序列化才能 json.dumps。"""
    def _to_jsonable(v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    serialized = {k: _to_jsonable(v) for k, v in profile_dict.items()}
    serialized["udd"] = udd
    return serialized


async def _watch(profile_id: str, process: asyncio.subprocess.Process) -> None:
    """Worker 一退出就把 entry 移走，同时记录 returncode 到 recent_exits。
    比惰性 _cleanup() 实时；UI 5s 轮询能立刻反映崩溃状态。"""
    try:
        rc = await process.wait()
    except asyncio.CancelledError:
        # stop_profile 取消了我们 — 由 stop_profile 自己负责清理
        return
    except Exception:
        return

    inst = running_instances.pop(profile_id, None)
    if inst is None:
        return  # 已经被 stop_profile 清掉
    _close_log_file(inst)
    _record_exit(profile_id, inst, rc)


async def launch_profile(
    profile_dict: dict,
    bookmarks: list[dict],
) -> None:
    profile_id = profile_dict["id"]

    async with _lock_for(profile_id):
        # 在锁内再检查一次 — 防止 TOCTOU 双开
        if profile_id in running_instances:
            raise ValueError(f"Profile {profile_id} is already running")

        udd = profile_dict.get("user_data_dir") or str(Path("data/profiles") / profile_id)
        Path(udd).mkdir(parents=True, exist_ok=True)

        serializable_profile = _serialize_profile(profile_dict, udd)

        from ..config import get_license_key
        license_key = get_license_key()

        payload = base64.b64encode(
            json.dumps(
                {"profile": serializable_profile, "bookmarks": bookmarks, "license_key": license_key}
            ).encode()
        ).decode()

        env = os.environ.copy()
        if license_key:
            env["CLOAKBROWSER_LICENSE_KEY"] = license_key

        # 把 worker 的 stdout/stderr 重定向到 udd 下的日志文件 — 用户排查闪退时直接看，
        # 也避免子进程 stderr buffer 填满导致写阻塞 / SIGPIPE。
        log_path = Path(udd) / "_cloaktoast_subprocess.log"
        log_file = log_path.open("a", encoding="utf-8", errors="replace")
        log_file.write(
            f"\n========== launch @ {datetime.now(timezone.utc).isoformat()} ==========\n"
        )
        log_file.flush()

        creation_flags = 0
        if sys.platform == "win32":
            # 把 worker 放到新进程组 — 当 uvicorn 收到 Ctrl-C 时浏览器不会被一起干掉。
            # 主动 stop 时仍可用 process.terminate() 关掉。
            import subprocess as _sp
            creation_flags = getattr(_sp, "CREATE_NEW_PROCESS_GROUP", 0)

        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                str(WORKER),
                payload,
                env=env,
                stdout=log_file,
                stderr=log_file,
                creationflags=creation_flags,
            )
        except Exception:
            log_file.close()
            raise

        inst = {
            "process": process,
            "started_at": datetime.now(timezone.utc),
            "log_file": log_file,
            "log_path": str(log_path),
            "state": "running",
            "watcher": None,
        }
        running_instances[profile_id] = inst

        # 给 worker 一点时间起来 — 如果它在 STARTUP_PROBE_SECONDS 内退出，
        # 说明配置/许可/参数有问题，立刻把错误抛给前端而不是默默"成功"。
        try:
            await asyncio.wait_for(process.wait(), timeout=STARTUP_PROBE_SECONDS)
        except asyncio.TimeoutError:
            # 期望路径：超时 = worker 还活着 = 启动成功。挂上 watcher 然后返回。
            inst["watcher"] = asyncio.create_task(_watch(profile_id, process))
            return

        # worker 已退出 — 启动失败
        rc = process.returncode
        running_instances.pop(profile_id, None)
        _close_log_file(inst)
        _record_exit(profile_id, inst, rc)

        tail = _read_log_tail(log_path, max_chars=800)
        raise ValueError(
            f"浏览器启动失败（exit code={rc}）。最近日志：\n{tail}\n完整日志: {log_path}"
        )


def _read_log_tail(path: Path, max_chars: int = 800) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"<无法读取日志 {path}: {e}>"
    return data[-max_chars:] if len(data) > max_chars else data


async def stop_profile(profile_id: str) -> None:
    async with _lock_for(profile_id):
        inst = running_instances.get(profile_id)
        if inst is None:
            raise ValueError(f"Profile {profile_id} is not running")

        inst["state"] = "stopping"
        process = inst["process"]
        watcher: asyncio.Task | None = inst.get("watcher")

        # 取消 watcher：我们这里手动 wait + 写 recent_exits，不让 _watch 重复写
        if watcher is not None:
            watcher.cancel()
            try:
                await watcher
            except (asyncio.CancelledError, Exception):
                pass

        try:
            try:
                process.terminate()
            except ProcessLookupError:
                pass  # 已经死了，往下走

            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(process.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    # 真杀不动 — 保留 entry 让用户看到 "stopping" 卡住
                    return

            # 确认退出 — 把 entry 移走
            running_instances.pop(profile_id, None)
            _close_log_file(inst)
            _record_exit(profile_id, inst, process.returncode)
        except Exception:
            # 任何意外都不要把 entry 留在 "stopping" 状态吊死 — 移走它
            running_instances.pop(profile_id, None)
            _close_log_file(inst)
            _record_exit(profile_id, inst, process.returncode)
            raise


async def stop_all() -> None:
    """供 FastAPI lifespan 在关停时调用 — 干净地关掉所有浏览器。"""
    pids = list(running_instances.keys())
    if not pids:
        return
    await asyncio.gather(
        *(stop_profile(pid) for pid in pids),
        return_exceptions=True,
    )
