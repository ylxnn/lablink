"""Durable in-app notification delivery. No email/SMS is claimed or silently simulated."""

import asyncio
import logging
from datetime import timedelta
from sqlmodel import select
from app.lab.models import Booking, Equipment, Outbox, Notification, Audit, now
from app.lab.service import transaction, notify

log = logging.getLogger(__name__)


def maintenance(engine, stamp=None):
    stamp = stamp or now()
    with transaction(engine) as session:
        # Same equipment lock order as booking commands; re-read rows after locking.
        for item in session.exec(
            select(Equipment).order_by(Equipment.id).with_for_update()
        ).all():
            for booking in session.exec(
                select(Booking).where(
                    Booking.equipment_id == item.id,
                    Booking.status.in_(["pending", "approved"]),
                )
            ).all():
                pending_expired = booking.status == "pending" and (
                    booking.created_at + timedelta(hours=24) < stamp
                    or booking.starts_at <= stamp
                )
                no_show = booking.status == "approved" and booking.ends_at <= stamp
                if pending_expired or no_show:
                    booking.status = "expired" if pending_expired else "no_show"
                    session.add(booking)
                    session.add(
                        Audit(
                            actor_id="system",
                            team_id=item.team_id,
                            action="booking." + booking.status,
                            target_id=booking.id,
                        )
                    )
                    notify(
                        session,
                        booking.user_id,
                        booking.id + ":" + booking.status,
                        "预约已结束",
                        item.name + "：未审批过期"
                        if pending_expired
                        else item.name + "：未领用已结束",
                        booking.id,
                    )


def deliver_one(engine, fail_delivery=False):
    with transaction(engine) as session:
        query = (
            select(Outbox)
            .where(Outbox.status == "pending", Outbox.available_at <= now())
            .order_by(Outbox.available_at)
            .limit(1)
        )
        if engine.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        event = session.exec(query).first()
        if not event:
            return False
        if event.event_key.endswith(":reminder"):
            booking = session.get(Booking, event.booking_id)
            if not booking or booking.status != "approved":
                event.status = "skipped"
                session.add(event)
                return True
        event.attempts += 1
        try:
            # A savepoint isolates a delivery error from the event's retry bookkeeping.
            with session.begin_nested():
                if fail_delivery:
                    raise RuntimeError("injected delivery failure")
                existing = session.exec(
                    select(Notification).where(
                        Notification.event_key == event.event_key
                    )
                ).first()
                if not existing:
                    session.add(
                        Notification(
                            recipient_id=event.recipient_id,
                            event_key=event.event_key,
                            title=event.title,
                            body=event.body,
                        )
                    )
                    session.flush()
            event.status = "delivered"
            event.last_error = ""
        except Exception:
            event.last_error = "delivery_failed"
            event.status = "dead" if event.attempts >= 5 else "pending"
            event.available_at = now() + timedelta(seconds=min(300, 2**event.attempts))
        session.add(event)
        return True


async def worker_loop(engine):
    while True:
        try:
            await asyncio.to_thread(maintenance, engine)
            for _ in range(30):
                if not await asyncio.to_thread(deliver_one, engine):
                    break
        except Exception:
            log.exception("Background delivery failed; retrying on next cycle")
        await asyncio.sleep(5)
