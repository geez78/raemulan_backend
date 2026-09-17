import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas, security
from ..database import get_db
from .assets import _asset_out, _enrich_logs
from .asset_sets import _set_out

router = APIRouter(prefix="/sync", tags=["sync"])


# ── Pull: "give me everything that changed since <since>" ────────────────────

@router.get("/pull", response_model=schemas.SyncPullResponse)
def pull(
    since: datetime | None = Query(
        None, description="ISO8601 timestamp of the last successful pull. Omit for a full first sync."
    ),
    db: Session = Depends(get_db),
    _user: models.User = Depends(security.get_current_user),
):
    # Captured before we run the queries below so that anything written to
    # the DB between "now" and when the response is built is simply picked
    # up again on the *next* pull, instead of being silently missed.
    server_time = datetime.now(timezone.utc)

    asset_stmt = select(models.Asset).options(selectinload(models.Asset.location))
    location_stmt = select(models.Location)
    set_stmt = select(models.AssetSet)
    log_stmt = select(models.ConditionLog)

    if since is not None:
        asset_stmt = asset_stmt.where(models.Asset.updated_at > since)
        location_stmt = location_stmt.where(models.Location.updated_at > since)
        set_stmt = set_stmt.where(models.AssetSet.updated_at > since)
        # ConditionLog has no updated_at (it's an immutable event log) —
        # created_at is what we compare against instead.
        log_stmt = log_stmt.where(models.ConditionLog.created_at > since)

    assets = db.scalars(asset_stmt).all()
    locations = db.scalars(location_stmt).all()
    asset_sets = db.scalars(set_stmt).all()
    logs = db.scalars(log_stmt.order_by(models.ConditionLog.created_at)).all()

    return schemas.SyncPullResponse(
        server_time=server_time,
        assets=[_asset_out(a) for a in assets],
        locations=[schemas.LocationOut.model_validate(l) for l in locations],
        asset_sets=[_set_out(s) for s in asset_sets],
        condition_logs=_enrich_logs(db, logs),
    )


# ── Push: "here's a batch of things I did offline, apply them in order" ──────

@router.post("/push", response_model=schemas.SyncPushResponse)
def push(
    ops: list[schemas.SyncPushOp],
    db: Session = Depends(get_db),
    user: models.User = Depends(security.get_current_user),
):
    results: list[schemas.SyncPushOpResult] = []

    for op in ops:
        try:
            _apply_op(db, op, user)
            db.commit()
            results.append(schemas.SyncPushOpResult(op_id=op.op_id, status="ok"))
        except Exception as e:  # noqa: BLE001
            # One bad/conflicting op must not sink the rest of the batch —
            # everything queued offline gets its own independent result, so
            # the client knows exactly which items are safe to drop from
            # its local queue and which ones still need attention.
            db.rollback()
            results.append(
                schemas.SyncPushOpResult(op_id=op.op_id, status="error", detail=str(e))
            )

    return schemas.SyncPushResponse(results=results, server_time=datetime.now(timezone.utc))


def _uuid(v):
    """Payload values arrive as plain JSON (no Pydantic validation on the
    nested dict), so ids come in as plain strings — coerce them to
    uuid.UUID explicitly rather than relying on the DB driver to do it."""
    if v is None or isinstance(v, uuid.UUID):
        return v
    return uuid.UUID(str(v))


def _date(v):
    if v is None or isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def _datetime(v):
    if v is None or isinstance(v, datetime):
        return v
    # Dart's DateTime.toIso8601String() and 'Z'-suffixed ISO strings both
    # need normalizing before fromisoformat() will accept them.
    s = str(v).replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def _apply_op(db: Session, op: schemas.SyncPushOp, user: models.User) -> None:
    payload = op.payload

    if op.action == "create_asset":
        asset_id = _uuid(payload.get("id"))
        if asset_id is None:
            raise ValueError("create_asset requires payload.id (client-generated uuid)")
        existing = db.get(models.Asset, asset_id)
        if existing is not None:
            # Already applied in a previous sync run whose response never
            # made it back to the client (e.g. connection dropped right
            # after the server committed) — treat as success, don't
            # duplicate.
            return
        if db.scalar(select(models.Asset).where(models.Asset.asset_code == payload["asset_code"])):
            raise ValueError(f"Asset code {payload['asset_code']} already exists")
        asset = models.Asset(
            id=asset_id,
            asset_code=payload["asset_code"],
            name=payload["name"],
            asset_type=payload.get("asset_type", "individual"),
            description=payload.get("description"),
            set_id=_uuid(payload.get("set_id")),
            category=payload.get("category"),
            brand=payload.get("brand"),
            set_code=payload.get("set_code"),
            part_number=payload.get("part_number"),
            purchase_date=_date(payload.get("purchase_date")),
            purchase_value=payload.get("purchase_value"),
            condition=payload.get("condition", "good"),
            status=payload.get("status", "in_storage"),
            current_location_id=_uuid(payload.get("location_id")),
            qr_code_data=payload["asset_code"],
            notes=payload.get("notes"),
            is_active=True,
            created_by=_uuid(payload.get("created_by")) or user.id,
            updated_by=_uuid(payload.get("created_by")) or user.id,
        )
        db.add(asset)

    elif op.action == "update_asset":
        asset = db.get(models.Asset, op.record_id)
        if asset is None:
            raise ValueError(f"Asset {op.record_id} not found")
        for field in (
            "name", "description", "category", "brand", "set_code", "part_number",
            "condition", "purchase_value", "notes",
        ):
            if field in payload and payload[field] is not None:
                setattr(asset, field, payload[field])
        if payload.get("purchase_date") is not None:
            asset.purchase_date = _date(payload["purchase_date"])
        if payload.get("updated_by"):
            asset.updated_by = _uuid(payload["updated_by"])
        asset.updated_at = datetime.now(timezone.utc)

    elif op.action == "update_condition_status":
        asset = db.get(models.Asset, op.record_id)
        if asset is None:
            raise ValueError(f"Asset {op.record_id} not found")
        asset.condition = payload["condition"]
        asset.status = payload["status"]
        asset.current_location_id = _uuid(payload.get("location_id"))
        if payload.get("updated_by"):
            asset.updated_by = _uuid(payload["updated_by"])
        asset.updated_at = datetime.now(timezone.utc)

    elif op.action == "create_scan_event":
        log_id = _uuid(payload.get("id"))
        if log_id is not None and db.get(models.ConditionLog, log_id) is not None:
            return  # already applied in a previous sync run — skip duplicate
        log = models.ConditionLog(
            id=log_id or uuid.uuid4(),
            asset_id=_uuid(payload["asset_id"]),
            set_id=_uuid(payload.get("set_id")),
            scanned_by=_uuid(payload["scanned_by"]),
            location_id=_uuid(payload.get("location_id")),
            event_type=payload["event_type"],
            condition_before=payload.get("condition_before"),
            condition_after=payload["condition_after"],
            status_before=payload.get("status_before"),
            status_after=payload["status_after"],
            notes=payload.get("notes"),
            # Preserve the moment the scan actually happened offline,
            # rather than when it happened to reach the server — this is
            # what keeps the activity feed / history in true chronological
            # order after a batch of queued scans lands all at once.
            scanned_at=_datetime(payload.get("scanned_at")) or datetime.now(timezone.utc),
        )
        db.add(log)

    elif op.action == "deploy_asset_set":
        aset = db.get(models.AssetSet, op.record_id)
        if aset is None:
            raise ValueError(f"Asset set {op.record_id} not found")
        now = datetime.now(timezone.utc)
        location_id = _uuid(payload.get("location_id"))
        aset.current_location_id = location_id
        aset.status = "deployed"
        aset.updated_at = now
        db.query(models.Asset).filter(models.Asset.set_id == aset.id).update({
            "current_location_id": location_id,
            "status": "deployed",
            "updated_by": _uuid(payload.get("updated_by")) or user.id,
            "updated_at": now,
        })

    elif op.action == "pull_out_asset_set":
        aset = db.get(models.AssetSet, op.record_id)
        if aset is None:
            raise ValueError(f"Asset set {op.record_id} not found")
        now = datetime.now(timezone.utc)
        aset.current_location_id = None
        aset.status = "in_storage"
        aset.updated_at = now
        db.query(models.Asset).filter(models.Asset.set_id == aset.id).update({
            "current_location_id": None,
            "status": "in_storage",
            "updated_by": _uuid(payload.get("updated_by")) or user.id,
            "updated_at": now,
        })

    else:
        raise ValueError(f"Unknown sync action: {op.action}")
