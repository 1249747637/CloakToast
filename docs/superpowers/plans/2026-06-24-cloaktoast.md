# CloakToast WebUI 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 CloakToast，一个基于 CloakBrowser 的本地指纹浏览器实例管理 WebUI，支持 Profile 管理、URL 任务追踪、浏览器进程生命周期控制。

**Architecture:** FastAPI 后端提供 REST API，SQLite 持久化数据，Python subprocess 通过固定 worker 脚本管理 CloakBrowser 进程；React + TypeScript + Ant Design 前端编译为静态文件由 FastAPI 直接 serve，单进程单命令启动。

**Tech Stack:** Python 3.10+, FastAPI 0.111+, SQLAlchemy 2.x, SQLite, pytest 8+, httpx; React 18, TypeScript 5, Ant Design 5, Vite 5, React Router 6.

## Global Constraints

- Python >= 3.10（类型注解使用 `str | None` 语法）
- 服务端口：`8765`，访问地址 `http://localhost:8765`
- 数据目录：项目根下 `./data/`，含 `cloaktoast.db` 和 `profiles/` 子目录
- License Key 存储在 `./data/config.json`，key 为 `"license_key"`
- 所有 API 路径以 `/api/` 为前缀
- Profile ID 使用 `uuid.uuid4()` 字符串，同时作为 `data/profiles/{id}/` 目录名
- 前端编译输出到 `frontend/dist/`
- JSON 列（extension_paths, extra_args, urls）在 SQLite 中存为 TEXT，读写时序列化/反序列化
- 无认证，所有端点公开
- 主平台 Windows，代码兼容 Linux/macOS

---

## 文件结构总览

```
CloakToast/
├── backend/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── config.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── profiles.py
│   │   ├── instances.py
│   │   ├── tasks.py
│   │   └── system.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── browser.py
│   │   └── browser_worker.py
│   └── requirements.txt
├── tests/
│   ├── conftest.py
│   ├── test_profiles.py
│   ├── test_instances.py
│   ├── test_tasks.py
│   └── test_system.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── types.ts
│       ├── api/
│       │   ├── client.ts
│       │   ├── profiles.ts
│       │   ├── instances.ts
│       │   ├── tasks.ts
│       │   └── system.ts
│       ├── components/
│       │   └── StatusBadge.tsx
│       └── pages/
│           ├── Profiles/
│           │   ├── index.tsx
│           │   ├── ProfileCard.tsx
│           │   └── ProfileForm.tsx
│           ├── Tasks/
│           │   ├── index.tsx
│           │   └── TaskDetail.tsx
│           └── Settings/
│               └── index.tsx
├── start.bat
└── start.sh
```

---

### Task 1: 后端基础脚手架 + 数据库

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/database.py`
- Create: `backend/models.py`
- Create: `backend/schemas.py`
- Create: `backend/routers/__init__.py`
- Create: `backend/services/__init__.py`
- Create: `backend/main.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Produces: `get_db()` session 依赖，`Base`，`Profile`/`URLTask`/`TaskProfile` ORM 模型，所有 Pydantic schema 类，FastAPI `app` 实例

- [ ] **Step 1: 写 requirements.txt**

```
fastapi==0.111.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.30
httpx==0.27.0
pytest==8.2.0
pytest-asyncio==0.23.7
```

- [ ] **Step 2: 写 backend/config.py**

```python
import json
from pathlib import Path

CONFIG_PATH = Path("data/config.json")

def get_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}

def save_config(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def get_license_key() -> str | None:
    return get_config().get("license_key")
```

- [ ] **Step 3: 写 backend/database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path

Path("data").mkdir(exist_ok=True)
DATABASE_URL = "sqlite:///./data/cloaktoast.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: 写 backend/models.py**

```python
import json
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, Float, Text, DateTime
from sqlalchemy.types import TypeDecorator
from .database import Base

class JSONList(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return json.dumps(value or [])

    def process_result_value(self, value, dialect):
        return json.loads(value) if value else []


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    color_tag = Column(String, default="#1677ff")
    notes = Column(Text, default="")
    proxy_type = Column(String, default="none")
    proxy_host = Column(String, default="")
    proxy_port = Column(Integer, nullable=True)
    proxy_user = Column(String, default="")
    proxy_pass = Column(String, default="")
    timezone = Column(String, default="")
    locale = Column(String, default="zh-CN")
    headless = Column(Boolean, default=False)
    humanize = Column(Boolean, default=True)
    human_preset = Column(String, default="default")
    fingerprint_seed = Column(Integer, nullable=True)
    fp_noise_enabled = Column(Boolean, default=True)
    fp_platform = Column(String, default="")
    fp_hardware_concurrency = Column(Integer, nullable=True)
    fp_device_memory = Column(Integer, nullable=True)
    fp_screen_width = Column(Integer, nullable=True)
    fp_screen_height = Column(Integer, nullable=True)
    fp_taskbar_height = Column(Integer, nullable=True)
    fp_gpu_vendor = Column(String, default="")
    fp_gpu_renderer = Column(String, default="")
    fp_webrtc_ip = Column(String, default="")
    fp_location_lat = Column(Float, nullable=True)
    fp_location_lng = Column(Float, nullable=True)
    fp_storage_quota = Column(Integer, nullable=True)
    fp_fonts_dir = Column(String, default="")
    user_agent = Column(String, default="")
    fp_brand = Column(String, default="")
    fp_brand_version = Column(String, default="")
    fp_platform_version = Column(String, default="")
    extension_paths = Column(JSONList, default=list)
    user_data_dir = Column(String, default="")
    cdp_port = Column(Integer, nullable=True)
    extra_args = Column(JSONList, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class URLTask(Base):
    __tablename__ = "url_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    urls = Column(JSONList, default=list)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class TaskProfile(Base):
    __tablename__ = "task_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, nullable=False)
    profile_id = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending/done/skipped
    notes = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 5: 写 backend/schemas.py**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ProfileBase(BaseModel):
    name: str
    color_tag: str = "#1677ff"
    notes: str = ""
    proxy_type: str = "none"
    proxy_host: str = ""
    proxy_port: Optional[int] = None
    proxy_user: str = ""
    proxy_pass: str = ""
    timezone: str = ""
    locale: str = "zh-CN"
    headless: bool = False
    humanize: bool = True
    human_preset: str = "default"
    fingerprint_seed: Optional[int] = None
    fp_noise_enabled: bool = True
    fp_platform: str = ""
    fp_hardware_concurrency: Optional[int] = None
    fp_device_memory: Optional[int] = None
    fp_screen_width: Optional[int] = None
    fp_screen_height: Optional[int] = None
    fp_taskbar_height: Optional[int] = None
    fp_gpu_vendor: str = ""
    fp_gpu_renderer: str = ""
    fp_webrtc_ip: str = ""
    fp_location_lat: Optional[float] = None
    fp_location_lng: Optional[float] = None
    fp_storage_quota: Optional[int] = None
    fp_fonts_dir: str = ""
    user_agent: str = ""
    fp_brand: str = ""
    fp_brand_version: str = ""
    fp_platform_version: str = ""
    extension_paths: list[str] = []
    user_data_dir: str = ""
    cdp_port: Optional[int] = None
    extra_args: list[str] = []


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    pass


class ProfileResponse(ProfileBase):
    id: str
    created_at: datetime
    updated_at: datetime
    is_running: bool = False
    running_since: Optional[datetime] = None

    model_config = {"from_attributes": True}


class URLTaskBase(BaseModel):
    name: str
    urls: list[str] = []
    notes: str = ""


class URLTaskCreate(URLTaskBase):
    pass


class URLTaskUpdate(URLTaskBase):
    pass


class URLTaskResponse(URLTaskBase):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TaskProfileResponse(BaseModel):
    id: str
    task_id: str
    profile_id: str
    status: str
    notes: str
    updated_at: datetime
    profile: Optional[ProfileResponse] = None

    model_config = {"from_attributes": True}


class URLTaskDetail(URLTaskResponse):
    profiles: list[TaskProfileResponse] = []
    total_profiles: int = 0
    done_count: int = 0


class AddProfilesRequest(BaseModel):
    profile_ids: list[str]


class UpdateStatusRequest(BaseModel):
    status: str  # pending/done/skipped
    notes: str = ""


class LaunchRequest(BaseModel):
    profile_id: str
    task_id: Optional[str] = None


class SystemInfo(BaseModel):
    installed_version: Optional[str] = None
    license_key: Optional[str] = None


class LicenseRequest(BaseModel):
    license_key: str
```

- [ ] **Step 6: 写 backend/main.py 骨架**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from .database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="CloakToast")

from .routers import profiles, instances, tasks, system

app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])
app.include_router(instances.router, prefix="/api/instances", tags=["instances"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(system.router, prefix="/api/system", tags=["system"])

DIST = Path(__file__).parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(str(DIST / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8765, reload=False)
```

- [ ] **Step 7: 写 backend/routers/__init__.py 和 backend/services/__init__.py**（均为空文件）

- [ ] **Step 8: 写 tests/conftest.py**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, get_db
from backend.main import app

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 9: 验证数据库初始化**

```bash
cd E:/Code/CloakToast
pip install -r backend/requirements.txt
python -c "from backend.database import Base, engine; Base.metadata.create_all(bind=engine); print('OK')"
```

期望输出：`OK`

- [ ] **Step 10: Commit**

```bash
git init
git add backend/ tests/conftest.py
git commit -m "feat: backend scaffolding, database models and schemas"
```

---

### Task 2: Profile CRUD API

**Files:**
- Create: `backend/routers/profiles.py`
- Create: `tests/test_profiles.py`

**Interfaces:**
- Consumes: `get_db()`, `Profile` model, `ProfileCreate`/`ProfileUpdate`/`ProfileResponse` schemas
- Produces: `GET/POST/PUT/DELETE /api/profiles`, `POST /api/profiles/{id}/duplicate`

- [ ] **Step 1: 写 tests/test_profiles.py**

```python
def test_create_profile(client):
    resp = client.post("/api/profiles", json={"name": "Test Profile"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Profile"
    assert "id" in data
    assert data["is_running"] is False

def test_list_profiles(client):
    client.post("/api/profiles", json={"name": "P1"})
    client.post("/api/profiles", json={"name": "P2"})
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

def test_get_profile(client):
    created = client.post("/api/profiles", json={"name": "P"}).json()
    resp = client.get(f"/api/profiles/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "P"

def test_update_profile(client):
    created = client.post("/api/profiles", json={"name": "Old"}).json()
    resp = client.put(f"/api/profiles/{created['id']}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"

def test_delete_profile(client):
    created = client.post("/api/profiles", json={"name": "Del"}).json()
    resp = client.delete(f"/api/profiles/{created['id']}")
    assert resp.status_code == 200
    assert client.get(f"/api/profiles/{created['id']}").status_code == 404

def test_duplicate_profile(client):
    created = client.post("/api/profiles", json={"name": "Original"}).json()
    resp = client.post(f"/api/profiles/{created['id']}/duplicate")
    assert resp.status_code == 200
    dup = resp.json()
    assert dup["name"] == "Original (副本)"
    assert dup["id"] != created["id"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_profiles.py -v
```

期望：FAILED（router 未实现）

- [ ] **Step 3: 写 backend/routers/profiles.py**

```python
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Profile
from ..schemas import ProfileCreate, ProfileUpdate, ProfileResponse
from ..services.browser import is_running, get_running_instances

router = APIRouter()

def _enrich(profile: Profile) -> dict:
    data = ProfileResponse.model_validate(profile).model_dump()
    inst = get_running_instances()
    if profile.id in inst:
        data["is_running"] = True
        data["running_since"] = datetime.fromisoformat(inst[profile.id]["started_at"])
    return data

@router.get("", response_model=list[ProfileResponse])
def list_profiles(db: Session = Depends(get_db)):
    profiles = db.query(Profile).order_by(Profile.created_at.desc()).all()
    return [_enrich(p) for p in profiles]

@router.post("", response_model=ProfileResponse)
def create_profile(body: ProfileCreate, db: Session = Depends(get_db)):
    p = Profile(id=str(uuid.uuid4()), **body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _enrich(p)

@router.get("/{profile_id}", response_model=ProfileResponse)
def get_profile(profile_id: str, db: Session = Depends(get_db)):
    p = db.get(Profile, profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    return _enrich(p)

@router.put("/{profile_id}", response_model=ProfileResponse)
def update_profile(profile_id: str, body: ProfileUpdate, db: Session = Depends(get_db)):
    p = db.get(Profile, profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return _enrich(p)

@router.delete("/{profile_id}")
def delete_profile(profile_id: str, db: Session = Depends(get_db)):
    p = db.get(Profile, profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    if is_running(profile_id):
        raise HTTPException(400, "Stop the instance before deleting")
    db.delete(p)
    db.commit()
    return {"ok": True}

@router.post("/{profile_id}/duplicate", response_model=ProfileResponse)
def duplicate_profile(profile_id: str, db: Session = Depends(get_db)):
    p = db.get(Profile, profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    data = ProfileCreate.model_validate(p).model_dump()
    data["name"] = f"{p.name} (副本)"
    new_p = Profile(id=str(uuid.uuid4()), **data)
    db.add(new_p)
    db.commit()
    db.refresh(new_p)
    return _enrich(new_p)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_profiles.py -v
```

期望：全部 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/routers/profiles.py tests/test_profiles.py
git commit -m "feat: Profile CRUD API"
```

---

### Task 3: Browser Worker + 进程管理服务 + Instances API

**Files:**
- Create: `backend/services/browser_worker.py`
- Create: `backend/services/browser.py`
- Create: `backend/routers/instances.py`
- Create: `tests/test_instances.py`

**Interfaces:**
- Produces: `is_running(profile_id)`, `get_running_instances()`, `launch_profile(profile_dict, task_id, urls)`, `stop_profile(profile_id)`
- Produces: `POST /api/instances/launch`, `POST /api/instances/stop/{profile_id}`, `GET /api/instances`

- [ ] **Step 1: 写 backend/services/browser_worker.py**

```python
"""
独立子进程脚本，由 browser.py 以 subprocess 启动。
用法: python browser_worker.py <base64_json_payload>
"""
import sys
import json
import base64


def build_fingerprint_args(profile: dict) -> list[str]:
    args = []
    if profile.get("fingerprint_seed"):
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
    if profile.get("fp_webrtc_ip"):
        args.append(f"--fingerprint-webrtc-ip={profile['fp_webrtc_ip']}")
    lat = profile.get("fp_location_lat")
    lng = profile.get("fp_location_lng")
    if lat is not None and lng is not None:
        args.append(f"--fingerprint-location={lat},{lng}")
    if profile.get("fp_storage_quota"):
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


def build_proxy(profile: dict) -> str | None:
    if profile.get("proxy_type", "none") == "none" or not profile.get("proxy_host"):
        return None
    creds = ""
    if profile.get("proxy_user"):
        creds = f"{profile['proxy_user']}:{profile['proxy_pass']}@"
    return f"{profile['proxy_type']}://{creds}{profile['proxy_host']}:{profile['proxy_port']}"


def main():
    payload = json.loads(base64.b64decode(sys.argv[1]))
    profile = payload["profile"]
    urls = payload.get("urls", [])

    from cloakbrowser import launch_persistent_context

    context = launch_persistent_context(
        user_data_dir=profile["udd"],
        proxy=build_proxy(profile),
        timezone=profile.get("timezone") or None,
        locale=profile.get("locale") or None,
        humanize=profile.get("humanize", True),
        human_preset=profile.get("human_preset", "default"),
        headless=profile.get("headless", False),
        user_agent=profile.get("user_agent") or None,
        args=build_fingerprint_args(profile),
    )

    for url in urls:
        page = context.new_page()
        page.goto(url)

    context.wait_for_close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 写 backend/services/browser.py**

```python
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

    payload = base64.b64encode(
        json.dumps({"profile": {**profile_dict, "udd": udd}, "urls": urls}).encode()
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
```

- [ ] **Step 3: 写 tests/test_instances.py**

```python
from unittest.mock import AsyncMock, patch, MagicMock

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

def test_launch_profile(client):
    p = client.post("/api/profiles", json={"name": "P"}).json()
    mock_process = MagicMock()
    mock_process.returncode = None
    with patch(
        "backend.services.browser.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=mock_process,
    ):
        resp = client.post("/api/instances/launch", json={"profile_id": p["id"]})
    assert resp.status_code == 200
    instances = client.get("/api/instances").json()
    assert len(instances) == 1
    assert instances[0]["profile_id"] == p["id"]
```

- [ ] **Step 4: 写 backend/routers/instances.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Profile
from ..schemas import LaunchRequest
from ..services import browser

router = APIRouter()

@router.get("")
def list_instances():
    return list(browser.get_running_instances().values())

@router.post("/launch")
async def launch(body: LaunchRequest, db: Session = Depends(get_db)):
    p = db.get(Profile, body.profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    if browser.is_running(body.profile_id):
        raise HTTPException(400, "Already running")

    task_urls: list[str] = []
    if body.task_id:
        from ..models import URLTask
        task = db.get(URLTask, body.task_id)
        if task:
            task_urls = task.urls or []

    profile_dict = {c.name: getattr(p, c.name) for c in p.__table__.columns}
    try:
        await browser.launch_profile(profile_dict, body.task_id, task_urls)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}

@router.post("/stop/{profile_id}")
async def stop(profile_id: str):
    if not browser.is_running(profile_id):
        raise HTTPException(400, "Not running")
    try:
        await browser.stop_profile(profile_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/test_instances.py -v
```

期望：全部 PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/services/ backend/routers/instances.py tests/test_instances.py
git commit -m "feat: browser worker, process manager, instances API"
```

---

### Task 4: URL Tasks + TaskProfile API

**Files:**
- Create: `backend/routers/tasks.py`
- Create: `tests/test_tasks.py`

**Interfaces:**
- Consumes: `URLTask`, `TaskProfile`, `Profile` models；所有 task schemas
- Produces: 完整 tasks API（列表、详情、CRUD、进度管理）

- [ ] **Step 1: 写 tests/test_tasks.py**

```python
def test_create_task(client):
    resp = client.post("/api/tasks", json={"name": "Task A", "urls": ["https://a.com"]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Task A"
    assert data["urls"] == ["https://a.com"]

def test_task_detail_with_profiles(client):
    task = client.post("/api/tasks", json={"name": "T"}).json()
    p1 = client.post("/api/profiles", json={"name": "P1"}).json()
    p2 = client.post("/api/profiles", json={"name": "P2"}).json()
    client.post(f"/api/tasks/{task['id']}/profiles", json={"profile_ids": [p1["id"], p2["id"]]})
    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["total_profiles"] == 2
    assert detail["done_count"] == 0

def test_update_profile_status(client):
    task = client.post("/api/tasks", json={"name": "T"}).json()
    p = client.post("/api/profiles", json={"name": "P"}).json()
    client.post(f"/api/tasks/{task['id']}/profiles", json={"profile_ids": [p["id"]]})
    client.patch(f"/api/tasks/{task['id']}/profiles/{p['id']}/status", json={"status": "done"})
    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["done_count"] == 1

def test_remove_profile_from_task(client):
    task = client.post("/api/tasks", json={"name": "T"}).json()
    p = client.post("/api/profiles", json={"name": "P"}).json()
    client.post(f"/api/tasks/{task['id']}/profiles", json={"profile_ids": [p["id"]]})
    client.delete(f"/api/tasks/{task['id']}/profiles/{p['id']}")
    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["total_profiles"] == 0

def test_delete_task(client):
    task = client.post("/api/tasks", json={"name": "T"}).json()
    client.delete(f"/api/tasks/{task['id']}")
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_tasks.py -v
```

- [ ] **Step 3: 写 backend/routers/tasks.py**

```python
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import URLTask, TaskProfile, Profile
from ..schemas import (
    URLTaskCreate, URLTaskUpdate, URLTaskResponse, URLTaskDetail,
    TaskProfileResponse, AddProfilesRequest, UpdateStatusRequest,
    ProfileResponse,
)
from ..services.browser import get_running_instances

router = APIRouter()

def _build_detail(task: URLTask, db: Session) -> dict:
    tps = db.query(TaskProfile).filter(TaskProfile.task_id == task.id).all()
    inst = get_running_instances()
    profiles_data = []
    done = 0
    for tp in tps:
        p = db.get(Profile, tp.profile_id)
        pr = None
        if p:
            pd = ProfileResponse.model_validate(p).model_dump()
            if p.id in inst:
                pd["is_running"] = True
                pd["running_since"] = datetime.fromisoformat(inst[p.id]["started_at"])
            pr = pd
        if tp.status == "done":
            done += 1
        profiles_data.append({
            "id": tp.id, "task_id": tp.task_id, "profile_id": tp.profile_id,
            "status": tp.status, "notes": tp.notes, "updated_at": tp.updated_at,
            "profile": pr,
        })
    base = URLTaskResponse.model_validate(task).model_dump()
    return {**base, "profiles": profiles_data, "total_profiles": len(tps), "done_count": done}

@router.get("", response_model=list[URLTaskResponse])
def list_tasks(db: Session = Depends(get_db)):
    return db.query(URLTask).order_by(URLTask.created_at.desc()).all()

@router.post("", response_model=URLTaskResponse)
def create_task(body: URLTaskCreate, db: Session = Depends(get_db)):
    t = URLTask(id=str(uuid.uuid4()), **body.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

@router.get("/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    t = db.get(URLTask, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    return _build_detail(t, db)

@router.put("/{task_id}", response_model=URLTaskResponse)
def update_task(task_id: str, body: URLTaskUpdate, db: Session = Depends(get_db)):
    t = db.get(URLTask, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t

@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    t = db.get(URLTask, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    db.query(TaskProfile).filter(TaskProfile.task_id == task_id).delete()
    db.delete(t)
    db.commit()
    return {"ok": True}

@router.post("/{task_id}/profiles")
def add_profiles(task_id: str, body: AddProfilesRequest, db: Session = Depends(get_db)):
    t = db.get(URLTask, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    existing = {
        tp.profile_id
        for tp in db.query(TaskProfile).filter(TaskProfile.task_id == task_id).all()
    }
    for pid in body.profile_ids:
        if pid not in existing:
            db.add(TaskProfile(id=str(uuid.uuid4()), task_id=task_id, profile_id=pid))
    db.commit()
    return {"ok": True}

@router.delete("/{task_id}/profiles/{profile_id}")
def remove_profile(task_id: str, profile_id: str, db: Session = Depends(get_db)):
    tp = (
        db.query(TaskProfile)
        .filter(TaskProfile.task_id == task_id, TaskProfile.profile_id == profile_id)
        .first()
    )
    if not tp:
        raise HTTPException(404, "Not found")
    db.delete(tp)
    db.commit()
    return {"ok": True}

@router.patch("/{task_id}/profiles/{profile_id}/status")
def update_status(task_id: str, profile_id: str, body: UpdateStatusRequest, db: Session = Depends(get_db)):
    if body.status not in ("pending", "done", "skipped"):
        raise HTTPException(400, "status must be pending/done/skipped")
    tp = (
        db.query(TaskProfile)
        .filter(TaskProfile.task_id == task_id, TaskProfile.profile_id == profile_id)
        .first()
    )
    if not tp:
        raise HTTPException(404, "Not found")
    tp.status = body.status
    tp.notes = body.notes
    tp.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/test_tasks.py -v
```

期望：全部 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/routers/tasks.py tests/test_tasks.py
git commit -m "feat: URL tasks and task-profile progress API"
```

---

### Task 5: System API（版本检查 + SSE 更新 + License）

**Files:**
- Create: `backend/routers/system.py`
- Create: `tests/test_system.py`

**Interfaces:**
- Produces: `GET /api/system/info`, `POST /api/system/update` (SSE), `PUT /api/system/license`

- [ ] **Step 1: 写 tests/test_system.py**

```python
import json

def test_get_system_info(client):
    resp = client.get("/api/system/info")
    assert resp.status_code == 200
    data = resp.json()
    assert "installed_version" in data
    assert "license_key" in data

def test_save_license(client, tmp_path, monkeypatch):
    import backend.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.json")
    resp = client.put("/api/system/license", json={"license_key": "TEST-KEY"})
    assert resp.status_code == 200
    assert cfg.get_license_key() == "TEST-KEY"
```

- [ ] **Step 2: 写 backend/routers/system.py**

```python
import asyncio
import subprocess
import sys
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

@router.put("/license")
def save_license(body: LicenseRequest):
    cfg = get_config()
    cfg["license_key"] = body.license_key
    save_config(cfg)
    return {"ok": True}
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/test_system.py -v
```

期望：全部 PASSED

- [ ] **Step 4: 运行全量后端测试**

```bash
pytest tests/ -v
```

期望：全部 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/routers/system.py tests/test_system.py
git commit -m "feat: system info, update (SSE), license API"
```

---

### Task 6: 前端脚手架 + 类型定义 + API 客户端

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/api/profiles.ts`
- Create: `frontend/src/api/instances.ts`
- Create: `frontend/src/api/tasks.ts`
- Create: `frontend/src/api/system.ts`

**Interfaces:**
- Produces: 所有 TypeScript 类型，所有 API 函数，带路由的 App 骨架

- [ ] **Step 1: 写 frontend/package.json**

```json
{
  "name": "cloaktoast-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "antd": "^5.17.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.23.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.4.5",
    "vite": "^5.2.11"
  }
}
```

- [ ] **Step 2: 写 frontend/tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

- [ ] **Step 3: 写 frontend/vite.config.ts**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:8765" },
  },
  build: { outDir: "dist" },
});
```

- [ ] **Step 4: 写 frontend/index.html**

```html
<!doctype html>
<html lang="zh">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>CloakToast</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: 写 frontend/src/main.tsx**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "antd/dist/reset.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 6: 写 frontend/src/types.ts**

```typescript
export interface Profile {
  id: string;
  name: string;
  color_tag: string;
  notes: string;
  proxy_type: "none" | "http" | "socks5";
  proxy_host: string;
  proxy_port: number | null;
  proxy_user: string;
  proxy_pass: string;
  timezone: string;
  locale: string;
  headless: boolean;
  humanize: boolean;
  human_preset: string;
  fingerprint_seed: number | null;
  fp_noise_enabled: boolean;
  fp_platform: string;
  fp_hardware_concurrency: number | null;
  fp_device_memory: number | null;
  fp_screen_width: number | null;
  fp_screen_height: number | null;
  fp_taskbar_height: number | null;
  fp_gpu_vendor: string;
  fp_gpu_renderer: string;
  fp_webrtc_ip: string;
  fp_location_lat: number | null;
  fp_location_lng: number | null;
  fp_storage_quota: number | null;
  fp_fonts_dir: string;
  user_agent: string;
  fp_brand: string;
  fp_brand_version: string;
  fp_platform_version: string;
  extension_paths: string[];
  user_data_dir: string;
  cdp_port: number | null;
  extra_args: string[];
  created_at: string;
  updated_at: string;
  is_running: boolean;
  running_since: string | null;
}

export interface URLTask {
  id: string;
  name: string;
  urls: string[];
  notes: string;
  created_at: string;
}

export interface TaskProfileEntry {
  id: string;
  task_id: string;
  profile_id: string;
  status: "pending" | "done" | "skipped";
  notes: string;
  updated_at: string;
  profile: Profile | null;
}

export interface URLTaskDetail extends URLTask {
  profiles: TaskProfileEntry[];
  total_profiles: number;
  done_count: number;
}

export interface RunningInstance {
  profile_id: string;
  started_at: string;
  task_id: string | null;
}

export interface SystemInfo {
  installed_version: string | null;
  license_key: string | null;
}
```

- [ ] **Step 7: 写 frontend/src/api/client.ts**

```typescript
export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail: string }).detail || "Request failed");
  }
  return res.json() as Promise<T>;
}
```

- [ ] **Step 8: 写 frontend/src/api/profiles.ts**

```typescript
import { apiFetch } from "./client";
import type { Profile } from "../types";

export const getProfiles = () => apiFetch<Profile[]>("/profiles");
export const getProfile = (id: string) => apiFetch<Profile>(`/profiles/${id}`);
export const createProfile = (data: Partial<Profile>) =>
  apiFetch<Profile>("/profiles", { method: "POST", body: JSON.stringify(data) });
export const updateProfile = (id: string, data: Partial<Profile>) =>
  apiFetch<Profile>(`/profiles/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteProfile = (id: string) =>
  apiFetch<{ ok: boolean }>(`/profiles/${id}`, { method: "DELETE" });
export const duplicateProfile = (id: string) =>
  apiFetch<Profile>(`/profiles/${id}/duplicate`, { method: "POST" });
```

- [ ] **Step 9: 写 frontend/src/api/instances.ts**

```typescript
import { apiFetch } from "./client";
import type { RunningInstance } from "../types";

export const getInstances = () => apiFetch<RunningInstance[]>("/instances");
export const launchInstance = (profile_id: string, task_id?: string) =>
  apiFetch<{ ok: boolean }>("/instances/launch", {
    method: "POST",
    body: JSON.stringify({ profile_id, task_id }),
  });
export const stopInstance = (profile_id: string) =>
  apiFetch<{ ok: boolean }>(`/instances/stop/${profile_id}`, { method: "POST" });
```

- [ ] **Step 10: 写 frontend/src/api/tasks.ts**

```typescript
import { apiFetch } from "./client";
import type { URLTask, URLTaskDetail } from "../types";

export const getTasks = () => apiFetch<URLTask[]>("/tasks");
export const getTask = (id: string) => apiFetch<URLTaskDetail>(`/tasks/${id}`);
export const createTask = (data: Partial<URLTask>) =>
  apiFetch<URLTask>("/tasks", { method: "POST", body: JSON.stringify(data) });
export const updateTask = (id: string, data: Partial<URLTask>) =>
  apiFetch<URLTask>(`/tasks/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteTask = (id: string) =>
  apiFetch<{ ok: boolean }>(`/tasks/${id}`, { method: "DELETE" });
export const addProfilesToTask = (task_id: string, profile_ids: string[]) =>
  apiFetch<{ ok: boolean }>(`/tasks/${task_id}/profiles`, {
    method: "POST",
    body: JSON.stringify({ profile_ids }),
  });
export const removeProfileFromTask = (task_id: string, profile_id: string) =>
  apiFetch<{ ok: boolean }>(`/tasks/${task_id}/profiles/${profile_id}`, { method: "DELETE" });
export const updateProfileStatus = (
  task_id: string,
  profile_id: string,
  status: string,
  notes = ""
) =>
  apiFetch<{ ok: boolean }>(`/tasks/${task_id}/profiles/${profile_id}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status, notes }),
  });
```

- [ ] **Step 11: 写 frontend/src/api/system.ts**

```typescript
import { apiFetch } from "./client";
import type { SystemInfo } from "../types";

export const getSystemInfo = () => apiFetch<SystemInfo>("/system/info");
export const saveLicense = (license_key: string) =>
  apiFetch<{ ok: boolean }>("/system/license", {
    method: "PUT",
    body: JSON.stringify({ license_key }),
  });
```

- [ ] **Step 12: 写 frontend/src/App.tsx**

```tsx
import { Layout, Menu } from "antd";
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom";
import ProfilesPage from "./pages/Profiles";
import TasksPage from "./pages/Tasks";
import TaskDetailPage from "./pages/Tasks/TaskDetail";
import SettingsPage from "./pages/Settings";

const { Sider, Content } = Layout;

const NAV_ITEMS = [
  { key: "/", label: "Profile 管理" },
  { key: "/tasks", label: "URL 任务" },
  { key: "/settings", label: "系统设置" },
];

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const selectedKey = location.pathname.startsWith("/tasks") ? "/tasks" : location.pathname;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider>
        <div style={{ padding: "16px 24px", color: "white", fontWeight: "bold", fontSize: 16 }}>
          CloakToast
        </div>
        <Menu
          theme="dark"
          selectedKeys={[selectedKey]}
          items={NAV_ITEMS}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Content style={{ padding: 24 }}>
          <Routes>
            <Route path="/" element={<ProfilesPage />} />
            <Route path="/tasks" element={<TasksPage />} />
            <Route path="/tasks/:id" element={<TaskDetailPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
    </BrowserRouter>
  );
}
```

- [ ] **Step 13: 创建页面占位文件（让 App.tsx 能编译）**

`frontend/src/pages/Profiles/index.tsx`:
```tsx
export default function ProfilesPage() { return <div>Profiles</div>; }
```

`frontend/src/pages/Tasks/index.tsx`:
```tsx
export default function TasksPage() { return <div>Tasks</div>; }
```

`frontend/src/pages/Tasks/TaskDetail.tsx`:
```tsx
export default function TaskDetailPage() { return <div>Task Detail</div>; }
```

`frontend/src/pages/Settings/index.tsx`:
```tsx
export default function SettingsPage() { return <div>Settings</div>; }
```

- [ ] **Step 14: 安装依赖并验证编译**

```bash
cd frontend
npm install
npm run build
```

期望：`frontend/dist/` 生成成功，无 TypeScript 错误

- [ ] **Step 15: Commit**

```bash
cd ..
git add frontend/
git commit -m "feat: frontend scaffolding, types, API client, routing"
```

---

### Task 7: Profile 列表页 + 卡片 + 状态徽标

**Files:**
- Create: `frontend/src/components/StatusBadge.tsx`
- Create: `frontend/src/pages/Profiles/ProfileCard.tsx`
- Modify: `frontend/src/pages/Profiles/index.tsx`（替换占位）

**Interfaces:**
- Consumes: `Profile` type, `getProfiles`, `launchInstance`, `stopInstance`, `deleteProfile`, `duplicateProfile`
- Produces: `<ProfilesPage>` 完整列表，`<ProfileCard profile onEdit onRefresh />`，`<StatusBadge isRunning runningSince />`

- [ ] **Step 1: 写 frontend/src/components/StatusBadge.tsx**

```tsx
import { Badge, Tooltip } from "antd";

interface Props {
  isRunning: boolean;
  runningSince?: string | null;
}

function elapsed(since: string): string {
  const secs = Math.floor((Date.now() - new Date(since).getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m`;
  return `${Math.floor(secs / 3600)}h${Math.floor((secs % 3600) / 60)}m`;
}

export default function StatusBadge({ isRunning, runningSince }: Props) {
  if (isRunning) {
    return (
      <Tooltip title={runningSince ? `已运行 ${elapsed(runningSince)}` : "运行中"}>
        <Badge status="processing" text="运行中" />
      </Tooltip>
    );
  }
  return <Badge status="default" text="已停止" />;
}
```

- [ ] **Step 2: 写 frontend/src/pages/Profiles/ProfileCard.tsx**

```tsx
import { Card, Button, Popconfirm, Space, Tag, Typography } from "antd";
import { PlayCircleOutlined, StopOutlined, EditOutlined, CopyOutlined, DeleteOutlined } from "@ant-design/icons";
import type { Profile } from "../../types";
import StatusBadge from "../../components/StatusBadge";
import { launchInstance, stopInstance } from "../../api/instances";
import { deleteProfile, duplicateProfile } from "../../api/profiles";
import { message } from "antd";

interface Props {
  profile: Profile;
  onEdit: (profile: Profile) => void;
  onRefresh: () => void;
}

export default function ProfileCard({ profile, onEdit, onRefresh }: Props) {
  const proxyLabel =
    profile.proxy_type === "none"
      ? "无代理"
      : `${profile.proxy_type}://${profile.proxy_host}:${profile.proxy_port}`;

  async function handleLaunch() {
    try {
      await launchInstance(profile.id);
      message.success("启动成功");
      onRefresh();
    } catch (e: any) {
      message.error(e.message);
    }
  }

  async function handleStop() {
    try {
      await stopInstance(profile.id);
      message.success("已停止");
      onRefresh();
    } catch (e: any) {
      message.error(e.message);
    }
  }

  async function handleDuplicate() {
    try {
      await duplicateProfile(profile.id);
      message.success("已复制");
      onRefresh();
    } catch (e: any) {
      message.error(e.message);
    }
  }

  async function handleDelete() {
    try {
      await deleteProfile(profile.id);
      onRefresh();
    } catch (e: any) {
      message.error(e.message);
    }
  }

  return (
    <Card
      size="small"
      title={
        <Space>
          <span
            style={{
              display: "inline-block",
              width: 12,
              height: 12,
              borderRadius: "50%",
              background: profile.color_tag,
            }}
          />
          <Typography.Text strong>{profile.name}</Typography.Text>
        </Space>
      }
      extra={<StatusBadge isRunning={profile.is_running} runningSince={profile.running_since} />}
      actions={[
        profile.is_running ? (
          <Button
            key="stop"
            type="text"
            danger
            icon={<StopOutlined />}
            onClick={handleStop}
          >
            停止
          </Button>
        ) : (
          <Button key="launch" type="text" icon={<PlayCircleOutlined />} onClick={handleLaunch}>
            启动
          </Button>
        ),
        <Button key="edit" type="text" icon={<EditOutlined />} onClick={() => onEdit(profile)}>
          编辑
        </Button>,
        <Button key="copy" type="text" icon={<CopyOutlined />} onClick={handleDuplicate}>
          复制
        </Button>,
        <Popconfirm
          key="delete"
          title="确认删除此 Profile？"
          onConfirm={handleDelete}
          okText="删除"
          cancelText="取消"
        >
          <Button type="text" danger icon={<DeleteOutlined />}>
            删除
          </Button>
        </Popconfirm>,
      ]}
    >
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        {proxyLabel}
      </Typography.Text>
      {profile.notes && (
        <Typography.Paragraph
          type="secondary"
          style={{ fontSize: 12, marginTop: 4, marginBottom: 0 }}
          ellipsis={{ rows: 1 }}
        >
          {profile.notes}
        </Typography.Paragraph>
      )}
    </Card>
  );
}
```

- [ ] **Step 3: 写 frontend/src/pages/Profiles/index.tsx（完整版）**

```tsx
import { useEffect, useState, useCallback } from "react";
import { Button, Row, Col, Typography, Empty, Spin } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { Profile } from "../../types";
import { getProfiles } from "../../api/profiles";
import ProfileCard from "./ProfileCard";
import ProfileForm from "./ProfileForm";

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Profile | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getProfiles();
      setProfiles(data);
    } finally {
      setLoading(false);
    }
  }, []);

  // 每 5 秒轮询更新运行状态
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  function openCreate() {
    setEditing(null);
    setDrawerOpen(true);
  }

  function openEdit(profile: Profile) {
    setEditing(profile);
    setDrawerOpen(true);
  }

  function onFormClose() {
    setDrawerOpen(false);
    setEditing(null);
    refresh();
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Profile 管理
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建 Profile
        </Button>
      </div>

      {loading ? (
        <Spin />
      ) : profiles.length === 0 ? (
        <Empty description="暂无 Profile，点击右上角新建" />
      ) : (
        <Row gutter={[16, 16]}>
          {profiles.map((p) => (
            <Col key={p.id} xs={24} sm={12} lg={8} xl={6}>
              <ProfileCard profile={p} onEdit={openEdit} onRefresh={refresh} />
            </Col>
          ))}
        </Row>
      )}

      <ProfileForm open={drawerOpen} profile={editing} onClose={onFormClose} />
    </div>
  );
}
```

- [ ] **Step 4: 验证前端编译无误**

```bash
cd frontend && npm run build
```

期望：编译成功

- [ ] **Step 5: Commit**

```bash
cd ..
git add frontend/src/components/ frontend/src/pages/Profiles/
git commit -m "feat: profile list page with status badges and action buttons"
```

---

### Task 8: Profile 表单（三 Tab 抽屉）

**Files:**
- Create: `frontend/src/pages/Profiles/ProfileForm.tsx`

**Interfaces:**
- Consumes: `Profile` type, `createProfile`, `updateProfile`
- Props: `open: boolean`, `profile: Profile | null`（null = 新建）, `onClose: () => void`

- [ ] **Step 1: 写 frontend/src/pages/Profiles/ProfileForm.tsx**

```tsx
import { useEffect } from "react";
import {
  Drawer, Form, Input, Select, Switch, InputNumber, Button,
  Space, Tabs, Divider, message, ColorPicker,
} from "antd";
import { PlusOutlined, MinusCircleOutlined } from "@ant-design/icons";
import type { Profile } from "../../types";
import { createProfile, updateProfile } from "../../api/profiles";

interface Props {
  open: boolean;
  profile: Profile | null;
  onClose: () => void;
}

const TIMEZONES = [
  "Asia/Shanghai", "Asia/Tokyo", "Asia/Seoul", "Asia/Singapore",
  "America/New_York", "America/Los_Angeles", "Europe/London",
  "Europe/Berlin", "Europe/Moscow", "UTC",
];

const LOCALES = [
  { value: "zh-CN", label: "中文（简体）" },
  { value: "zh-TW", label: "中文（繁体）" },
  { value: "en-US", label: "English (US)" },
  { value: "ja-JP", label: "日本語" },
  { value: "ko-KR", label: "한국어" },
  { value: "ru-RU", label: "Русский" },
  { value: "de-DE", label: "Deutsch" },
  { value: "fr-FR", label: "Français" },
];

export default function ProfileForm({ open, profile, onClose }: Props) {
  const [form] = Form.useForm();
  const isEdit = !!profile;

  useEffect(() => {
    if (open) {
      if (profile) {
        form.setFieldsValue({
          ...profile,
          extra_args: profile.extra_args?.join("\n") ?? "",
        });
      } else {
        form.resetFields();
        form.setFieldsValue({
          color_tag: "#1677ff",
          proxy_type: "none",
          locale: "zh-CN",
          humanize: true,
          human_preset: "default",
          fp_noise_enabled: true,
          headless: false,
        });
      }
    }
  }, [open, profile, form]);

  async function onSubmit() {
    try {
      const values = await form.validateFields();
      const extra_args = (values.extra_args as string)
        .split("\n")
        .map((s: string) => s.trim())
        .filter(Boolean);
      const payload = { ...values, extra_args };
      if (typeof payload.color_tag === "object") {
        payload.color_tag = (payload.color_tag as any).toHexString?.() ?? payload.color_tag;
      }
      if (isEdit) {
        await updateProfile(profile!.id, payload);
        message.success("已保存");
      } else {
        await createProfile(payload);
        message.success("创建成功");
      }
      onClose();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e.message);
    }
  }

  const commonTab = (
    <>
      <Form.Item label="名称" name="name" rules={[{ required: true, message: "请输入名称" }]}>
        <Input placeholder="Profile 名称" />
      </Form.Item>
      <Form.Item label="颜色标签" name="color_tag">
        <ColorPicker format="hex" />
      </Form.Item>
      <Form.Item label="备注" name="notes">
        <Input.TextArea rows={2} />
      </Form.Item>
      <Divider>代理设置</Divider>
      <Form.Item label="代理类型" name="proxy_type">
        <Select options={[
          { value: "none", label: "不使用" },
          { value: "http", label: "HTTP" },
          { value: "socks5", label: "SOCKS5" },
        ]} />
      </Form.Item>
      <Form.Item noStyle shouldUpdate={(p, c) => p.proxy_type !== c.proxy_type}>
        {({ getFieldValue }) =>
          getFieldValue("proxy_type") !== "none" && (
            <>
              <Form.Item label="Host" name="proxy_host">
                <Input placeholder="127.0.0.1" />
              </Form.Item>
              <Form.Item label="Port" name="proxy_port">
                <InputNumber style={{ width: "100%" }} min={1} max={65535} />
              </Form.Item>
              <Form.Item label="用户名" name="proxy_user">
                <Input />
              </Form.Item>
              <Form.Item label="密码" name="proxy_pass">
                <Input.Password />
              </Form.Item>
            </>
          )
        }
      </Form.Item>
      <Divider>浏览器设置</Divider>
      <Form.Item label="时区" name="timezone">
        <Select
          allowClear
          placeholder="留空=跟随代理 GeoIP"
          options={TIMEZONES.map((tz) => ({ value: tz, label: tz }))}
        />
      </Form.Item>
      <Form.Item label="语言" name="locale">
        <Select options={LOCALES} />
      </Form.Item>
      <Form.Item label="无头模式" name="headless" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item label="Humanize" name="humanize" valuePropName="checked">
        <Switch />
      </Form.Item>
      <Form.Item label="Humanize 预设" name="human_preset">
        <Select options={[
          { value: "default", label: "Default" },
          { value: "careful", label: "Careful（更谨慎）" },
        ]} />
      </Form.Item>
    </>
  );

  const fingerprintTab = (
    <>
      <Form.Item label="指纹 Seed" name="fingerprint_seed" extra="留空=每次随机">
        <InputNumber style={{ width: "100%" }} min={1} />
      </Form.Item>
      <Form.Item label="噪声注入" name="fp_noise_enabled" valuePropName="checked">
        <Switch checkedChildren="开启" unCheckedChildren="关闭" />
      </Form.Item>
      <Form.Item label="平台伪装" name="fp_platform">
        <Select allowClear placeholder="跟随种子" options={[
          { value: "windows", label: "Windows" },
          { value: "macos", label: "macOS" },
        ]} />
      </Form.Item>
      <Form.Item label="CPU 核心数" name="fp_hardware_concurrency" extra="留空=跟随种子">
        <InputNumber style={{ width: "100%" }} min={1} max={256} />
      </Form.Item>
      <Form.Item label="设备内存(GB)" name="fp_device_memory" extra="留空=跟随种子">
        <InputNumber style={{ width: "100%" }} min={1} max={512} />
      </Form.Item>
      <Space.Compact block>
        <Form.Item label="屏幕宽度" name="fp_screen_width" style={{ width: "50%" }}>
          <InputNumber style={{ width: "100%" }} placeholder="留空=随机" />
        </Form.Item>
        <Form.Item label="屏幕高度" name="fp_screen_height" style={{ width: "50%" }}>
          <InputNumber style={{ width: "100%" }} placeholder="留空=随机" />
        </Form.Item>
      </Space.Compact>
      <Form.Item label="任务栏高度" name="fp_taskbar_height" extra="留空=跟随种子">
        <InputNumber style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="WebGL 厂商" name="fp_gpu_vendor" extra="留空=跟随种子">
        <Input placeholder="如 Intel Inc." />
      </Form.Item>
      <Form.Item label="WebGL 渲染器" name="fp_gpu_renderer" extra="留空=跟随种子">
        <Input placeholder="如 Intel Iris OpenGL Engine" />
      </Form.Item>
      <Form.Item label="WebRTC IP" name="fp_webrtc_ip" extra="留空=不覆盖">
        <Input placeholder="如 192.168.1.1" />
      </Form.Item>
      <Space.Compact block>
        <Form.Item label="纬度" name="fp_location_lat" style={{ width: "50%" }}>
          <InputNumber style={{ width: "100%" }} placeholder="留空=不覆盖" />
        </Form.Item>
        <Form.Item label="经度" name="fp_location_lng" style={{ width: "50%" }}>
          <InputNumber style={{ width: "100%" }} placeholder="留空=不覆盖" />
        </Form.Item>
      </Space.Compact>
      <Form.Item label="存储配额(MB)" name="fp_storage_quota" extra="留空=跟随种子">
        <InputNumber style={{ width: "100%" }} />
      </Form.Item>
      <Form.Item label="字体目录" name="fp_fonts_dir" extra="留空=不覆盖">
        <Input placeholder="C:\fonts" />
      </Form.Item>
    </>
  );

  const advancedTab = (
    <>
      <Form.Item label="User Agent" name="user_agent" extra="留空=自动">
        <Input.TextArea rows={2} />
      </Form.Item>
      <Form.Item label="浏览器品牌" name="fp_brand" extra="留空=自动">
        <Input />
      </Form.Item>
      <Form.Item label="品牌版本" name="fp_brand_version">
        <Input />
      </Form.Item>
      <Form.Item label="系统版本" name="fp_platform_version">
        <Input />
      </Form.Item>
      <Divider>扩展路径</Divider>
      <Form.List name="extension_paths">
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, ...rest }) => (
              <Form.Item key={key} {...rest} name={name} style={{ marginBottom: 8 }}>
                <Input
                  placeholder="扩展目录路径"
                  suffix={
                    <MinusCircleOutlined onClick={() => remove(name)} style={{ color: "red" }} />
                  }
                />
              </Form.Item>
            ))}
            <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />} block>
              添加扩展路径
            </Button>
          </>
        )}
      </Form.List>
      <Divider />
      <Form.Item label="User Data Dir" name="user_data_dir" extra="留空=自动管理">
        <Input />
      </Form.Item>
      <Form.Item label="CDP 端口" name="cdp_port" extra="留空=自动分配">
        <InputNumber style={{ width: "100%" }} min={1024} max={65535} />
      </Form.Item>
      <Form.Item label="额外启动参数" name="extra_args" extra="每行一条">
        <Input.TextArea rows={4} placeholder={"--disable-web-security\n--no-sandbox"} />
      </Form.Item>
    </>
  );

  return (
    <Drawer
      title={isEdit ? "编辑 Profile" : "新建 Profile"}
      open={open}
      onClose={onClose}
      width={520}
      extra={
        <Space>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={onSubmit}>
            保存
          </Button>
        </Space>
      }
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Tabs
          items={[
            { key: "common", label: "常用", children: commonTab },
            { key: "fingerprint", label: "指纹", children: fingerprintTab },
            { key: "advanced", label: "高级", children: advancedTab },
          ]}
        />
      </Form>
    </Drawer>
  );
}
```

- [ ] **Step 2: 验证编译**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/pages/Profiles/ProfileForm.tsx
git commit -m "feat: profile form drawer with 3 tabs (common/fingerprint/advanced)"
```

---

### Task 9: URL 任务页（列表 + 详情）

**Files:**
- Modify: `frontend/src/pages/Tasks/index.tsx`（替换占位）
- Modify: `frontend/src/pages/Tasks/TaskDetail.tsx`（替换占位）

- [ ] **Step 1: 写 frontend/src/pages/Tasks/index.tsx**

```tsx
import { useEffect, useState } from "react";
import { Table, Button, Popconfirm, Typography, Modal, Form, Input, Space, message, Progress } from "antd";
import { PlusOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { URLTask } from "../../types";
import { getTasks, createTask, deleteTask } from "../../api/tasks";

export default function TasksPage() {
  const [tasks, setTasks] = useState<URLTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  async function refresh() {
    try {
      setTasks(await getTasks());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function handleCreate() {
    try {
      const values = await form.validateFields();
      const urls = (values.urls as string).split("\n").map((s: string) => s.trim()).filter(Boolean);
      await createTask({ name: values.name, urls, notes: values.notes || "" });
      message.success("创建成功");
      setModalOpen(false);
      form.resetFields();
      refresh();
    } catch (e: any) {
      if (!e?.errorFields) message.error(e.message);
    }
  }

  async function handleDelete(id: string) {
    await deleteTask(id);
    refresh();
  }

  const columns = [
    {
      title: "任务名称",
      dataIndex: "name",
      render: (name: string, r: URLTask) => (
        <Button type="link" onClick={() => navigate(`/tasks/${r.id}`)}>{name}</Button>
      ),
    },
    { title: "URL 数量", dataIndex: "urls", render: (urls: string[]) => urls.length },
    {
      title: "创建时间",
      dataIndex: "created_at",
      render: (t: string) => new Date(t).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      render: (_: unknown, r: URLTask) => (
        <Popconfirm title="确认删除？" onConfirm={() => handleDelete(r.id)}>
          <Button type="link" danger>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>URL 任务</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          新建任务
        </Button>
      </div>
      <Table
        dataSource={tasks}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={false}
      />
      <Modal
        title="新建任务"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => { setModalOpen(false); form.resetFields(); }}
        okText="创建"
      >
        <Form form={form} layout="vertical">
          <Form.Item label="任务名称" name="name" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="URL 列表（每行一个）" name="urls">
            <Input.TextArea rows={5} placeholder={"https://example.com\nhttps://another.com"} />
          </Form.Item>
          <Form.Item label="备注" name="notes">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
```

- [ ] **Step 2: 写 frontend/src/pages/Tasks/TaskDetail.tsx**

```tsx
import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Button, Table, Tag, Space, Typography, Form, Input,
  message, Modal, Checkbox, Spin, Popconfirm,
} from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import type { URLTaskDetail, TaskProfileEntry, Profile } from "../../types";
import { getTask, addProfilesToTask, removeProfileFromTask, updateProfileStatus, updateTask } from "../../api/tasks";
import { getProfiles } from "../../api/profiles";
import { launchInstance, stopInstance } from "../../api/instances";
import StatusBadge from "../../components/StatusBadge";

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<URLTaskDetail | null>(null);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [allProfiles, setAllProfiles] = useState<Profile[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [form] = Form.useForm();

  const refresh = useCallback(async () => {
    if (!id) return;
    const data = await getTask(id);
    setTask(data);
    form.setFieldsValue({
      name: data.name,
      urls: data.urls.join("\n"),
      notes: data.notes,
    });
  }, [id, form]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  async function handleSaveTask() {
    if (!id) return;
    const values = await form.validateFields();
    const urls = (values.urls as string).split("\n").map((s: string) => s.trim()).filter(Boolean);
    await updateTask(id, { name: values.name, urls, notes: values.notes || "" });
    message.success("已保存");
    refresh();
  }

  async function openAddProfiles() {
    const profiles = await getProfiles();
    const existingIds = new Set(task?.profiles.map((p) => p.profile_id) ?? []);
    setAllProfiles(profiles.filter((p) => !existingIds.has(p.id)));
    setSelectedIds([]);
    setAddModalOpen(true);
  }

  async function handleAddProfiles() {
    if (!id || selectedIds.length === 0) return;
    await addProfilesToTask(id, selectedIds);
    setAddModalOpen(false);
    refresh();
  }

  async function handleLaunch(entry: TaskProfileEntry) {
    try {
      await launchInstance(entry.profile_id, id);
      message.success("启动成功");
      refresh();
    } catch (e: any) { message.error(e.message); }
  }

  async function handleStop(entry: TaskProfileEntry) {
    try {
      await stopInstance(entry.profile_id);
      message.success("已停止");
      refresh();
    } catch (e: any) { message.error(e.message); }
  }

  async function handleStatus(entry: TaskProfileEntry, status: "done" | "skipped" | "pending") {
    await updateProfileStatus(id!, entry.profile_id, status);
    refresh();
  }

  const statusTag: Record<string, React.ReactNode> = {
    pending: <Tag>待完成</Tag>,
    done: <Tag color="green">已完成</Tag>,
    skipped: <Tag color="orange">已跳过</Tag>,
  };

  const columns = [
    {
      title: "Profile",
      render: (_: unknown, r: TaskProfileEntry) => (
        <Space>
          <span
            style={{
              display: "inline-block",
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: r.profile?.color_tag ?? "#ccc",
            }}
          />
          {r.profile?.name ?? r.profile_id}
        </Space>
      ),
    },
    {
      title: "代理",
      render: (_: unknown, r: TaskProfileEntry) =>
        r.profile?.proxy_type === "none"
          ? "无代理"
          : `${r.profile?.proxy_type}://${r.profile?.proxy_host}:${r.profile?.proxy_port}`,
    },
    {
      title: "状态",
      render: (_: unknown, r: TaskProfileEntry) => (
        <Space>
          {statusTag[r.status]}
          {r.profile?.is_running && (
            <StatusBadge isRunning runningSince={r.profile.running_since} />
          )}
        </Space>
      ),
    },
    {
      title: "操作",
      render: (_: unknown, r: TaskProfileEntry) => (
        <Space size="small">
          {r.profile?.is_running ? (
            <Button size="small" danger onClick={() => handleStop(r)}>停止</Button>
          ) : (
            <Button size="small" type="primary" onClick={() => handleLaunch(r)}>启动</Button>
          )}
          <Button size="small" onClick={() => handleStatus(r, "done")} disabled={r.status === "done"}>
            标记完成
          </Button>
          <Button size="small" onClick={() => handleStatus(r, "skipped")} disabled={r.status === "skipped"}>
            跳过
          </Button>
          <Button size="small" onClick={() => handleStatus(r, "pending")} disabled={r.status === "pending"}>
            重置
          </Button>
          <Popconfirm title="移出任务？" onConfirm={() => removeProfileFromTask(id!, r.profile_id).then(refresh)}>
            <Button size="small" danger>移出</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (!task) return <Spin />;

  return (
    <div>
      <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/tasks")} style={{ marginBottom: 16 }}>
        返回
      </Button>
      <Form form={form} layout="vertical">
        <Form.Item label="任务名称" name="name" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item label="URL 列表（每行一个）" name="urls">
          <Input.TextArea rows={4} />
        </Form.Item>
        <Form.Item label="备注" name="notes">
          <Input />
        </Form.Item>
        <Button type="primary" onClick={handleSaveTask}>保存任务信息</Button>
      </Form>

      <div style={{ display: "flex", justifyContent: "space-between", margin: "24px 0 12px" }}>
        <Typography.Text strong>
          Profile 进度：{task.done_count} / {task.total_profiles} 已完成
        </Typography.Text>
        <Button onClick={openAddProfiles}>添加 Profile</Button>
      </div>

      <Table
        dataSource={task.profiles}
        columns={columns}
        rowKey="id"
        pagination={false}
        size="small"
        rowClassName={(r) => (r.profile?.is_running ? "ant-table-row-selected" : "")}
      />

      <Modal
        title="添加 Profile 到任务"
        open={addModalOpen}
        onOk={handleAddProfiles}
        onCancel={() => setAddModalOpen(false)}
        okText="添加"
      >
        <Checkbox.Group
          style={{ display: "flex", flexDirection: "column", gap: 8 }}
          options={allProfiles.map((p) => ({ label: p.name, value: p.id }))}
          value={selectedIds}
          onChange={(vals) => setSelectedIds(vals as string[])}
        />
        {allProfiles.length === 0 && <Typography.Text type="secondary">所有 Profile 已在此任务中</Typography.Text>}
      </Modal>
    </div>
  );
}
```

- [ ] **Step 3: 验证编译**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/src/pages/Tasks/
git commit -m "feat: URL tasks list and detail pages with progress tracking"
```

---

### Task 10: 系统设置页

**Files:**
- Modify: `frontend/src/pages/Settings/index.tsx`（替换占位）

- [ ] **Step 1: 写 frontend/src/pages/Settings/index.tsx**

```tsx
import { useEffect, useState, useRef } from "react";
import { Card, Button, Input, Typography, Space, Divider, message, Spin } from "antd";
import type { SystemInfo } from "../../types";
import { getSystemInfo, saveLicense } from "../../api/system";

export default function SettingsPage() {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [licenseInput, setLicenseInput] = useState("");
  const [updating, setUpdating] = useState(false);
  const [updateLog, setUpdateLog] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getSystemInfo().then((data) => {
      setInfo(data);
      setLicenseInput(data.license_key ?? "");
    });
  }, []);

  async function handleSaveLicense() {
    try {
      await saveLicense(licenseInput);
      message.success("License Key 已保存");
    } catch (e: any) {
      message.error(e.message);
    }
  }

  async function handleUpdate() {
    setUpdating(true);
    setUpdateLog([]);
    try {
      const res = await fetch("/api/system/update", { method: "POST" });
      if (!res.body) throw new Error("No response body");
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const text = line.slice(6);
            setUpdateLog((prev) => [...prev, text]);
            setTimeout(() => logRef.current?.scrollTo(0, logRef.current.scrollHeight), 0);
          }
        }
      }
    } catch (e: any) {
      message.error(e.message);
    } finally {
      setUpdating(false);
      getSystemInfo().then(setInfo);
    }
  }

  if (!info) return <Spin />;

  return (
    <div style={{ maxWidth: 600 }}>
      <Typography.Title level={4}>系统设置</Typography.Title>

      <Card title="CloakBrowser" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: "100%" }}>
          <Typography.Text>
            当前版本：<Typography.Text strong>{info.installed_version ?? "未安装"}</Typography.Text>
          </Typography.Text>
          <Button type="primary" loading={updating} onClick={handleUpdate}>
            执行更新
          </Button>
          {updateLog.length > 0 && (
            <div
              ref={logRef}
              style={{
                background: "#000",
                color: "#0f0",
                fontFamily: "monospace",
                fontSize: 12,
                padding: 12,
                borderRadius: 4,
                maxHeight: 200,
                overflowY: "auto",
              }}
            >
              {updateLog.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
            </div>
          )}
        </Space>
      </Card>

      <Card title="License Key">
        <Space.Compact style={{ width: "100%" }}>
          <Input.Password
            value={licenseInput}
            onChange={(e) => setLicenseInput(e.target.value)}
            placeholder="输入 CloakBrowser License Key"
          />
          <Button type="primary" onClick={handleSaveLicense}>
            保存
          </Button>
        </Space.Compact>
        <Typography.Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: "block" }}>
          保存后将在启动浏览器实例时自动注入
        </Typography.Text>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: 验证编译**

```bash
cd frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/pages/Settings/
git commit -m "feat: system settings page with update log and license key"
```

---

### Task 11: 静态文件集成 + 启动脚本 + 端到端验证

**Files:**
- Modify: `backend/main.py`（确认静态 serve 逻辑）
- Create: `start.bat`
- Create: `start.sh`

- [ ] **Step 1: 验证 backend/main.py 静态文件逻辑正确**

确认 `backend/main.py` 中 DIST 路径为：
```python
DIST = Path(__file__).parent.parent / "frontend" / "dist"
```
且 SPA fallback 路由在所有 `/api/` 路由注册之后。

- [ ] **Step 2: 写 start.bat**

```bat
@echo off
cd /d "%~dp0"

echo [1/3] 检查 Python 依赖...
pip install -r backend\requirements.txt -q

echo [2/3] 检查前端构建...
if not exist "frontend\dist\index.html" (
    echo 正在构建前端...
    cd frontend
    call npm install -q
    call npm run build
    cd ..
)

echo [3/3] 启动 CloakToast...
echo 访问 http://localhost:8765
python -m backend.main
```

- [ ] **Step 3: 写 start.sh**

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "[1/3] 检查 Python 依赖..."
pip install -r backend/requirements.txt -q

echo "[2/3] 检查前端构建..."
if [ ! -f "frontend/dist/index.html" ]; then
  echo "正在构建前端..."
  cd frontend && npm install -q && npm run build && cd ..
fi

echo "[3/3] 启动 CloakToast..."
echo "访问 http://localhost:8765"
python -m backend.main
```

- [ ] **Step 4: 运行全量后端测试**

```bash
pytest tests/ -v
```

期望：全部 PASSED

- [ ] **Step 5: 构建前端并启动服务**

```bash
cd frontend && npm run build && cd ..
python -m backend.main
```

在浏览器打开 `http://localhost:8765`，验证：
- 左侧导航显示「Profile 管理 / URL 任务 / 系统设置」
- 能新建 Profile，三个 Tab 均可展示
- 能新建 URL 任务，进入详情页
- 系统设置页显示 CloakBrowser 版本信息

- [ ] **Step 6: 最终 Commit**

```bash
git add start.bat start.sh backend/main.py
git commit -m "feat: start scripts and static file serving integration"
```

---

## 自检清单

- [x] Profile CRUD：新建、编辑、删除、复制 ✓
- [x] Profile 三 Tab 表单：常用 / 指纹（14 个 fp_* 字段）/ 高级 ✓
- [x] 指纹参数转 `--fingerprint-*` 启动标志 ✓
- [x] 实例启动/停止，防止重复启动 ✓
- [x] 运行状态实时显示在 Profile 卡片 ✓
- [x] URL 任务 CRUD，progress 追踪 ✓
- [x] 从任务详情启动实例自动带 URL ✓
- [x] 系统设置：版本 + SSE 更新日志 + License Key ✓
- [x] License Key 注入子进程环境变量 ✓
- [x] 单命令启动（start.bat / start.sh）✓
- [x] 所有后端 API 有对应测试 ✓
