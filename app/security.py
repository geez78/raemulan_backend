import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from . import models

bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    """bcrypt — salted, deliberately slow (tunable cost factor), the
    standard choice for password storage. Replaces the old unsalted
    SHA-256 hex digest, which was fast enough to brute-force offline if
    the database were ever leaked."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _legacy_sha256(password: str) -> str:
    """Old hashing scheme, kept ONLY so accounts created before the bcrypt
    migration can still log in — see verify_password()."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    """Bcrypt hashes always start with a $2 prefix; anything else is
    assumed to be a pre-migration SHA-256 hash. Checking the prefix lets
    both formats coexist during the transition without a schema change or
    a one-time migration script that would need every user's plaintext
    password (which we never have)."""
    if stored_hash.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except ValueError:
            return False
    return _legacy_sha256(password) == stored_hash


def needs_rehash(stored_hash: str) -> bool:
    """True for any hash that isn't bcrypt yet — used to silently upgrade
    a user's hash to bcrypt right after they successfully log in with
    their correct password, without ever requiring a forced password
    reset."""
    return not stored_hash.startswith("$2")


def create_access_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    user_id = decode_access_token(credentials.credentials)
    user = db.get(models.User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user