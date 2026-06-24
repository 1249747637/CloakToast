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
