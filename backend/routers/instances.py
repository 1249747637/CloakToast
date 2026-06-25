from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Profile, Bookmark
from ..schemas import LaunchRequest
from ..services import browser

router = APIRouter()


@router.get("")
def list_instances():
    return list(browser.get_running_instances().values())


@router.get("/recent_exits")
def list_recent_exits():
    """最近退出的 worker — 用于前端展示崩溃日志（returncode != 0）。"""
    return browser.get_recent_exits()


@router.post("/launch")
async def launch(body: LaunchRequest, db: Session = Depends(get_db)):
    p = db.get(Profile, body.profile_id)
    if not p:
        raise HTTPException(404, "Profile not found")
    if browser.is_running(body.profile_id):
        raise HTTPException(400, "Already running")

    bookmarks = db.query(Bookmark).order_by(Bookmark.sort_order, Bookmark.created_at).all()
    bookmark_list = [{"name": b.name, "url": b.url} for b in bookmarks]

    profile_dict = {c.name: getattr(p, c.name) for c in p.__table__.columns}
    try:
        await browser.launch_profile(profile_dict, bookmark_list)
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
