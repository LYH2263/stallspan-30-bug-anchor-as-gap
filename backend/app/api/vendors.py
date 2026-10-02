import math

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Vendor
router = APIRouter(prefix="/vendors", tags=["vendors"])


def _serialize(r: Vendor) -> dict:
    return {"id": r.id, "market_day_id": r.market_day_id, "name": r.name,
            "stall_width_m": r.stall_width_m, "priority": r.priority,
            "anchor_m": r.anchor_m, "anchor_tolerance_m": r.anchor_tolerance_m}


@router.get("")
def list_vendors(db: Session = Depends(get_db)):
    return [_serialize(r)
            for r in db.scalars(select(Vendor).order_by(Vendor.priority, Vendor.id)).all()]


class AnchorUpdate(BaseModel):
    # 均允许 None：传 null 即清除锚点，恢复从左填法。
    anchor_m: float | None = None
    anchor_tolerance_m: float | None = None


@router.patch("/{vendor_id}")
def update_anchor(vendor_id: int, body: AnchorUpdate, db: Session = Depends(get_db)):
    row = db.get(Vendor, vendor_id)
    if not row:
        raise HTTPException(404, "摊主不存在")
    if body.anchor_m is None:
        # 清除锚点；容差一并清空。
        row.anchor_m = None
        row.anchor_tolerance_m = None
    else:
        # 非法米标（NaN/Infinity/负数）或负容差：整单打回，不写库——
        # 图和“放不下”名单因此保持改前那次分配的结果。
        if not math.isfinite(body.anchor_m) or body.anchor_m < 0:
            raise HTTPException(422, "锚点米标非法：须为不小于 0 的数字")
        tol = body.anchor_tolerance_m if body.anchor_tolerance_m is not None else 0.0
        if not math.isfinite(tol) or tol < 0:
            raise HTTPException(422, "容差非法：须为不小于 0 的数字")
        row.anchor_m = body.anchor_m
        row.anchor_tolerance_m = tol
    db.commit()
    db.refresh(row)
    return _serialize(row)
