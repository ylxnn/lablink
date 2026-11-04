"""Business invariants live here; every command and its outbox events commit atomically."""

import hashlib
from contextlib import contextmanager
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import text
from sqlmodel import Session, select
from app.models import User
from app.lab.models import Equipment, Booking, Fault, Audit, Outbox, Idempotency, now

ACTIVE = ["pending", "approved", "checked_out"]


def fail(code, message):
    raise HTTPException(code, message)


def same_team(actor, team):
    if actor.role != "admin" and actor.team_id != team:
        fail(404, "资源不存在或无权访问")


def manager(actor, team):
    same_team(actor, team)
    if actor.role not in ("admin", "manager"):
        fail(403, "需要设备管理员权限")


@contextmanager
def transaction(engine):
    with Session(engine) as session:
        try:
            # SQLite serializes writes before read/check/write. PostgreSQL locks only relevant rows.
            if engine.dialect.name == "sqlite":
                session.execute(text("BEGIN IMMEDIATE"))
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def device(session, eid, actor):
    item = session.exec(
        select(Equipment).where(Equipment.id == eid).with_for_update()
    ).first()
    if not item:
        fail(404, "设备不存在")
    same_team(actor, item.team_id)
    return item


def audit(session, actor, action, item, team, detail=""):
    session.add(
        Audit(
            actor_id=str(actor.id),
            team_id=team,
            action=action,
            target_id=item,
            detail=detail,
        )
    )


def notify(session, recipient, key, title, body, booking_id=None, available_at=None):
    session.add(
        Outbox(
            recipient_id=recipient,
            event_key=key,
            title=title,
            body=body,
            booking_id=booking_id,
            available_at=available_at or now(),
        )
    )


def reserve(engine, actor, body, key):
    stamp = now()
    if body.starts_at < stamp or body.starts_at > stamp + timedelta(days=30):
        fail(422, "请预约未来 30 天内的时段")
    digest = hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    with transaction(engine) as session:
        # Serializes the per-user quota and idempotency key across different equipment rows.
        session.exec(select(User).where(User.id == actor.id).with_for_update()).one()
        prior = session.exec(
            select(Idempotency).where(
                Idempotency.user_id == actor.id, Idempotency.key == key
            )
        ).first()
        if prior:
            if prior.fingerprint != digest:
                fail(409, "同一个提交标识不能用于不同预约，请重新提交")
            return session.get(Booking, prior.resource_id).model_dump()
        item = device(session, body.equipment_id, actor)
        if item.status != "available":
            fail(409, "设备维护中或已停用，暂不可预约")
        if (
            len(
                session.exec(
                    select(Booking).where(
                        Booking.user_id == actor.id, Booking.status.in_(ACTIVE)
                    )
                ).all()
            )
            >= 3
        ):
            fail(409, "最多保留 3 个未结束预约，请先完成或取消")
        overlap = session.exec(
            select(Booking).where(
                Booking.equipment_id == item.id,
                Booking.status.in_(ACTIVE),
                Booking.starts_at < body.ends_at,
                Booking.ends_at > body.starts_at,
            )
        ).first()
        if overlap:
            fail(409, "这个时段已被预约，请选择其他时段")
        booking = Booking(
            **body.model_dump(),
            user_id=actor.id,
            status="pending" if item.approval_required else "approved",
        )
        session.add(booking)
        session.flush()
        session.add(
            Idempotency(
                user_id=actor.id, key=key, fingerprint=digest, resource_id=booking.id
            )
        )
        audit(session, actor, "booking.created", booking.id, item.team_id)
        notify(
            session,
            actor.id,
            booking.id + ":created",
            "预约已提交",
            item.name
            + "："
            + ("等待管理员审批" if item.approval_required else "预约已通过"),
            booking.id,
        )
        managers = session.exec(
            select(User).where(
                User.team_id == item.team_id,
                User.role == "manager",
                User.is_active == True,
            )
        ).all()  # noqa: E712
        for user in managers:
            notify(
                session,
                user.id,
                booking.id + ":approval:" + str(user.id),
                "有新的设备预约",
                actor.full_name + " 申请使用 " + item.name,
                booking.id,
            )
        notify(
            session,
            actor.id,
            booking.id + ":reminder",
            "预约即将开始",
            item.name + " 将在 30 分钟内开始，请及时领用",
            booking.id,
            body.starts_at - timedelta(minutes=30),
        )
        return booking.model_dump()


def transition(engine, actor, bid, body):
    with transaction(engine) as session:
        record = session.get(Booking, bid)
        if not record:
            fail(404, "预约不存在")
        item = device(session, record.equipment_id, actor)
        # Refresh after obtaining the equipment lock; another command may have just committed.
        session.refresh(record)
        action, stamp = body.action, now()
        owner = record.user_id == actor.id
        if action in ("approve", "reject"):
            manager(actor, item.team_id)
            if owner:
                fail(403, "不能审批自己的预约")
            if record.status != "pending":
                fail(409, "只有待审批预约可以审批")
            if record.starts_at <= stamp:
                fail(409, "预约已过开始时间，请重新申请")
            if action == "approve" and item.status != "available":
                fail(409, "设备不可用，无法通过审批")
            if action == "reject" and not body.note.strip():
                fail(422, "请填写拒绝原因")
            record.status = "approved" if action == "approve" else "rejected"
            record.reviewed_by = actor.id
        elif action == "cancel":
            if not owner:
                manager(actor, item.team_id)
            if record.status not in ("pending", "approved"):
                fail(409, "当前状态不能取消")
            record.status = "cancelled"
        elif action == "checkout":
            if not owner:
                fail(403, "仅预约本人可以领用")
            if record.status != "approved" or item.status != "available":
                fail(409, "只有已通过且设备可用的预约可以领用")
            if not record.starts_at - timedelta(minutes=15) <= stamp < record.ends_at:
                fail(409, "请在预约开始前 15 分钟至结束前领用")
            other = session.exec(
                select(Booking).where(
                    Booking.equipment_id == item.id, Booking.status == "checked_out"
                )
            ).first()
            if other:
                fail(409, "设备仍未归还，请联系管理员")
            record.status = "checked_out"
            record.checked_out_at = stamp
        elif action == "return":
            if not owner:
                manager(actor, item.team_id)
            if record.status != "checked_out":
                fail(409, "只能归还已领用的设备")
            record.status = "returned"
            record.returned_at = stamp
        record.decision_note = body.note
        session.add(record)
        audit(session, actor, "booking." + action, bid, item.team_id, body.note)
        notify(
            session,
            record.user_id,
            bid + ":" + action,
            "预约状态更新",
            item.name + "：" + action + (" · " + body.note if body.note else ""),
            bid,
        )
        return record.model_dump()


def set_device_state(session, actor, item, status, reason):
    if item.status == "retired" and status != "retired":
        fail(409, "已停用设备不能重新启用，请新建设备记录")
    occupied = session.exec(
        select(Booking).where(
            Booking.equipment_id == item.id, Booking.status == "checked_out"
        )
    ).first()
    if status == "retired" and occupied:
        fail(409, "设备尚未归还，不能停用")
    if status != "available":
        bookings = session.exec(
            select(Booking).where(
                Booking.equipment_id == item.id,
                Booking.status.in_(["pending", "approved"]),
            )
        ).all()
        for booking in bookings:
            booking.status = "cancelled"
            booking.decision_note = reason
            session.add(booking)
            notify(
                session,
                booking.user_id,
                booking.id + ":device-unavailable",
                "设备不可用，预约已取消",
                item.name + "：" + reason,
                booking.id,
            )
    item.status = status
    session.add(item)
    audit(session, actor, "equipment." + status, item.id, item.team_id, reason)


def report_fault(engine, actor, body):
    with transaction(engine) as session:
        item = device(session, body.equipment_id, actor)
        if item.status == "retired":
            fail(409, "设备已停用")
        fault = Fault(
            equipment_id=item.id, user_id=actor.id, description=body.description
        )
        session.add(fault)
        set_device_state(
            session, actor, item, "maintenance", "故障报修：" + body.description
        )
        audit(session, actor, "fault.created", fault.id, item.team_id)
        for user in session.exec(
            select(User).where(User.team_id == item.team_id, User.role == "manager")
        ).all():
            notify(
                session,
                user.id,
                fault.id + ":" + str(user.id),
                "设备故障待处理",
                item.name + "：" + body.description,
            )
        return fault.model_dump()
