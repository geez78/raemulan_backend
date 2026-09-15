from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/lookups", tags=["lookups"])


# ── Categories ────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[schemas.LookupOut])
def get_categories(db: Session = Depends(get_db),
                    _user: models.User = Depends(security.get_current_user)):
    rows = db.scalars(
        select(models.AssetCategory).where(models.AssetCategory.is_active.is_(True))
        .order_by(models.AssetCategory.name)
    ).all()
    return rows


@router.post("/categories", response_model=schemas.LookupOut)
def create_category(payload: schemas.LookupCreate, db: Session = Depends(get_db),
                     _user: models.User = Depends(security.get_current_user)):
    row = models.AssetCategory(name=payload.name, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/categories/{item_id}/deactivate")
def deactivate_category(item_id: str, db: Session = Depends(get_db),
                         _user: models.User = Depends(security.get_current_user)):
    row = db.get(models.AssetCategory, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    row.is_active = False
    db.commit()
    return {"ok": True}


# ── Asset types ───────────────────────────────────────────────────────────────

@router.get("/asset-types", response_model=list[schemas.AssetTypeLookupOut])
def get_asset_types(db: Session = Depends(get_db),
                     _user: models.User = Depends(security.get_current_user)):
    rows = db.scalars(
        select(models.AssetTypeLookup).where(models.AssetTypeLookup.is_active.is_(True))
        .order_by(models.AssetTypeLookup.name)
    ).all()
    return rows


@router.post("/asset-types", response_model=schemas.AssetTypeLookupOut)
def create_asset_type(payload: schemas.AssetTypeLookupCreate, db: Session = Depends(get_db),
                       _user: models.User = Depends(security.get_current_user)):
    code = payload.code.strip().lower().replace(" ", "_")
    existing = db.scalar(select(models.AssetTypeLookup).where(models.AssetTypeLookup.code == code))
    if existing:
        raise HTTPException(status_code=409, detail="Code already exists")
    row = models.AssetTypeLookup(name=payload.name, code=code, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/asset-types/{item_id}/deactivate")
def deactivate_asset_type(item_id: str, db: Session = Depends(get_db),
                           _user: models.User = Depends(security.get_current_user)):
    row = db.get(models.AssetTypeLookup, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    row.is_active = False
    db.commit()
    return {"ok": True}


# ── Set codes ─────────────────────────────────────────────────────────────────

@router.get("/set-codes", response_model=list[schemas.LookupOut])
def get_set_codes(db: Session = Depends(get_db),
                   _user: models.User = Depends(security.get_current_user)):
    rows = db.scalars(
        select(models.SetCode).where(models.SetCode.is_active.is_(True))
        .order_by(models.SetCode.name)
    ).all()
    return rows


@router.post("/set-codes", response_model=schemas.LookupOut)
def create_set_code(payload: schemas.LookupCreate, db: Session = Depends(get_db),
                     _user: models.User = Depends(security.get_current_user)):
    row = models.SetCode(name=payload.name, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/set-codes/{item_id}/deactivate")
def deactivate_set_code(item_id: str, db: Session = Depends(get_db),
                         _user: models.User = Depends(security.get_current_user)):
    row = db.get(models.SetCode, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    row.is_active = False
    db.commit()
    return {"ok": True}
