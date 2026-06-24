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
    data = ProfileCreate.model_validate(p, from_attributes=True).model_dump()
    data["name"] = f"{p.name} (副本)"
    new_p = Profile(id=str(uuid.uuid4()), **data)
    db.add(new_p)
    db.commit()
    db.refresh(new_p)
    return _enrich(new_p)
