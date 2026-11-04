from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, UTC
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, select
from app.core.db import make_engine
from app.core.security import get_password_hash, create_access_token
from app.models import User
from app.main import create_app
from app.lab.models import Equipment, Booking, Outbox, Notification, Audit, now
from app.lab.schemas import BookingInput, Decision, FaultInput
from app.lab.service import reserve, transition, report_fault
from app.lab.worker import deliver_one, maintenance


@pytest.fixture(scope="session")
def password_hash():
    return get_password_hash("TestingPass2026!")


@pytest.fixture
def lab(tmp_path, password_hash):
    engine = make_engine("sqlite:///" + (tmp_path / "lab.db").as_posix())
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        users = [
            User(
                email=f"{role}@example.com",
                full_name=role,
                role=role if role != "other" else "member",
                team_id="other" if role == "other" else "vision",
                hashed_password=password_hash,
            )
            for role in ["admin", "manager", "member", "other"]
        ]
        s.add_all(users)
        s.flush()
        device = Equipment(
            name="GPU workstation",
            code="GPU-01",
            team_id="vision",
            location="A302",
            approval_required=True,
        )
        s.add(device)
        s.commit()
        s.refresh(device)
        for user in users:
            s.refresh(user)
            s.expunge(user)
        s.expunge(device)
    app = create_app(engine=engine, demo=False, worker=False)
    with TestClient(app) as client:
        yield engine, users, device, client
    engine.dispose()


def body(device, hours=1):
    start = now() + timedelta(hours=hours)
    return BookingInput(
        equipment_id=device.id,
        starts_at=start.replace(tzinfo=UTC),
        ends_at=(start + timedelta(hours=1)).replace(tzinfo=UTC),
        purpose="Run inference experiment",
    )


def headers(user):
    return {
        "Authorization": "Bearer " + create_access_token(user.id, timedelta(hours=1))
    }


def test_auth_and_scope(lab):
    engine, users, d, c = lab
    assert c.get("/api/v1/equipment").status_code == 401
    assert c.get("/api/v1/equipment", headers=headers(users[3])).json()["total"] == 0
    assert (
        c.get(
            "/api/v1/equipment/" + d.id + "/schedule", headers=headers(users[3])
        ).status_code
        == 404
    )
    assert c.get("/api/v1/audit", headers=headers(users[2])).status_code == 403
    assert c.get("/api/v1/operations", headers=headers(users[1])).status_code == 403


def test_login_masks_password(lab):
    _, users, _, c = lab
    r = c.post(
        "/api/v1/auth/login",
        json={"email": users[2].email, "password": "TestingPass2026!"},
    )
    assert r.status_code == 200
    assert "hashed_password" not in str(r.json())
    assert (
        c.post(
            "/api/v1/auth/login", json={"email": users[2].email, "password": "bad"}
        ).status_code
        == 401
    )


def test_idempotency_and_conflict(lab):
    e, u, d, _ = lab
    b = body(d)
    first = reserve(e, u[2], b, "same-key-123")
    assert reserve(e, u[2], b, "same-key-123")["id"] == first["id"]
    with pytest.raises(Exception) as exc:
        reserve(e, u[2], body(d, 3), "same-key-123")
    assert exc.value.status_code == 409
    with pytest.raises(Exception) as exc:
        reserve(e, u[1], b, "another-key")
    assert exc.value.status_code == 409


def test_concurrent_booking_one_winner(lab):
    e, u, d, _ = lab
    b = body(d)

    def attempt(i):
        try:
            return reserve(e, u[2], b, str(uuid.uuid4()))["id"]
        except Exception as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(8)))
    assert sum(isinstance(r, str) for r in results) == 1
    assert results.count(409) == 7


def test_adjacent_intervals_allowed(lab):
    e, u, d, _ = lab
    b = body(d)
    reserve(e, u[2], b, "first-key")
    adjacent = b.model_copy(
        update={"starts_at": b.ends_at, "ends_at": b.ends_at + timedelta(hours=1)}
    )
    assert reserve(e, u[2], adjacent, "second-key")["id"]


def test_cross_team_write_denied(lab):
    e, u, d, _ = lab
    with pytest.raises(Exception) as exc:
        reserve(e, u[3], body(d), "cross-key")
    assert exc.value.status_code == 404


def test_approval_and_return_state_machine(lab):
    e, u, d, _ = lab
    b = body(d)
    record = reserve(e, u[2], b, "state-key")
    bid = record["id"]
    with pytest.raises(Exception):
        transition(e, u[2], bid, Decision(action="approve"))
    transition(e, u[1], bid, Decision(action="approve"))
    with pytest.raises(Exception):
        transition(e, u[1], bid, Decision(action="approve"))
    with pytest.raises(Exception):
        transition(e, u[2], bid, Decision(action="checkout"))
    with Session(e) as s:
        r = s.get(Booking, bid)
        r.starts_at = now() - timedelta(minutes=1)
        s.add(r)
        s.commit()
    assert (
        transition(e, u[2], bid, Decision(action="checkout"))["status"] == "checked_out"
    )
    with pytest.raises(Exception):
        transition(e, u[2], bid, Decision(action="cancel"))
    assert transition(e, u[2], bid, Decision(action="return"))["status"] == "returned"
    with pytest.raises(Exception):
        transition(e, u[2], bid, Decision(action="return"))


def test_fault_cancels_and_notifies_atomically(lab):
    e, u, d, _ = lab
    bid = reserve(e, u[2], body(d), "fault-key")["id"]
    report_fault(e, u[2], FaultInput(equipment_id=d.id, description="GPU cannot start"))
    with Session(e) as s:
        assert s.get(Equipment, d.id).status == "maintenance"
        assert s.get(Booking, bid).status == "cancelled"
        assert s.exec(
            select(Outbox).where(Outbox.event_key == bid + ":device-unavailable")
        ).first()
    with pytest.raises(Exception):
        reserve(e, u[2], body(d, 5), "blocked-key")


def test_outbox_delivery_idempotent(lab):
    e, u, d, _ = lab
    reserve(e, u[2], body(d), "delivery-key")
    for _ in range(10):
        deliver_one(e)
    with Session(e) as s:
        rows = s.exec(select(Notification)).all()
        assert rows and len({n.event_key for n in rows}) == len(rows)


def test_outbox_backoff_and_dead_letter(lab):
    e, u, d, _ = lab
    with Session(e) as s:
        event = Outbox(
            recipient_id=u[2].id, event_key="fail", title="test", body="test"
        )
        s.add(event)
        s.commit()
        s.refresh(event)
        eid = event.id
    for _ in range(5):
        with Session(e) as s:
            r = s.get(Outbox, eid)
            r.available_at = now() - timedelta(seconds=1)
            s.add(r)
            s.commit()
        deliver_one(e, fail_delivery=True)
    with Session(e) as s:
        assert s.get(Outbox, eid).status == "dead"


def test_pending_expiry(lab):
    e, u, d, _ = lab
    bid = reserve(e, u[2], body(d), "expire-key")["id"]
    maintenance(e, now() + timedelta(hours=2))
    with Session(e) as s:
        assert s.get(Booking, bid).status == "expired"


def test_fault_resolution_permissions(lab):
    e, u, d, c = lab
    fid = report_fault(
        e, u[2], FaultInput(equipment_id=d.id, description="Camera signal missing")
    )["id"]
    assert (
        c.post(
            f"/api/v1/faults/{fid}/resolve",
            headers=headers(u[2]),
            json={"resolution": "replaced cable"},
        ).status_code
        == 403
    )
    assert (
        c.post(
            f"/api/v1/faults/{fid}/resolve",
            headers=headers(u[1]),
            json={"resolution": "replaced cable"},
        ).status_code
        == 200
    )
    with Session(e) as s:
        assert s.get(Equipment, d.id).status == "available"


@pytest.mark.parametrize(
    "endpoint",
    ["/equipment", "/bookings", "/faults", "/notifications", "/dashboard", "/auth/me"],
)
def test_member_reads(lab, endpoint):
    _, u, _, c = lab
    assert c.get("/api/v1" + endpoint, headers=headers(u[2])).status_code == 200


def test_submission_validation_and_audit(lab):
    e, u, d, c = lab
    assert c.post("/api/v1/bookings", headers=headers(u[2]), json={}).status_code == 422
    reserve(e, u[2], body(d), "audit-key")
    with Session(e) as s:
        assert s.exec(select(Audit).where(Audit.action == "booking.created")).first()


def test_schedule_does_not_leak_private_details(lab):
    e, u, d, c = lab
    reserve(e, u[1], body(d), "privacy-key")
    rows = c.get(
        "/api/v1/equipment/" + d.id + "/schedule", headers=headers(u[2])
    ).json()
    assert set(rows[0]) == {"starts_at", "ends_at", "status"}


def test_http_booking_lifecycle_and_export(lab):
    e, u, d, c = lab
    packet = body(d).model_dump(mode="json")
    packet["starts_at"] += "Z"
    packet["ends_at"] += "Z"
    h = headers(u[2]) | {"Idempotency-Key": "http-booking-key"}
    r = c.post("/api/v1/bookings", json=packet, headers=h)
    assert r.status_code == 201
    bid = r.json()["id"]
    assert c.post("/api/v1/bookings", json=packet, headers=h).json()["id"] == bid
    assert (
        c.post(
            f"/api/v1/bookings/{bid}/actions",
            json={"action": "approve"},
            headers=headers(u[1]),
        ).status_code
        == 200
    )
    assert (
        c.get("/api/v1/bookings?status=approved&limit=1", headers=headers(u[2])).json()[
            "total"
        ]
        == 1
    )
    assert c.get("/api/v1/bookings/export", headers=headers(u[2])).status_code == 403
    assert c.get("/api/v1/bookings/export", headers=headers(u[1])).status_code == 200
    assert c.get("/api/v1/audit", headers=headers(u[1])).json()["total"] >= 2


def test_create_equipment_and_state_change(lab):
    e, u, d, c = lab
    packet = {
        "name": "Depth Camera",
        "code": "CAM-02",
        "location": "A3",
        "team_id": "vision",
    }
    assert (
        c.post("/api/v1/equipment", headers=headers(u[2]), json=packet).status_code
        == 403
    )
    r = c.post("/api/v1/equipment", headers=headers(u[1]), json=packet)
    assert r.status_code == 201
    assert (
        c.post("/api/v1/equipment", headers=headers(u[1]), json=packet).status_code
        == 409
    )
    assert (
        c.get("/api/v1/equipment?q=Depth", headers=headers(u[1])).json()["total"] == 1
    )
    eid = r.json()["id"]
    assert (
        c.patch(
            f"/api/v1/equipment/{eid}/status",
            headers=headers(u[1]),
            json={"status": "retired"},
        ).status_code
        == 200
    )
    assert (
        c.patch(
            f"/api/v1/equipment/{eid}/status",
            headers=headers(u[1]),
            json={"status": "available"},
        ).status_code
        == 409
    )


def test_users_and_notifications_owner_boundary(lab):
    e, u, d, c = lab
    packet = {
        "email": "new@example.com",
        "full_name": "new",
        "password": "LongPass2026!",
        "team_id": "vision",
        "role": "member",
    }
    assert (
        c.post("/api/v1/users", headers=headers(u[1]), json=packet).status_code == 403
    )
    assert (
        c.post("/api/v1/users", headers=headers(u[0]), json=packet).status_code == 201
    )
    assert len(c.get("/api/v1/users", headers=headers(u[0])).json()) == 5
    reserve(e, u[2], body(d), "notify-key")
    for _ in range(6):
        deliver_one(e)
    rows = c.get("/api/v1/notifications", headers=headers(u[2])).json()
    assert rows
    nid = rows[0]["id"]
    assert (
        c.post(f"/api/v1/notifications/{nid}/read", headers=headers(u[3])).status_code
        == 404
    )
    assert (
        c.post(f"/api/v1/notifications/{nid}/read", headers=headers(u[2])).status_code
        == 200
    )


def test_dead_letter_manual_retry_and_health(lab):
    e, u, d, c = lab
    with Session(e) as s:
        event = Outbox(
            recipient_id=u[2].id,
            event_key="dead",
            title="test",
            body="test",
            status="dead",
            attempts=5,
        )
        s.add(event)
        s.commit()
        s.refresh(event)
        eid = event.id
    assert (
        c.get("/api/v1/operations", headers=headers(u[0])).json()["counts"]["dead"] == 1
    )
    assert (
        c.post(f"/api/v1/operations/{eid}/retry", headers=headers(u[1])).status_code
        == 403
    )
    assert (
        c.post(f"/api/v1/operations/{eid}/retry", headers=headers(u[0])).status_code
        == 200
    )
    assert c.get("/api/health").json()["status"] == "ok"


def test_reject_requires_reason_and_releases_slot(lab):
    e, u, d, c = lab
    b = body(d)
    bid = reserve(e, u[2], b, "reject-key")["id"]
    assert (
        c.post(
            f"/api/v1/bookings/{bid}/actions",
            headers=headers(u[1]),
            json={"action": "reject"},
        ).status_code
        == 422
    )
    assert (
        c.post(
            f"/api/v1/bookings/{bid}/actions",
            headers=headers(u[1]),
            json={"action": "reject", "note": "需要安全培训"},
        ).status_code
        == 200
    )
    assert reserve(e, u[2], b, "retry-new-key")["id"] != bid


def test_datetime_must_have_timezone(lab):
    _, u, d, c = lab
    packet = {
        "equipment_id": d.id,
        "starts_at": "2026-12-01T10:00",
        "ends_at": "2026-12-01T11:00",
        "purpose": "test",
    }
    assert (
        c.post(
            "/api/v1/bookings",
            json=packet,
            headers=headers(u[2]) | {"Idempotency-Key": "timezone-key"},
        ).status_code
        == 422
    )


def test_bulk_read_scoped_and_idempotent(lab):
    e, u, d, c = lab
    with Session(e) as s:
        for i in range(120):
            s.add(
                Notification(
                    recipient_id=u[2].id,
                    event_key=f"bulk-{i}",
                    title="test",
                    body="test",
                )
            )
        s.add(
            Notification(
                recipient_id=u[3].id,
                event_key="other-private",
                title="private",
                body="private",
            )
        )
        s.commit()
    assert c.post("/api/v1/notifications/read-all").status_code == 401
    assert (
        c.post("/api/v1/notifications/read-all", headers=headers(u[2])).json()[
            "updated"
        ]
        == 120
    )
    assert (
        c.post("/api/v1/notifications/read-all", headers=headers(u[2])).json()[
            "updated"
        ]
        == 0
    )
    with Session(e) as s:
        assert (
            s.exec(select(Notification).where(Notification.recipient_id == u[3].id))
            .one()
            .read_at
            is None
        )


def test_profile_persistence_and_role_protection(lab):
    e, u, d, c = lab
    packet = {
        "full_name": "Researcher",
        "email": u[2].email,
        "bio": "Agent safety",
        "phone": "13800000000",
    }
    response = c.patch("/api/v1/auth/me", headers=headers(u[2]), json=packet)
    assert response.status_code == 200
    assert (
        c.get("/api/v1/auth/me", headers=headers(u[2])).json()["bio"] == "Agent safety"
    )
    assert (
        c.patch(
            "/api/v1/auth/me", headers=headers(u[2]), json=packet | {"role": "admin"}
        ).status_code
        == 422
    )
    assert c.get("/api/v1/auth/me", headers=headers(u[3])).json()["bio"] == ""
    assert (
        c.patch(
            "/api/v1/auth/me", headers=headers(u[2]), json=packet | {"full_name": "   "}
        ).status_code
        == 422
    )


def test_profile_email_change_requires_password_and_unique(lab):
    e, u, d, c = lab
    packet = {"full_name": "Member", "email": "new-login@example.com"}
    assert (
        c.patch("/api/v1/auth/me", headers=headers(u[2]), json=packet).status_code
        == 403
    )
    packet["current_password"] = "TestingPass2026!"
    assert (
        c.patch(
            "/api/v1/auth/me",
            headers=headers(u[2]),
            json=packet | {"email": u[1].email},
        ).status_code
        == 409
    )
    assert (
        c.patch("/api/v1/auth/me", headers=headers(u[2]), json=packet).status_code
        == 200
    )
    assert (
        c.post(
            "/api/v1/auth/login",
            json={"email": packet["email"], "password": packet["current_password"]},
        ).status_code
        == 200
    )

def test_student_id_preserves_zeros_and_login_persistence(lab):
    e,u,d,c=lab
    packet={'full_name':u[2].full_name,'email':u[2].email,'student_id':'001A2026'}
    assert c.patch('/api/v1/auth/me',headers=headers(u[2]),json=packet).status_code==200
    assert c.get('/api/v1/auth/me',headers=headers(u[2])).json()['student_id']=='001A2026'
    login=c.post('/api/v1/auth/login',json={'email':u[2].email,'password':'TestingPass2026!'})
    assert login.json()['user']['student_id']=='001A2026'
    assert c.get('/api/v1/auth/me',headers=headers(u[3])).json()['student_id']==''
    assert c.patch('/api/v1/auth/me',headers=headers(u[2]),json=packet|{'student_id':'1'*33}).status_code==422
    assert c.patch('/api/v1/auth/me',headers=headers(u[2]),json=packet|{'student_id':''}).status_code==200
