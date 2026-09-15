from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from .assets import _enrich_logs

router = APIRouter(prefix="/condition-logs", tags=["condition-logs"])


@router.get("", response_model=schemas.Page[schemas.ConditionLogOut])
def get_logs(
    asset_id: str | None = None,
    set_id: str | None = None,
    location_id: str | None = None,
    limit: int = Query(20, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: models.User = Depends(security.get_current_user),
):
    """Unified endpoint covering getForAsset / getForSet / getForLocation / getRecent."""
    stmt = select(models.ConditionLog)
    if asset_id:
        stmt = stmt.where(models.ConditionLog.asset_id == asset_id)
    if set_id:
        stmt = stmt.where(models.ConditionLog.set_id == set_id)
    if location_id:
        stmt = stmt.where(models.ConditionLog.location_id == location_id)

    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(models.ConditionLog.id).subquery()))

    stmt = stmt.order_by(models.ConditionLog.scanned_at.desc()).offset(offset).limit(limit)
    logs = db.scalars(stmt).all()
    return schemas.Page(items=_enrich_logs(db, logs), total=total or 0, limit=limit, offset=offset)


@router.get("/recent", response_model=schemas.Page[schemas.ConditionLogOut])
def get_recent(limit: int = Query(20, le=1000), offset: int = 0, db: Session = Depends(get_db),
                _user: models.User = Depends(security.get_current_user)):
    total = db.scalar(select(func.count()).select_from(models.ConditionLog))
    logs = db.scalars(
        select(models.ConditionLog)
        .order_by(models.ConditionLog.scanned_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return schemas.Page(items=_enrich_logs(db, logs), total=total or 0, limit=limit, offset=offset)
