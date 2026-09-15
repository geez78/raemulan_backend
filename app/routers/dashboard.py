from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas, security
from ..database import get_db
from .assets import compute_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=schemas.DashboardSummaryOut)
def summary(db: Session = Depends(get_db),
            _user: models.User = Depends(security.get_current_user)):
    return compute_dashboard_summary(db)
