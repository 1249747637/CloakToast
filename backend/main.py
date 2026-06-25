from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from .database import Base, engine, migrate_add_columns

Base.metadata.create_all(bind=engine)
migrate_add_columns()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动阶段无事可做
    yield
    # 关停阶段：尝试干净地关掉所有正在跑的浏览器，避免留 orphan Chromium 卡住 user_data_dir
    from .services.browser import stop_all
    try:
        await stop_all()
    except Exception:
        pass


app = FastAPI(title="CloakToast", lifespan=lifespan)

from .routers import profiles, instances, bookmarks, system

app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])
app.include_router(instances.router, prefix="/api/instances", tags=["instances"])
app.include_router(bookmarks.router, prefix="/api/bookmarks", tags=["bookmarks"])
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
