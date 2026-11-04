"""Explicit administrator provisioning; never ships a production default password."""

import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlmodel import Session, select  # noqa: E402
from app.core.db import engine  # noqa: E402
from app.core.security import get_password_hash  # noqa: E402
from app.models import User  # noqa: E402

email = input("Administrator email: ").strip().lower()
name = input("Display name: ").strip()
password = getpass.getpass("New password (12+ characters): ")
if "@" not in email or not name or len(password) < 12:
    raise SystemExit("Invalid email/name or password too short")
if getpass.getpass("Confirm password: ") != password:
    raise SystemExit("Passwords do not match")
with Session(engine) as session:
    if session.exec(select(User).where(User.email == email)).first():
        raise SystemExit("Account already exists; no change made")
    user = User(
        email=email,
        full_name=name,
        team_id="vision",
        role="admin",
        is_superuser=True,
        hashed_password=get_password_hash(password),
    )
    session.add(user)
    session.commit()
print("Administrator created. No password printed or written to logs.")
