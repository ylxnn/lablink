from datetime import datetime, UTC
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class Login(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=128)


class EquipmentInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    category: str = Field(default="计算设备", max_length=50)
    location: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    approval_required: bool = True
    team_id: str = Field(default="vision", min_length=1, max_length=50)


class BookingInput(BaseModel):
    equipment_id: str
    starts_at: datetime
    ends_at: datetime
    purpose: str = Field(min_length=3, max_length=1000)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def utc_time(cls, value):
        if value.tzinfo is None:
            raise ValueError("时间必须包含时区")
        return value.astimezone(UTC).replace(tzinfo=None)

    @model_validator(mode="after")
    def valid_interval(self):
        hours = (self.ends_at - self.starts_at).total_seconds() / 3600
        if not 0 < hours <= 24:
            raise ValueError("单次预约须大于零且不超过 24 小时")
        return self


class Decision(BaseModel):
    action: Literal["approve", "reject", "cancel", "checkout", "return"]
    note: str = Field(default="", max_length=1000)


class FaultInput(BaseModel):
    equipment_id: str
    description: str = Field(min_length=5, max_length=2000)


class ResolveInput(BaseModel):
    resolution: str = Field(min_length=3, max_length=2000)


class DeviceState(BaseModel):
    status: Literal["available", "maintenance", "retired"]


class UserInput(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    full_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=10, max_length=128)
    team_id: str = Field(min_length=1, max_length=50)
    role: Literal["member", "manager"] = "member"


class ProfileInput(BaseModel):
    model_config = {"extra": "forbid"}
    full_name: str = Field(min_length=1, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    bio: str = Field(default="", max_length=500)
    phone: str = Field(default="", max_length=30)
    student_id: str = Field(default="", max_length=32, pattern=r"^[A-Za-z0-9_-]*$")
    current_password: str = Field(default="", max_length=128)

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("姓名不能为空")
        return value.strip()
