
from uuid import uuid4

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def create_user_and_login(client, role="volunteer"):
    email = f"{role}_{uuid4().hex[:10]}@example.com"
    password = "StrongPass123!"

    db = SessionLocal()
    try:
        user = User(
            full_name="Assignment Test User",
            email=email,
            hashed_password=hash_password(password),
            role=UserRole(role),
            is_active=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_volunteer(client):
    headers = create_user_and_login(client, "volunteer")
    response = client.post(
        "/volunteers/me",
        headers=headers,
        json={
            "phone": "9876543210",
            "skills": "Teaching and community service",
            "availability": "Weekends",
            "city": "Chennai",
        },
    )
    assert response.status_code == 201
    return headers, response.json()["id"]


def create_project(client, status="planned"):
    manager_headers = create_user_and_login(client, "ngo_manager")

    response = client.post(
        "/projects/",
        headers=manager_headers,
        json={
            "title": f"Assignment Project {uuid4().hex[:6]}",
            "description": "Project created for assignment tests",
            "location": "Chennai",
            "budget": 10000,
        },
    )
    assert response.status_code == 201
    project_id = response.json()["id"]

    update = client.patch(
        f"/projects/{project_id}",
        headers=manager_headers,
        json={"status": status},
    )
    assert update.status_code == 200

    return manager_headers, project_id


def create_assignment(client):
    volunteer_headers, volunteer_id = create_volunteer(client)
    manager_headers, project_id = create_project(client)

    response = client.post(
        "/assignments/",
        headers=manager_headers,
        json={
            "volunteer_id": volunteer_id,
            "project_id": project_id,
            "notes": "Weekend volunteering",
        },
    )
    assert response.status_code == 201

    return (
        volunteer_headers,
        manager_headers,
        volunteer_id,
        project_id,
        response.json()["id"],
    )


def test_assignment_creation_requires_authentication(client):
    response = client.post(
        "/assignments/",
        json={"volunteer_id": 1, "project_id": 1},
    )
    assert response.status_code == 401


def test_donor_cannot_create_assignment(client):
    donor_headers = create_user_and_login(client, "donor")

    response = client.post(
        "/assignments/",
        headers=donor_headers,
        json={"volunteer_id": 1, "project_id": 1},
    )

    assert response.status_code == 403


def test_create_assignment_successfully(client):
    _, manager_headers, volunteer_id, project_id, assignment_id = (
        create_assignment(client)
    )

    response = client.get(
        "/assignments/",
        headers=manager_headers,
    )

    assert response.status_code == 200
    assignment = next(
        item for item in response.json()
        if item["id"] == assignment_id
    )
    assert assignment["volunteer_id"] == volunteer_id
    assert assignment["project_id"] == project_id
    assert assignment["status"] == "pending"
    assert assignment["notes"] == "Weekend volunteering"


def test_assignment_rejects_missing_volunteer(client):
    manager_headers, project_id = create_project(client)

    response = client.post(
        "/assignments/",
        headers=manager_headers,
        json={
            "volunteer_id": 999999999,
            "project_id": project_id,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Volunteer profile not found"


def test_assignment_rejects_missing_project(client):
    manager_headers, volunteer_id = None, None
    _, volunteer_id = create_volunteer(client)
    manager_headers = create_user_and_login(client, "ngo_manager")

    response = client.post(
        "/assignments/",
        headers=manager_headers,
        json={
            "volunteer_id": volunteer_id,
            "project_id": 999999999,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_assignment_rejects_draft_project(client):
    _, volunteer_id = create_volunteer(client)
    manager_headers, project_id = create_project(client, "draft")

    response = client.post(
        "/assignments/",
        headers=manager_headers,
        json={
            "volunteer_id": volunteer_id,
            "project_id": project_id,
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Volunteer can only be assigned to planned or active projects"
    )


def test_duplicate_assignment_is_rejected(client):
    _, manager_headers, volunteer_id, project_id, _ = create_assignment(client)

    response = client.post(
        "/assignments/",
        headers=manager_headers,
        json={
            "volunteer_id": volunteer_id,
            "project_id": project_id,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Volunteer is already assigned to this project"
    )


def test_volunteer_can_view_own_assignments(client):
    volunteer_headers, _, _, _, assignment_id = create_assignment(client)

    response = client.get(
        "/assignments/me",
        headers=volunteer_headers,
    )

    assert response.status_code == 200
    assert any(item["id"] == assignment_id for item in response.json())


def test_volunteer_can_accept_own_assignment(client):
    volunteer_headers, _, _, _, assignment_id = create_assignment(client)

    response = client.patch(
        f"/assignments/{assignment_id}/status",
        headers=volunteer_headers,
        json={"status": "accepted"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_volunteer_cannot_skip_assignment_status(client):
    volunteer_headers, _, _, _, assignment_id = create_assignment(client)

    response = client.patch(
        f"/assignments/{assignment_id}/status",
        headers=volunteer_headers,
        json={"status": "completed"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid assignment status transition"


def test_volunteer_cannot_update_another_volunteers_assignment(client):
    _, manager_headers, _, _, assignment_id = create_assignment(client)
    another_volunteer_headers, _ = create_volunteer(client)

    response = client.patch(
        f"/assignments/{assignment_id}/status",
        headers=another_volunteer_headers,
        json={"status": "accepted"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "You can only update your own assignments"
    )


def test_manager_cannot_reset_assignment_to_pending(client):
    _, manager_headers, _, _, assignment_id = create_assignment(client)

    response = client.patch(
        f"/assignments/{assignment_id}/status",
        headers=manager_headers,
        json={"status": "pending"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Cannot manually reset an assignment to pending"
    )


def test_missing_assignment_returns_404(client):
    manager_headers = create_user_and_login(client, "ngo_manager")

    response = client.patch(
        "/assignments/999999999/status",
        headers=manager_headers,
        json={"status": "accepted"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Assignment not found"
