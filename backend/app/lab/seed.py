"""Explicit opt-in synthetic demo data. Never run on a production database."""

from datetime import timedelta
from sqlmodel import Session, select
from app.models import User
from app.core.security import get_password_hash
from app.lab.models import Equipment, Booking, Audit, now

DEMO_PASSWORD = "LabLink2026!"


def seed(engine):
    with Session(engine) as session:
        if session.exec(select(User)).first():
            return
        people = [
            ("admin@lablink.local", "林老师", "admin", "vision"),
            ("manager@lablink.local", "陈同学", "manager", "vision"),
            ("student@lablink.local", "邓同学", "member", "vision"),
            ("robot@lablink.local", "周同学", "manager", "robotics"),
        ]
        users = []
        for email, name, role, team in people:
            user = User(
                email=email,
                full_name=name,
                role=role,
                team_id=team,
                is_superuser=role == "admin",
                hashed_password=get_password_hash(DEMO_PASSWORD),
            )
            session.add(user)
            users.append(user)
        session.flush()
        devices = [
            Equipment(
                name="视觉计算工作站",
                code="VIS-001",
                team_id="vision",
                category="计算设备",
                location="清华大学（演示）A302",
                description="RTX 4090 · 64GB RAM。用于模型训练、推理和视觉实验。",
            ),
            Equipment(
                name="便携采集套件",
                code="VIS-002",
                team_id="vision",
                category="采集设备",
                location="清华大学（演示）A305",
                description="深度相机、三脚架与采集终端。使用前请确认配件完整。",
                approval_required=False,
            ),
            Equipment(
                name="边缘推理开发板",
                code="VIS-003",
                team_id="vision",
                category="端侧设备",
                location="清华大学（演示）A302",
                description="低功耗端侧模型验证；请保留原始系统镜像。",
                approval_required=False,
            ),
            Equipment(
                name="精密电子示波器",
                code="VIS-004",
                team_id="vision",
                category="测量设备",
                location="清华大学（演示）A306",
                description="模拟设备，当前暂停预约，等待校准。",
                status="maintenance",
            ),
            Equipment(
                name="移动机器人平台",
                code="ROB-001",
                team_id="robotics",
                category="机器人",
                location="北京大学（演示）B201",
                description="仅机器人实验室可见的示例设备。",
            ),
        ]
        session.add_all(devices)
        session.flush()
        stamp = now()
        booking = Booking(
            equipment_id=devices[0].id,
            user_id=users[2].id,
            starts_at=stamp + timedelta(hours=2),
            ends_at=stamp + timedelta(hours=4),
            purpose="验证低算力跌倒检测模型的推理延迟",
            status="pending",
        )
        session.add(booking)
        session.add(
            Audit(
                actor_id="system",
                team_id="vision",
                action="demo.initialized",
                target_id="demo",
                detail="全部设备和预约为合成演示数据",
            )
        )
        session.commit()
