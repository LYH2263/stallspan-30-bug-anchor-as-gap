from datetime import date
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.models import MarketDay, Pillar, Segment, Vendor

# 种子锚点：林记糖水期望锚点 11m、容差 ±1m（起点须落在 10～12，且不跨柱）。
SEED_ANCHORS = {
    "林记糖水": (11.0, 1.0),
}


def seed_if_empty(db: Session, backfill_anchors: bool = False) -> None:
    is_empty = (db.scalar(select(func.count()).select_from(MarketDay)) or 0) == 0
    if is_empty:
        day = MarketDay(name="周末夜市", day=date(2026, 9, 20))
        db.add(day); db.flush()
        seg = Segment(market_day_id=day.id, name="东街段", width_m=30.0)
        db.add(seg); db.flush()
        db.add(Pillar(segment_id=seg.id, position_m=10.0, thickness_m=0.5, label="灯柱A"))
        db.add(Pillar(segment_id=seg.id, position_m=20.0, thickness_m=0.5, label="灯柱B"))
        vendors = [
            ("阿强烧烤", 4.0, 1), ("林记糖水", 3.0, 1), ("老周水果", 5.0, 2),
            ("小美饰品", 2.5, 2), ("大碗面", 6.0, 1), ("手作皮具", 3.5, 3),
            ("巨型舞台车", 12.0, 9),
        ]
        for name, wdt, pri in vendors:
            anchor, tol = SEED_ANCHORS.get(name, (None, None))
            db.add(Vendor(market_day_id=day.id, name=name, stall_width_m=wdt, priority=pri,
                          anchor_m=anchor, anchor_tolerance_m=tol))
        db.commit()
    elif backfill_anchors:
        # 从锚点功能上线前的旧库升级：锚点列本次才新增，所有摊主此前无法设置锚点，
        # 因此对种子摊主做**一次性**回填。此后启动不再进入本分支，绝不覆盖摊主
        # 在页面上设置或主动清空的值。
        for name, (anchor, tol) in SEED_ANCHORS.items():
            row = db.scalars(select(Vendor).where(Vendor.name == name)).first()
            if row is not None:
                row.anchor_m = anchor
                row.anchor_tolerance_m = tol
        db.commit()
