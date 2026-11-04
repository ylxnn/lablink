from alembic import context
from sqlmodel import SQLModel
from app.core.db import make_engine
from app.core.config import settings
from app.models import User, Item
from app.lab import models

def run():
    with make_engine(settings.DATABASE_URL).connect() as connection:
        context.configure(connection=connection,target_metadata=SQLModel.metadata,compare_type=True)
        with context.begin_transaction():context.run_migrations()
run()
