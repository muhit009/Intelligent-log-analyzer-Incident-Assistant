"""
Bootstrap the first admin user.

Usage:
    python -m app.scripts.seed_admin

Reads FIRST_ADMIN_USERNAME and FIRST_ADMIN_PASSWORD from environment / .env.
No-op if an admin user already exists.
"""

import sys
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def seed_admin() -> None:
    db = SessionLocal()
    try:
        existing_admin = db.query(User).filter(User.role == UserRole.admin.value).first()
        if existing_admin:
            print(f"Admin user already exists: {existing_admin.username}")
            return

        username = settings.FIRST_ADMIN_USERNAME
        password = settings.FIRST_ADMIN_PASSWORD

        if not username or not password:
            print("FIRST_ADMIN_USERNAME and FIRST_ADMIN_PASSWORD must be set.")
            sys.exit(1)

        user = User(
            username=username,
            hashed_password=hash_password(password),
            role=UserRole.admin.value,
        )
        db.add(user)
        db.commit()
        print(f"Admin user '{username}' created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
