import csv
import io
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import timedelta
from typing import Annotated
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import Response
from sqlalchemy import func, update
from sqlmodel import Session, select
from app.core.config import settings
from app.core.security import (
    create_access_token,
    verify_password,
    get_password_hash,
    ALGORITHM,
)
from app.models import User
from app.lab.models import (
    Equipment,
    Booking,
    Fault,
    Audit,
    Outbox,
    Notification,
    UserProfile,
    now,
)
from app.lab.schemas import (
    Login,
    EquipmentInput,
    BookingInput,
    Decision,
    FaultInput,
    ResolveInput,
    DeviceState,
    UserInput,
    ProfileInput,
)
from app.lab.service import (
    transaction,
    manager,
    same_team,
    device,
    audit,
    reserve,
    transition,
    set_device_state,
    report_fault,
    fail,
)

router = APIRouter(prefix="/api/v1")
bearer = HTTPBearer(auto_error=False)
login_attempts = defaultdict(deque)
login_lock = threading.Lock()


def public_user(user):
    return {
        key: getattr(user, key)
        for key in ("id", "email", "full_name", "role", "team_id", "is_active")
    }


def current(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    if not credentials:
        fail(401, "请先登录")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        uid = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        fail(401, "登录已过期，请重新登录")
    with Session(request.app.state.engine) as session:
        user = session.get(User, uid)
        if not user or not user.is_active:
            fail(401, "账号不存在或已停用")
        session.expunge(user)
        return user


Actor = Annotated[User, Depends(current)]


def scoped(actor, model):
    query = select(model)
    return (
        query if actor.role == "admin" else query.where(model.team_id == actor.team_id)
    )


def booking_rows(session, actor):
    query = select(Booking).join(Equipment)
    if actor.role != "admin":
        query = query.where(Equipment.team_id == actor.team_id)
    if actor.role == "member":
        query = query.where(Booking.user_id == actor.id)
    return query


@router.post("/auth/login")
def login(body: Login, request: Request):
    key = ((request.client.host if request.client else "local"), body.email.lower())
    stamp = time.monotonic()
    with login_lock:
        if len(login_attempts) > 2000:
            for old in list(login_attempts):
                if not login_attempts[old] or login_attempts[old][-1] < stamp - 60:
                    del login_attempts[old]
            if len(login_attempts) > 2000:
                fail(429, "登录请求过多，请稍后重试")
        attempts = login_attempts[key]
        while attempts and attempts[0] < stamp - 60:
            attempts.popleft()
        if len(attempts) >= 8:
            raise HTTPException(
                429, "尝试过于频繁，请一分钟后重试", headers={"Retry-After": "60"}
            )
        attempts.append(stamp)
    with Session(request.app.state.engine) as session:
        user = session.exec(
            select(User).where(User.email == body.email.lower())
        ).first()
        # A fixed dummy hash also makes unknown-account attempts perform the password work.
        hashed = user.hashed_password if user else request.app.state.dummy_hash
        try:
            valid, replacement = verify_password(body.password, hashed)
        except Exception:
            valid, replacement = False, None
        if not valid or not user or not user.is_active:
            fail(401, "邮箱或密码不正确")
        if replacement:
            user.hashed_password = replacement
            session.add(user)
            session.commit()
        token = create_access_token(
            user.id, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": public_user(user) | profile_data(session, user.id),
        }


@router.get("/auth/me")
def me(request: Request, actor: Actor):
    with Session(request.app.state.engine) as session:
        return public_user(actor) | profile_data(session, actor.id)


def profile_data(session, uid):
    profile = session.get(UserProfile, uid)
    return {
        "bio": profile.bio if profile else "",
        "phone": profile.phone if profile else "",
        "student_id": profile.student_id if profile else "",
    }


@router.patch("/auth/me")
def update_profile(body: ProfileInput, request: Request, actor: Actor):
    with transaction(request.app.state.engine) as session:
        user = session.get(User, actor.id)
        email = body.email.strip().lower()
        if email != user.email:
            valid, _ = verify_password(body.current_password, user.hashed_password)
            if not valid:
                fail(403, "更改登录邮箱需要正确的当前密码")
        user.full_name, user.email = body.full_name, email
        profile = session.get(UserProfile, user.id) or UserProfile(user_id=user.id)
        profile.bio, profile.phone = body.bio, body.phone
        profile.student_id = body.student_id
        session.add(user)
        session.add(profile)
        session.flush()
        audit(session, actor, "profile.updated", str(user.id), user.team_id)
        return public_user(user) | profile_data(session, user.id)


@router.get("/equipment")
def equipment(
    request: Request,
    actor: Actor,
    q: str = Query("", max_length=100),
    status: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    with Session(request.app.state.engine) as session:
        query = scoped(actor, Equipment)
        if q:
            query = query.where(
                Equipment.name.contains(q, autoescape=True)
                | Equipment.code.contains(q, autoescape=True)
            )
        if status:
            query = query.where(Equipment.status == status)
        total = session.exec(select(func.count()).select_from(query.subquery())).one()
        return {
            "items": session.exec(
                query.order_by(Equipment.created_at.desc()).offset(offset).limit(limit)
            ).all(),
            "total": total,
        }


@router.post("/equipment", status_code=201)
def add_equipment(body: EquipmentInput, request: Request, actor: Actor):
    manager(actor, body.team_id)
    with transaction(request.app.state.engine) as session:
        item = Equipment(**body.model_dump())
        session.add(item)
        session.flush()
        audit(session, actor, "equipment.created", item.id, item.team_id)
        return item.model_dump()


@router.patch("/equipment/{eid}/status")
def equipment_status(eid: str, body: DeviceState, request: Request, actor: Actor):
    with transaction(request.app.state.engine) as session:
        item = device(session, eid, actor)
        manager(actor, item.team_id)
        if (
            body.status == "available"
            and session.exec(
                select(Fault).where(Fault.equipment_id == eid, Fault.status == "open")
            ).first()
        ):
            fail(409, "请先处理设备的未关闭报修")
        set_device_state(session, actor, item, body.status, "管理员变更设备状态")
        return item.model_dump()


@router.get("/equipment/{eid}/schedule")
def schedule(eid: str, request: Request, actor: Actor):
    with Session(request.app.state.engine) as session:
        item = session.get(Equipment, eid)
        if not item:
            fail(404, "设备不存在")
        same_team(actor, item.team_id)
        rows = session.exec(
            select(Booking)
            .where(
                Booking.equipment_id == eid,
                Booking.status.in_(["pending", "approved", "checked_out"]),
                Booking.ends_at > now(),
            )
            .order_by(Booking.starts_at)
            .limit(100)
        ).all()
        # Public occupancy data must not leak names, purpose or booking IDs of other users.
        return [
            {"starts_at": b.starts_at, "ends_at": b.ends_at, "status": b.status}
            for b in rows
        ]


@router.post("/bookings", status_code=201)
def add_booking(
    body: BookingInput,
    request: Request,
    actor: Actor,
    idempotency_key: str = Header(min_length=8, max_length=100),
):
    return reserve(request.app.state.engine, actor, body, idempotency_key)


@router.get("/bookings")
def bookings(
    request: Request,
    actor: Actor,
    status: str = "",
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    with Session(request.app.state.engine) as session:
        query = booking_rows(session, actor)
        if status:
            query = query.where(Booking.status == status)
        total = session.exec(select(func.count()).select_from(query.subquery())).one()
        rows = session.exec(
            query.order_by(Booking.created_at.desc()).offset(offset).limit(limit)
        ).all()
        items = []
        for row in rows:
            item = session.get(Equipment, row.equipment_id)
            user = session.get(User, row.user_id)
            items.append(
                row.model_dump()
                | {"equipment_name": item.name, "user_name": user.full_name}
            )
        return {"items": items, "total": total}


@router.get("/bookings/export")
def export_bookings(request: Request, actor: Actor):
    manager(actor, actor.team_id)
    with Session(request.app.state.engine) as session:
        rows = session.exec(
            booking_rows(session, actor).order_by(Booking.created_at.desc()).limit(5000)
        ).all()
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            ["预约编号", "设备编号", "开始时间 UTC", "结束时间 UTC", "状态", "用途"]
        )
        for row in rows:
            purpose = (
                "'" + row.purpose
                if row.purpose.lstrip().startswith(("=", "+", "-", "@"))
                else row.purpose
            )
            writer.writerow(
                [
                    row.id,
                    row.equipment_id,
                    row.starts_at.isoformat(),
                    row.ends_at.isoformat(),
                    row.status,
                    purpose,
                ]
            )
        return Response(
            "\ufeff" + buffer.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="bookings.csv"'},
        )


@router.post("/bookings/{bid}/actions")
def booking_action(bid: str, body: Decision, request: Request, actor: Actor):
    return transition(request.app.state.engine, actor, bid, body)


@router.post("/faults", status_code=201)
def new_fault(body: FaultInput, request: Request, actor: Actor):
    return report_fault(request.app.state.engine, actor, body)


@router.get("/faults")
def faults(
    request: Request,
    actor: Actor,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    with Session(request.app.state.engine) as session:
        query = select(Fault).join(Equipment)
        if actor.role != "admin":
            query = query.where(Equipment.team_id == actor.team_id)
        if actor.role == "member":
            query = query.where(Fault.user_id == actor.id)
        total = session.exec(select(func.count()).select_from(query.subquery())).one()
        rows = session.exec(
            query.order_by(Fault.created_at.desc()).offset(offset).limit(limit)
        ).all()
        return {
            "items": [
                r.model_dump()
                | {"equipment_name": session.get(Equipment, r.equipment_id).name}
                for r in rows
            ],
            "total": total,
        }


@router.post("/faults/{fid}/resolve")
def resolve_fault(fid: str, body: ResolveInput, request: Request, actor: Actor):
    with transaction(request.app.state.engine) as session:
        fault = session.get(Fault, fid)
        if not fault:
            fail(404, "报修记录不存在")
        item = device(session, fault.equipment_id, actor)
        manager(actor, item.team_id)
        session.refresh(fault)
        if fault.status != "open":
            fail(409, "报修已处理")
        fault.status = "resolved"
        fault.resolution = body.resolution
        fault.resolved_at = now()
        session.add(fault)
        session.flush()
        remaining = session.exec(
            select(Fault).where(Fault.equipment_id == item.id, Fault.status == "open")
        ).first()
        if not remaining and item.status != "retired":
            item.status = "available"
            session.add(item)
        audit(session, actor, "fault.resolved", fid, item.team_id, body.resolution)
        from app.lab.service import notify

        notify(
            session,
            fault.user_id,
            fid + ":resolved",
            "报修已处理",
            item.name + "：" + body.resolution,
        )
        return fault.model_dump()


@router.get("/notifications")
def notifications(request: Request, actor: Actor):
    with Session(request.app.state.engine) as session:
        return session.exec(
            select(Notification)
            .where(Notification.recipient_id == actor.id)
            .order_by(Notification.created_at.desc())
            .limit(100)
        ).all()


@router.post("/notifications/read-all")
def read_all_notifications(request: Request, actor: Actor):
    with transaction(request.app.state.engine) as session:
        result = session.execute(
            update(Notification)
            .where(
                Notification.recipient_id == actor.id, Notification.read_at.is_(None)
            )
            .values(read_at=now())
        )
        return {"updated": result.rowcount}


@router.post("/notifications/{nid}/read")
def read_notification(nid: str, request: Request, actor: Actor):
    with transaction(request.app.state.engine) as session:
        item = session.get(Notification, nid)
        if not item or item.recipient_id != actor.id:
            fail(404, "通知不存在")
        item.read_at = now()
        session.add(item)
        return {"ok": True}


@router.get("/audit")
def audit_log(
    request: Request,
    actor: Actor,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    manager(actor, actor.team_id)
    with Session(request.app.state.engine) as session:
        query = scoped(actor, Audit)
        total = session.exec(select(func.count()).select_from(query.subquery())).one()
        return {
            "items": session.exec(
                query.order_by(Audit.created_at.desc()).offset(offset).limit(limit)
            ).all(),
            "total": total,
        }


@router.get("/users")
def users(request: Request, actor: Actor):
    manager(actor, actor.team_id)
    with Session(request.app.state.engine) as session:
        return [
            public_user(u)
            for u in session.exec(
                scoped(actor, User).order_by(User.created_at.desc()).limit(200)
            ).all()
        ]


@router.post("/users", status_code=201)
def create_user(body: UserInput, request: Request, actor: Actor):
    if actor.role != "admin":
        fail(403, "只有平台管理员可以创建账号")
    with transaction(request.app.state.engine) as session:
        user = User(
            email=body.email.lower(),
            full_name=body.full_name,
            role=body.role,
            team_id=body.team_id,
            hashed_password=get_password_hash(body.password),
        )
        session.add(user)
        session.flush()
        audit(session, actor, "user.created", str(user.id), user.team_id)
        return public_user(user)


@router.get("/dashboard")
def dashboard(request: Request, actor: Actor):
    with Session(request.app.state.engine) as session:
        devices = session.exec(scoped(actor, Equipment)).all()
        bookings = session.exec(booking_rows(session, actor)).all()
        return {
            "equipment_total": len(devices),
            "available": sum(e.status == "available" for e in devices),
            "maintenance": sum(e.status == "maintenance" for e in devices),
            "pending": sum(b.status == "pending" for b in bookings),
            "active": sum(b.status in ("approved", "checked_out") for b in bookings),
            "completed": sum(b.status == "returned" for b in bookings),
            "overdue": sum(
                b.status == "checked_out" and b.ends_at < now() for b in bookings
            ),
            "recent_bookings": sorted(
                bookings, key=lambda b: b.created_at, reverse=True
            )[:6],
        }


@router.get("/operations")
def operations(request: Request, actor: Actor):
    if actor.role != "admin":
        fail(403, "只有平台管理员可以查看通知队列")
    with Session(request.app.state.engine) as session:
        counts = session.exec(
            select(Outbox.status, func.count()).group_by(Outbox.status)
        ).all()
        dead = session.exec(
            select(Outbox).where(Outbox.status == "dead").limit(50)
        ).all()
        return {"counts": dict(counts), "dead_letters": dead}


@router.post("/operations/{oid}/retry")
def retry_delivery(oid: str, request: Request, actor: Actor):
    if actor.role != "admin":
        fail(403, "只有平台管理员可以重试通知")
    with transaction(request.app.state.engine) as session:
        item = session.exec(
            select(Outbox).where(Outbox.id == oid).with_for_update()
        ).first()
        if not item or item.status != "dead":
            fail(409, "只有失败通知可以重试")
        item.status, item.attempts, item.available_at = "pending", 0, now()
        session.add(item)
        audit(session, actor, "outbox.retried", oid, actor.team_id)
        return {"ok": True}
