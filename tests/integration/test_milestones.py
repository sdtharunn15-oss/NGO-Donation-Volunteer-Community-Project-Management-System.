
from datetime import date, timedelta
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

    return {
        "Authorization": f"Bearer {response.json()['access_token']}"
    }


def create_project(client, headers):
    payload = {
        "title": f"Milestone Project {uuid4().hex[:8]}",
        "budget": "10000.00",
    }

    response = client.post(
        "/projects/",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201, response.text

    return response.json()


def create_milestone(client, headers=None, **overrides):
    if headers is None:
        headers = create_user_and_login(client, "ngo_manager")

    project_headers = headers

    # Volunteers coordinators can create milestones but cannot
    # necessarily create projects, so use a manager for that setup.
    if getattr(headers, "_role", None) == "volunteer_coordinator":
        project_headers = create_user_and_login(client, "ngo_manager")

    project = create_project(client, project_headers)

    payload = {
        "project_id": project["id"],
        "title": f"Milestone {uuid4().hex[:8]}",
        "description": "Milestone integration test",
        "due_date": str(date.today() + timedelta(days=14)),
    }
    payload.update(overrides)

    response = client.post(
        "/milestones/",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201, response.text

    return response.json(), headers, project


def test_create_milestone_requires_authentication(client):
    response = client.post(
        "/milestones/",
        json={
            "project_id": 1,
            "title": "First Milestone",
        },
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [
        "ngo_manager",
        "super_admin",
        "volunteer_coordinator",
    ],
)
def test_authorized_roles_can_create_milestone(client, role):
    headers = create_user_and_login(client, role)

    # Project creation is restricted to project-authorized roles.
    project_headers = (
        headers
        if role in ("ngo_manager", "super_admin")
        else create_user_and_login(client, "ngo_manager")
    )
    project = create_project(client, project_headers)

    response = client.post(
        "/milestones/",
        json={
            "project_id": project["id"],
            "title": "Community Planning",
            "description": "Complete initial planning",
            "due_date": str(date.today() + timedelta(days=10)),
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()
    assert data["project_id"] == project["id"]
    assert data["title"] == "Community Planning"
    assert data["status"] == "pending"
    assert data["created_by"] > 0


def test_donor_cannot_create_milestone(client):
    donor_headers = create_user_and_login(client, "donor")
    manager_headers = create_user_and_login(client, "ngo_manager")
    project = create_project(client, manager_headers)

    response = client.post(
        "/milestones/",
        json={
            "project_id": project["id"],
            "title": "Donor Milestone",
        },
        headers=donor_headers,
    )

    assert response.status_code == 403


def test_create_milestone_for_missing_project_returns_404(client):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.post(
        "/milestones/",
        json={
            "project_id": 999999999,
            "title": "Missing Project Milestone",
        },
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


@pytest.mark.parametrize(
    "payload",
    [
        {"project_id": 1, "title": "AB"},
        {"project_id": 0, "title": "Invalid Project ID"},
        {"project_id": -1, "title": "Invalid Project ID"},
        {"title": "Missing Project ID"},
    ],
)
def test_create_milestone_rejects_invalid_payload(client, payload):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.post(
        "/milestones/",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 422, response.text


def test_list_milestones_requires_authentication(client):
    response = client.get("/milestones/")

    assert response.status_code == 401


def test_authorized_user_can_list_milestones(client):
    milestone, headers, _ = create_milestone(client)

    response = client.get(
        "/milestones/",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert any(
        item["id"] == milestone["id"]
        for item in response.json()
    )


def test_list_milestones_filters_by_project(client):
    milestone, headers, project = create_milestone(client)

    other_project = create_project(client, headers)

    other_milestone, _, _ = create_milestone(
        client,
        headers,
        project_id=other_project["id"],
    )

    response = client.get(
        f"/milestones/?project_id={project['id']}",
        headers=headers,
    )

    assert response.status_code == 200, response.text

    ids = [item["id"] for item in response.json()]
    assert milestone["id"] in ids
    assert other_milestone["id"] not in ids


def test_list_milestones_with_nonexistent_project_returns_empty_list(client):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.get(
        "/milestones/?project_id=999999999",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_update_milestone_title_and_status(client):
    milestone, headers, _ = create_milestone(client)

    response = client.patch(
        f"/milestones/{milestone['id']}",
        json={
            "title": "Updated Milestone",
            "status": "in_progress",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated Milestone"
    assert response.json()["status"] == "in_progress"


def test_update_milestone_due_date(client):
    milestone, headers, _ = create_milestone(client)
    new_due_date = date.today() + timedelta(days=30)

    response = client.patch(
        f"/milestones/{milestone['id']}",
        json={"due_date": str(new_due_date)},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["due_date"] == str(new_due_date)


def test_update_milestone_rejects_short_title(client):
    milestone, headers, _ = create_milestone(client)

    response = client.patch(
        f"/milestones/{milestone['id']}",
        json={"title": "AB"},
        headers=headers,
    )

    assert response.status_code == 422


def test_update_missing_milestone_returns_404(client):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.patch(
        "/milestones/999999999",
        json={"title": "Updated Milestone"},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Milestone not found"


def test_donor_cannot_update_milestone(client):
    milestone, _, _ = create_milestone(client)
    donor_headers = create_user_and_login(client, "donor")

    response = client.patch(
        f"/milestones/{milestone['id']}",
        json={"title": "Unauthorized Update"},
        headers=donor_headers,
    )

    assert response.status_code == 403
