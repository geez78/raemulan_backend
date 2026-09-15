import uuid
from datetime import datetime, date
from typing import Optional, Generic, TypeVar
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic paginated response — items for the current page plus the
    total count across all pages, so the client can render page controls
    and knows a search actually covers the whole table, not just whatever
    happened to be loaded."""
    items: list[T]
    total: int
    limit: int
    offset: int



# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class SessionUserOut(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    role: str
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: SessionUserOut
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    user_id: uuid.UUID
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    full_name: str
    role: str = "field_user"
    password: str = "Welcome@1234"
    phone: Optional[str] = None
    employee_id: Optional[str] = None


class UpdateRoleRequest(BaseModel):
    role: str


class AppUserOut(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── User profile (UserProfileEntity) ─────────────────────────────────────────

class UserProfileOut(BaseModel):
    id: uuid.UUID
    full_name: str
    role: str
    phone: Optional[str] = None
    employee_id: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Locations ─────────────────────────────────────────────────────────────────

class LocationCreate(BaseModel):
    name: str
    code: str
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class LocationUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class LocationOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    address: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LocationBreakdownOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    city: Optional[str] = None
    asset_count: int
    damaged_count: int


# ── Assets ────────────────────────────────────────────────────────────────────

class AssetCreate(BaseModel):
    asset_code: str
    name: str
    asset_type: str = "individual"
    description: Optional[str] = None
    set_id: Optional[uuid.UUID] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    set_code: Optional[str] = None
    part_number: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_value: Optional[float] = None
    condition: str = "good"
    location_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    created_by: Optional[uuid.UUID] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    set_code: Optional[str] = None
    part_number: Optional[str] = None
    condition: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_value: Optional[float] = None
    notes: Optional[str] = None
    updated_by: Optional[uuid.UUID] = None


class AssetConditionStatusUpdate(BaseModel):
    condition: str
    status: str
    location_id: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class AssetOut(BaseModel):
    id: uuid.UUID
    asset_code: str
    name: str
    asset_type: str
    description: Optional[str] = None
    set_id: Optional[uuid.UUID] = None
    category: Optional[str] = None
    brand: Optional[str] = None
    set_code: Optional[str] = None
    part_number: Optional[str] = None
    purchase_date: Optional[date] = None
    purchase_value: Optional[float] = None
    condition: str
    status: str
    current_location_id: Optional[uuid.UUID] = None
    current_location_name: Optional[str] = None
    qr_code_data: Optional[str] = None
    photo_url: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: Optional[datetime] = None


class AssetWithLocationOut(BaseModel):
    asset: AssetOut
    location_name: Optional[str] = None
    set_name: Optional[str] = None


class ImportResultOut(BaseModel):
    success: int
    failed: int
    errors: list[str]


# ── Asset sets ────────────────────────────────────────────────────────────────

class AssetSetCreate(BaseModel):
    set_code: str
    name: str
    description: Optional[str] = None
    total_units: int = 0
    asset_type: str = "set"
    notes: Optional[str] = None
    created_by: Optional[uuid.UUID] = None


class AssetSetOut(BaseModel):
    id: uuid.UUID
    set_code: str
    name: str
    description: Optional[str] = None
    total_units: int
    asset_type: str
    status: str
    current_location_id: Optional[uuid.UUID] = None
    current_location_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AssetSetWithStatsOut(BaseModel):
    set: AssetSetOut
    member_count: int
    good_count: int
    fair_count: int
    damaged_count: int
    location_name: Optional[str] = None


class DeploySetRequest(BaseModel):
    location_id: uuid.UUID
    updated_by: uuid.UUID


class PullOutSetRequest(BaseModel):
    updated_by: uuid.UUID


# ── Condition logs ────────────────────────────────────────────────────────────

class ScanEventCreate(BaseModel):
    asset_id: uuid.UUID
    scanned_by: uuid.UUID
    event_type: str
    condition_before: str
    condition_after: str
    status_before: str
    status_after: str
    location_id: Optional[uuid.UUID] = None
    set_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None

class ConditionLogOut(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    asset_code: Optional[str] = None
    asset_name: Optional[str] = None
    scanned_by: uuid.UUID
    scanned_by_name: str
    event_type: str
    condition_after: str
    status_after: str
    set_id: Optional[uuid.UUID] = None
    location_id: Optional[uuid.UUID] = None
    location_name: Optional[str] = None
    condition_before: Optional[str] = None
    status_before: Optional[str] = None
    notes: Optional[str] = None
    photo_url: Optional[str] = None
    scanned_at: datetime


# ── Lookup tables (Settings screen: categories / asset types / set codes) ────

class LookupCreate(BaseModel):
    name: str


class AssetTypeLookupCreate(BaseModel):
    name: str
    code: str


class LookupOut(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetTypeLookupOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Generic asset-set status/location touch (group scan screen) ─────────────

class AssetSetStatusLocationUpdate(BaseModel):
    status: Optional[str] = None
    current_location_id: Optional[uuid.UUID] = None


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardSummaryOut(BaseModel):
    total_assets: int
    deployed: int
    in_storage: int
    in_maintenance: int
    disposed: int
    condition_good: int
    condition_for_repair: int
    condition_for_replacement: int
    condition_for_disposal: int
    active_sites: int


# ── Offline sync ──────────────────────────────────────────────────────────────
# Lets the mobile app queue writes made while offline and replay them once
# connectivity is back (POST /sync/push), and lets it pull down anything
# that changed on the server since its last successful sync
# (GET /sync/pull?since=...).

class SyncPushOp(BaseModel):
    # Client-generated id for this queued operation (a uuid4 string is
    # fine). Echoed back in the result so the client knows exactly which
    # queued item to drop once it's confirmed applied.
    op_id: str
    # "create_asset" | "update_asset" | "update_condition_status" | "create_scan_event"
    action: str
    # Required for update_asset / update_condition_status (the asset being
    # changed). Not required for create_asset / create_scan_event, since
    # those carry their own id inside `payload` (the client generates the
    # uuid up front so it can save the record locally before it's ever
    # synced, and the server just uses that same id — no id remapping
    # needed on either side).
    record_id: Optional[uuid.UUID] = None
    payload: dict


class SyncPushOpResult(BaseModel):
    op_id: str
    status: str  # "ok" | "error"
    detail: Optional[str] = None


class SyncPushResponse(BaseModel):
    results: list[SyncPushOpResult]
    server_time: datetime


class SyncPullResponse(BaseModel):
    server_time: datetime
    assets: list[AssetOut]
    locations: list[LocationOut]
    asset_sets: list[AssetSetOut]
    condition_logs: list[ConditionLogOut]