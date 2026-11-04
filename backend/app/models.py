"""Account and legacy item tables adapted from the MIT-licensed FastAPI template.

Item is retained solely for the immutable initial migration; LabLink does not expose
its original demo CRUD. Keep it in metadata to avoid a destructive schema drift.
"""
import uuid
from datetime import UTC, datetime
from pydantic import EmailStr
from sqlmodel import Field, SQLModel


def get_datetime_utc():
    return datetime.now(UTC)


class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    role: str = Field(default="member", index=True)
    team_id: str = Field(default="vision", index=True)
    hashed_password: str
    created_at: datetime | None = Field(default_factory=get_datetime_utc)


class Item(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    created_at: datetime | None = Field(default_factory=get_datetime_utc)
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
