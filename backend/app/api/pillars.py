from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Pillar
router = APIRouter(prefix="/pillars", tags=["pillars"])

@router.get("")
def list_pillars(db: Session = Depends(get_db)):
    return [{"id": r.id, "segment_id": r.segment_id, "position_m": r.position_m,
             "thickness_m": r.thickness_m, "label": r.label}
            for r in db.scalars(select(Pillar).order_by(Pillar.position_m)).all()]
