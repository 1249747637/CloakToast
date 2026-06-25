import asyncio
import os
import signal
import subprocess
import sys
import threading
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from ..config import get_config, save_config, get_license_key
from ..schemas import SystemInfo, LicenseRequest

router = APIRouter()


def _get_installed_version() -> str | None:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "cloakbrowser", "info"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            if "version" in line.lower():
                parts = line.split()
                if parts:
                    return parts[-1]
        return result.stdout.strip() or None
    except Exception:
        return None


@router.get("/info", response_model=SystemInfo)
def system_info():
    return SystemInfo(
        installed_version=_get_installed_version(),
        license_key=get_license_key(),
    )


@router.post("/update")
async def update_cloakbrowser():
    async def event_stream():
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "cloakbrowser", "update",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in process.stdout:
            text = line.decode(errors="replace").rstrip()
            yield f"data: {text}\n\n"
        await process.wait()
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/shutdown")
async def shutdown():
    async def _do():
        await asyncio.sleep(0.4)   # 让 HTTP 响应先发出去
        from ..services.browser import stop_all
        try:
            await stop_all()
        except Exception:
            pass
        os._exit(0)                # 强制退出，Windows 下最可靠
    asyncio.create_task(_do())
    return {"ok": True}


@router.put("/license")
def save_license(body: LicenseRequest):
    cfg = get_config()
    cfg["license_key"] = body.license_key
    save_config(cfg)
    return {"ok": True}
