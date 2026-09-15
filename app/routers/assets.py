import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/assets", tags=["assets"])


def _asset_out(a: models.Asset) -> schemas.AssetOut:
    return schemas.AssetOut(
        id=a.id, asset_code=a.asset_code, name=a.name, asset_type=a.asset_type,
        description=a.description, set_id=a.set_id, category=a.category, brand=a.brand,
        set_code=a.set_code, part_number=a.part_number, purchase_date=a.purchase_date,
        purchase_value=float(a.purchase_value) if a.purchase_value is not None else None,
        condition=a.condition, status=a.status, current_location_id=a.current_location_id,
        current_location_name=a.location.name if a.location else None,
        qr_code_data=a.qr_code_data, photo_url=a.photo_url, notes=a.notes,
        is_active=a.is_active, created_at=a.created_at, updated_at=a.updated_at,
        last_seen_at=a.last_seen_at,
    )


@router.get("", response_model=schemas.Page[schemas.AssetWithLocationOut])
def get_assets(
    location_id: str | None = None,
    condition: str | None = None,
    status: str | None = None,
    set_id: str | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = Query(20, le=5000),
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: models.User = Depends(security.get_current_user),
):
    stmt = select(models.Asset).options(selectinload(models.Asset.location)).where(models.Asset.is_active.is_(True))
    if location_id:
        stmt = stmt.where(models.Asset.current_location_id == location_id)
    if condition:
        stmt = stmt.where(models.Asset.condition == condition)
    if status:
        stmt = stmt.where(models.Asset.status == status)
    if set_id:
        stmt = stmt.where(models.Asset.set_id == set_id)
    if category:
        stmt = stmt.where(models.Asset.category == category)
    if search and search.strip():
        s = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                models.Asset.asset_code.ilike(s),
                models.Asset.name.ilike(s),
                models.Asset.category.ilike(s),
                models.Asset.brand.ilike(s),
            )
        )

    # Total across the WHOLE filtered set (not just the current page) —
    # needed so search results are correct no matter which page you're on.
    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(models.Asset.id).subquery()))

    stmt = stmt.order_by(models.Asset.updated_at.desc()).offset(offset).limit(limit)
    assets = db.scalars(stmt).all()

    set_ids = {a.set_id for a in assets if a.set_id}
    set_map = {}
    if set_ids:
        sets = db.scalars(select(models.AssetSet).where(models.AssetSet.id.in_(set_ids))).all()
        set_map = {s.id: s.name for s in sets}

    items = [
        schemas.AssetWithLocationOut(
            asset=_asset_out(a),
            location_name=a.location.name if a.location else None,
            set_name=set_map.get(a.set_id) if a.set_id else None,
        )
        for a in assets
    ]
    return schemas.Page(items=items, total=total or 0, limit=limit, offset=offset)


@router.get("/categories", response_model=list[str])
def get_categories(db: Session = Depends(get_db),
                    _user: models.User = Depends(security.get_current_user)):
    rows = db.scalars(
        select(models.Asset.category).where(
            models.Asset.is_active.is_(True), models.Asset.category.is_not(None)
        )
    ).all()
    return sorted(set(rows))


@router.get("/by-code/{code}", response_model=schemas.AssetOut)
def get_by_code(code: str, db: Session = Depends(get_db),
                 _user: models.User = Depends(security.get_current_user)):
    a = db.scalar(
        select(models.Asset).options(selectinload(models.Asset.location))
        .where(models.Asset.asset_code == code, models.Asset.is_active.is_(True))
    )
    if a is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _asset_out(a)


@router.get("/{asset_id}", response_model=schemas.AssetOut)
def get_by_id(asset_id: str, db: Session = Depends(get_db),
              _user: models.User = Depends(security.get_current_user)):
    a = db.scalar(
        select(models.Asset).options(selectinload(models.Asset.location)).where(models.Asset.id == asset_id)
    )
    if a is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return _asset_out(a)


@router.get("/{asset_id}/history", response_model=schemas.Page[schemas.ConditionLogOut])
def get_history(
    asset_id: str,
    limit: int = Query(20, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: models.User = Depends(security.get_current_user),
):
    total = db.scalar(
        select(func.count()).select_from(
            select(models.ConditionLog.id)
            .where(models.ConditionLog.asset_id == asset_id)
            .subquery()
        )
    )
    logs = db.scalars(
        select(models.ConditionLog)
        .where(models.ConditionLog.asset_id == asset_id)
        .order_by(models.ConditionLog.scanned_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return schemas.Page(items=_enrich_logs(db, logs), total=total or 0, limit=limit, offset=offset)


@router.post("", response_model=schemas.AssetOut)
def create_asset(payload: schemas.AssetCreate, db: Session = Depends(get_db),
                  user: models.User = Depends(security.get_current_user)):
    existing = db.scalar(select(models.Asset).where(models.Asset.asset_code == payload.asset_code))
    if existing:
        raise HTTPException(status_code=409, detail="Asset code already exists")
    asset = models.Asset(
        asset_code=payload.asset_code,
        name=payload.name,
        asset_type=payload.asset_type,
        description=payload.description,
        set_id=payload.set_id,
        category=payload.category,
        brand=payload.brand,
        set_code=payload.set_code,
        part_number=payload.part_number,
        purchase_date=payload.purchase_date,
        purchase_value=payload.purchase_value,
        condition=payload.condition,
        status="in_storage",
        current_location_id=payload.location_id,
        qr_code_data=payload.asset_code,
        is_active=True,
        created_by=payload.created_by or user.id,
        updated_by=payload.created_by or user.id,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return _asset_out(asset)


@router.patch("/{asset_id}", response_model=schemas.AssetOut)
def update_asset(asset_id: str, payload: schemas.AssetUpdate, db: Session = Depends(get_db),
                  _user: models.User = Depends(security.get_current_user)):
    asset = db.get(models.Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(asset, k, v)
    asset.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(asset)
    return _asset_out(asset)


@router.post("/{asset_id}/condition-status", response_model=schemas.AssetOut)
def update_condition_and_status(asset_id: str, payload: schemas.AssetConditionStatusUpdate,
                                 db: Session = Depends(get_db),
                                 _user: models.User = Depends(security.get_current_user)):
    asset = db.get(models.Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.condition = payload.condition
    asset.status = payload.status
    asset.current_location_id = payload.location_id  # always overwritten, matches Flutter behavior
    if payload.updated_by:
        asset.updated_by = payload.updated_by
    asset.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(asset)
    return _asset_out(asset)


@router.post("/{asset_id}/deactivate")
def soft_delete(asset_id: str, updated_by: str, db: Session = Depends(get_db),
                 _user: models.User = Depends(security.get_current_user)):
    asset = db.get(models.Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.is_active = False
    asset.updated_by = updated_by
    asset.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.post("/{asset_id}/touch", response_model=schemas.AssetOut)
def touch_last_seen(asset_id: str, db: Session = Depends(get_db),
                     _user: models.User = Depends(security.get_current_user)):
    asset = db.get(models.Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(asset)
    return _asset_out(asset)


@router.post("/scan-events", response_model=schemas.ConditionLogOut)
def log_scan_event(payload: schemas.ScanEventCreate, db: Session = Depends(get_db),
                    _user: models.User = Depends(security.get_current_user)):
    log = models.ConditionLog(
        asset_id=payload.asset_id,
        set_id=payload.set_id,
        scanned_by=payload.scanned_by,
        location_id=payload.location_id,
        event_type=payload.event_type,
        condition_before=payload.condition_before,
        condition_after=payload.condition_after,
        status_before=payload.status_before,
        status_after=payload.status_after,
        notes=payload.notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return _enrich_logs(db, [log])[0]


@router.post("/import", response_model=schemas.ImportResultOut)
def batch_import(rows: list[dict], db: Session = Depends(get_db),
                  _user: models.User = Depends(security.get_current_user)):
    success, failed = 0, 0
    errors: list[str] = []
    for m in rows:
        code = m.get("asset_code") or m.get("code") or ""
        existing = db.scalar(select(models.Asset).where(models.Asset.asset_code == code))
        if existing:
            errors.append(f"{code}: already exists, skipped")
            failed += 1
            continue
        try:
            asset = models.Asset(
                asset_code=code,
                name=m.get("name") or code,
                asset_type=m.get("asset_type") or "individual",
                category=m.get("category"),
                brand=m.get("brand"),
                set_code=m.get("set_code"),
                part_number=m.get("part_number"),
                condition=m.get("condition") or "good",
                status=m.get("status") or "in_storage",
                is_active=True,
            )
            db.add(asset)
            db.commit()
            success += 1
        except Exception as e:  # noqa: BLE001
            db.rollback()
            errors.append(f"{code}: {e}")
            failed += 1
    return schemas.ImportResultOut(success=success, failed=failed, errors=errors)


def compute_dashboard_summary(db: Session) -> schemas.DashboardSummaryOut:
    assets = db.scalars(select(models.Asset).where(models.Asset.is_active.is_(True))).all()
    deployed = in_storage = maintenance = disposed = 0
    good = for_repair = for_replacement = for_disposal = 0
    active_sites = set()
    for a in assets:
        if a.status == "deployed":
            deployed += 1
        elif a.status == "in_storage":
            in_storage += 1
        elif a.status == "maintenance":
            maintenance += 1
        elif a.status == "disposed":
            disposed += 1
        if a.condition == "good":
            good += 1
        elif a.condition == "for_repair":
            for_repair += 1
        elif a.condition == "for_replacement":
            for_replacement += 1
        elif a.condition == "for_disposal":
            for_disposal += 1
        if a.status == "deployed" and a.current_location_id:
            active_sites.add(a.current_location_id)

    return schemas.DashboardSummaryOut(
        total_assets=len(assets), deployed=deployed, in_storage=in_storage,
        in_maintenance=maintenance, disposed=disposed, condition_good=good,
        condition_for_repair=for_repair, condition_for_replacement=for_replacement,
        condition_for_disposal=for_disposal, active_sites=len(active_sites),
    )


# ── Shared helper also used by condition_logs router ──────────────────────────

def _enrich_logs(db: Session, logs: list[models.ConditionLog]) -> list[schemas.ConditionLogOut]:
    if not logs:
        return []
    user_ids = {log.scanned_by for log in logs}
    users = db.scalars(select(models.User).where(models.User.id.in_(user_ids))).all()
    user_map = {u.id: u.full_name for u in users}

    loc_ids = {log.location_id for log in logs if log.location_id}
    loc_map = {}
    if loc_ids:
        locs = db.scalars(select(models.Location).where(models.Location.id.in_(loc_ids))).all()
        loc_map = {l.id: l.name for l in locs}

    asset_ids = {log.asset_id for log in logs}
    asset_code_map, asset_name_map = {}, {}
    if asset_ids:
        assets = db.scalars(select(models.Asset).where(models.Asset.id.in_(asset_ids))).all()
        asset_code_map = {a.id: a.asset_code for a in assets}
        asset_name_map = {a.id: a.name for a in assets}

    out = []
    for log in logs:
        out.append(schemas.ConditionLogOut(
            id=log.id, asset_id=log.asset_id,
            asset_code=asset_code_map.get(log.asset_id),
            asset_name=asset_name_map.get(log.asset_id),
            scanned_by=log.scanned_by,
            scanned_by_name=user_map.get(log.scanned_by, str(log.scanned_by)),
            event_type=log.event_type, condition_after=log.condition_after,
            status_after=log.status_after, set_id=log.set_id, location_id=log.location_id,
            location_name=loc_map.get(log.location_id) if log.location_id else None,
            condition_before=log.condition_before, status_before=log.status_before,
            notes=log.notes, photo_url=log.photo_url, scanned_at=log.scanned_at,
        ))
    return out