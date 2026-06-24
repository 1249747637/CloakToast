import asyncio
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# profile_id -> {process, started_at, task_id}
running_instances: dict[str, dict] = {}

WORKER = Path(__file__).parent / "browser_worker.py"


def _cleanup():
    to_remove = [
        pid for pid, inst in running_instances.items()
        if inst["process"].returncode is not None
    ]
    for pid in to_remove:
        del running_instances[pid]


def is_running(profile_id: str) -> bool:
    _cleanup()
    return profile_id in running_instances


def get_running_instances() -> dict:
    _cleanup()
    return {
        pid: {
            "profile_id": pid,
            "started_at": inst["started_at"].isoformat(),
            "task_id": inst["task_id"],
        }
        for pid, inst in running_instances.items()
    }


async def launch_profile(profile_dict: dict, task_id: Optional[str], urls: list[str]) -> None:
    profile_id = profile_dict["id"]
    if is_running(profile_id):
        raise ValueError(f"Profile {profile_id} is already running")

    udd = profile_dict.get("user_data_dir") or str(Path("data/profiles") / profile_id)
    Path(udd).mkdir(parents=True, exist_ok=True)

    # Serialize profile_dict: convert datetime objects to ISO strings so the
    # payload is JSON-serialisable (created_at / updated_at come from SQLAlchemy).
    def _serialize(v):
        if isinstance(v, datetime):
            return v.isoformat()
        return v

    serializable_profile = {k: _serialize(v) for k, v in profile_dict.items()}
    serializable_profile["udd"] = udd

    payload = base64.b64encode(
        json.dumps({"profile": serializable_profile, "urls": urls}).encode()
    ).decode()

    from ..config import get_license_key
    env = os.environ.copy()
    license_key = get_license_key()
    if license_key:
        env["CLOAKBROWSER_LICENSE_KEY"] = license_key

    process = await asyncio.create_subprocess_exec(
        sys.executable, str(WORKER), payload, env=env
    )

    running_instances[profile_id] = {
        "process": process,
        "started_at": datetime.utcnow(),
        "task_id": task_id,
    }


async def stop_profile(profile_id: str) -> None:
    if not is_running(profile_id):
        raise ValueError(f"Profile {profile_id} is not running")
    inst = running_instances.pop(profile_id)
    inst["process"].terminate()
    try:
        await asyncio.wait_for(inst["process"].wait(), timeout=5.0)
    except asyncio.TimeoutError:
        inst["process"].kill()
