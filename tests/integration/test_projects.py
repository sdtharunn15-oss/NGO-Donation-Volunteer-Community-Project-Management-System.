from datetime import date, timedelta
from decimal import Decimal
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
    token = response.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


def create_project(client, headers=None, **overrides):
    if headers is None:
        headers = create_user_and_login(client, "ngo_manager")

    payload = {
        "title": f"Community Project {uuid4().hex[:8]}",
        "description": "Integration test project",
        "location": "Chennai",
        "budget": "25000.00",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=30)),
    }
    payload.update(overrides)

    requested_status = payload.pop("status", None)

    response = client.post("/projects/", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    project = response.json()

    if requested_status and requested_status != "draft":
        update_response = client.patch(
            f"/projects/{project['id']}",
            json={"status": requested_status},
            headers=headers,
        )
        assert update_response.status_code == 200, update_response.text
        project = update_response.json()

    return project, headers


def test_create_project_requires_authentication(client):
    response = client.post(
        "/projects/",
        json={"title": "Community Project"},
    )
    assert response.status_code == 401


def test_donor_cannot_create_project(client):
    headers = create_user_and_login(client, "donor")
    response = client.post(
        "/projects/",
        json={"title": "Community Project"},
        headers=headers,
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["ngo_manager", "super_admin"])
def test_authorized_user_can_create_project(client, role):
    headers = create_user_and_login(client, role)
    payload = {
        "title": "Community Development",
        "description": "Improve local facilities",
        "location": "Chennai",
        "budget": "50000.00",
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=60)),
    }

    response = client.post("/projects/", json=payload, headers=headers)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["location"] == payload["location"]
    assert Decimal(data["budget"]) == Decimal("50000.00")
    assert data["status"] == "draft"
    assert data["created_by"] > 0


def test_create_project_uses_default_budget(client):
    headers = create_user_and_login(client, "ngo_manager")
    response = client.post(
        "/projects/",
        json={"title": "Default Budget Project"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert Decimal(response.json()["budget"]) == Decimal("0.00")


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "AB"},
        {"title": ""},
        {"title": "Valid Project", "budget": "-1"},
        {
            "title": "Invalid Dates Project",
            "start_date": "2026-12-20",
            "end_date": "2026-12-01",
        },
    ],
)
def test_create_project_rejects_invalid_payload(client, payload):
    headers = create_user_and_login(client, "ngo_manager")
    response = client.post("/projects/", json=payload, headers=headers)
    assert response.status_code == 422


def test_list_projects_requires_authentication(client):
    response = client.get("/projects/")
    assert response.status_code == 401


def test_authorized_user_can_list_projects(client):
    headers = create_user_and_login(client, "volunteer")
    created, manager_headers = create_project(client)

    response = client.get("/projects/", headers=headers)

    assert response.status_code == 200, response.text
    assert any(item["id"] == created["id"] for item in response.json())


def test_list_projects_filters_by_status(client):
    headers = create_user_and_login(client, "ngo_manager")
    draft, _ = create_project(client, headers=headers)
    planned, _ = create_project(
        client, headers=headers, title="Planned Community Project", status="planned"
    )

    response = client.get("/projects/?status=planned", headers=headers)

    assert response.status_code == 200, response.text
    projects = response.json()
    ids = [item["id"] for item in projects]

    assert planned["id"] in ids
    assert draft["id"] not in ids
    assert all(item["status"] == "planned" for item in projects)


def test_list_projects_rejects_invalid_status(client):
    headers = create_user_and_login(client, "ngo_manager")
    response = client.get("/projects/?status=unknown", headers=headers)
    assert response.status_code == 422


def test_get_project_by_id(client):
    created, headers = create_project(client)

    response = client.get(f"/projects/{created['id']}", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["id"] == created["id"]
    assert response.json()["title"] == created["title"]


def test_get_missing_project_returns_404(client):
    headers = create_user_and_login(client, "ngo_manager")
    response = client.get("/projects/999999999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_update_project_title_and_budget(client):
    created, headers = create_project(client)

    response = client.patch(
        f"/projects/{created['id']}",
        json={"title": "Updated Community Project", "budget": "75000.00"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated Community Project"
    assert Decimal(response.json()["budget"]) == Decimal("75000.00")


def test_update_project_status(client):
    created, headers = create_project(client)

    response = client.patch(
        f"/projects/{created['id']}",
        json={"status": "planned"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "planned"


def test_update_project_rejects_invalid_dates(client):
    created, headers = create_project(client)

    response = client.patch(
        f"/projects/{created['id']}",
        json={
            "start_date": "2026-12-20",
            "end_date": "2026-12-01",
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_update_missing_project_returns_404(client):
    headers = create_user_and_login(client, "ngo_manager")
    response = client.patch(
        "/projects/999999999",
        json={"title": "Updated Project"},
        headers=headers,
    )

    assert response.status_code == 404


def test_donor_cannot_update_project(client):
    created, _ = create_project(client)
    donor_headers = create_user_and_login(client, "donor")

    response = client.patch(
        f"/projects/{created['id']}",
        json={"title": "Unauthorized Update"},
        headers=donor_headers,
    )

    assert response.status_code == 403
