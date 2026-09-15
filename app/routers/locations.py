from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=schemas.Page[schemas.LocationOut])
def get_all(
    active_only: bool = Query(True),
    search: str | None = None,
    limit: int = Query(20, le=2000),
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: models.User = Depends(security.get_current_user),
):
    stmt = select(models.Location)
    if active_only:
        stmt = stmt.where(models.Location.is_active.is_(True))
    if search and search.strip():
        s = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                models.Location.name.ilike(s),
                models.Location.code.ilike(s),
                models.Location.city.ilike(s),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(models.Location.id).subquery()))

    stmt = stmt.order_by(models.Location.name).offset(offset).limit(limit)
    items = db.scalars(stmt).all()
    return schemas.Page(items=items, total=total or 0, limit=limit, offset=offset)


@router.get("/breakdown", response_model=list[schemas.LocationBreakdownOut])
def breakdown(db: Session = Depends(get_db),
              _user: models.User = Depends(security.get_current_user)):
    locs = db.scalars(
        select(models.Location).where(models.Location.is_active.is_(True)).order_by(models.Location.name)
    ).all()
    assets = db.scalars(
        select(models.Asset).where(models.Asset.is_active.is_(True), models.Asset.status == "deployed")
    ).all()

    count_map: dict = {}
    damage_map: dict = {}
    for a in assets:
        if a.current_location_id is None:
            continue
        count_map[a.current_location_id] = count_map.get(a.current_location_id, 0) + 1
        if a.condition in ("for_disposal", "damaged"):
            damage_map[a.current_location_id] = damage_map.get(a.current_location_id, 0) + 1

    return [
        schemas.LocationBreakdownOut(
            id=loc.id, name=loc.name, code=loc.code, city=loc.city,
            asset_count=count_map.get(loc.id, 0),
            damaged_count=damage_map.get(loc.id, 0),
        )
        for loc in locs
    ]


@router.get("/by-code/{code}", response_model=schemas.LocationOut)
def get_by_code(code: str, db: Session = Depends(get_db),
                 _user: models.User = Depends(security.get_current_user)):
    loc = db.scalar(select(models.Location).where(models.Location.code == code))
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return loc


@router.get("/{location_id}", response_model=schemas.LocationOut)
def get_by_id(location_id: str, db: Session = Depends(get_db),
              _user: models.User = Depends(security.get_current_user)):
    loc = db.get(models.Location, location_id)
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return loc


@router.post("", response_model=schemas.LocationOut)
def create(payload: schemas.LocationCreate, db: Session = Depends(get_db),
           user: models.User = Depends(security.get_current_user)):
    loc = models.Location(
        name=payload.name,
        code=payload.code.upper(),
        address=payload.address,
        city=payload.city,
        province=payload.province,
        latitude=payload.latitude,
        longitude=payload.longitude,
        created_by=user.id,
        is_active=True,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return loc


@router.patch("/{location_id}", response_model=schemas.LocationOut)
def update(location_id: str, payload: schemas.LocationUpdate, db: Session = Depends(get_db),
           _user: models.User = Depends(security.get_current_user)):
    loc = db.get(models.Location, location_id)
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    data = payload.model_dump(exclude_unset=True)
    if "code" in data and data["code"]:
        data["code"] = data["code"].upper()
    for k, v in data.items():
        setattr(loc, k, v)
    loc.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(loc)
    return loc


@router.post("/{location_id}/deactivate")
def deactivate(location_id: str, db: Session = Depends(get_db),
               _user: models.User = Depends(security.get_current_user)):
    loc = db.get(models.Location, location_id)
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    loc.is_active = False
    db.commit()
    return {"ok": True}