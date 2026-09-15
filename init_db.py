"""
Run once after creating the Postgres database to:
1. Apply all Alembic migrations (creates every table)
2. Seed one admin user so you can log in for the first time

Usage:
    python init_db.py

Equivalent to running:
    alembic upgrade head
manually and then seeding the admin user — this script just does both
in one step for convenience.
"""
from alembic import command
from alembic.config import Config

from app.database import SessionLocal
from app import models
from app.security import hash_password


def run_migrations():
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    print("✅ Alembic migrations applied (tables created/updated).")


def seed_admin():
    db = SessionLocal()
    try:
        existing = db.query(models.User).filter(models.User.username == "admin").first()
        if existing:
            print("ℹ️  'admin' user already exists, skipping seed.")
            return
        admin = models.User(
            username="admin",
            full_name="System Administrator",
            role="admin",
            password_hash=hash_password("Welcome@1234"),
            must_change_password=True,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print("✅ Seeded admin user -> username: admin / password: Welcome@1234")
        print("   (You will be forced to change this password on first login.)")
    finally:
        db.close()


if __name__ == "__main__":
    run_migrations()
    seed_admin()
