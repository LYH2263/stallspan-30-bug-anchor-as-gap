import hashlib
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import AllocationRun, Pillar, Segment, Vendor
from app.services.first_fit_engine import allocate_first_fit, result_to_dict
router = APIRouter(prefix="/allocate", tags=["allocate"])


def _gather_inputs(db: Session, segment_id: int):
    """取提交瞬间的街段/挡柱/摊主（含最新锚点米标与容差）。"""
    seg = db.get(Segment, segment_id)
    if not seg:
        raise HTTPException(404, "街段不存在")
    pillars = [{"position_m": p.position_m, "thickness_m": p.thickness_m}
               for p in db.scalars(select(Pillar).where(Pillar.segment_id == segment_id)).all()]
    vendors = [{"id": v.id, "name": v.name, "stall_width_m": v.stall_width_m,
                "priority": v.priority, "anchor_m": v.anchor_m,
                "anchor_tolerance_m": v.anchor_tolerance_m}
               for v in db.scalars(select(Vendor).where(Vendor.market_day_id == seg.market_day_id)).all()]
    return seg, pillars, vendors


def _input_fingerprint(seg: Segment, pillars: list[dict], vendors: list[dict]) -> str:
    """分配输入指纹：米标/容差/宽度/优先级或挡柱一变，指纹即变。

    用于识别存档 run 是否按改前的带子算出——指纹不符的旧结果禁止再吐给前端。
    """
    payload = {
        "width_m": seg.width_m,
        "pillars": sorted((p["position_m"], p["thickness_m"]) for p in pillars),
        "vendors": sorted(
            (v["id"], v["stall_width_m"], v["priority"],
             v["anchor_m"], v["anchor_tolerance_m"])
            for v in vendors
        ),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _compute(seg: Segment, pillars: list[dict], vendors: list[dict]) -> dict:
    result = result_to_dict(allocate_first_fit(seg.width_m, vendors, pillars))
    result["segment"] = {"id": seg.id, "name": seg.name, "width_m": seg.width_m}
    result["pillars"] = pillars
    result["input_fingerprint"] = _input_fingerprint(seg, pillars, vendors)
    return result


@router.post("/run")
def run_allocate(segment_id: int = 1, db: Session = Depends(get_db)):
    seg, pillars, vendors = _gather_inputs(db, segment_id)
    # 永远按本次提交瞬间的输入重算：最新锚点、容差随改随生效，不吃改前落点。
    result = _compute(seg, pillars, vendors)
    run = AllocationRun(segment_id=segment_id, created_at=datetime.utcnow(),
                        result_json=json.dumps(result, ensure_ascii=False))
    db.add(run); db.commit(); db.refresh(run)
    return {"id": run.id, **result}


@router.get("/latest")
def latest(segment_id: int = 1, db: Session = Depends(get_db)):
    seg, pillars, vendors = _gather_inputs(db, segment_id)
    current_fp = _input_fingerprint(seg, pillars, vendors)
    run = db.scalars(select(AllocationRun).where(AllocationRun.segment_id == segment_id)
                     .order_by(AllocationRun.id.desc())).first()
    if run is not None:
        data = json.loads(run.result_json)
        # 指纹缺失（锚点功能前的旧 run）或与当前米标/容差不符：旧带子结果作废，
        # 立即按提交瞬间的新带子重算，禁止前端吃到改前落点。
        if data.get("input_fingerprint") == current_fp:
            return {"id": run.id, **data}
    return run_allocate(segment_id=segment_id, db=db)
