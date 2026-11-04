import uuid
from datetime import UTC, datetime
from sqlalchemy import CheckConstraint, UniqueConstraint, Index
from sqlmodel import SQLModel, Field


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now(UTC).replace(tzinfo=None)


class Equipment(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    name: str = Field(max_length=120)
    code: str = Field(unique=True, max_length=50)
    team_id: str = Field(index=True)
    category: str = Field(default="计算设备", max_length=50)
    location: str = Field(max_length=120)
    description: str = Field(default="", max_length=2000)
    status: str = Field(default="available", index=True)
    approval_required: bool = True
    created_at: datetime = Field(default_factory=now)
    __table_args__ = (
        CheckConstraint("status IN ('available','maintenance','retired')"),
    )


class Booking(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    equipment_id: str = Field(foreign_key="equipment.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    starts_at: datetime
    ends_at: datetime
    purpose: str = Field(max_length=1000)
    status: str = Field(default="pending", index=True)
    decision_note: str = Field(default="", max_length=1000)
    reviewed_by: uuid.UUID | None = Field(default=None, foreign_key="user.id")
    checked_out_at: datetime | None = None
    returned_at: datetime | None = None
    created_at: datetime = Field(default_factory=now)
    __table_args__ = (
        CheckConstraint("ends_at > starts_at"),
        CheckConstraint(
            "status IN ('pending','approved','checked_out','returned','cancelled','rejected','expired','no_show')"
        ),
        Index("ix_booking_overlap", "equipment_id", "status", "starts_at", "ends_at"),
    )


class Fault(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    equipment_id: str = Field(foreign_key="equipment.id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    description: str = Field(max_length=2000)
    status: str = "open"
    resolution: str = ""
    created_at: datetime = Field(default_factory=now)
    resolved_at: datetime | None = None


class Audit(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    actor_id: str
    team_id: str = Field(index=True)
    action: str
    target_id: str
    detail: str = ""
    created_at: datetime = Field(default_factory=now)


class Outbox(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    recipient_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    event_key: str = Field(unique=True)
    title: str
    body: str
    booking_id: str | None = None
    available_at: datetime = Field(default_factory=now, index=True)
    status: str = Field(default="pending", index=True)
    attempts: int = 0
    last_error: str = ""
    created_at: datetime = Field(default_factory=now)


class Notification(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    recipient_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    event_key: str = Field(unique=True)
    title: str
    body: str
    read_at: datetime | None = None
    created_at: datetime = Field(default_factory=now)


class Idempotency(SQLModel, table=True):
    id: str = Field(default_factory=uid, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id")
    key: str = Field(max_length=100)
    fingerprint: str
    resource_id: str
    created_at: datetime = Field(default_factory=now)
    __table_args__ = (UniqueConstraint("user_id", "key"),)


class UserProfile(SQLModel, table=True):
    user_id: uuid.UUID = Field(primary_key=True, foreign_key="user.id")
    bio: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=30)
    student_id: str = Field(default="", max_length=32)
