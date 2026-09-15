from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

# ── Brute-force lockout settings ────────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


@router.post("/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    username = payload.username.strip().lower()
    # NOTE: deliberately not filtering is_active in this query — we need
    # the user row regardless, so an inactive OR locked-out account still
    # gets a clear, specific message instead of the generic "invalid
    # username or password" (which is only for genuinely wrong credentials).
    user = db.scalar(select(models.User).where(models.User.username == username))

    now = datetime.now(timezone.utc)

    if user is not None and user.locked_until is not None:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            # Some DB drivers return naive datetimes even for
            # timezone-aware columns — treat naive values as UTC rather
            # than risk a comparison crash.
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > now:
            remaining_seconds = max(60, int((locked_until - now).total_seconds()) + 1)
            remaining_minutes = max(1, remaining_seconds // 60 + (1 if remaining_seconds % 60 else 0))
            raise HTTPException(
                status_code=429,
                detail={
                    "message": f"Too many failed attempts. Try again in {remaining_minutes} minute"
                               f"{'s' if remaining_minutes != 1 else ''}.",
                    "retry_after_seconds": remaining_seconds,
                },
            )
        # Lockout window has passed — clear it so this attempt is evaluated
        # normally below.
        user.locked_until = None
        user.failed_login_attempts = 0

    if (
        user is None
        or not user.is_active
        or not security.verify_password(payload.password, user.password_hash)
    ):
        # Only track/increment attempts against a real, active account —
        # doing this for unknown usernames too would let someone lock out
        # an account they don't control by repeatedly failing on purpose,
        # and it's meaningless for accounts that don't exist.
        if user is not None and user.is_active:
            user.failed_login_attempts += 1
            remaining = MAX_FAILED_ATTEMPTS - user.failed_login_attempts
            if remaining <= 0:
                user.locked_until = now + LOCKOUT_DURATION
                db.commit()
                raise HTTPException(
                    status_code=429,
                    detail={
                        "message": f"Too many failed attempts. Try again in "
                                   f"{int(LOCKOUT_DURATION.total_seconds() // 60)} minutes.",
                        "retry_after_seconds": int(LOCKOUT_DURATION.total_seconds()),
                    },
                )
            db.commit()
            # Warn before the account actually locks, but only once it's
            # close — no need to nag on the very first typo.
            if remaining <= 2:
                raise HTTPException(
                    status_code=401,
                    detail=f"Invalid username or password. {remaining} attempt"
                           f"{'s' if remaining != 1 else ''} remaining before your "
                           f"account is temporarily locked.",
                )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Successful login — clear any lockout tracking.
    if user.failed_login_attempts != 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

    # Transparently upgrade a pre-bcrypt hash now that we've verified the
    # plaintext password against it — the user never notices this happens.
    if security.needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(payload.password)
        db.commit()

    token = security.create_access_token(user.id)
    return schemas.LoginResponse(
        access_token=token,
        user=schemas.SessionUserOut(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
        ),
        must_change_password=user.must_change_password,
    )


@router.get("/me", response_model=schemas.SessionUserOut)
def me(user: models.User = Depends(security.get_current_user)):
    return schemas.SessionUserOut(
        id=user.id, username=user.username, full_name=user.full_name,
        role=user.role, is_active=user.is_active,
    )


@router.get("/must-change-password/{user_id}")
def must_change_password(user_id: str, db: Session = Depends(get_db),
                          _user: models.User = Depends(security.get_current_user)):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"must_change_password": user.must_change_password}


@router.post("/change-password")
def change_password(payload: schemas.ChangePasswordRequest, db: Session = Depends(get_db),
                     _user: models.User = Depends(security.get_current_user)):
    user = db.get(models.User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = security.hash_password(payload.new_password)
    user.must_change_password = False
    db.commit()
    return {"ok": True}