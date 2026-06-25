from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Bookmark
from ..schemas import BookmarkCreate, BookmarkUpdate, BookmarkResponse, BookmarkReorderItem

router = APIRouter()


@router.get("", response_model=list[BookmarkResponse])
def list_bookmarks(db: Session = Depends(get_db)):
    return db.query(Bookmark).order_by(Bookmark.sort_order, Bookmark.created_at).all()


@router.post("", response_model=BookmarkResponse)
def create_bookmark(body: BookmarkCreate, db: Session = Depends(get_db)):
    bm = Bookmark(**body.model_dump())
    db.add(bm)
    db.commit()
    db.refresh(bm)
    return bm


@router.post("/reorder")
def reorder_bookmarks(body: list[BookmarkReorderItem], db: Session = Depends(get_db)):
    for item in body:
        bm = db.get(Bookmark, item.id)
        if bm:
            bm.sort_order = item.sort_order
    db.commit()
    return {"ok": True}


@router.put("/{bookmark_id}", response_model=BookmarkResponse)
def update_bookmark(bookmark_id: str, body: BookmarkUpdate, db: Session = Depends(get_db)):
    bm = db.get(Bookmark, bookmark_id)
    if not bm:
        raise HTTPException(404, "Bookmark not found")
    for k, v in body.model_dump().items():
        setattr(bm, k, v)
    db.commit()
    db.refresh(bm)
    return bm


@router.delete("/{bookmark_id}")
def delete_bookmark(bookmark_id: str, db: Session = Depends(get_db)):
    bm = db.get(Bookmark, bookmark_id)
    if not bm:
        raise HTTPException(404, "Bookmark not found")
    db.delete(bm)
    db.commit()
    return {"ok": True}
