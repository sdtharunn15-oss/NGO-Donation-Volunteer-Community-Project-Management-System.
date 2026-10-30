
from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole
from app.models.volunteer import Volunteer


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


def create_project(client, headers):
    response = client.post(
        "/projects/",
        json={
            "title": f"Task Project {uuid4().hex[:8]}",
            "budget": "10000.00",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_milestone(client, headers):
    project = create_project(client, headers)

    response = client.post(
        "/milestones/",
        json={
            "project_id": project["id"],
            "title": f"Milestone {uuid4().hex[:8]}",
            "description": "Task test milestone",
            "due_date": str(date.today() + timedelta(days=14)),
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_task(client, headers=None, **overrides):
    if headers is None:
        headers = create_user_and_login(client, "ngo_manager")

    milestone = create_milestone(client, headers)

    payload = {
        "milestone_id": milestone["id"],
        "title": f"Task {uuid4().hex[:8]}",
        "description": "Task integration test",
        "due_date": str(date.today() + timedelta(days=7)),
    }
    payload.update(overrides)

    response = client.post(
        "/tasks/",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201, response.text

    return response.json(), headers, milestone


def test_create_task_requires_authentication(client):
    response = client.post(
        "/tasks/",
        json={"milestone_id": 1, "title": "First Task"},
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    ["ngo_manager", "super_admin", "volunteer_coordinator"],
)
def test_authorized_roles_can_create_task(client, role):
    headers = create_user_and_login(client, role)

    project_headers = (
        headers
        if role in ("ngo_manager", "super_admin")
        else create_user_and_login(client, "ngo_manager")
    )

    milestone = create_milestone(client, project_headers)

    response = client.post(
        "/tasks/",
        json={
            "milestone_id": milestone["id"],
            "title": "Community Outreach",
            "description": "Prepare outreach activities",
        },
        headers=headers,
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["milestone_id"] == milestone["id"]
    assert data["title"] == "Community Outreach"
    assert data["status"] == "todo"
    assert data["created_by"] > 0


def test_donor_cannot_create_task(client):
    donor_headers = create_user_and_login(client, "donor")
    manager_headers = create_user_and_login(client, "ngo_manager")
    milestone = create_milestone(client, manager_headers)

    response = client.post(
        "/tasks/",
        json={
            "milestone_id": milestone["id"],
            "title": "Unauthorized Task",
        },
        headers=donor_headers,
    )

    assert response.status_code == 403


def test_create_task_for_missing_milestone_returns_404(client):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.post(
        "/tasks/",
        json={
            "milestone_id": 999999999,
            "title": "Missing Milestone Task",
        },
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Milestone not found"


@pytest.mark.parametrize(
    "payload",
    [
        {"milestone_id": 1, "title": "AB"},
        {"milestone_id": 0, "title": "Invalid Milestone"},
        {"milestone_id": -1, "title": "Invalid Milestone"},
        {"title": "Missing Milestone ID"},
    ],
)
def test_create_task_rejects_invalid_payload(client, payload):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.post(
        "/tasks/",
        json=payload,
        headers=headers,
    )

    assert response.status_code == 422, response.text


def test_create_task_with_invalid_volunteer_returns_404(client):
    headers = create_user_and_login(client, "ngo_manager")
    milestone = create_milestone(client, headers)

    response = client.post(
        "/tasks/",
        json={
            "milestone_id": milestone["id"],
            "title": "Assign Task",
            "assigned_to": 999999999,
        },
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Volunteer profile not found"


def test_list_tasks_requires_authentication(client):
    response = client.get("/tasks/")
    assert response.status_code == 401


def test_authorized_user_can_list_tasks(client):
    task, headers, _ = create_task(client)

    response = client.get("/tasks/", headers=headers)

    assert response.status_code == 200, response.text
    assert any(item["id"] == task["id"] for item in response.json())


def test_list_tasks_filters_by_milestone(client):
    task, headers, milestone = create_task(client)

    other_milestone = create_milestone(client, headers)
    other_task, _, _ = create_task(
        client,
        headers,
        milestone_id=other_milestone["id"],
    )

    response = client.get(
        f"/tasks/?milestone_id={milestone['id']}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()]
    assert task["id"] in ids
    assert other_task["id"] not in ids


def test_list_tasks_with_nonexistent_milestone_returns_empty_list(client):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.get(
        "/tasks/?milestone_id=999999999",
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == []


def test_update_task_title_and_description(client):
    task, headers, _ = create_task(client)

    response = client.patch(
        f"/tasks/{task['id']}",
        json={
            "title": "Updated Task",
            "description": "Updated task description",
        },
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "Updated Task"
    assert response.json()["description"] == "Updated task description"


def test_update_task_status_through_general_update_endpoint(client):
    task, headers, _ = create_task(client)

    response = client.patch(
        f"/tasks/{task['id']}",
        json={"status": "in_progress"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "in_progress"


def test_update_task_rejects_short_title(client):
    task, headers, _ = create_task(client)

    response = client.patch(
        f"/tasks/{task['id']}",
        json={"title": "AB"},
        headers=headers,
    )

    assert response.status_code == 422


def test_update_task_with_invalid_volunteer_returns_404(client):
    task, headers, _ = create_task(client)

    response = client.patch(
        f"/tasks/{task['id']}",
        json={"assigned_to": 999999999},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Volunteer profile not found"


def test_update_missing_task_returns_404(client):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.patch(
        "/tasks/999999999",
        json={"title": "Updated Task"},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_donor_cannot_update_task(client):
    task, _, _ = create_task(client)
    donor_headers = create_user_and_login(client, "donor")

    response = client.patch(
        f"/tasks/{task['id']}",
        json={"title": "Unauthorized Update"},
        headers=donor_headers,
    )

    assert response.status_code == 403


def test_update_task_status(client):
    task, headers, _ = create_task(client)

    response = client.patch(
        f"/tasks/{task['id']}/status",
        params={"new_status": "completed"},
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "completed"


def test_update_missing_task_status_returns_404(client):
    headers = create_user_and_login(client, "ngo_manager")

    response = client.patch(
        "/tasks/999999999/status",
        params={"new_status": "completed"},
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


def test_donor_cannot_update_task_status(client):
    task, _, _ = create_task(client)
    donor_headers = create_user_and_login(client, "donor")

    response = client.patch(
        f"/tasks/{task['id']}/status",
        params={"new_status": "completed"},
        headers=donor_headers,
    )

    assert response.status_code == 403


def test_invalid_task_status_returns_422(client):
    task, headers, _ = create_task(client)

    response = client.patch(
        f"/tasks/{task['id']}/status",
        params={"new_status": "invalid_status"},
        headers=headers,
    )

    assert response.status_code == 422
