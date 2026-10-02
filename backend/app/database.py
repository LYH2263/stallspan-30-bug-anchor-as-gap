from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def ensure_schema() -> dict:
    """对已存在的表做幂等补列（create_all 不会给旧表加新列），返回本次结构变更。

    锚点功能在 vendors 上新增 anchor_m / anchor_tolerance_m。
    仅当检测到旧表缺列（即从锚点功能上线前的库升级）时才返回
    ``vendors_anchor_added=True``，供种子做**一次性**回填；新建库与后续启动
    都为 False，从而不会覆盖摊主日后主动设置或清空的锚点。
    """
    changes = {"vendors_anchor_added": False}
    with engine.begin() as conn:
        insp = inspect(conn)
        has_vendors = insp.has_table("vendors")
        existing = {c["name"] for c in insp.get_columns("vendors")} if has_vendors else set()
        for col in ("anchor_m", "anchor_tolerance_m"):
            if col not in existing:
                if not changes["vendors_anchor_added"]:
                    changes["vendors_anchor_added"] = has_vendors
                conn.execute(text(
                    f"ALTER TABLE vendors ADD COLUMN IF NOT EXISTS {col} DOUBLE PRECISION"
                ))
    return changes


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
