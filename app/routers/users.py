from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/users", tags=["users"])


# ── app_users management (mirrors AuthRepository) ───────────────────────────

@router.get("", response_model=schemas.Page[schemas.AppUserOut])
def get_all_users(
    search: str | None = None,
    limit: int = Query(20, le=2000),
    offset: int = 0,
    db: Session = Depends(get_db),
    _user: models.User = Depends(security.get_current_user),
):
    stmt = select(models.User)
    if search and search.strip():
        s = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(models.User.full_name.ilike(s), models.User.username.ilike(s))
        )

    total = db.scalar(select(func.count()).select_from(stmt.with_only_columns(models.User.id).subquery()))

    stmt = stmt.order_by(models.User.full_name).offset(offset).limit(limit)
    items = db.scalars(stmt).all()
    return schemas.Page(items=items, total=total or 0, limit=limit, offset=offset)


@router.post("", response_model=schemas.AppUserOut)
def create_user(payload: schemas.CreateUserRequest, db: Session = Depends(get_db),
                 _admin: models.User = Depends(security.require_admin)):
    existing = db.scalar(select(models.User).where(models.User.username == payload.username.strip().lower()))
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = models.User(
        username=payload.username.strip().lower(),
        full_name=payload.full_name.strip(),
        role=payload.role,
        phone=payload.phone,
        employee_id=payload.employee_id,
        password_hash=security.hash_password(payload.password),
        must_change_password=True,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/reset-password")
def reset_password(user_id: str, db: Session = Depends(get_db),
                    _admin: models.User = Depends(security.require_admin)):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = security.hash_password("Welcome@1234")
    user.must_change_password = True
    db.commit()
    return {"ok": True}


@router.patch("/{user_id}/role")
def update_role(user_id: str, payload: schemas.UpdateRoleRequest, db: Session = Depends(get_db),
                 _admin: models.User = Depends(security.require_admin)):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = payload.role
    db.commit()
    return {"ok": True}


@router.post("/{user_id}/deactivate")
def deactivate_user(user_id: str, db: Session = Depends(get_db),
                     _admin: models.User = Depends(security.require_admin)):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    return {"ok": True}


# ── Profiles (mirrors former `user_profiles` table used by UserRepository) ───

@router.get("/profiles", response_model=list[schemas.UserProfileOut])
def get_all_profiles(db: Session = Depends(get_db),
                      _user: models.User = Depends(security.get_current_user)):
    rows = db.scalars(
        select(models.User).where(models.User.is_active.is_(True)).order_by(models.User.full_name)
    ).all()
    return rows


@router.get("/profiles/{user_id}", response_model=schemas.UserProfileOut)
def get_profile(user_id: str, db: Session = Depends(get_db),
                 _user: models.User = Depends(security.get_current_user)):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user