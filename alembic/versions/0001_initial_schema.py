"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-17 00:32:46.945594

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk():
    return sa.Column(
        'id', postgresql.UUID(as_uuid=True), primary_key=True,
        server_default=sa.text('gen_random_uuid()'),
    )


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    # -- app_users (merges former Supabase app_users + user_profiles) --------
    op.create_table(
        'app_users',
        _uuid_pk(),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='field_user'),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('employee_id', sa.String(length=64), nullable=True),
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('password_hash', sa.String(length=128), nullable=False),
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('username'),
    )
    op.create_index('ix_app_users_username', 'app_users', ['username'])

    # -- locations -------------------------------------------------------------
    op.create_table(
        'locations',
        _uuid_pk(),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(length=128), nullable=True),
        sa.Column('province', sa.String(length=128), nullable=True),
        sa.Column('latitude', sa.Numeric(10, 6), nullable=True),
        sa.Column('longitude', sa.Numeric(10, 6), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_locations_code', 'locations', ['code'])

    # -- asset_sets --------------------------------------------------------------
    op.create_table(
        'asset_sets',
        _uuid_pk(),
        sa.Column('set_code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('total_units', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('asset_type', sa.String(length=32), nullable=False, server_default='set'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='in_storage'),
        sa.Column('current_location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('set_code'),
    )
    op.create_index('ix_asset_sets_set_code', 'asset_sets', ['set_code'])
    op.create_index('ix_asset_sets_status', 'asset_sets', ['status'])
    op.create_index('ix_asset_sets_current_location_id', 'asset_sets', ['current_location_id'])

    # -- assets --------------------------------------------------------------
    op.create_table(
        'assets',
        _uuid_pk(),
        sa.Column('asset_code', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('asset_type', sa.String(length=32), nullable=False, server_default='individual'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('set_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('asset_sets.id'), nullable=True),
        sa.Column('category', sa.String(length=128), nullable=True),
        sa.Column('brand', sa.String(length=128), nullable=True),
        sa.Column('set_code', sa.String(length=64), nullable=True),
        sa.Column('part_number', sa.String(length=128), nullable=True),
        sa.Column('purchase_date', sa.Date(), nullable=True),
        sa.Column('purchase_value', sa.Numeric(14, 2), nullable=True),
        sa.Column('condition', sa.String(length=32), nullable=False, server_default='good'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='in_storage'),
        sa.Column('current_location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id'), nullable=True),
        sa.Column('qr_code_data', sa.Text(), nullable=True),
        sa.Column('photo_url', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id'), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('asset_code'),
    )
    op.create_index('ix_assets_asset_code', 'assets', ['asset_code'])
    op.create_index('ix_assets_set_id', 'assets', ['set_id'])
    op.create_index('ix_assets_category', 'assets', ['category'])
    op.create_index('ix_assets_condition', 'assets', ['condition'])
    op.create_index('ix_assets_status', 'assets', ['status'])
    op.create_index('ix_assets_current_location_id', 'assets', ['current_location_id'])
    op.create_index('ix_assets_is_active', 'assets', ['is_active'])
    op.create_index('ix_assets_updated_at', 'assets', ['updated_at'])

    # -- condition_logs --------------------------------------------------------
    op.create_table(
        'condition_logs',
        _uuid_pk(),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('assets.id'), nullable=False),
        sa.Column('set_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('asset_sets.id'), nullable=True),
        sa.Column('scanned_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('app_users.id'), nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id'), nullable=True),
        sa.Column('event_type', sa.String(length=32), nullable=False),
        sa.Column('condition_before', sa.String(length=32), nullable=True),
        sa.Column('condition_after', sa.String(length=32), nullable=False),
        sa.Column('status_before', sa.String(length=32), nullable=True),
        sa.Column('status_after', sa.String(length=32), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('photo_url', sa.Text(), nullable=True),
        sa.Column('scanned_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_condition_logs_asset_id', 'condition_logs', ['asset_id'])
    op.create_index('ix_condition_logs_set_id', 'condition_logs', ['set_id'])
    op.create_index('ix_condition_logs_location_id', 'condition_logs', ['location_id'])
    op.create_index('ix_condition_logs_scanned_at', 'condition_logs', ['scanned_at'])

    # -- lookup tables (Settings screen) --------------------------------------
    op.create_table(
        'asset_categories',
        _uuid_pk(),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        'asset_types',
        _uuid_pk(),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('code'),
    )

    op.create_table(
        'set_codes',
        _uuid_pk(),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('set_codes')
    op.drop_table('asset_types')
    op.drop_table('asset_categories')
    op.drop_table('condition_logs')
    op.drop_table('assets')
    op.drop_table('asset_sets')
    op.drop_table('locations')
    op.drop_table('app_users')
