from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/asset-sets", tags=["asset-sets"])


def _set_out(s: models.AssetSet, location_name: str | None = None) -> schemas.AssetSetOut:
    return schemas.AssetSetOut(
        id=s.id, set_code=s.set_code, name=s.name, description=s.description,
        total_units=s.total_units, asset_type=s.asset_type, status=s.status,
        current_location_id=s.current_location_id, current_location_name=location_name,
        notes=s.notes, created_at=s.created_at, updated_at=s.updated_at,
    )


@router.get("", response_model=list[schemas.AssetSetOut])
def get_all(location_id: str | None = None, status: str | None = None,
            db: Session = Depends(get_db), _user: models.User = Depends(security.get_current_user)):
    stmt = select(models.AssetSet)
    if location_id:
        stmt = stmt.where(models.AssetSet.current_location_id == location_id)
    if status:
        stmt = stmt.where(models.AssetSet.status == status)
    stmt = stmt.order_by(models.AssetSet.updated_at.desc())
    return [_set_out(s) for s in db.scalars(stmt).all()]


@router.get("/with-stats", response_model=list[schemas.AssetSetWithStatsOut])
def get_all_with_stats(db: Session = Depends(get_db),
                        _user: models.User = Depends(security.get_current_user)):
    sets = db.scalars(select(models.AssetSet).order_by(models.AssetSet.updated_at.desc())).all()
    return [_with_stats(db, s) for s in sets]


@router.get("/by-code/{code}", response_model=schemas.AssetSetOut)
def get_by_code(code: str, db: Session = Depends(get_db),
                 _user: models.User = Depends(security.get_current_user)):
    s = db.scalar(select(models.AssetSet).where(models.AssetSet.set_code == code))
    if s is None:
        raise HTTPException(status_code=404, detail="Asset set not found")
    return _set_out(s)


@router.get("/{set_id}", response_model=schemas.AssetSetOut)
def get_by_id(set_id: str, db: Session = Depends(get_db),
              _user: models.User = Depends(security.get_current_user)):
    s = db.get(models.AssetSet, set_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Asset set not found")
    return _set_out(s)


@router.get("/{set_id}/stats", response_model=schemas.AssetSetWithStatsOut)
def get_with_stats(set_id: str, db: Session = Depends(get_db),
                    _user: models.User = Depends(security.get_current_user)):
    s = db.get(models.AssetSet, set_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Asset set not found")
    return _with_stats(db, s)


def _with_stats(db: Session, s: models.AssetSet) -> schemas.AssetSetWithStatsOut:
    members = db.scalars(
        select(models.Asset).where(models.Asset.set_id == s.id, models.Asset.is_active.is_(True))
    ).all()
    good = fair = damaged = 0
    for m in members:
        if m.condition == "good":
            good += 1
        elif m.condition in ("for_repair", "for_replacement"):
            fair += 1
        elif m.condition == "for_disposal":
            damaged += 1

    location_name = None
    if s.current_location_id:
        loc = db.get(models.Location, s.current_location_id)
        location_name = loc.name if loc else None

    return schemas.AssetSetWithStatsOut(
        set=_set_out(s, location_name=location_name),
        member_count=len(members), good_count=good, fair_count=fair,
        damaged_count=damaged, location_name=location_name,
    )


@router.post("", response_model=schemas.AssetSetOut)
def create_set(payload: schemas.AssetSetCreate, db: Session = Depends(get_db),
                user: models.User = Depends(security.get_current_user)):
    existing = db.scalar(select(models.AssetSet).where(models.AssetSet.set_code == payload.set_code))
    if existing:
        raise HTTPException(status_code=409, detail="Set code already exists")
    s = models.AssetSet(
        set_code=payload.set_code, name=payload.name, description=payload.description,
        total_units=payload.total_units, asset_type=payload.asset_type, status="in_storage",
        notes=payload.notes, created_by=payload.created_by or user.id,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _set_out(s)


@router.patch("/{set_id}/status-location")
def update_status_location(set_id: str, payload: schemas.AssetSetStatusLocationUpdate,
                            db: Session = Depends(get_db),
                            _user: models.User = Depends(security.get_current_user)):
    s = db.get(models.AssetSet, set_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Asset set not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(s, k, v)
    s.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.post("/{set_id}/deploy")
def deploy_set(set_id: str, payload: schemas.DeploySetRequest, db: Session = Depends(get_db),
                _user: models.User = Depends(security.get_current_user)):
    s = db.get(models.AssetSet, set_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Asset set not found")
    now = datetime.now(timezone.utc)
    s.current_location_id = payload.location_id
    s.status = "deployed"
    s.updated_at = now
    db.query(models.Asset).filter(models.Asset.set_id == set_id).update({
        "current_location_id": payload.location_id,
        "status": "deployed",
        "updated_by": payload.updated_by,
        "updated_at": now,
    })
    db.commit()
    return {"ok": True}


@router.post("/{set_id}/pull-out")
def pull_out_set(set_id: str, payload: schemas.PullOutSetRequest, db: Session = Depends(get_db),
                  _user: models.User = Depends(security.get_current_user)):
    s = db.get(models.AssetSet, set_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Asset set not found")
    now = datetime.now(timezone.utc)
    s.current_location_id = None
    s.status = "in_storage"
    s.updated_at = now
    db.query(models.Asset).filter(models.Asset.set_id == set_id).update({
        "current_location_id": None,
        "status": "in_storage",
        "updated_by": payload.updated_by,
        "updated_at": now,
    })
    db.commit()
    return {"ok": True}
