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
            "id": tp.id,
            "task_id": tp.task_id,
            "profile_id": tp.profile_id,
            "status": tp.status,
            "notes": tp.notes,
            "updated_at": tp.updated_at.isoformat() if tp.updated_at else None,
            "profile": pr,
        })
    base = URLTaskResponse.model_validate(task).model_dump()
    # Serialize datetime fields in base dict
    for k, v in base.items():
        if isinstance(v, datetime):
            base[k] = v.isoformat()
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
def update_status(
    task_id: str,
    profile_id: str,
    body: UpdateStatusRequest,
    db: Session = Depends(get_db),
):
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
