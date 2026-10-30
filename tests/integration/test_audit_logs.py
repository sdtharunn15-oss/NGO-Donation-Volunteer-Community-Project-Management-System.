
from uuid import uuid4

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole


def create_user_with_role(role: UserRole) -> tuple[int, str]:
    email = f"audit_{uuid4().hex}@example.com"
    db = SessionLocal()

    try:
        user = User(
            full_name="Audit Permission Test",
            email=email,
            hashed_password=hash_password("StrongPass123!"),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, email
    finally:
        db.close()


def login_and_get_token(client, email: str) -> str:
    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_successful_write_request_creates_audit_log(client):
    email = f"audit_{uuid4().hex}@example.com"

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Audit Test User",
            "email": email,
            "password": "StrongPass123!",
        },
    )

    assert response.status_code in (200, 201)

    db = SessionLocal()
    try:
        logs = db.scalars(
            select(AuditLog)
            .where(
                AuditLog.action == "post /auth/register",
                AuditLog.entity_type == "api_request",
            )
            .order_by(AuditLog.id.desc())
            .limit(50)
        ).all()

        assert any(
            log.extra_data
            and log.extra_data.get("path") == "/auth/register"
            and log.extra_data.get("status_code") == response.status_code
            for log in logs
        ), "Successful registration was not recorded in audit logs"
    finally:
        db.close()


def test_unauthenticated_user_cannot_view_audit_logs(client):
    response = client.get("/audit-logs/")
    assert response.status_code == 401


def test_donor_cannot_view_audit_logs(client):
    _, email = create_user_with_role(UserRole.DONOR)
    token = login_and_get_token(client, email)

    response = client.get(
        "/audit-logs/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def test_super_admin_can_view_audit_logs(client):
    _, email = create_user_with_role(UserRole.SUPER_ADMIN)
    token = login_and_get_token(client, email)

    response = client.get(
        "/audit-logs/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
