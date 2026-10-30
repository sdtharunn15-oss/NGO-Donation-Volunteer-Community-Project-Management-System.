
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def create_user_and_login(client, role="ngo_manager"):
    email = f"{role}_{uuid4().hex}@example.com"
    password = "TestPass123!"

    db = SessionLocal()
    try:
        user = User(
            full_name=f"Test {role}",
            email=email,
            hashed_password=hash_password(password),
            role=UserRole(role),
            is_active=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text

    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_approval(client, headers=None, **overrides):
    if headers is None:
        headers = create_user_and_login(client, "ngo_manager")

    payload = {
        "entity_type": "project",
        "entity_id": 1,
        "request_notes": "Please review this request",
    }
    payload.update(overrides)

    response = client.post(
        "/approvals/",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json(), headers


def test_create_approval_requires_authentication(client):
    response = client.post(
        "/approvals/",
        json={"entity_type": "project", "entity_id": 1},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [
        "super_admin",
        "ngo_manager",
        "finance_officer",
        "volunteer_coordinator",
    ],
)
def test_authorized_roles_can_create_approval(client, role):
    headers = create_user_and_login(client, role)

    response = client.post(
        "/approvals/",
        json={
            "entity_type": "project",
            "entity_id": 1,
            "request_notes": "Approval test",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["entity_type"] == "project"
    assert data["entity_id"] == 1
    assert data["status"] == "pending"
    assert data["requested_by"] > 0
    assert data["reviewed_by"] is None


@pytest.mark.parametrize("role", ["donor", "volunteer"])
def test_unauthorized_roles_cannot_create_approval(client, role):
    headers = create_user_and_login(client, role)

    response = client.post(
        "/approvals/",
        json={"entity_type": "project", "entity_id": 1},
        headers=headers,
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"entity_type": "x", "entity_id": 1},
        {"entity_type": "project", "entity_id": 0},
        {"entity_type": "project", "entity_id": -1},
        {"entity_id": 1},
        {"entity_type": "project"},
    ],
)
def test_create_approval_rejects_invalid_payload(client, payload):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.post(
        "/approvals/",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 422


def test_create_approval_rejects_long_request_notes(client):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.post(
        "/approvals/",
        json={
            "entity_type": "project",
            "entity_id": 1,
            "request_notes": "x" * 2001,
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_list_approvals_requires_authentication(client):
    response = client.get("/approvals/")
    assert response.status_code == 401


@pytest.mark.parametrize("role", ["super_admin", "ngo_manager"])
def test_authorized_roles_can_list_approvals(client, role):
    headers = create_user_and_login(client, role)
    approval, _ = create_approval(client)

    response = client.get("/approvals/", headers=headers)

    assert response.status_code == 200, response.text
    assert any(item["id"] == approval["id"] for item in response.json())


@pytest.mark.parametrize(
    "role",
    [
        "finance_officer",
        "volunteer_coordinator",
        "volunteer",
        "donor",
    ],
)
def test_unauthorized_roles_cannot_list_approvals(client, role):
    headers = create_user_and_login(client, role)

    response = client.get("/approvals/", headers=headers)

    assert response.status_code == 403


def test_review_approval_requires_authentication(client):
    response = client.patch(
        "/approvals/1/review",
        json={"status": "approved"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize("status_value", ["approved", "rejected"])
def test_manager_can_review_another_users_approval(client, status_value):
    requester_headers = create_user_and_login(client, "finance_officer")
    approval, _ = create_approval(client, requester_headers)

    reviewer_headers = create_user_and_login(client, "ngo_manager")

    response = client.patch(
        f"/approvals/{approval['id']}/review",
        json={
            "status": status_value,
            "review_notes": "Reviewed by manager",
        },
        headers=reviewer_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == status_value
    assert data["reviewed_by"] is not None
    assert data["review_notes"] == "Reviewed by manager"
    assert data["reviewed_at"] is not None


def test_super_admin_can_review_another_users_approval(client):
    requester_headers = create_user_and_login(client, "ngo_manager")
    approval, _ = create_approval(client, requester_headers)

    reviewer_headers = create_user_and_login(client, "super_admin")

    response = client.patch(
        f"/approvals/{approval['id']}/review",
        json={"status": "approved"},
        headers=reviewer_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"


def test_user_cannot_review_own_approval(client):
    headers = create_user_and_login(client, "ngo_manager")
    approval, _ = create_approval(client, headers)

    response = client.patch(
        f"/approvals/{approval['id']}/review",
        json={"status": "approved"},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You cannot review your own request"


def test_review_missing_approval_returns_404(client):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.patch(
        "/approvals/999999999/review",
        json={"status": "approved"},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Approval request not found"


def test_review_already_reviewed_approval_returns_409(client):
    requester_headers = create_user_and_login(client, "finance_officer")
    approval, _ = create_approval(client, requester_headers)
    reviewer_headers = create_user_and_login(client, "ngo_manager")

    first_response = client.patch(
        f"/approvals/{approval['id']}/review",
        json={"status": "approved"},
        headers=reviewer_headers,
    )
    assert first_response.status_code == 200, first_response.text

    second_response = client.patch(
        f"/approvals/{approval['id']}/review",
        json={"status": "rejected"},
        headers=create_user_and_login(client, "super_admin"),
    )

    assert second_response.status_code == 409
    assert second_response.json()["detail"] == (
        "This request has already been reviewed"
    )


def test_review_rejects_pending_as_review_status(client):
    requester_headers = create_user_and_login(client, "finance_officer")
    approval, _ = create_approval(client, requester_headers)
    reviewer_headers = create_user_and_login(client, "ngo_manager")

    response = client.patch(
        f"/approvals/{approval['id']}/review",
        json={"status": "pending"},
        headers=reviewer_headers,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Review status must be approved or rejected"
    )


def test_review_rejects_invalid_status(client):
    requester_headers = create_user_and_login(client, "finance_officer")
    approval, _ = create_approval(client, requester_headers)
    reviewer_headers = create_user_and_login(client, "ngo_manager")

    response = client.patch(
        f"/approvals/{approval['id']}/review",
        json={"status": "invalid"},
        headers=reviewer_headers,
    )

    assert response.status_code == 422


@pytest.mark.parametrize("role", ["finance_officer", "volunteer_coordinator", "donor"])
def test_unauthorized_roles_cannot_review_approval(client, role):
    requester_headers = create_user_and_login(client, "ngo_manager")
    approval, _ = create_approval(client, requester_headers)
    reviewer_headers = create_user_and_login(client, role)

    response = client.patch(
        f"/approvals/{approval['id']}/review",
        json={"status": "approved"},
        headers=reviewer_headers,
    )

    assert response.status_code == 403
