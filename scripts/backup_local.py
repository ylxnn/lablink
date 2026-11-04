"""Consistent SQLite backup, including data still in WAL. PostgreSQL uses pg_dump."""

import sqlite3
import sys
from datetime import datetime, UTC
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.config import settings  # noqa: E402

if not settings.DATABASE_URL.startswith("sqlite:///"):
    raise SystemExit("Use pg_dump for PostgreSQL; this utility only handles SQLite.")
source = Path(settings.DATABASE_URL.removeprefix("sqlite:///")).resolve()
if not source.is_file():
    raise SystemExit("Database file does not exist")
folder = source.parent / "backups"
folder.mkdir(exist_ok=True)
target = folder / ("lablink-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f") + ".db")
with sqlite3.connect(source) as db, sqlite3.connect(target) as backup:
    db.backup(backup)
print("Backup created:", target)
